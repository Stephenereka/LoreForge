import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildConfig
from services.combat_engine import (
    Combatant, player_attack, player_defend, roll_initiative,
    roll, modifier, resolve_named_attack, detect_attack_name,
    tick_conditions, has_condition, apply_condition, effective_ac, CONDITIONS,
    resolve_grapple, resolve_shove, resolve_hide, resolve_taunt,
)
from services.ai_service import classify_combat_action
from cogs.character import resolve_character, CharacterPickView, pick_embed

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


def _build_combatant(char: Character, user_id: int) -> Combatant:
    inventory = char.inventory or []
    equipped_weapon = next(
        (it["key"] for it in inventory if it.get("type") == "weapon" and it.get("equipped")),
        "unarmed",
    )
    return Combatant(
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
        if len(self.log) > 8:
            self.log.pop(0)

    def advance_turn(self):
        while True:
            self.current_idx = (self.current_idx + 1) % len(self.turn_order)
            if self.current_idx == 0:
                self.round += 1
            c = self.turn_order[self.current_idx]
            if c.is_dead:
                continue
            break

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
        embed.set_footer(text="Click Join Fight to enter • Host clicks Start Battle when ready (min 2 fighters)")
        return embed

    def status_embed(self) -> discord.Embed:
        current = self.current_combatant
        pct = current.hp_current / current.hp_max if current.hp_max > 0 else 0
        color = 0x22C55E if pct > 0.5 else (0xF97316 if pct > 0.25 else 0xEF4444)

        embed = discord.Embed(
            title=f"⚔️ {self.title}  —  Round {self.round}  —  **{current.name}'s turn**",
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
        combatant = _build_combatant(char, interaction.user.id)
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
        super().__init__(timeout=None)
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
        combatant = _build_combatant(char, interaction.user.id)
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


# ── Invite View — sent when host invites a specific user ─────────────────────

class InviteView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=None)
        self.session = session

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
        combatant = _build_combatant(char, interaction.user.id)
        session.players.append(combatant)
        session.player_user_ids.append(interaction.user.id)
        await interaction.response.send_message(f"✅ **{char.name}** joined the fight!", ephemeral=True)
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=LobbyView(session))
        self.stop()


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


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _update_status_and_prompt(session: CombatSession, next_c: Combatant):
    if session.status_message is None:
        return

    dot_lines = tick_conditions(next_c)
    for line in dot_lines:
        await session.status_message.channel.send(line)

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


async def _resolve_player_action(session: CombatSession, action_data: dict):
    player = session.current_combatant
    target = session.pending_target
    session.pending_target = None
    action = action_data.get("action", "UNCLEAR")
    channel = session.status_message.channel if session.status_message else None

    if action in ("ATTACK", "SPELL", "SKILL") and target:
        attack_name = action_data.get("detected_attack")
        if attack_name:
            res = resolve_named_attack(player, attack_name, target)
            for line in res.get("log_lines", []):
                if channel:
                    await channel.send(line)
            if res["is_heal"]:
                player.heal(res["heal_amount"])
                session.add_log(f"💚 {player.name} heals **{res['heal_amount']} HP** from **{attack_name}**!")
            elif res["miss"]:
                session.add_log(f"🎲 {player.name} — natural 1 on **{attack_name}**!")
            elif res["hit"]:
                if res["damage"] > 0:
                    target.take_damage(res["damage"])
                    crit = " *(Crit!)*" if res["crit"] else ""
                    session.add_log(f"⚔️ **{attack_name}** — {player.name} hits {target.name} for **{res['damage']} dmg**{crit}")
                for cond in res.get("conditions_applied", []):
                    apply_condition(target, cond["name"], cond["duration"])
                    icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                    session.add_log(f"{icon} {target.name} is now {cond['name']}!")
            else:
                session.add_log(f"🛡️ **{attack_name}** misses {target.name} ({res.get('attack_roll', '?')} vs AC {effective_ac(target)})")
            for cond in res.get("self_conditions", []):
                apply_condition(player, cond["name"], cond["duration"])
                icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                session.add_log(f"{icon} {player.name} is now {cond['name']}!")
        else:
            result = player_attack(player, weapon=player.weapon)
            if channel:
                await channel.send(f"🎲 {player.name} rolls **{result['attack_roll']}** to hit {target.name}.")
            if result["is_miss"]:
                session.add_log(f"🎲 {player.name} — natural 1, missed!")
            elif result["attack_roll"] >= effective_ac(target):
                target.take_damage(result["damage"])
                crit = " *(Crit!)*" if result["is_crit"] else ""
                sneak = f" +{result['sneak_dice']}d6 sneak" if result["sneak_dice"] else ""
                session.add_log(f"⚔️ {player.name} hits {target.name} for **{result['damage']} dmg**{crit}{sneak}")
            else:
                session.add_log(f"🛡️ {player.name} misses {target.name} ({result['attack_roll']} vs AC {effective_ac(target)})")

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

    session.advance_turn()
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
                if p.is_dead:
                    char.is_dead = True
                    char.hp_current = 0

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

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message(
            "You don't have a living character. Use `/character create` first.", ephemeral=True
        )
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters with no active one. Use `/character use` first.", ephemeral=True
        )
        return
    if char.is_unconscious:
        await interaction.response.send_message("Your character is unconscious.", ephemeral=True)
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

    combatant = _build_combatant(char, interaction.user.id)
    session.players.append(combatant)
    session.player_user_ids.append(interaction.user.id)

    lobby_view = LobbyView(session)
    session.lobby_message = await interaction.channel.send(embed=session.lobby_embed(), view=lobby_view)
    await interaction.response.send_message("✅ Combat lobby created!", ephemeral=True)
    if invite:
        await interaction.channel.send(
            f"⚔️ {invite.mention} — you've been invited to join **{session.title}**!",
            view=InviteView(session),
        )


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
    await interaction.channel.send(
        f"⚔️ {user.mention} — you've been invited to join **{session.title}**!",
        view=InviteView(session),
    )


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
        combatant = _build_combatant(char, inter.user.id)
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

    from services.utils import is_gm
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


# ── Cog ───────────────────────────────────────────────────────────────────────

class CombatCog(commands.Cog, name="Combat"):
    def __init__(self, bot):
        self.bot = bot
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

        # DnD fights: ONLY read proxy webhook messages (PluralKit / Tupperbox)
        if session.fight_type == "dnd":
            if not message.webhook_id:
                return  # ignore all non-proxy messages as OOC
        else:
            if message.author.bot:
                return

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
