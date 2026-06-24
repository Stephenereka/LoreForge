import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildConfig
from services.combat_engine import (
    Combatant, make_enemy, enemy_attack, enemy_xp,
    player_attack, player_defend, roll_initiative,
    check_level_up, hp_gain_on_level, roll, modifier, ENEMIES,
    resolve_named_attack, detect_attack_name, tick_conditions,
    has_condition, apply_condition, remove_condition, effective_ac, CONDITIONS,
)
from services.ai_service import classify_combat_action
from cogs.character import resolve_character, get_characters, CharacterPickView, pick_embed
import random

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


MAX_PLAYERS = 4


def _build_combatant(char: Character, user_id: int) -> "Combatant":
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
    def __init__(self, enemy_key: str, channel_id: int, guild_id: int, initiator_id: int):
        self.enemy_key = enemy_key
        self.enemy = make_enemy(enemy_key)
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

        # Chat-reading combat state
        self.status_message: discord.Message | None = None
        self.confirm_message: discord.Message | None = None
        self.pending_action: dict | None = None
        self.lobby_message: discord.Message | None = None

    @property
    def current_combatant(self) -> Combatant:
        return self.turn_order[self.current_idx]

    @property
    def living_players(self) -> list[Combatant]:
        return [p for p in self.players if p.is_alive]

    @property
    def all_players_down(self) -> bool:
        return all(p.is_dead or p.is_unconscious for p in self.players)

    def add_log(self, line: str):
        self.log.append(line)
        if len(self.log) > 8:
            self.log.pop(0)

    def advance_turn(self):
        start = self.current_idx
        while True:
            self.current_idx = (self.current_idx + 1) % len(self.turn_order)
            if self.current_idx == 0:
                self.round += 1
            c = self.turn_order[self.current_idx]
            if c.is_player and c.is_dead:
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
        e = self.enemy
        embed = discord.Embed(
            title=f"⚔️ Combat Lobby — vs {e.name}",
            description=f"**{e.name}**  ❤️ {e.hp_max} HP  🛡️ AC {e.armor_class}\n\nWaiting for players... (max {MAX_PLAYERS})",
            color=0xF59E0B,
        )
        if self.players:
            lines = [f"• **{p.name}** (Level {p.level} {p.char_class})" for p in self.players]
            embed.add_field(name=f"Players ({len(self.players)}/{MAX_PLAYERS})", value="\n".join(lines), inline=False)
        embed.set_footer(text="Click Join Fight to enter • Host clicks Start Battle when ready")
        return embed

    def status_embed(self) -> discord.Embed:
        current = self.current_combatant
        turn_label = f"**{current.name}'s turn**"

        # Color reflects current combatant's HP health
        if current.hp_max > 0:
            pct = current.hp_current / current.hp_max
        else:
            pct = 0
        if pct > 0.5:
            color = 0x22C55E   # green — healthy
        elif pct > 0.25:
            color = 0xF97316   # orange — wounded
        else:
            color = 0xEF4444   # red — critical / enemy turn

        embed = discord.Embed(
            title=f"⚔️ Round {self.round}  —  {turn_label}",
            color=color,
        )

        e = self.enemy
        e_pct = max(0, e.hp_current / e.hp_max)
        e_bar = "█" * round(e_pct * 10) + "░" * (10 - round(e_pct * 10))
        e_status = "💀" if e.is_dead else "✅"
        e_cond = " ".join(CONDITIONS.get(c["name"], {}).get("icon", "") for c in (e.conditions or []))
        embed.add_field(
            name=f"{e_status} {e.name} {e_cond}".strip(),
            value=f"❤️ `{e.hp_current}/{e.hp_max}` {e_bar}  🛡️ AC `{effective_ac(e)}`",
            inline=False,
        )

        for p in self.players:
            p_pct = max(0, p.hp_current / p.hp_max)
            p_bar = "█" * round(p_pct * 10) + "░" * (10 - round(p_pct * 10))
            if p.is_dead:
                status = "💀 Dead"
            elif p.is_unconscious:
                status = f"😵 Down  ✅{p.death_saves_success}/3 ❌{p.death_saves_failure}/3"
            else:
                status = "✅"
            arrow = " ◄" if current == p else ""
            p_cond = " ".join(CONDITIONS.get(c["name"], {}).get("icon", "") for c in (p.conditions or []))
            embed.add_field(
                name=f"{status}  {p.name} (Lv{p.level} {p.char_class}){arrow} {p_cond}".strip(),
                value=f"❤️ `{p.hp_current}/{p.hp_max}` {p_bar}  🛡️ AC `{effective_ac(p)}`",
                inline=True,
            )

        if self.log:
            embed.add_field(name="📜 Log", value="\n".join(self.log), inline=False)

        return embed

    def victory_embed(self, xp: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"🏆 Victory! {self.enemy.name} defeated!",
            description=f"All surviving players earn **+{xp} XP**.",
            color=0x22C55E,
        )
        for p in self.players:
            if p.is_dead:
                embed.add_field(name=f"💀 {p.name}", value="Fell in battle — no XP", inline=True)
            else:
                embed.add_field(name=f"✅ {p.name}", value=f"❤️ `{p.hp_current}/{p.hp_max}`", inline=True)
        embed.set_footer(text="LoreForge")
        return embed

    def defeat_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"💀 Defeated — {self.enemy.name} wins.",
            description="All fighters are down.",
            color=0x1F2937,
        )
        embed.set_footer(text="Use /character sheet to check your status.")
        return embed


# ── Combat join char picker ───────────────────────────────────────────────────

class CombatJoinCharSelect(discord.ui.Select):
    def __init__(self, chars: list, session: "CombatSession", lobby_view: "LobbyView"):
        self._chars = chars
        self._session = session
        self._lobby_view = lobby_view
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                description=f"Lv{c.level} {c.race} {c.char_class}",
            )
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
        await interaction.response.edit_message(
            content=f"✅ **{char.name}** joined the fight!", embed=None, view=None
        )
        if session.lobby_message:
            await session.lobby_message.edit(embed=session.lobby_embed(), view=self._lobby_view)


class CombatJoinCharView(discord.ui.View):
    def __init__(self, chars: list, session: "CombatSession", lobby_view: "LobbyView"):
        super().__init__(timeout=30)
        self.add_item(CombatJoinCharSelect(chars, session, lobby_view))


# ── Lobby View (buttons OK here — pre-combat) ─────────────────────────────────

class LobbyView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=300)
        self.session = session

    @discord.ui.button(label="Join Fight", style=discord.ButtonStyle.success, emoji="⚔️")
    async def join(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if interaction.user.id in session.player_user_ids:
            await interaction.response.send_message("You're already in this fight.", ephemeral=True)
            return
        if len(session.players) >= MAX_PLAYERS:
            await interaction.response.send_message("The party is full.", ephemeral=True)
            return

        char, chars = await resolve_character(interaction.user.id, interaction.guild_id)

        if not chars:
            await interaction.response.send_message(
                "You don't have a living character. Use `/character create` first.", ephemeral=True
            )
            return

        if not char:
            # Multiple chars, none active — show ephemeral picker
            await interaction.response.send_message(
                embed=pick_embed("fight as"),
                view=CombatJoinCharView(chars, session, self),
                ephemeral=True,
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
        if not session.players:
            await interaction.response.send_message("At least one player must join first.", ephemeral=True)
            return

        session.state = "active"
        all_combatants = session.players + [session.enemy]
        session.turn_order = roll_initiative(all_combatants)

        first = session.turn_order[0]
        session.add_log(f"🎲 Initiative rolled! **{first.name}** goes first.")

        current = session.current_combatant
        prompt = (
            f"**{current.name}** — it's your turn. Type your action in RP."
            if current.is_player
            else f"**{session.enemy.name}** is moving..."
        )

        # Lobby message becomes the persistent status message
        session.status_message = interaction.message
        await interaction.response.edit_message(content=prompt, embed=session.status_embed(), view=None)

        if not first.is_player:
            await _resolve_enemy_turn(session)

    async def on_timeout(self):
        session = self.session
        if session.state == "lobby":
            session.state = "over"
            _sessions.pop(session.channel_id, None)


# ── Confirm View — shown after AI classifies a player's action ────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, session: "CombatSession", player_uid: int):
        super().__init__(timeout=30)
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
        try:
            await interaction.message.delete()
        except Exception:
            pass
        session.confirm_message = None
        await interaction.response.send_message(
            "Action cancelled — type your next move.", ephemeral=True
        )

    async def on_timeout(self):
        session = self.session
        session.pending_action = None
        session.confirm_message = None


# ── Death Save View ───────────────────────────────────────────────────────────

class DeathSaveView(discord.ui.View):
    def __init__(self, session: "CombatSession", player_uid: int):
        super().__init__(timeout=120)
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

        if session.all_players_down:
            await _end_defeat(session)
            return

        session.advance_turn()
        next_c = session.current_combatant

        if session.status_message:
            session.status_message = await session.status_message.channel.send(embed=session.status_embed())

        if not next_c.is_player:
            await _resolve_enemy_turn(session)
        else:
            await _update_status_and_prompt(session, next_c)

    async def on_timeout(self):
        session = self.session
        player = session.current_combatant
        if player.is_unconscious:
            player.death_saves_failure += 1
            session.add_log(f"⏱️ {player.name}'s death save timed out — failure!")
            if player.death_saves_failure >= 3:
                player.is_dead = True
                player.is_unconscious = False
                session.add_log(f"💀 {player.name} dies.")


# ── Shared helpers ────────────────────────────────────────────────────────────

async def _update_status_and_prompt(session: CombatSession, next_c: Combatant):
    if session.status_message is None:
        return

    # Tick conditions at the start of this combatant's turn
    dot_lines = tick_conditions(next_c)
    for line in dot_lines:
        await session.status_message.channel.send(line)

    # DoT may have knocked them out
    if next_c.is_player and next_c.is_dead:
        session.add_log(f"💀 {next_c.name} dies from their wounds!")
        if session.all_players_down:
            await _end_defeat(session)
            return
    elif next_c.is_player and next_c.is_unconscious:
        session.add_log(f"😵 {next_c.name} falls unconscious!")

    # Skip turn if stunned
    if has_condition(next_c, "stunned"):
        session.add_log(f"⚡ **{next_c.name}** is stunned and loses their turn!")
        session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        session.advance_turn()
        next_next = session.current_combatant
        if not next_next.is_player:
            await _resolve_enemy_turn(session)
        else:
            await _update_status_and_prompt(session, next_next)
        return

    if next_c.is_unconscious:
        uid = session.user_id_for(next_c)
        session.status_message = await session.status_message.channel.send(
            content=f"😵 **{next_c.name}** is unconscious.",
            embed=session.status_embed(),
        )
        await session.status_message.channel.send(
            f"😵 **{next_c.name}** — roll your death saving throw!",
            view=DeathSaveView(session, uid),
        )
    else:
        session.status_message = await session.status_message.channel.send(
            content=f"**{next_c.name}** — it's your turn. Type your action in RP.",
            embed=session.status_embed(),
        )


async def _resolve_player_action(session: CombatSession, action_data: dict):
    player = session.current_combatant
    action = action_data.get("action", "UNCLEAR")

    if action in ("ATTACK", "SPELL"):
        enemy = session.enemy
        channel = session.status_message.channel if session.status_message else None
        attack_name = action_data.get("detected_attack")

        if attack_name:
            res = resolve_named_attack(player, attack_name, enemy)
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
                    enemy.take_damage(res["damage"])
                    crit = " *(Crit!)*" if res["crit"] else ""
                    session.add_log(f"⚔️ **{attack_name}** — {player.name} hits for **{res['damage']} dmg**{crit}")
                for cond in res.get("conditions_applied", []):
                    apply_condition(enemy, cond["name"], cond["duration"])
                    icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                    session.add_log(f"{icon} {enemy.name} is now {cond['name']}!")
            else:
                atk_roll = res.get("attack_roll", "?")
                session.add_log(f"🛡️ **{attack_name}** misses ({atk_roll} vs AC {effective_ac(enemy)})")
            for cond in res.get("self_conditions", []):
                apply_condition(player, cond["name"], cond["duration"])
                icon = CONDITIONS.get(cond["name"], {}).get("icon", "⚡")
                session.add_log(f"{icon} {player.name} is now {cond['name']}!")
        else:
            result = player_attack(player, weapon=player.weapon)
            if channel:
                await channel.send(f"🎲 {player.name} rolls **{result['attack_roll']}** to hit.")
            if result["is_miss"]:
                session.add_log(f"🎲 {player.name} — natural 1, missed!")
            elif result["attack_roll"] >= effective_ac(enemy):
                enemy.take_damage(result["damage"])
                crit = " *(Crit!)*" if result["is_crit"] else ""
                sneak = f" +{result['sneak_dice']}d6 sneak" if result["sneak_dice"] else ""
                session.add_log(f"⚔️ {player.name} hits for **{result['damage']} dmg**{crit}{sneak}")
            else:
                session.add_log(f"🛡️ {player.name} misses ({result['attack_roll']} vs AC {effective_ac(enemy)})")

        if not enemy.is_alive:
            await _end_victory(session)
            return

    elif action == "DEFEND":
        result = player_defend(player)
        if result["success"]:
            session.add_log(f"🛡️ {player.name} braces — +{result['temp_hp']} temp HP!")
        else:
            session.add_log(f"🛡️ {player.name} braces but gains nothing.")

    elif action == "FLEE":
        dex_mod = modifier(player.dexterity)
        enemy_dex_mod = modifier(session.enemy.dexterity)
        player_roll = roll(20) + dex_mod
        enemy_roll = roll(20) + enemy_dex_mod

        if player_roll > enemy_roll:
            idx = session.players.index(player)
            session.players.pop(idx)
            session.player_user_ids.pop(idx)
            session.turn_order = [c for c in session.turn_order if c is not player]
            session.current_idx = session.current_idx % max(len(session.turn_order), 1)

            if player_roll >= 15:
                session.add_log(f"💨 {player.name} escapes and is far enough to rest safely!")
            else:
                session.add_log(
                    f"💨 {player.name} escapes — but {session.enemy.name} is close. No rest yet."
                )

            if not session.players:
                session.state = "over"
                _sessions.pop(session.channel_id, None)
                await _set_combat_active(session.guild_id, None)
                embed = discord.Embed(title="💨 All fighters fled.", color=0xF59E0B)
                if session.status_message:
                    await session.status_message.channel.send(embed=embed)
                return

            # After removing player, current_idx already points to next combatant
            next_c = session.turn_order[session.current_idx % len(session.turn_order)]
            if session.status_message:
                session.status_message = await session.status_message.channel.send(embed=session.status_embed())
            if not next_c.is_player:
                await _resolve_enemy_turn(session)
            else:
                await _update_status_and_prompt(session, next_c)
            return

        else:
            session.add_log(
                f"💨 {player.name} tried to flee but was caught! (rolled {player_roll} vs {enemy_roll}) — loses their turn."
            )

    elif action == "ITEM":
        healed = player.heal(roll(4) + 2)
        session.add_log(f"🧪 {player.name} uses a potion — healed **{healed} HP**!")

    # Normal turn advance
    session.advance_turn()
    next_c = session.current_combatant

    if not next_c.is_player:
        if session.status_message:
            session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        await _resolve_enemy_turn(session)
    else:
        await _update_status_and_prompt(session, next_c)


async def _resolve_enemy_turn(session: CombatSession):
    enemy = session.enemy
    channel = session.status_message.channel if session.status_message else None

    # Tick enemy conditions (DoT, expiry)
    dot_lines = tick_conditions(enemy)
    if channel:
        for line in dot_lines:
            await channel.send(line)

    if enemy.is_dead:
        await _end_victory(session)
        return

    # Stunned: skip enemy turn
    if has_condition(enemy, "stunned"):
        session.add_log(f"⚡ **{enemy.name}** is stunned and loses their turn!")
        session.advance_turn()
        next_c = session.current_combatant
        if not next_c.is_player:
            await _resolve_enemy_turn(session)
        else:
            await _update_status_and_prompt(session, next_c)
        return

    # Frightened: 50% chance to cower and lose turn
    if has_condition(enemy, "frightened") and random.random() < 0.5:
        session.add_log(f"😨 **{enemy.name}** cowers in fear and cannot act!")
        if session.status_message:
            session.status_message = await session.status_message.channel.send(embed=session.status_embed())
        session.advance_turn()
        next_c = session.current_combatant
        if not next_c.is_player:
            await _resolve_enemy_turn(session)
        else:
            await _update_status_and_prompt(session, next_c)
        return

    targets = session.living_players

    if not targets:
        unconscious = [p for p in session.players if p.is_unconscious]
        if unconscious:
            for p in unconscious:
                p.death_saves_failure += 1
                session.add_log(f"💀 {enemy.name} attacks downed {p.name} — death save failure!")
                if p.death_saves_failure >= 3:
                    p.is_dead = True
                    p.is_unconscious = False
                    session.add_log(f"💀 {p.name} dies.")
        if session.all_players_down:
            await _end_defeat(session)
            return
    else:
        target = random.choice(targets)
        result = enemy_attack(session.enemy_key)
        if channel:
            await channel.send(f"🎲 **{enemy.name}** rolls **{result['attack_roll']}** to hit {target.name}.")
        if result["is_miss"]:
            session.add_log(f"🎲 {enemy.name} — natural 1, missed!")
        elif result["attack_roll"] >= effective_ac(target):
            status = target.take_damage(result["damage"])
            crit = " *(Crit!)*" if result["is_crit"] else ""
            session.add_log(f"⚔️ {enemy.name} hits {target.name} for **{result['damage']} dmg**{crit}")
            if status == "unconscious":
                session.add_log(f"😵 {target.name} drops to 0 HP!")
        else:
            session.add_log(
                f"🛡️ {enemy.name} attacks {target.name} ({result['attack_roll']} vs AC {effective_ac(target)}) — miss!"
            )

    if session.all_players_down:
        await _end_defeat(session)
        return

    session.advance_turn()
    next_c = session.current_combatant

    if not next_c.is_player:
        await _resolve_enemy_turn(session)
    else:
        await _update_status_and_prompt(session, next_c)


async def _end_victory(session: CombatSession):
    session.state = "over"
    xp = enemy_xp(session.enemy_key)

    async with get_db() as db:
        for i, p in enumerate(session.players):
            uid = session.player_user_ids[i]
            result = await db.execute(
                select(Character).where(
                    Character.user_id == uid,
                    Character.guild_id == session.guild_id,
                )
            )
            char = result.scalar_one_or_none()
            if not char:
                continue
            char.hp_current = p.hp_current
            char.hp_temp = p.hp_temp
            if not p.is_dead:
                char.xp += xp
                new_level = check_level_up(char.xp, char.level)
                if new_level:
                    hp_gain = hp_gain_on_level(char.char_class, char.constitution, new_level)
                    char.level = new_level
                    char.hp_max += hp_gain
                    char.hp_current = char.hp_max
            else:
                char.is_dead = True
                char.hp_current = 0

    _sessions.pop(session.channel_id, None)
    await _set_combat_active(session.guild_id, None)

    if session.status_message:
        await session.status_message.channel.send(embed=session.victory_embed(xp))


async def _end_defeat(session: CombatSession):
    session.state = "over"

    async with get_db() as db:
        for i, p in enumerate(session.players):
            uid = session.player_user_ids[i]
            result = await db.execute(
                select(Character).where(
                    Character.user_id == uid,
                    Character.guild_id == session.guild_id,
                )
            )
            char = result.scalar_one_or_none()
            if char:
                char.hp_current = 0
                if p.is_dead:
                    char.is_dead = True

    _sessions.pop(session.channel_id, None)
    await _set_combat_active(session.guild_id, None)

    if session.status_message:
        await session.status_message.channel.send(embed=session.defeat_embed())


# ── Enemy select ──────────────────────────────────────────────────────────────

class EnemySelect(discord.ui.Select):
    def __init__(self, initiator_id: int):
        self.initiator_id = initiator_id
        options = [
            discord.SelectOption(
                label=data["name"],
                value=key,
                description=f"HP: {data['hp']}  AC: {data['ac']}  XP: {data['xp']}",
            )
            for key, data in ENEMIES.items()
        ]
        super().__init__(placeholder="Choose your enemy...", options=options)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.initiator_id:
            await interaction.response.send_message("Only the host picks the enemy.", ephemeral=True)
            return

        enemy_key = self.values[0]
        session = CombatSession(
            enemy_key=enemy_key,
            channel_id=interaction.channel_id,
            guild_id=interaction.guild_id,
            initiator_id=self.initiator_id,
        )
        _sessions[interaction.channel_id] = session
        await _set_combat_active(interaction.guild_id, interaction.channel_id)

        char, _ = await resolve_character(interaction.user.id, interaction.guild_id)
        if char and not char.is_unconscious:
            combatant = _build_combatant(char, interaction.user.id)
            session.players.append(combatant)
            session.player_user_ids.append(interaction.user.id)

        lobby_view = LobbyView(session)
        session.lobby_message = await interaction.channel.send(embed=session.lobby_embed(), view=lobby_view)
        await interaction.response.edit_message(
            content="✅ Lobby created! Others can join in the channel.", embed=None, view=None
        )


class EnemySelectView(discord.ui.View):
    def __init__(self, initiator_id: int):
        super().__init__(timeout=60)
        self.add_item(EnemySelect(initiator_id))


# ── Command group ─────────────────────────────────────────────────────────────

combat_group = app_commands.Group(name="combat", description="Start and manage combat encounters")


@combat_group.command(name="start", description="Start a combat encounter — others can join before it begins")
async def combat_start(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    if interaction.channel_id in _sessions:
        await interaction.response.send_message(
            "A combat is already active in this channel.", ephemeral=True
        )
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message(
            "You don't have a living character. Use `/character create` first.", ephemeral=True
        )
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters with no active one set. Use `/character use` first.", ephemeral=True
        )
        return
    if char.is_unconscious:
        await interaction.response.send_message("Your character is unconscious.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚔️ Choose your enemy",
        description=f"**{char.name}** — Level {char.level} {char.char_class}",
        color=0x8B5CF6,
    )
    await interaction.response.send_message(embed=embed, view=EnemySelectView(interaction.user.id), ephemeral=True)


@combat_group.command(name="status", description="Check the current combat status")
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

    is_participant = interaction.user.id in session.player_user_ids
    if not is_participant:
        await interaction.response.send_message("You are not in this fight.", ephemeral=True)
        return

    session.state = "over"
    _sessions.pop(session.channel_id, None)
    await _set_combat_active(session.guild_id, None)

    embed = discord.Embed(
        title="🏳️ Combat Ended",
        description=f"Ended by **{interaction.user.display_name}**.",
        color=0xF59E0B,
    )
    await interaction.response.send_message(embed=embed)


@combat_group.command(name="forfeit", description="Forfeit combat — removes you from the current fight")
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
    session.add_log(f"🏳️ {player.name} forfeited the fight.")

    await interaction.response.send_message(f"**{player.name}** has left the fight.", ephemeral=True)

    if not session.players:
        session.state = "over"
        _sessions.pop(session.channel_id, None)
        await _set_combat_active(session.guild_id, None)
        if session.status_message:
            embed = discord.Embed(title="💨 All fighters withdrew.", color=0xF59E0B)
            await session.status_message.channel.send(embed=embed)
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
        if message.author.bot or not message.guild:
            return

        session = _sessions.get(message.channel.id)
        if not session or session.state != "active":
            return
        if message.channel.id != session.channel_id:
            return
        if message.content.startswith("/"):
            return

        current = session.current_combatant
        if not current.is_player:
            return

        uid = session.user_id_for(current)
        if message.author.id != uid:
            return

        # Don't stack confirmations
        if session.pending_action is not None:
            return

        # Detect named attack first (before Groq, to surface it in the confirm label)
        known_attacks = current.class_resources.get("attacks", [])
        attack_name = detect_attack_name(message.content, known_attacks) if known_attacks else None

        result = await classify_combat_action(message.content, current.name, session.enemy.name)

        if attack_name:
            result["action"] = "ATTACK"
            result["detected_attack"] = attack_name
        elif result["action"] == "UNCLEAR":
            return

        session.pending_action = result
        action = result["action"]
        target = result.get("target") or session.enemy.name
        weapon = result.get("weapon")

        if attack_name:
            desc = f"⚔️ **{attack_name}** at **{target}**"
        else:
            labels = {
                "ATTACK": f"⚔️ Attack **{target}**" + (f" with {weapon}" if weapon else ""),
                "DEFEND": "🛡️ Take a defensive stance",
                "FLEE":   "💨 Attempt to flee",
                "ITEM":   "🧪 Use an item",
                "SPELL":  f"✨ Cast a spell at **{target}**",
            }
            desc = labels.get(action, action)

        session.confirm_message = await message.reply(
            f"*{desc}* — is that right?",
            view=ConfirmView(session, uid),
            mention_author=False,
        )

    @commands.Cog.listener()
    async def on_ready(self):
        async with get_db() as db:
            result = await db.execute(
                select(GuildConfig).where(GuildConfig.combat_active == True)
            )
            interrupted = result.scalars().all()
            for config in interrupted:
                config.combat_active = False
                config.combat_channel_id = None
                channel = self.bot.get_channel(config.combat_channel_id or 0)
                if channel:
                    try:
                        await channel.send(
                            "⚠️ **LoreForge restarted** — the active combat was interrupted. Use `/combat start` to begin a new fight."
                        )
                    except Exception:
                        pass


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
