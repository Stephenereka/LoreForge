import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from services.combat_engine import (
    Combatant, make_enemy, enemy_attack, enemy_xp,
    player_attack, player_defend, roll_initiative,
    check_level_up, hp_gain_on_level, ENEMIES,
)
import asyncio

# ── Active sessions: guild_id → CombatSession ────────────────────────────────
# In-memory is fine for combat — sessions are short-lived (minutes, not hours).
# A bot restart mid-fight is acceptable; we don't want the complexity of
# DB-persisted combat state for Phase 1.
_sessions: dict[int, "CombatSession"] = {}

# ── Session ───────────────────────────────────────────────────────────────────

class CombatSession:
    def __init__(self, player: Combatant, enemy: Combatant, enemy_key: str,
                 channel_id: int, guild_id: int, initiator_id: int):
        self.player = player
        self.enemy = enemy
        self.enemy_key = enemy_key
        self.channel_id = channel_id
        self.guild_id = guild_id
        self.initiator_id = initiator_id
        self.turn = 0           # 0 = player, 1 = enemy
        self.round = 1
        self.log: list[str] = []
        self.over = False
        self.message: discord.Message | None = None

    def add_log(self, line: str):
        self.log.append(line)
        if len(self.log) > 6:
            self.log.pop(0)

    def status_embed(self) -> discord.Embed:
        p = self.player
        e = self.enemy

        turn_label = f"**{p.name}'s turn**" if self.turn == 0 else f"**{e.name}'s turn**"

        def hp_bar(current, max_hp, length=10) -> str:
            filled = round((current / max(max_hp, 1)) * length)
            return "█" * filled + "░" * (length - filled)

        embed = discord.Embed(
            title=f"⚔️ {p.name}  vs  {e.name}",
            description=f"Round {self.round}  •  {turn_label}",
            color=0xEF4444 if self.turn == 1 else 0x8B5CF6,
        )

        p_status = "💀 Dead" if p.is_dead else ("😵 Unconscious" if p.is_unconscious else "✅ Alive")
        e_status = "💀 Dead" if e.is_dead else ("😵 Unconscious" if e.is_unconscious else "✅ Alive")

        embed.add_field(
            name=f"{p.name} ({p.char_class})",
            value=f"❤️ `{p.hp_current}/{p.hp_max}` {hp_bar(p.hp_current, p.hp_max)}\n🛡️ AC `{p.armor_class}`  {p_status}",
            inline=True,
        )
        embed.add_field(
            name=e.name,
            value=f"❤️ `{e.hp_current}/{e.hp_max}` {hp_bar(e.hp_current, e.hp_max)}\n🛡️ AC `{e.armor_class}`  {e_status}",
            inline=True,
        )

        if p.is_unconscious:
            embed.add_field(
                name="💀 Death Saves",
                value=f"✅ {p.death_saves_success}/3   ❌ {p.death_saves_failure}/3",
                inline=False,
            )

        if self.log:
            embed.add_field(name="📜 Combat Log", value="\n".join(self.log), inline=False)

        embed.set_footer(text="Your turn — choose an action below.")
        return embed

    def victory_embed(self, xp_gained: int, leveled_up: bool, new_level: int) -> discord.Embed:
        embed = discord.Embed(
            title=f"🏆 Victory! {self.enemy.name} defeated.",
            color=0x22C55E,
        )
        embed.add_field(name="XP Gained", value=f"`+{xp_gained} XP`", inline=True)
        if leveled_up:
            embed.add_field(name="⬆️ Level Up!", value=f"You are now **Level {new_level}**!", inline=True)
        embed.add_field(
            name=f"{self.player.name}",
            value=f"❤️ `{self.player.hp_current}/{self.player.hp_max} HP`",
            inline=False,
        )
        embed.set_footer(text="LoreForge")
        return embed

    def defeat_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"💀 {self.player.name} has fallen.",
            description=f"{self.enemy.name} stood victorious.",
            color=0x6B7280,
        )
        embed.set_footer(text="LoreForge — Use /character sheet to check your status.")
        return embed


# ── Combat View (buttons) ─────────────────────────────────────────────────────

class CombatView(discord.ui.View):
    def __init__(self, session: CombatSession):
        super().__init__(timeout=300)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.initiator_id:
            await interaction.response.send_message("This isn't your fight.", ephemeral=True)
            return False
        if self.session.turn != 0:
            await interaction.response.send_message("It's not your turn.", ephemeral=True)
            return False
        return True

    async def _end_player_turn(self, interaction: discord.Interaction):
        """After player acts, run enemy turn then refresh the message."""
        session = self.session
        enemy = session.enemy
        player = session.player

        # Enemy turn
        session.turn = 1
        if enemy.is_alive:
            if player.is_unconscious:
                # Enemy attacks unconscious player — auto death save fail
                player.death_saves_failure += 1
                session.add_log(f"💀 {enemy.name} attacks {player.name} while down — death save failure!")
                if player.death_saves_failure >= 3:
                    player.is_dead = True
            else:
                result = enemy_attack(session.enemy_key)
                if result["is_miss"]:
                    session.add_log(f"🎲 {enemy.name} attacks — natural 1, missed!")
                elif result["attack_roll"] >= player.armor_class:
                    status = player.take_damage(result["damage"])
                    crit_tag = " *(Critical!)*" if result["is_crit"] else ""
                    session.add_log(
                        f"⚔️ {enemy.name} hits with {result['attack_name']} for **{result['damage']} dmg**{crit_tag}"
                    )
                    if status == "unconscious":
                        session.add_log(f"😵 {player.name} drops to 0 HP!")
                else:
                    session.add_log(f"🛡️ {enemy.name} attacks ({result['attack_roll']}) — missed your AC {player.armor_class}!")

        # Check end conditions
        if player.is_dead:
            await self._end_combat_defeat(interaction)
            return

        session.round += 1
        session.turn = 0

        # If player is unconscious — show death save buttons instead
        if player.is_unconscious:
            new_view = DeathSaveView(session)
            await interaction.response.edit_message(embed=session.status_embed(), view=new_view)
            session.message = await interaction.original_response()
            return

        new_view = CombatView(session)
        await interaction.response.edit_message(embed=session.status_embed(), view=new_view)
        session.message = await interaction.original_response()

    async def _end_combat_victory(self, interaction: discord.Interaction):
        session = self.session
        session.over = True
        xp = enemy_xp(session.enemy_key)

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == session.initiator_id,
                    Character.guild_id == session.guild_id,
                )
            )
            char = result.scalar_one_or_none()
            leveled_up = False
            new_level = char.level if char else 1
            if char:
                char.xp += xp
                char.hp_current = session.player.hp_current
                char.hp_temp = session.player.hp_temp
                new_level_check = check_level_up(char.xp, char.level)
                if new_level_check:
                    leveled_up = True
                    new_level = new_level_check
                    hp_gain = hp_gain_on_level(char.char_class, char.constitution, new_level)
                    char.level = new_level
                    char.hp_max += hp_gain
                    char.hp_current = char.hp_max

        _sessions.pop(session.guild_id, None)
        embed = session.victory_embed(xp, leveled_up, new_level)
        await interaction.response.edit_message(embed=embed, view=None)

    async def _end_combat_defeat(self, interaction: discord.Interaction):
        session = self.session
        session.over = True
        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == session.initiator_id,
                    Character.guild_id == session.guild_id,
                )
            )
            char = result.scalar_one_or_none()
            if char:
                char.is_dead = True
                char.hp_current = 0

        _sessions.pop(session.guild_id, None)
        await interaction.response.edit_message(embed=session.defeat_embed(), view=None)

    @discord.ui.button(label="Attack", style=discord.ButtonStyle.danger, emoji="⚔️", row=0)
    async def attack(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        result = player_attack(session.player, weapon=session.player.weapon)
        enemy = session.enemy

        if result["is_miss"]:
            session.add_log(f"🎲 {session.player.name} attacks — natural 1, missed!")
        elif result["attack_roll"] >= enemy.armor_class:
            enemy.take_damage(result["damage"])
            crit_tag = " *(Critical!)*" if result["is_crit"] else ""
            sneak_tag = f" + {result['sneak_dice']}d6 Sneak" if result["sneak_dice"] else ""
            session.add_log(
                f"⚔️ {session.player.name} hits for **{result['damage']} dmg**{crit_tag}{sneak_tag}"
            )
        else:
            session.add_log(
                f"🛡️ {session.player.name} attacks ({result['attack_roll']}) — missed AC {enemy.armor_class}!"
            )

        if not enemy.is_alive:
            await self._end_combat_victory(interaction)
            return

        await self._end_player_turn(interaction)

    @discord.ui.button(label="Defend", style=discord.ButtonStyle.primary, emoji="🛡️", row=0)
    async def defend(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        result = player_defend(session.player)
        if result["success"]:
            session.add_log(
                f"🛡️ {session.player.name} braces — gained **{result['temp_hp']} temp HP**!"
            )
        else:
            session.add_log(f"🛡️ {session.player.name} braces but gains no footing.")
        await self._end_player_turn(interaction)

    @discord.ui.button(label="Flee", style=discord.ButtonStyle.secondary, emoji="💨", row=0)
    async def flee(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        from services.combat_engine import roll, modifier
        dex_mod = modifier(session.player.dexterity)
        flee_roll = roll(20) + dex_mod
        dc = 12
        if flee_roll >= dc:
            session.over = True
            _sessions.pop(session.guild_id, None)
            embed = discord.Embed(
                title="💨 Escaped!",
                description=f"{session.player.name} fled the battle.",
                color=0xF59E0B,
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            session.add_log(f"💨 {session.player.name} tried to flee but failed! (rolled {flee_roll} vs DC {dc})")
            await self._end_player_turn(interaction)

    async def on_timeout(self):
        session = self.session
        if not session.over:
            session.over = True
            _sessions.pop(session.guild_id, None)
            if session.message:
                try:
                    await session.message.edit(
                        content="⏱️ Combat timed out — you hesitated too long.",
                        embed=None, view=None,
                    )
                except Exception:
                    pass


# ── Death Save View ───────────────────────────────────────────────────────────

class DeathSaveView(discord.ui.View):
    def __init__(self, session: CombatSession):
        super().__init__(timeout=120)
        self.session = session

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.session.initiator_id:
            await interaction.response.send_message("This isn't your fight.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Roll Death Save", style=discord.ButtonStyle.danger, emoji="🎲")
    async def death_save(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        result = session.player.death_save()

        if result["outcome"] == "critical_success":
            session.add_log(f"🌟 Natural 20! {session.player.name} recovers with 1 HP!")
            new_view = CombatView(session)
            await interaction.response.edit_message(embed=session.status_embed(), view=new_view)
        elif result["outcome"] == "stabilized":
            session.add_log(f"✅ {session.player.name} stabilizes (3 successes).")
            # Stabilized but still 0 HP — end combat as a loss (no more enemy turns needed)
            session.over = True
            _sessions.pop(session.guild_id, None)
            embed = discord.Embed(
                title="😴 Stabilized but unconscious.",
                description=f"{session.player.name} is stable but out of the fight.",
                color=0xF59E0B,
            )
            await interaction.response.edit_message(embed=embed, view=None)
        elif result["outcome"] == "dead":
            # Persist death to DB
            async with get_db() as db:
                r = await db.execute(
                    select(Character).where(
                        Character.user_id == session.initiator_id,
                        Character.guild_id == session.guild_id,
                    )
                )
                char = r.scalar_one_or_none()
                if char:
                    char.is_dead = True
                    char.hp_current = 0
            session.over = True
            _sessions.pop(session.guild_id, None)
            embed = discord.Embed(
                title=f"💀 {session.player.name} is dead.",
                description="3 death save failures. Your character is gone.",
                color=0x1F2937,
            )
            await interaction.response.edit_message(embed=embed, view=None)
        else:
            s = result.get("successes", 0)
            f = result.get("failures", 0)
            outcome_label = "✅ Success" if result["outcome"] == "success" else "❌ Failure"
            session.add_log(f"🎲 Death save — {outcome_label} (rolled {result['roll']})  ✅{s}/3 ❌{f}/3")
            await interaction.response.edit_message(embed=session.status_embed(), view=self)


# ── Enemy select for /combat start ───────────────────────────────────────────

class EnemySelect(discord.ui.Select):
    def __init__(self, player_char: Character):
        self.player_char = player_char
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
        enemy_key = self.values[0]
        pc = self.player_char

        # Detect equipped weapon from inventory
        inventory = pc.inventory or []
        equipped_weapon = next(
            (it["key"] for it in inventory if it.get("type") == "weapon" and it.get("equipped")),
            "unarmed",
        )

        player = Combatant(
            id=str(pc.user_id),
            name=pc.name,
            is_player=True,
            level=pc.level,
            char_class=pc.char_class,
            hp_max=pc.hp_max,
            hp_current=pc.hp_current,
            hp_temp=pc.hp_temp,
            strength=pc.strength,
            dexterity=pc.dexterity,
            constitution=pc.constitution,
            intelligence=pc.intelligence,
            wisdom=pc.wisdom,
            charisma=pc.charisma,
            armor_class=pc.armor_class,
            is_dead=pc.is_dead,
            is_unconscious=pc.is_unconscious,
            death_saves_success=pc.death_saves_success,
            death_saves_failure=pc.death_saves_failure,
            conditions=list(pc.conditions or []),
            class_resources=dict(pc.class_resources or {}),
            weapon=equipped_weapon,
        )
        enemy = make_enemy(enemy_key)

        # Roll initiative
        order = roll_initiative([player, enemy])
        first = order[0]

        session = CombatSession(
            player=player,
            enemy=enemy,
            enemy_key=enemy_key,
            channel_id=interaction.channel_id,
            guild_id=interaction.guild_id,
            initiator_id=interaction.user.id,
        )

        if first.id != str(pc.user_id):
            # Enemy goes first
            session.turn = 1
            result = enemy_attack(enemy_key)
            if result["attack_roll"] >= player.armor_class:
                player.take_damage(result["damage"])
                session.add_log(
                    f"🎲 {enemy.name} wins initiative and strikes first for **{result['damage']} dmg**!"
                )
            else:
                session.add_log(f"🎲 {enemy.name} wins initiative but misses ({result['attack_roll']} vs AC {player.armor_class})!")
            session.turn = 0
        else:
            session.add_log(f"🎲 {player.name} wins initiative!")

        _sessions[interaction.guild_id] = session

        view = CombatView(session)
        await interaction.response.edit_message(
            embed=session.status_embed(),
            view=view,
        )
        session.message = await interaction.original_response()


class EnemySelectView(discord.ui.View):
    def __init__(self, player_char: Character):
        super().__init__(timeout=60)
        self.add_item(EnemySelect(player_char))


# ── Command Group ─────────────────────────────────────────────────────────────

combat_group = app_commands.Group(
    name="combat",
    description="Start and manage combat encounters",
)


@combat_group.command(name="start", description="Start a combat encounter")
async def combat_start(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if interaction.guild_id in _sessions:
        await interaction.response.send_message(
            "A combat is already active in this server. Finish it first.", ephemeral=True
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
        await interaction.response.send_message(
            "Your character is unconscious and can't fight.", ephemeral=True
        )
        return

    embed = discord.Embed(
        title="⚔️ Choose your enemy",
        description=f"**{char.name}** — Level {char.level} {char.char_class}\n❤️ `{char.hp_current}/{char.hp_max} HP`  🛡️ AC `{char.armor_class}`",
        color=0x8B5CF6,
    )
    await interaction.response.send_message(
        embed=embed,
        view=EnemySelectView(char),
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


async def setup(bot):
    await bot.add_cog(CombatCog(bot))
