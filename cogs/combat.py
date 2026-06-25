import asyncio
import random
import math
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildConfig, SpawnedBoss, BossTemplate, AIConfig
from services.combat_engine import (
    Combatant, player_attack, player_defend, roll_initiative,
    roll, modifier, resolve_named_attack, detect_attack_name,
    tick_conditions, has_condition, apply_condition, effective_ac, CONDITIONS,
    resolve_grapple, resolve_shove, resolve_hide, resolve_taunt,
)
from services.ai_service import classify_combat_action
from services.leveling import pvp_xp_reward, check_level_up, hp_gain_on_level, feature_at_level, xp_bar, ASI_LEVELS
from cogs.character import resolve_character, CharacterPickView, pick_embed, _offer_attack_unlock
from services.title_service import get_active_title
from services.utils import is_gm
from discord.ext import commands

# Module-level bot reference — set when cog loads
_bot_instance: commands.Bot | None = None

# ── Active sessions: channel_id → CombatSession (infinite per guild) ─────────
_sessions: dict[int, "CombatSession"] = {}


async def _set_combat_active(guild_id: int, channel_id: int | None):
    async with get_db() as db:
        result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == guild_id))
        config = result.scalar_one_or_none()
        if config:
            config.combat_active = channel_id is not None
            config.combat_channel_id = channel_id
        else:
            if channel_id is not None:
                db.add(GuildConfig(
                    guild_id=guild_id,
                    combat_active=True,
                    combat_channel_id=channel_id,
                ))


async def _build_combatant(char: Character, user_id: int) -> Combatant:
    inventory = char.inventory or []
    equipped_weapon = next(
        (it["key"] for it in inventory if it.get("type") == "weapon" and it.get("equipped")),
        "unarmed",
    )
    combatant = Combatant(
        id=str(user_id),
        name=char.name,
        is_player=True,
        level=char.level,
        char_class=char.char_class,
        hp_max=char.hp_max,
        hp_current=char.hp_current,
        hp_temp=char.hp_temp,
        strength=char.strength,
        dexterity=char.dexterity,
        constitution=char.constitution,
        intelligence=char.intelligence,
        wisdom=char.wisdom,
        charisma=char.charisma,
        armor_class=char.armor_class,
        is_dead=char.is_dead,
        is_unconscious=char.is_unconscious,
        death_saves_success=char.death_saves_success,
        death_saves_failure=char.death_saves_failure,
        conditions=list(char.conditions or []),
        class_resources=dict(char.class_resources or {}),
        weapon=equipped_weapon,
    )
    # Load active title
    try:
        async with get_db() as db:
            active = await get_active_title(db, char.id)
        if active:
            combatant.title_display = active[0]
    except Exception:
        pass
    return combatant


# ── Session ───────────────────────────────────────────────────────────────────

class CombatSession:
    def __init__(self, title: str, fight_type: str, channel_id: int, guild_id: int, initiator_id: int):
        self.title = title
        self.fight_type = fight_type  # "dnd" or "manual"
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id

        self.players: list[Combatant] = []
        self.player_user_ids: list[int] = []
        self.turn_order: list[Combatant] = []
        self.current_idx: int = 0
        self.round: int = 1
        self.state: str = "lobby"
        self.log: list[str] = []

        self.status_message: discord.Message | None = None
        self.confirm_message: discord.Message | None = None
        self.pending_action: dict | None = None
        self.pending_target: Combatant | None = None
        self.lobby_message: discord.Message | None = None

    @property
    def current_combatant(self) -> Combatant:
        return self.turn_order[self.current_idx]

    @property
    def living_players(self) -> list[Combatant]:
        return [p for p in self.players if p.is_alive]

    def add_log(self, line: str):
        self.log.append(line)
        if len(self.log) > 15:
            self.log.pop(0)

    def advance_turn(self):
        while True:
            self.current_idx = (self.current_idx + 1) % len(self.turn_order)
            if self.current_idx == 0:
                self.round += 1
                self._new_round = True  # flag for boss lair action check
            else:
                self._new_round = False
            c = self.turn_order[self.current_idx]
            if c.is_dead:
                continue
            break

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._new_round = False

    def user_id_for(self, combatant: Combatant) -> int | None:
        try:
            idx = self.players.index(combatant)
            return self.player_user_ids[idx]
        except ValueError:
            return None

    # ── Embeds ────────────────────────────────────────────────────────────────

    def lobby_embed(self) -> discord.Embed:
        fight_label = "⚔️ DnD (AI)" if self.fight_type == "dnd" else "📜 Manual (GM-run)"
        embed = discord.Embed(
            title=f"⚔️ {self.title}",
            description=f"**Fight Type:** {fight_label}\n\nWaiting for fighters to join...",
            color=0xF59E0B,
        )
        if self.players:
            lines = [f"• **{p.name}** (Lv{p.level} {p.char_class})" for p in self.players]
            embed.add_field(name=f"Fighters ({len(self.players)})", value="\n".join(lines), inline=False)
        embed.set_footer(text="Click Join Fight to enter • Host clicks Start Battle when ready (min 2 fighters) • Lobby closes in 10 minutes")
        return embed

    def status_embed(self) -> discord.Embed:
        current = self.current_combatant
        pct = current.hp_current / current.hp_max if current.hp_max > 0 else 0
        color = 0x22C55E if pct > 0.5 else (0xF97316 if pct > 0.25 else 0xEF4444)
        current_label = f"{current.title_display} | {current.name}" if current.title_display else current.name

        embed = discord.Embed(
            title=f"⚔️ {self.title}  —  Round {self.round}  —  **{current_label}'s turn**",
            color=color,
        )
        for p in self.players:
            p_pct = max(0, p.hp_current / p.hp_max) if p.hp_max > 0 else 0
            p_bar = "█" * round(p_pct * 10) + "░" * (10 - round(p_pct * 10))
            if p.is_dead:
                status = "💀"
            elif p.is_unconscious:
                status = f"😵 ✅{p.death_saves_success}/3 ❌{p.death_saves_failure}/3"
            else:
                status = "✅"
            arrow = " ◄" if current == p else ""
            p_cond = " ".join(CONDITIONS.get(c["name"], {}).get("icon", "") for c in (p.conditions or []))
            embed.add_field(
                name=f"{status} {p.name} (Lv{p.level} {p.char_class}){arrow} {p_cond}".strip(),
                value=f"❤️ `{p.hp_current}/{p.hp_max}` {p_bar}  🛡️ AC `{effective_ac(p)}`",
                inline=True,
            )
        if self.log:
            embed.add_field(name="📜 Log", value="\n".join(self.log), inline=False)
        return embed

    def winner_embed(self, winner: Combatant | None) -> discord.Embed:
        if winner:
            embed = discord.Embed(
                title=f"🏆 {winner.name} wins!",
                description=f"**{self.title}** is over.",
                color=0x22C55E,
            )
        else:
            embed = discord.Embed(
                title="🤝 Draw — all fighters are down.",
                description=f"**{self.title}** is over.",
                color=0xF59E0B,
            )
        for p in self.players:
            icon = "💀" if p.is_dead else ("😵" if p.is_unconscious else "✅")
            embed.add_field(name=f"{icon} {p.name}", value=f"❤️ `{p.hp_current}/{p.hp_max}`", inline=True)
        embed.set_footer(text="LoreForge")
        return embed


# ── Join char picker (for multi-char users) ───────────────────────────────────

class CombatJoinCharSelect(discord.ui.Select):
    def __init__(self, chars: list, session: "CombatSession", lobby_view: "LobbyView"):
        self._chars = chars
        self._session = session
        self._lobby_view = lobby_view
        options = [
            discord.SelectOption(label=c.name, value=str(c.id), description=f"Lv{c.level} {c.race} {c.char_class}")
            for c in chars
        ]
        super().__init__(placeholder="Choose your fighter...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char = next((c for c in self._chars if c.id == int(self.values[0])), None)
        session = self._session
        if not char:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return
        if char.is_unconscious:
            await interaction.response.edit_message(content="That character is unconscious.", embed=None, view=None)
            return
        if interaction.user.id in session.player_user_ids:
            await interaction.response.edit_message(content="You're already in this fight.", embed=None, view=None)
            return
        combatant = await _build_combatant(char, interaction.user.id)
        session.players.append(combatant)
        session.player_user_ids.append(interaction.user.id)
        await interaction.response.edit_message(content=f"✅ **{char.name}** joined the fight!", embed=None, view=None)
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=self._lobby_view)


class CombatJoinCharView(discord.ui.View):
    def __init__(self, chars: list, session: "CombatSession", lobby_view: "LobbyView"):
        super().__init__(timeout=None)
        self.add_item(CombatJoinCharSelect(chars, session, lobby_view))


# ── Lobby View ────────────────────────────────────────────────────────────────

class LobbyView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=600)
        self.session = session

    @discord.ui.button(label="Join Fight", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if interaction.user.id in session.player_user_ids:
            await interaction.response.send_message("You're already in this fight.", ephemeral=True)
            return
        char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
        if not chars:
            await interaction.response.send_message(
                "You don't have a living character. Use `/character create` first.", ephemeral=True
            )
            return
        if not char:
            await interaction.response.send_message(
                embed=pick_embed("fight as"), view=CombatJoinCharView(chars, session, self), ephemeral=True
            )
            return
        if char.is_unconscious:
            await interaction.response.send_message("Your character is unconscious.", ephemeral=True)
            return
        combatant = await _build_combatant(char, interaction.user.id)
        session.players.append(combatant)
        session.player_user_ids.append(interaction.user.id)
        await interaction.response.defer()
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=self)

    @discord.ui.button(label="Start Battle", style=discord.ButtonStyle.danger, emoji="🗡️")
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if interaction.user.id != session.initiator_id:
            await interaction.response.send_message("Only the host can start the battle.", ephemeral=True)
            return
        if len(session.players) < 2:
            await interaction.response.send_message("At least 2 fighters must join first.", ephemeral=True)
            return

        session.state = "active"
        session.turn_order = roll_initiative(session.players)
        first = session.turn_order[0]
        session.add_log(f"🎲 Initiative rolled! **{first.name}** goes first.")

        action_hint = "Type your action in RP." if session.fight_type == "dnd" else "Declare your action."
        session.status_message = interaction.message
        await interaction.response.edit_message(
            content=f"**{first.name}** — it's your turn. {action_hint}",
            embed=session.status_embed(),
            view=None,
        )

    async def on_timeout(self):
        session = self.session
        if session.state == "lobby":
            session.state = "over"
            _sessions.pop(session.channel_id, None)
            await _set_combat_active(session.guild_id, None)
            if session.lobby_message:
                try:
                    await session.lobby_message.edit(
                        content="⏱️ **Lobby expired** — no battle started within 10 minutes.",
                        embed=None,
                        view=None,
                    )
                except Exception:
                    pass


# ── Invite View — sent when host invites a specific user ─────────────────────

class InviteView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=600)
        self.session = session
        self._message: discord.Message | None = None

    @discord.ui.button(label="Join Fight", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if session.state != "lobby":
            await interaction.response.send_message("This lobby is no longer open.", ephemeral=True)
            return
        if interaction.user.id in session.player_user_ids:
            await interaction.response.send_message("You're already in this fight.", ephemeral=True)
            return
        char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
        if not chars:
            await interaction.response.send_message(
                "You don't have a living character. Use `/character create` first.", ephemeral=True
            )
            return
        if not char:
            await interaction.response.send_message(
                embed=pick_embed("fight as"),
                view=CombatJoinCharView(chars, session, LobbyView(session)),
                ephemeral=True,
            )
            return
        if char.is_unconscious:
            await interaction.response.send_message("Your character is unconscious.", ephemeral=True)
            return
        combatant = await _build_combatant(char, interaction.user.id)
        session.players.append(combatant)
        session.player_user_ids.append(interaction.user.id)
        await interaction.response.send_message(f"✅ **{char.name}** joined the fight!", ephemeral=True)
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=LobbyView(session))
        self.stop()

    async def on_timeout(self):
        self.stop()
        if self._message:
            try:
                await self._message.edit(
                    content="⏱️ **Invite expired** — this invitation is no longer valid.",
                    view=None,
                )
            except Exception:
                pass


# ── Fuzzy target matching ─────────────────────────────────────────────────────

def _fuzzy_find_target(name: str | None, candidates: list[Combatant]) -> Combatant | None:
    if not name:
        return None
    name_lower = name.lower()
    for c in candidates:
        if c.name.lower() == name_lower:
            return c
    for c in candidates:
        if name_lower in c.name.lower() or c.name.lower() in name_lower:
            return c
    return None


# ── Target Select — shown for ATTACK/SPELL before confirm ─────────────────────

class TargetSelect(discord.ui.Select):
    def __init__(self, session: "CombatSession", player_uid: int, action_data: dict, targets: list[Combatant]):
        self._session = session
        self._player_uid = player_uid
        self._action_data = action_data
        options = [
            discord.SelectOption(
                label=p.name,
                value=p.id,
                description=f"Lv{p.level} {p.char_class}  ❤️ {p.hp_current}/{p.hp_max}  🛡️ AC {effective_ac(p)}",
            )
            for p in targets
        ]
        super().__init__(placeholder="Choose your target...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self._player_uid:
            await interaction.response.send_message("This isn't your turn.", ephemeral=True)
            return
        session = self._session
        target = next((p for p in session.players if p.id == self.values[0]), None)
        if not target:
            await interaction.response.send_message("Target not found.", ephemeral=True)
            return
        session.pending_target = target
        attack_name = self._action_data.get("detected_attack")
        desc = f"⚔️ **{attack_name}** at **{target.name}**" if attack_name else f"⚔️ Attack **{target.name}**"
        try:
            await interaction.message.delete()
        except Exception:
            pass
        session.confirm_message = await interaction.channel.send(
            f"*{desc}* — is that right?",
            view=ConfirmView(session, self._player_uid),
        )
        await interaction.response.defer()


class TargetSelectView(discord.ui.View):
    def __init__(self, session: "CombatSession", player_uid: int, action_data: dict, targets: list[Combatant]):
        super().__init__(timeout=900)
        self.session = session
        self.add_item(TargetSelect(session, player_uid, action_data, targets))

    async def on_timeout(self):
        self.session.pending_action = None


# ── Confirm View ──────────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, session: "CombatSession", player_uid: int):
        super().__init__(timeout=900)
        self.session = session
        self.player_uid = player_uid

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_uid:
            await interaction.response.send_message("This isn't your turn.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        session = self.session
        action_data = session.pending_action
        session.pending_action = None
        try:
            await interaction.message.delete()
        except Exception:
            pass
        session.confirm_message = None
        await _resolve_player_action(session, action_data)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        session.pending_action = None
        session.pending_target = None
        try:
            await interaction.message.delete()
        except Exception:
            pass
        session.confirm_message = None
        await interaction.response.send_message("Action cancelled — type your next move.", ephemeral=True)

    async def on_timeout(self):
        self.session.pending_action = None
        self.session.pending_target = None
        self.session.confirm_message = None


# ── Death Save View ───────────────────────────────────────────────────────────

class DeathSaveView(discord.ui.View):
    def __init__(self, session: "CombatSession", player_uid: int):
        super().__init__(timeout=900)
        self.session = session
        self.player_uid = player_uid

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.player_uid:
            await interaction.response.send_message("This isn't your death save.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Roll Death Save", style=discord.ButtonStyle.danger, emoji="🎲")
    async def death_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        session = self.session
        player = session.current_combatant
        result = player.death_save()

        if result["outcome"] == "critical_success":
            session.add_log(f"🌟 {player.name} — natural 20! Back on 1 HP!")
        elif result["outcome"] == "stabilized":
            session.add_log(f"✅ {player.name} stabilizes (3 successes).")
        elif result["outcome"] == "dead":
            session.add_log(f"💀 {player.name} is dead (3 failures).")
        else:
            s = result.get("successes", 0)
            f = result.get("failures", 0)
            label = "✅" if result["outcome"] == "success" else "❌"
            session.add_log(f"🎲 {player.name} death save {label} (rolled {result['roll']})  ✅{s}/3 ❌{f}/3")

        self.stop()
        try:
            await interaction.message.delete()
        except Exception:
            pass

        living = session.living_players
        if len(living) <= 1:
            await _end_combat(session, living[0] if living else None)
            return

        session.advance_turn()
        next_c = session.current_combatant
        if session.status_message:
            session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        await _update_status_and_prompt(session, next_c)

    async def on_timeout(self):
        player = self.session.current_combatant
        if player.is_unconscious:
            player.death_saves_failure += 1
            self.session.add_log(f"⏱️ {player.name}'s death save timed out — failure!")
            if player.death_saves_failure >= 3:
                player.is_dead = True
                player.is_unconscious = False
                self.session.add_log(f"💀 {player.name} dies.")


# ── Kill or Spare View ────────────────────────────────────────────────────────

class KillOrSpareView(discord.ui.View):
    def __init__(self, session: "CombatSession", attacker_uid: int, target: "Combatant"):
        super().__init__(timeout=60)
        self.session = session
        self.attacker_uid = attacker_uid
        self.target = target
        self._resolved = False

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.attacker_uid:
            await interaction.response.send_message("This choice isn't yours to make.", ephemeral=True)
            return False
        return True

    async def _finish(self, interaction: discord.Interaction | None, kill: bool):
        if self._resolved:
            return
        self._resolved = True
        self.stop()
        session = self.session
        target = self.target

        if interaction:
            try:
                await interaction.message.delete()
            except Exception:
                pass
            await interaction.response.defer()

        if kill:
            target.is_dead = True
            target.is_unconscious = False
            session.add_log(f"☠️ **{target.name}** was finished off!")
        else:
            session.add_log(f"😴 **{target.name}** was spared — knocked out.")

        living = session.living_players
        if len(living) <= 1:
            await _end_combat(session, living[0] if living else None)
            return

        session.advance_turn()
        next_c = session.current_combatant
        if session.status_message:
            session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        await _update_status_and_prompt(session, next_c)

    @discord.ui.button(label="Finish", style=discord.ButtonStyle.danger, emoji="☠️")
    async def kill_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish(interaction, kill=True)

    @discord.ui.button(label="Spare", style=discord.ButtonStyle.secondary, emoji="😴")
    async def spare_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._finish(interaction, kill=False)

    async def on_timeout(self):
        if not self._resolved:
            self.session.add_log(f"😴 **{self.target.name}** was spared (no response — 60s timeout).")
            await self._finish(None, kill=False)


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _update_status_and_prompt(session: CombatSession, next_c: Combatant):
    if session.status_message is None:
        return

    dot_lines = tick_conditions(next_c)
    for line in dot_lines:
        await session.status_message.channel.send(line)

    # Perfect Tao Circulation — regen WIS mod Tao at start of each turn (level 10+)
    if next_c.char_class == "Heavenly Demon Heir" and next_c.level >= 10 and next_c.is_player:
        try:
            from sqlalchemy.orm.attributes import flag_modified
            async with get_db() as db:
                result = await db.execute(
                    select(Character).where(
                        Character.user_id == int(next_c.id),
                        Character.guild_id == session.guild_id,
                        Character.is_active == True,
                    )
                )
                char_row = result.scalar_one_or_none()
                if char_row:
                    res = char_row.class_resources or {}
                    wis_mod = max(0, (char_row.wisdom - 10) // 2)
                    regen = max(1, wis_mod)
                    tao_max = res.get("tao_max", 2)
                    cur = res.get("tao_current", 0)
                    if cur < tao_max:
                        new_tao = min(tao_max, cur + regen)
                        res["tao_current"] = new_tao
                        res["tao_exhausted"] = False
                        char_row.class_resources = res
                        flag_modified(char_row, "class_resources")
                        await db.commit()
                        await session.status_message.channel.send(
                            f"🌀 **Perfect Tao Circulation** — {next_c.name} regains {regen} Tao ({new_tao}/{tao_max})"
                        )
        except Exception:
            pass

    if next_c.is_dead:
        session.add_log(f"💀 {next_c.name} dies from their wounds!")
        living = session.living_players
        if len(living) <= 1:
            await _end_combat(session, living[0] if living else None)
            return
    elif next_c.is_unconscious:
        session.add_log(f"😵 {next_c.name} falls unconscious!")

    if has_condition(next_c, "stunned"):
        session.add_log(f"⚡ **{next_c.name}** is stunned and loses their turn!")
        session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        session.advance_turn()
        await _update_status_and_prompt(session, session.current_combatant)
        return

    if next_c.is_unconscious:
        uid = session.user_id_for(next_c)
        session.status_message = await session.status_message.channel.send(
            content=f"😵 **{next_c.name}** is unconscious.", embed=session.status_embed()
        )
        await session.status_message.channel.send(
            f"😵 **{next_c.name}** — roll your death saving throw!",
            view=DeathSaveView(session, uid),
        )
    else:
        action_hint = "Type your action in RP." if session.fight_type == "dnd" else "Declare your action."
        session.status_message = await session.status_message.channel.send(
            content=f"**{next_c.name}** — it's your turn. {action_hint}",
            embed=session.status_embed(),
        )


# ── Boss state helpers ─────────────────────────────────────────────────────────

async def _check_boss_state(session: CombatSession) -> list[str]:
    """Check active SpawnedBoss in this channel for phase changes, and return log lines."""
    lines = []
    channel = session.status_message.channel if session.status_message else None
    if not channel:
        return lines

    async with get_db() as db:
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == session.guild_id,
                SpawnedBoss.channel_id == session.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            return lines

        if not boss.phase_thresholds:
            return lines

        pct = (boss.hp_current / boss.hp_max) * 100 if boss.hp_max > 0 else 0
        for i, threshold in enumerate(boss.phase_thresholds):
            if pct <= threshold:
                new_phase = i + 2
                if new_phase > boss.current_phase and new_phase <= (boss.phase_count or 1):
                    boss.current_phase = new_phase
                    phase_descriptions = {
                        2: "The boss becomes more aggressive — new abilities unlock!",
                        3: "The boss is enraged! Powerful attacks are unleashed!",
                        4: "Desperate measures — the boss fights with everything it has!",
                    }
                    desc = phase_descriptions.get(new_phase, "The boss transforms!")
                    embed = discord.Embed(
                        title=f"⚡ Phase Change!",
                        description=f"**{boss.display_name}** shifts to **Phase {new_phase}**!\n\n*{desc}*",
                        color=0xEF4444,
                    )
                    await channel.send(embed=embed)
                    lines.append(f"[BOSS] {boss.display_name} enters Phase {new_phase}!")

    return lines


async def _check_lair_action(session: CombatSession) -> list[str]:
    """Check if a lair action should fire at initiative 20."""
    lines = []
    channel = session.status_message.channel if session.status_message else None
    if not channel:
        return lines

    async with get_db() as db:
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == session.guild_id,
                SpawnedBoss.channel_id == session.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss or not boss.is_lair_boss or not boss.lair_actions:
            return lines

        # Rotate through lair actions based on round
        idx = (session.round - 1) % len(boss.lair_actions)
        action = boss.lair_actions[idx]
        action_name = action.get("name", "Environment Effect")
        action_desc = action.get("description", "Something happens in the environment...") or "Something happens in the environment..."
        action_effect = action.get("effect", "")

        embed = discord.Embed(
            title=f"🏰 Lair Action — {action_name}",
            description=action_desc,
            color=0x6366F1,
        )
        if action_effect:
            embed.add_field(name="Effect", value=action_effect, inline=False)
        await channel.send(embed=embed)
        lines.append(f"[LAIR] {action_name}: {action_desc[:80]}")

    return lines


async def _check_boss_legendary(session: CombatSession) -> list[str]:
    """After a player's turn, auto-trigger a 1-cost legendary action if available."""
    lines = []
    channel = session.status_message.channel if session.status_message else None
    if not channel:
        return lines

    async with get_db() as db:
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == session.guild_id,
                SpawnedBoss.channel_id == session.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss or not boss.legendary_actions:
            return lines

        if boss.legendary_actions_remaining <= 0:
            return lines

        # Find the first 1-cost action
        one_cost = next((a for a in boss.legendary_actions if a.get("cost", 1) == 1), None)
        if not one_cost:
            return lines

        boss.legendary_actions_remaining -= 1
        action_name = one_cost.get("name", "Legendary Attack")
        action_desc = one_cost.get("description", f"{boss.display_name} uses legendary power!") or f"{boss.display_name} uses legendary power!"

        embed = discord.Embed(
            title=f"⚡ Legendary Action — {action_name}",
            description=action_desc,
            color=0xEF4444,
        )
        embed.set_footer(text=f"Legendary actions remaining: {boss.legendary_actions_remaining}/{boss.legendary_action_count}")
        await channel.send(embed=embed)
        lines.append(f"[LEGENDARY] {boss.display_name} uses {action_name}")

    return lines


async def _reset_boss_legendary(session: CombatSession):
    """Reset legendary actions at the start of the boss's turn."""
    async with get_db() as db:
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == session.guild_id,
                SpawnedBoss.channel_id == session.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if boss:
            boss.legendary_actions_remaining = boss.legendary_action_count


_BOSS_INITIATIVE = 15  # Boss acts on initiative 15


async def _resolve_player_action(session: CombatSession, action_data: dict):
    player = session.current_combatant
    target = session.pending_target
    session.pending_target = None
    action = action_data.get("action", "UNCLEAR")
    channel = session.status_message.channel if session.status_message else None

    if action in ("ATTACK", "SPELL", "SKILL") and target:
        attack_name = action_data.get("detected_attack")
        just_downed = False
        p_name_log = f"{player.title_display} | {player.name}" if player.title_display else player.name
        t_name_log = f"{target.title_display} | {target.name}" if target.title_display else target.name
        if attack_name:
            res = resolve_named_attack(player, attack_name, target)
            for line in res.get("log_lines", []):
                if channel:
                    await channel.send(line)
            if res["is_heal"]:
                player.heal(res["heal_amount"])
                session.add_log(f"💚 {p_name_log} heals **{res['heal_amount']} HP** from **{attack_name}**!")
            elif res["miss"]:
                session.add_log(f"🎲 {p_name_log} — natural 1 on **{attack_name}**!")
            elif res["hit"]:
                if res["damage"] > 0:
                    was_conscious = not target.is_unconscious and not target.is_dead
                    target.take_damage(res["damage"])
                    crit = " *(Crit!)*" if res["crit"] else ""
                    session.add_log(f"⚔️ **{attack_name}** — {p_name_log} hits {t_name_log} for **{res['damage']} dmg**{crit}")
                    if was_conscious and target.is_unconscious:
                        just_downed = True
                for cond in res.get("conditions_applied", []):
                    apply_condition(target, cond["name"], cond["duration"])
                    icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                    session.add_log(f"{icon} {t_name_log} is now {cond['name']}!")
            else:
                session.add_log(f"🛡️ **{attack_name}** misses {t_name_log} ({res.get('attack_roll', '?')} vs AC {effective_ac(target)})")
            for cond in res.get("self_conditions", []):
                apply_condition(player, cond["name"], cond["duration"])
                icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                session.add_log(f"{icon} {p_name_log} is now {cond['name']}!")
        else:
            result = player_attack(player, weapon=player.weapon)
            if channel:
                await channel.send(f"🎲 {p_name_log} rolls **{result['attack_roll']}** to hit {t_name_log}.")
            if result["is_miss"]:
                session.add_log(f"🎲 {p_name_log} — natural 1, missed!")
            elif result["attack_roll"] >= effective_ac(target):
                was_conscious = not target.is_unconscious and not target.is_dead
                target.take_damage(result["damage"])
                crit = " *(Crit!)*" if result["is_crit"] else ""
                sneak = f" +{result['sneak_dice']}d6 sneak" if result["sneak_dice"] else ""
                session.add_log(f"⚔️ {p_name_log} hits {t_name_log} for **{result['damage']} dmg**{crit}{sneak}")
                if was_conscious and target.is_unconscious:
                    just_downed = True
            else:
                session.add_log(f"🛡️ {p_name_log} misses {t_name_log} ({result['attack_roll']} vs AC {effective_ac(target)})")

        if just_downed:
            uid = session.user_id_for(player)
            if channel and uid:
                await channel.send(
                    f"<@{uid}> — **{target.name}** is down at your feet! What do you do?",
                    view=KillOrSpareView(session, uid, target),
                )
            return

        living = session.living_players
        if len(living) <= 1:
            await _end_combat(session, living[0] if living else None)
            return

    elif action == "DEFEND":
        result = player_defend(player)
        session.add_log(
            f"🛡️ {player.name} braces — +{result['temp_hp']} temp HP!" if result["success"]
            else f"🛡️ {player.name} braces but gains nothing."
        )

    elif action == "FLEE":
        player_roll = roll(20) + modifier(player.dexterity)
        if player_roll >= 12:
            idx = session.players.index(player)
            session.players.pop(idx)
            session.player_user_ids.pop(idx)
            session.turn_order = [c for c in session.turn_order if c is not player]
            session.current_idx = session.current_idx % max(len(session.turn_order), 1)
            session.add_log(f"💨 {player.name} escapes! (rolled {player_roll})")
            if not session.players:
                session.state = "over"
                _sessions.pop(session.channel_id, None)
                await _set_combat_active(session.guild_id, None)
                if session.status_message:
                    await session.status_message.channel.send(
                        embed=discord.Embed(title="💨 All fighters fled.", color=0xF59E0B)
                    )
                return
            next_c = session.turn_order[session.current_idx % len(session.turn_order)]
            if session.status_message:
                session.status_message = await session.status_message.channel.send(embed=session.status_embed())
            await _update_status_and_prompt(session, next_c)
            return
        else:
            session.add_log(f"💨 {player.name} tried to flee but was caught! (rolled {player_roll}) — loses their turn.")

    elif action in ("GRAPPLE", "SHOVE", "TAUNT") and target:
        if action == "GRAPPLE":
            res = resolve_grapple(player, target)
        elif action == "SHOVE":
            res = resolve_shove(player, target)
        else:
            res = resolve_taunt(player, target)
        for line in res["log_lines"]:
            if channel:
                await channel.send(line)

    elif action == "HIDE":
        res = resolve_hide(player)
        for line in res["log_lines"]:
            if channel:
                await channel.send(line)

    elif action == "DASH":
        session.add_log(f"💨 **{player.name}** dashes — repositioning for next turn!")

    elif action == "HELP":
        session.add_log(f"🤝 **{player.name}** takes the Help action — granting an ally advantage on their next move!")

    elif action == "ITEM":
        healed = player.heal(roll(4) + 2)
        session.add_log(f"🧪 {player.name} uses a potion — healed **{healed} HP**!")

    # ── Boss integration: legendary action after player turn ──
    try:
        boss_legendary_lines = await _check_boss_legendary(session)
        for line in boss_legendary_lines:
            session.add_log(line)
    except Exception:
        pass

    # ── Boss integration: check phase changes after damage ──
    try:
        boss_phase_lines = await _check_boss_state(session)
        for line in boss_phase_lines:
            session.add_log(line)
    except Exception:
        pass

    session.advance_turn()

    # ── Boss integration: lair action at start of new round ──
    if getattr(session, '_new_round', False):
        try:
            boss_lair_lines = await _check_lair_action(session)
            for line in boss_lair_lines:
                session.add_log(line)
        except Exception:
            pass
        # Reset legendary actions for new round
        try:
            await _reset_boss_legendary(session)
        except Exception:
            pass

    await _update_status_and_prompt(session, session.current_combatant)


async def _end_combat(session: CombatSession, winner: Combatant | None):
    session.state = "over"
    _sessions.pop(session.channel_id, None)
    await _set_combat_active(session.guild_id, None)

    async with get_db() as db:
        for i, p in enumerate(session.players):
            uid = session.player_user_ids[i]
            result = await db.execute(
                select(Character).where(Character.user_id == uid, Character.guild_id == session.guild_id)
            )
            char = result.scalar_one_or_none()
            if char:
                char.hp_current = p.hp_current
                char.hp_temp = p.hp_temp
                char.is_unconscious = p.is_unconscious
                char.death_saves_success = p.death_saves_success
                char.death_saves_failure = p.death_saves_failure
                char.conditions = list(p.conditions or [])
                if p.is_dead:
                    char.is_dead = True
                    char.hp_current = 0
                elif p.is_unconscious:
                    char.hp_current = 0

    # ── XP Awards ────────────────────────────────────────────────────────────
    winners = [p for p in session.players if not p.is_dead and not p.is_unconscious]
    losers  = [p for p in session.players if p.is_dead or p.is_unconscious]

    if winners and losers:
        total_xp_per_winner = sum(pvp_xp_reward(loser.level, len(winners)) for loser in losers)
        total_stones_per_winner = sum(random.randint(10, 50) for loser in losers)

        level_up_embeds: list[discord.Embed] = []
        async with get_db() as db:
            for i, p in enumerate(session.players):
                if p not in winners:
                    continue
                uid = session.player_user_ids[i]
                result = await db.execute(
                    select(Character).where(Character.user_id == uid, Character.guild_id == session.guild_id)
                )
                char = result.scalar_one_or_none()
                if not char:
                    continue
                char.balance = (char.balance or 0) + total_stones_per_winner
                char.xp = (char.xp or 0) + total_xp_per_winner
                new_level = check_level_up(char.xp, char.level)
                if new_level:
                    hp_gain = hp_gain_on_level(char.char_class, char.constitution)
                    char.level = new_level
                    char.hp_max = char.hp_max + hp_gain
                    char.hp_current = min(char.hp_current + hp_gain, char.hp_max)
                    feature = feature_at_level(char.char_class, new_level)
                    asi = new_level in ASI_LEVELS
                    lu_embed = discord.Embed(
                        title=f"🎉 {char.name} levelled up! → Lv{new_level}",
                        color=0xA855F7,
                    )
                    lu_embed.add_field(name="❤️ HP", value=f"+{hp_gain} (now {char.hp_max} max)", inline=True)
                    lu_embed.add_field(name="✨ XP", value=xp_bar(char.xp, new_level), inline=False)
                    if feature:
                        lu_embed.add_field(name="🌟 New Feature", value=feature, inline=False)
                    if asi:
                        lu_embed.add_field(name="⬆️ ASI Available", value="You can increase an ability score! Use `/character edit` to apply it.", inline=False)
                    level_up_embeds.append((char, new_level))

        channel = session.status_message.channel if session.status_message else None
        if channel:
            stone_lines = [f"• **{p.name}** earned **{total_stones_per_winner}** 🔮 Spirit Stones" for p in winners]
            xp_lines = [f"• **{p.name}** earned **{total_xp_per_winner} XP**" for p in winners]
            xp_embed = discord.Embed(
                title="⚔️ PvP Awards",
                description="\n".join(xp_lines) + "\n\n" + "\n".join(stone_lines),
                color=0xF59E0B,
            )
            await channel.send(embed=xp_embed)
            for char, new_level in level_up_embeds:
                char_snapshot = {"name": char.name, "level": new_level, "xp": char.xp, "hp_max": char.hp_max, "char_class": char.char_class, "constitution": char.constitution}
                hp_gain = hp_gain_on_level(char.char_class, char.constitution)
                feature = feature_at_level(char.char_class, new_level)
                asi = new_level in ASI_LEVELS
                lu_embed = discord.Embed(
                    title=f"🎉 {char_snapshot['name']} levelled up! → Lv{new_level}",
                    color=0xA855F7,
                )
                lu_embed.add_field(name="❤️ HP", value=f"+{hp_gain} (now {char_snapshot['hp_max']} max)", inline=True)
                lu_embed.add_field(name="✨ XP", value=xp_bar(char_snapshot['xp'], new_level), inline=False)
                if feature:
                    lu_embed.add_field(name="🌟 New Feature", value=feature, inline=False)
                if asi:
                    lu_embed.add_field(name="⬆️ ASI Available", value="You can increase an ability score! Use `/character edit` to apply it.", inline=False)
                await channel.send(embed=lu_embed)
                # Offer attack unlock via DM
                await _offer_attack_unlock(_bot_instance, char, new_level)

    if session.status_message:
        await session.status_message.channel.send(embed=session.winner_embed(winner))


# ── Command group ─────────────────────────────────────────────────────────────

combat_group = app_commands.Group(name="combat", description="Start and manage combat encounters")


@combat_group.command(name="start", description="Start a new combat encounter")
@app_commands.describe(
    title="Name for this combat (e.g. 'Arena Match', 'The Duel')",
    fight_type="DnD — AI resolves via RP + proxy messages. Manual — GM-run, bot tracks only.",
    invite="Optional: ping a user to join when the lobby is created",
)
@app_commands.choices(fight_type=[
    app_commands.Choice(name="DnD (AI resolves)", value="dnd"),
    app_commands.Choice(name="Manual (GM-run)", value="manual"),
])
async def combat_start(interaction: discord.Interaction, title: str, fight_type: app_commands.Choice[str], invite: discord.Member | None = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    if interaction.channel_id in _sessions:
        await interaction.response.send_message("A combat is already active in this channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.followup.send(
            "You don't have a living character. Use `/character create` first.", ephemeral=True
        )
        return
    if not char:
        await interaction.followup.send(
            "You have multiple characters with no active one. Use `/character use` first.", ephemeral=True
        )
        return
    if char.is_unconscious:
        await interaction.followup.send("Your character is unconscious.", ephemeral=True)
        return

    session = CombatSession(
        title=title.strip(),
        fight_type=fight_type.value,
        channel_id=interaction.channel_id,
        guild_id=interaction.guild_id,
        initiator_id=interaction.user.id,
    )
    _sessions[interaction.channel_id] = session
    await _set_combat_active(interaction.guild_id, interaction.channel_id)

    combatant = await _build_combatant(char, interaction.user.id)
    session.players.append(combatant)
    session.player_user_ids.append(interaction.user.id)

    lobby_view = LobbyView(session)
    session.lobby_message = await interaction.channel.send(embed=session.lobby_embed(), view=lobby_view)
    await interaction.followup.send("✅ Combat lobby created!", ephemeral=True)
    if invite:
        invite_view = InviteView(session)
        invite_msg = await interaction.channel.send(
            f"⚔️ {invite.mention} — you've been invited to join **{session.title}**!",
            view=invite_view,
        )
        invite_view._message = invite_msg


@combat_group.command(name="invite", description="Invite a user to the active combat lobby in this channel")
@app_commands.describe(user="The user to invite")
async def combat_invite(interaction: discord.Interaction, user: discord.Member):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state != "lobby":
        await interaction.response.send_message("No open combat lobby in this channel.", ephemeral=True)
        return
    if interaction.user.id != session.initiator_id:
        await interaction.response.send_message("Only the host can invite players.", ephemeral=True)
        return
    if user.id in session.player_user_ids:
        await interaction.response.send_message(f"**{user.display_name}** is already in this fight.", ephemeral=True)
        return
    await interaction.response.send_message("✅ Invite sent!", ephemeral=True)
    invite_view = InviteView(session)
    invite_msg = await interaction.channel.send(
        f"⚔️ {user.mention} — you've been invited to join **{session.title}**!",
        view=invite_view,
    )
    invite_view._message = invite_msg


@combat_group.command(name="join", description="Join an active combat lobby in this server")
async def combat_join(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    open_sessions = [s for s in _sessions.values() if s.guild_id == interaction.guild_id and s.state == "lobby"]
    if not open_sessions:
        await interaction.response.send_message("No open combat lobbies in this server right now.", ephemeral=True)
        return

    async def _join_session(inter: discord.Interaction, session: CombatSession):
        char, chars = await resolve_character(inter.user.id, inter.guild_id)
        if not chars:
            return "You don't have a living character. Use `/character create` first."
        if inter.user.id in session.player_user_ids:
            return "You're already in that fight."
        if not char:
            await inter.response.send_message(
                embed=pick_embed("fight as"),
                view=CombatJoinCharView(chars, session, LobbyView(session)),
                ephemeral=True,
            )
            return None
        if char.is_unconscious:
            return "Your character is unconscious."
        combatant = await _build_combatant(char, inter.user.id)
        session.players.append(combatant)
        session.player_user_ids.append(inter.user.id)
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=LobbyView(session))
        return f"✅ **{char.name}** joined **{session.title}**!"

    if len(open_sessions) == 1:
        msg = await _join_session(interaction, open_sessions[0])
        if msg is not None:
            await interaction.response.send_message(msg, ephemeral=True)
        return

    options = [
        discord.SelectOption(
            label=s.title,
            value=str(s.channel_id),
            description=f"{'DnD' if s.fight_type == 'dnd' else 'Manual'}  ·  {len(s.players)} fighter(s)",
        )
        for s in open_sessions
    ]

    class LobbyPickSelect(discord.ui.Select):
        def __init__(self_inner):
            super().__init__(placeholder="Choose a combat to join...", options=options)

        async def callback(self_inner, inter: discord.Interaction):
            chosen = _sessions.get(int(self_inner.values[0]))
            if not chosen or chosen.state != "lobby":
                await inter.response.edit_message(content="That lobby is no longer open.", embed=None, view=None)
                return
            msg = await _join_session(inter, chosen)
            if msg is not None:
                await inter.response.edit_message(content=msg, embed=None, view=None)

    class LobbyPickView(discord.ui.View):
        def __init__(self_inner):
            super().__init__(timeout=300)
            self_inner.add_item(LobbyPickSelect())

    embed = discord.Embed(
        title="⚔️ Active Combat Lobbies",
        description=f"**{len(open_sessions)}** open fight(s) in this server.",
        color=0x8B5CF6,
    )
    await interaction.response.send_message(embed=embed, view=LobbyPickView(), ephemeral=True)


@combat_group.command(name="status", description="Check the current combat status in this channel")
async def combat_status(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No combat active in this channel.", ephemeral=True)
        return
    await interaction.response.send_message(embed=session.status_embed(), ephemeral=True)


@combat_group.command(name="end", description="End the active combat in this channel")
async def combat_end(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return

    user_is_gm = await is_gm(interaction)
    user_is_initiator = interaction.user.id == session.initiator_id

    if not user_is_gm and not user_is_initiator:
        await interaction.response.send_message(
            "Only the player who started this combat or a GM can end it.", ephemeral=True
        )
        return

    session.state = "over"
    _sessions.pop(session.channel_id, None)
    await _set_combat_active(session.guild_id, None)
    await interaction.response.send_message(
        embed=discord.Embed(
            title="🏳️ Combat Ended",
            description=f"**{session.title}** ended by **{interaction.user.display_name}**.",
            color=0xF59E0B,
        )
    )


@combat_group.command(name="forfeit", description="Forfeit — removes you from the current fight")
async def combat_forfeit(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state != "active":
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return
    if interaction.user.id not in session.player_user_ids:
        await interaction.response.send_message("You're not in this fight.", ephemeral=True)
        return

    idx = session.player_user_ids.index(interaction.user.id)
    player = session.players[idx]
    session.players.pop(idx)
    session.player_user_ids.pop(idx)
    session.turn_order = [c for c in session.turn_order if c is not player]
    session.current_idx = session.current_idx % max(len(session.turn_order), 1)
    session.add_log(f"🏳️ {player.name} forfeited.")

    await interaction.response.send_message(f"**{player.name}** has left the fight.", ephemeral=True)

    if not session.players:
        session.state = "over"
        _sessions.pop(session.channel_id, None)
        await _set_combat_active(session.guild_id, None)
        if session.status_message:
            await session.status_message.channel.send(
                embed=discord.Embed(title="💨 All fighters withdrew.", color=0xF59E0B)
            )
        return

    living = session.living_players
    if len(living) <= 1:
        await _end_combat(session, living[0] if living else None)
        return

    if session.status_message:
        session.status_message = await session.status_message.channel.send(embed=session.status_embed())


# ── New Commands ──────────────────────────────────────────────────────────────

@combat_group.command(name="list", description="List all active combats in this server")
async def combat_list(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    server_sessions = [s for s in _sessions.values() if s.guild_id == interaction.guild_id]
    if not server_sessions:
        await interaction.response.send_message("No active combats in this server.", ephemeral=True)
        return
    embed = discord.Embed(
        title="⚔️ Active Combats",
        description=f"**{len(server_sessions)}** combat(s) in this server.",
        color=0x8B5CF6,
    )
    for s in server_sessions:
        fight_label = "DnD (AI)" if s.fight_type == "dnd" else "Manual"
        state_label = s.state.capitalize()
        embed.add_field(
            name=f"📌 {s.title}",
            value=(
                f"**Type:** {fight_label}  **State:** {state_label}\n"
                f"**Players:** {len(s.players)}  **Round:** {s.round}\n"
                f"**Channel:** <#{s.channel_id}>"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)


@combat_group.command(name="overview", description="Show everyone's current stats in this fight")
async def combat_overview(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No combat active in this channel.", ephemeral=True)
        return
    await interaction.response.send_message(embed=session.status_embed())


@combat_group.command(name="pause", description="Pause the current fight (manual fights only)")
async def combat_pause(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state != "active":
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return
    if session.fight_type != "manual":
        await interaction.response.send_message("Only manual fights can be paused.", ephemeral=True)
        return
    user_is_gm = await is_gm(interaction)
    if not user_is_gm and interaction.user.id != session.initiator_id:
        await interaction.response.send_message("Only the GM or fight host can pause combat.", ephemeral=True)
        return
    session.state = "paused"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="⏸️ Combat Paused",
            description=f"**{session.title}** has been paused. Use `/combat resume` to continue.",
            color=0xF59E0B,
        )
    )


@combat_group.command(name="resume", description="Resume a paused fight (manual fights only)")
async def combat_resume(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state != "paused":
        await interaction.response.send_message("No paused combat in this channel.", ephemeral=True)
        return
    user_is_gm = await is_gm(interaction)
    if not user_is_gm and interaction.user.id != session.initiator_id:
        await interaction.response.send_message("Only the GM or fight host can resume combat.", ephemeral=True)
        return
    session.state = "active"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="▶️ Combat Resumed",
            description=f"**{session.title}** is back in action!",
            color=0x22C55E,
        )
    )
    await _update_status_and_prompt(session, session.current_combatant)


@combat_group.command(name="hp", description="Update HP for a combatant (manual fights or GM)")
@app_commands.describe(
    amount="New HP value, or +/- for relative change (e.g. +5 or -10)",
    target="Target player (GM only — defaults to yourself)",
)
async def combat_hp(interaction: discord.Interaction, amount: str, target: discord.Member | None = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state not in ("active", "paused"):
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return
    user_is_gm = await is_gm(interaction)

    # Determine which combatant to update
    if target and target.id != interaction.user.id:
        if not user_is_gm:
            await interaction.response.send_message("Only the GM can update another player's HP.", ephemeral=True)
            return
        target_uid = target.id
    else:
        target_uid = interaction.user.id

    if not user_is_gm and session.fight_type != "manual":
        await interaction.response.send_message("Players can only update HP in manual fights.", ephemeral=True)
        return

    if target_uid not in session.player_user_ids:
        await interaction.response.send_message("That player is not in this fight.", ephemeral=True)
        return

    idx = session.player_user_ids.index(target_uid)
    combatant = session.players[idx]

    # Parse amount
    amount = amount.strip()
    try:
        if amount.startswith("+"):
            delta = int(amount[1:])
            new_hp = min(combatant.hp_current + delta, combatant.hp_max)
        elif amount.startswith("-"):
            delta = int(amount[1:])
            new_hp = max(combatant.hp_current - delta, 0)
        else:
            new_hp = max(0, min(int(amount), combatant.hp_max))
    except ValueError:
        await interaction.response.send_message("Invalid amount. Use a number like `25`, `+5`, or `-10`.", ephemeral=True)
        return

    old_hp = combatant.hp_current
    combatant.hp_current = new_hp
    if new_hp <= 0 and not combatant.is_dead:
        combatant.is_unconscious = True

    await interaction.response.send_message(
        embed=discord.Embed(
            title=f"❤️ {combatant.name} HP Updated",
            description=f"`{old_hp}` → `{new_hp}/{combatant.hp_max}`",
            color=0x22C55E if new_hp > combatant.hp_max * 0.5 else (0xF97316 if new_hp > 0 else 0xEF4444),
        )
    )
    # Re-post status embed
    if session.status_message:
        await session.status_message.channel.send(embed=session.status_embed())


@combat_group.command(name="log", description="Show the full combat log for this fight")
async def combat_log(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No combat active in this channel.", ephemeral=True)
        return
    log_text = "\n".join(session.log) if session.log else "*No log entries yet.*"
    embed = discord.Embed(
        title=f"📜 Combat Log — {session.title}",
        description=log_text,
        color=0x8B5CF6,
    )
    embed.set_footer(text="Showing most recent entries (last 8 lines)")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@combat_group.command(name="edit", description="Edit conditions or temp HP for a combatant (manual/GM)")
@app_commands.describe(
    field="What to edit",
    value="New value (for temp_hp: number; for conditions: comma-separated condition names to SET)",
    target="Target player (GM only)",
)
@app_commands.choices(field=[
    app_commands.Choice(name="Temp HP", value="temp_hp"),
    app_commands.Choice(name="Conditions (set list)", value="conditions"),
    app_commands.Choice(name="Clear all conditions", value="clear_conditions"),
])
async def combat_edit(
    interaction: discord.Interaction,
    field: app_commands.Choice[str],
    value: str = "",
    target: discord.Member | None = None,
):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session or session.state not in ("active", "paused"):
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return
    user_is_gm = await is_gm(interaction)

    # Determine target combatant
    if target and target.id != interaction.user.id:
        if not user_is_gm:
            await interaction.response.send_message("Only the GM can edit another player's stats.", ephemeral=True)
            return
        target_uid = target.id
    else:
        if not user_is_gm and session.fight_type != "manual":
            await interaction.response.send_message("Players can only edit their own stats in manual fights.", ephemeral=True)
            return
        target_uid = interaction.user.id

    if target_uid not in session.player_user_ids:
        await interaction.response.send_message("That player is not in this fight.", ephemeral=True)
        return

    idx = session.player_user_ids.index(target_uid)
    combatant = session.players[idx]

    field_val = field.value
    if field_val == "temp_hp":
        try:
            combatant.hp_temp = max(0, int(value))
        except ValueError:
            await interaction.response.send_message("Invalid value for temp HP — must be a number.", ephemeral=True)
            return
        desc = f"Temp HP set to **{combatant.hp_temp}**"
    elif field_val == "conditions":
        condition_names = [c.strip().lower() for c in value.split(",") if c.strip()]
        for cond_name in condition_names:
            apply_condition(combatant, cond_name, 3)
        desc = f"Conditions applied: **{', '.join(condition_names)}** (3 rounds each)"
    elif field_val == "clear_conditions":
        combatant.conditions = []
        desc = "All conditions cleared."
    else:
        await interaction.response.send_message("Unknown field.", ephemeral=True)
        return

    embed = discord.Embed(
        title=f"✏️ {combatant.name} Updated",
        description=desc,
        color=0x8B5CF6,
    )
    await interaction.response.send_message(embed=embed)
    if session.status_message:
        await session.status_message.channel.send(embed=session.status_embed())


def _build_summary_embed(session: CombatSession) -> discord.Embed:
    """Build a formatted Battle Report embed from session log and player states."""
    embed = discord.Embed(
        title=f"📋 Battle Report — {session.title}",
        color=0x6366F1,
    )
    embed.add_field(name="Round", value=str(session.round), inline=True)
    fight_label = "DnD (AI)" if session.fight_type == "dnd" else "Manual"
    embed.add_field(name="Fight Type", value=fight_label, inline=True)

    # Player states
    player_lines = []
    for p in session.players:
        if p.is_dead:
            status = "💀 Dead"
        elif p.is_unconscious:
            status = "😵 Unconscious"
        else:
            status = "✅ Standing"
        player_lines.append(f"**{p.name}** (Lv{p.level} {p.char_class}) — {status}  ❤️ `{p.hp_current}/{p.hp_max}`")
    if player_lines:
        embed.add_field(name="Combatants", value="\n".join(player_lines), inline=False)

    # Log
    if session.log:
        embed.add_field(name="📜 Recent Log", value="\n".join(session.log), inline=False)

    embed.set_footer(text="LoreForge Battle Report")
    return embed


@combat_group.command(name="summary", description="Generate a summary of this fight")
async def combat_summary(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No combat active in this channel.", ephemeral=True)
        return
    await interaction.response.send_message(embed=_build_summary_embed(session))


@combat_group.command(name="save", description="Pin the fight summary to a channel")
@app_commands.describe(channel="Channel to post the summary in")
async def combat_save(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.channel_id)
    if not session:
        await interaction.response.send_message("No combat active in this channel.", ephemeral=True)
        return
    user_is_gm = await is_gm(interaction)
    if not user_is_gm and interaction.user.id != session.initiator_id:
        await interaction.response.send_message("Only the GM or fight host can save the summary.", ephemeral=True)
        return
    summary_embed = _build_summary_embed(session)
    await channel.send(embed=summary_embed)
    await interaction.response.send_message(f"✅ Summary posted to {channel.mention}.", ephemeral=True)


# ── Config subgroup ───────────────────────────────────────────────────────────

combat_config = app_commands.Group(name="config", description="Configure combat settings")


@combat_config.command(name="log-channel", description="Set the audit log channel for character edits")
@app_commands.describe(channel="Channel for audit logs")
async def combat_config_log_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("You need the **Manage Server** permission to use this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
        config = result.scalar_one_or_none()
        if config:
            config.log_channel_id = channel.id
        else:
            db.add(GuildConfig(guild_id=interaction.guild_id, log_channel_id=channel.id))
    await interaction.followup.send(
        embed=discord.Embed(
            title="✅ Log Channel Set",
            description=f"Audit logs will be posted to {channel.mention}.",
            color=0x22C55E,
        ),
        ephemeral=True,
    )


# ── Cog ───────────────────────────────────────────────────────────────────────

class CombatCog(commands.Cog, name="Combat"):
    def __init__(self, bot):
        global _bot_instance
        self.bot = bot
        _bot_instance = bot
        combat_group.add_command(combat_config)
        bot.tree.add_command(combat_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("combat")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return

        session = _sessions.get(message.channel.id)
        if not session or session.state != "active":
            return
        if message.content.startswith("/"):
            return

        # Manual fights: log declarations only, don't classify or resolve
        if session.fight_type == "manual":
            if message.author.bot:
                return
            current = session.current_combatant
            uid = session.user_id_for(current)
            if message.author.id != uid:
                return
            if session.pending_action is not None:
                return
            # Just log the declaration and advance turn
            session.add_log(f"📜 **{current.name}**: {message.content[:80]}")
            session.advance_turn()
            await _update_status_and_prompt(session, session.current_combatant)
            return

        # DnD fights: ONLY read proxy webhook messages (PluralKit / Tupperbox)
        if session.fight_type == "dnd":
            if not message.webhook_id:
                return  # ignore all non-proxy messages as OOC

        current = session.current_combatant
        uid = session.user_id_for(current)

        # Match proxy message by character name (webhook display name)
        if message.webhook_id:
            if message.author.display_name.lower() != current.name.lower():
                return
        else:
            if message.author.id != uid:
                return

        if session.pending_action is not None:
            return

        known_attacks = current.class_resources.get("attacks", [])
        attack_name = detect_attack_name(message.content, known_attacks) if known_attacks else None

        # Build full combatants context for AI
        combatants_ctx = [
            {"name": p.name, "hp": f"{p.hp_current}/{p.hp_max}", "class_": p.char_class}
            for p in session.living_players
        ]

        result = await classify_combat_action(
            message.content,
            current.name,
            combatants_ctx,
            player_skills=known_attacks,
        )

        # Hard-override if a named skill was detected locally
        if attack_name:
            result["action"] = "ATTACK"
            result["detected_attack"] = attack_name
        elif result["action"] == "SKILL" and result.get("skill_name"):
            result["detected_attack"] = result["skill_name"]

        # OOC → silent, no response
        if result["action"] == "OOC":
            return

        # UNCLEAR → ask player to clarify
        if result["action"] == "UNCLEAR":
            await message.reply(
                "🤔 I couldn't make out your action — what are you trying to do?",
                mention_author=False,
            )
            return

        session.pending_action = result

        # Actions that require choosing a target
        _NEEDS_TARGET = {"ATTACK", "SPELL", "SKILL", "GRAPPLE", "SHOVE", "TAUNT"}
        if result["action"] in _NEEDS_TARGET:
            living_others = [p for p in session.living_players if p is not current]
            if not living_others:
                session.pending_action = None
                return

            # Try to auto-match target from AI's returned name
            ai_target = _fuzzy_find_target(result.get("target"), living_others)
            if ai_target and len(living_others) == 1:
                # Only one possible target — auto-confirm
                session.pending_target = ai_target
                action_desc = result.get("detected_attack") or result["action"].capitalize()
                session.confirm_message = await message.reply(
                    f"*{action_desc} at **{ai_target.name}*** — is that right?",
                    view=ConfirmView(session, uid),
                    mention_author=False,
                )
            else:
                await message.reply(
                    "⚔️ **Choose your target:**",
                    view=TargetSelectView(session, uid, result, living_others),
                    mention_author=False,
                )
            return

        labels = {
            "DEFEND": "🛡️ Take a defensive stance",
            "FLEE":   "💨 Attempt to flee",
            "ITEM":   "🧪 Use an item",
            "HIDE":   "👁️ Attempt to hide",
            "DASH":   "💨 Dash — reposition",
            "HELP":   "🤝 Take the Help action",
        }
        session.confirm_message = await message.reply(
            f"*{labels.get(result['action'], result['action'])}* — is that right?",
            view=ConfirmView(session, uid),
            mention_author=False,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        async with get_db() as db:
            result = await db.execute(select(GuildConfig).where(GuildConfig.combat_active == True))
            for config in result.scalars().all():
                config.combat_active = False
                config.combat_channel_id = None


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
