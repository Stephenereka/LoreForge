import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildConfig
from services.combat_engine import (
    Combatant, make_enemy, enemy_attack, enemy_xp,
    player_attack, player_defend, roll_initiative,
    check_level_up, hp_gain_on_level, ENEMIES,
)
import random

# ── Active sessions: guild_id → CombatSession ────────────────────────────────
_sessions: dict[int, "CombatSession"] = {}


async def _set_combat_active(guild_id: int, channel_id: int | None):
    """Persist combat state to DB so restarts can notify players."""
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

# ── Session ───────────────────────────────────────────────────────────────────

class CombatSession:
    def __init__(self, enemy_key: str, channel_id: int, guild_id: int, initiator_id: int):
        self.enemy_key = enemy_key
        self.enemy = make_enemy(enemy_key)
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id

        self.players: list[Combatant] = []
        self.player_user_ids: list[int] = []          # ordered, matches self.players
        self.turn_order: list[Combatant] = []         # set when combat starts
        self.current_idx: int = 0
        self.round: int = 1
        self.state: str = "lobby"                     # lobby | active | over
        self.log: list[str] = []
        self.message: discord.Message | None = None

    # ── Helpers ───────────────────────────────────────────────────────────────

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
        """Move to the next combatant in order, skipping dead ones."""
        start = self.current_idx
        while True:
            self.current_idx = (self.current_idx + 1) % len(self.turn_order)
            if self.current_idx == 0:
                self.round += 1
            c = self.turn_order[self.current_idx]
            # Skip dead players (enemy never removed, just check hp)
            if c.is_player and (c.is_dead or c.is_unconscious):
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

        embed = discord.Embed(
            title=f"⚔️ Round {self.round}  —  {turn_label}",
            color=0xEF4444 if not current.is_player else 0x8B5CF6,
        )

        # Enemy bar
        e = self.enemy
        e_pct = max(0, e.hp_current / e.hp_max)
        e_bar = "█" * round(e_pct * 10) + "░" * (10 - round(e_pct * 10))
        e_status = "💀" if e.is_dead else "✅"
        embed.add_field(
            name=f"{e_status} {e.name}",
            value=f"❤️ `{e.hp_current}/{e.hp_max}` {e_bar}  🛡️ AC `{e.armor_class}`",
            inline=False,
        )

        # Player bars
        for p in self.players:
            p_pct = max(0, p.hp_current / p.hp_max)
            p_bar = "█" * round(p_pct * 10) + "░" * (10 - round(p_pct * 10))
            if p.is_dead:
                status = "💀 Dead"
            elif p.is_unconscious:
                status = f"😵 Down  ✅{p.death_saves_success} ❌{p.death_saves_failure}"
            else:
                status = "✅"
            arrow = " ◄" if current == p else ""
            embed.add_field(
                name=f"{status}  {p.name} (Lv{p.level} {p.char_class}){arrow}",
                value=f"❤️ `{p.hp_current}/{p.hp_max}` {p_bar}  🛡️ AC `{p.armor_class}`",
                inline=True,
            )

        if self.log:
            embed.add_field(name="📜 Log", value="\n".join(self.log), inline=False)

        if current.is_player:
            embed.set_footer(text=f"{current.name} — choose your action.")
        else:
            embed.set_footer(text=f"{e.name} is taking its turn...")
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


# ── Lobby View ────────────────────────────────────────────────────────────────

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

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.is_dead == False,
                )
            )
            char = result.scalar_one_or_none()

        if not char:
            await interaction.response.send_message(
                "You don't have a living character. Use `/character create` first.", ephemeral=True
            )
            return
        if char.is_unconscious:
            await interaction.response.send_message("Your character is unconscious.", ephemeral=True)
            return

        inventory = char.inventory or []
        equipped_weapon = next(
            (it["key"] for it in inventory if it.get("type") == "weapon" and it.get("equipped")),
            "unarmed",
        )

        combatant = Combatant(
            id=str(interaction.user.id),
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
        session.players.append(combatant)
        session.player_user_ids.append(interaction.user.id)

        await interaction.response.edit_message(embed=session.lobby_embed(), view=self)

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

        view = CombatView(session)
        await interaction.response.edit_message(embed=session.status_embed(), view=view)
        session.message = await interaction.original_response()

        # If enemy goes first, auto-resolve immediately
        if not first.is_player:
            await _resolve_enemy_turn(session, interaction)

    async def on_timeout(self):
        session = self.session
        if session.state == "lobby":
            session.state = "over"
            _sessions.pop(session.guild_id, None)
            if session.message:
                try:
                    await session.message.edit(content="⏱️ Lobby timed out.", embed=None, view=None)
                except Exception:
                    pass


# ── Combat View ───────────────────────────────────────────────────────────────

class CombatView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=300)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        session = self.session
        current = session.current_combatant
        if not current.is_player:
            await interaction.response.send_message("It's the enemy's turn.", ephemeral=True)
            return False
        uid = session.user_id_for(current)
        if interaction.user.id != uid:
            await interaction.response.send_message(
                f"It's **{current.name}'s** turn, not yours.", ephemeral=True
            )
            return False
        return True

    # ── Shared post-action logic ──────────────────────────────────────────────

    async def _after_player_action(self, interaction: discord.Interaction):
        session = self.session

        # Check victory
        if not session.enemy.is_alive:
            await _end_victory(session, interaction)
            return

        # Advance to next combatant
        session.advance_turn()
        next_c = session.current_combatant

        if not next_c.is_player:
            # Enemy turn — edit message to show "enemy attacking..." then resolve
            await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))
            session.message = await interaction.original_response()
            await _resolve_enemy_turn(session, interaction)
        else:
            # Next player's turn
            if next_c.is_unconscious:
                # Unconscious player must roll death save
                view = DeathSaveView(session)
                await interaction.response.edit_message(embed=session.status_embed(), view=view)
            else:
                await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))
            session.message = await interaction.original_response()

    # ── Buttons ───────────────────────────────────────────────────────────────

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, emoji="⚔️", row=0)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        player = session.current_combatant
        result = player_attack(player, weapon=player.weapon)
        enemy = session.enemy

        if result["is_miss"]:
            session.add_log(f"🎲 {player.name} — natural 1, missed!")
        elif result["attack_roll"] >= enemy.armor_class:
            enemy.take_damage(result["damage"])
            crit = " *(Crit!)*" if result["is_crit"] else ""
            sneak = f" +{result['sneak_dice']}d6 sneak" if result["sneak_dice"] else ""
            session.add_log(f"⚔️ {player.name} hits for **{result['damage']} dmg**{crit}{sneak}")
        else:
            session.add_log(f"🛡️ {player.name} misses ({result['attack_roll']} vs AC {enemy.armor_class})")

        if not enemy.is_alive:
            await _end_victory(session, interaction)
            return

        await self._after_player_action(interaction)

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.primary, emoji="🛡️", row=0)
    async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        player = session.current_combatant
        result = player_defend(player)
        if result["success"]:
            session.add_log(f"🛡️ {player.name} braces — +{result['temp_hp']} temp HP!")
        else:
            session.add_log(f"🛡️ {player.name} braces but gains nothing.")
        await self._after_player_action(interaction)

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.secondary, emoji="💨", row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        from services.combat_engine import roll, modifier
        session = self.session
        player = session.current_combatant
        dex_mod = modifier(player.dexterity)
        flee_roll = roll(20) + dex_mod
        dc = 12

        if flee_roll >= dc:
            uid = session.user_id_for(player)
            # Remove player from session
            idx = session.players.index(player)
            session.players.pop(idx)
            session.player_user_ids.pop(idx)
            session.turn_order = [c for c in session.turn_order if c is not player]
            # Clamp current_idx
            session.current_idx = session.current_idx % max(len(session.turn_order), 1)
            session.add_log(f"💨 {player.name} fled the battle!")

            if not session.players:
                # Everyone fled — end session
                session.state = "over"
                _sessions.pop(session.guild_id, None)
                embed = discord.Embed(title="💨 All fighters fled.", color=0xF59E0B)
                await interaction.response.edit_message(embed=embed, view=None)
                return

            # Check if we now need to go to next turn
            next_c = session.turn_order[session.current_idx % len(session.turn_order)]
            if not next_c.is_player:
                await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))
                session.message = await interaction.original_response()
                await _resolve_enemy_turn(session, interaction)
            else:
                await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))
                session.message = await interaction.original_response()
        else:
            session.add_log(f"💨 {player.name} tried to flee! (rolled {flee_roll} vs DC {dc})")
            await self._after_player_action(interaction)

    async def on_timeout(self):
        session = self.session
        if not session.state == "over":
            session.state = "over"
            _sessions.pop(session.guild_id, None)
            if session.message:
                try:
                    await session.message.edit(content="⏱️ Combat timed out.", embed=None, view=None)
                except Exception:
                    pass


# ── Death Save View ───────────────────────────────────────────────────────────

class DeathSaveView(discord.ui.View):
    def __init__(self, session: "CombatSession"):
        super().__init__(timeout=120)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        session = self.session
        current = session.current_combatant
        uid = session.user_id_for(current)
        if interaction.user.id != uid:
            await interaction.response.send_message(
                f"It's **{current.name}'s** death save.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Roll Death Save", style=discord.ButtonStyle.danger, emoji="🎲")
    async def death_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        player = session.current_combatant
        result = player.death_save()

        if result["outcome"] == "critical_success":
            session.add_log(f"🌟 {player.name} — natural 20! Back on 1 HP!")
            session.advance_turn()
            await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))

        elif result["outcome"] == "stabilized":
            session.add_log(f"✅ {player.name} stabilizes (3 successes).")
            session.advance_turn()
            if session.all_players_down:
                await _end_defeat(session, interaction)
                return
            next_c = session.current_combatant
            view = DeathSaveView(session) if next_c.is_player and next_c.is_unconscious else CombatView(session)
            await interaction.response.edit_message(embed=session.status_embed(), view=view)

        elif result["outcome"] == "dead":
            session.add_log(f"💀 {player.name} is dead (3 failures).")
            if session.all_players_down:
                await _end_defeat(session, interaction)
                return
            session.advance_turn()
            next_c = session.current_combatant
            if not next_c.is_player:
                await interaction.response.edit_message(embed=session.status_embed(), view=CombatView(session))
                session.message = await interaction.original_response()
                await _resolve_enemy_turn(session, interaction)
            else:
                view = DeathSaveView(session) if next_c.is_unconscious else CombatView(session)
                await interaction.response.edit_message(embed=session.status_embed(), view=view)

        else:
            s = result.get("successes", 0)
            f = result.get("failures", 0)
            label = "✅" if result["outcome"] == "success" else "❌"
            session.add_log(f"🎲 {player.name} death save {label} (rolled {result['roll']})  ✅{s}/3 ❌{f}/3")
            await interaction.response.edit_message(embed=session.status_embed(), view=self)

        session.message = await interaction.original_response()


# ── Enemy turn resolution (shared helper) ─────────────────────────────────────

async def _resolve_enemy_turn(session: "CombatSession", interaction: discord.Interaction):
    """Auto-resolve enemy attack, then advance to next player turn."""
    enemy = session.enemy
    targets = session.living_players

    if not targets:
        # All players down — but some may be doing death saves
        unconscious = [p for p in session.players if p.is_unconscious]
        if unconscious:
            # Attack each unconscious player (auto fail)
            for p in unconscious:
                p.death_saves_failure += 1
                session.add_log(f"💀 {enemy.name} attacks downed {p.name} — death save failure!")
                if p.death_saves_failure >= 3:
                    p.is_dead = True
                    session.add_log(f"💀 {p.name} dies.")
        if session.all_players_down:
            await _end_defeat(session, interaction)
            return
    else:
        target = random.choice(targets)
        result = enemy_attack(session.enemy_key)
        if result["is_miss"]:
            session.add_log(f"🎲 {enemy.name} — natural 1, missed!")
        elif result["attack_roll"] >= target.armor_class:
            status = target.take_damage(result["damage"])
            crit = " *(Crit!)*" if result["is_crit"] else ""
            session.add_log(
                f"⚔️ {enemy.name} hits {target.name} for **{result['damage']} dmg**{crit}"
            )
            if status == "unconscious":
                session.add_log(f"😵 {target.name} drops to 0 HP!")
        else:
            session.add_log(
                f"🛡️ {enemy.name} attacks {target.name} ({result['attack_roll']} vs AC {target.armor_class}) — miss!"
            )

    if session.all_players_down:
        await _end_defeat(session, interaction)
        return

    session.advance_turn()
    next_c = session.current_combatant

    if next_c.is_unconscious:
        view = DeathSaveView(session)
    else:
        view = CombatView(session)

    try:
        msg = session.message
        if msg:
            await msg.edit(embed=session.status_embed(), view=view)
    except Exception:
        pass


# ── End conditions ────────────────────────────────────────────────────────────

async def _end_victory(session: "CombatSession", interaction: discord.Interaction):
    session.state = "over"
    xp = enemy_xp(session.enemy_key)
    survivors = [p for p in session.players if not p.is_dead]

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

    _sessions.pop(session.guild_id, None)
    await _set_combat_active(session.guild_id, None)
    await interaction.response.edit_message(embed=session.victory_embed(xp), view=None)


async def _end_defeat(session: "CombatSession", interaction: discord.Interaction):
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

    _sessions.pop(session.guild_id, None)
    await _set_combat_active(session.guild_id, None)
    try:
        if interaction.response.is_done():
            if session.message:
                await session.message.edit(embed=session.defeat_embed(), view=None)
        else:
            await interaction.response.edit_message(embed=session.defeat_embed(), view=None)
    except Exception:
        pass


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

        # Build session
        session = CombatSession(
            enemy_key=enemy_key,
            channel_id=interaction.channel_id,
            guild_id=interaction.guild_id,
            initiator_id=self.initiator_id,
        )
        _sessions[interaction.guild_id] = session
        await _set_combat_active(interaction.guild_id, interaction.channel_id)

        # Auto-add the initiator
        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.is_dead == False,
                )
            )
            char = result.scalar_one_or_none()

        if char:
            inventory = char.inventory or []
            equipped_weapon = next(
                (it["key"] for it in inventory if it.get("type") == "weapon" and it.get("equipped")),
                "unarmed",
            )
            combatant = Combatant(
                id=str(interaction.user.id),
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
            session.players.append(combatant)
            session.player_user_ids.append(interaction.user.id)

        lobby_view = LobbyView(session)
        await interaction.response.edit_message(embed=session.lobby_embed(), view=lobby_view)
        session.message = await interaction.original_response()


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

    if interaction.guild_id in _sessions:
        await interaction.response.send_message(
            "A combat is already active. Finish it first.", ephemeral=True
        )
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()

    if not char:
        await interaction.response.send_message(
            "You don't have a living character. Use `/character create` first.", ephemeral=True
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
    await interaction.response.send_message(
        embed=embed,
        view=EnemySelectView(interaction.user.id),
        ephemeral=True,
    )


@combat_group.command(name="status", description="Check the current combat status")
async def combat_status(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    session = _sessions.get(interaction.guild_id)
    if not session:
        await interaction.response.send_message("No combat active right now.", ephemeral=True)
        return
    await interaction.response.send_message(embed=session.status_embed(), ephemeral=True)


# ── Cog ───────────────────────────────────────────────────────────────────────

class CombatCog(commands.Cog, name="Combat"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(combat_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("combat")

    @commands.Cog.listener()
    async def on_ready(self):
        """On startup, notify any channels where combat was active before the restart."""
        from sqlalchemy import select as sa_select
        async with get_db() as db:
            result = await db.execute(
                sa_select(GuildConfig).where(GuildConfig.combat_active == True)
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
