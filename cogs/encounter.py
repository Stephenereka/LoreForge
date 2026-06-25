"""
Encounter system: GMs trigger NPC/boss attacks on players, launching a full
combat session automatically. NPCs auto-attack on their turns via a background
watcher task.
"""
import asyncio
import random
import re
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from database.session import get_db
from database.models import Character, NPC, BossTemplate
from services.combat_engine import Combatant, roll, modifier, roll_initiative, tick_conditions
from services.utils import gm_only

# Module-level: channel_ids currently running NPC watcher tasks
_npc_channels: set[int] = set()
_npc_processing: set[int] = set()


# ── NPC Combatant Builder ─────────────────────────────────────────────────────

def _build_npc_combatant(npc: NPC) -> Combatant:
    derived_level = max(1, (npc.xp_value or 50) // 50)
    return Combatant(
        id=f"npc:{npc.id}",
        name=npc.proxy_name or npc.name,
        is_player=False,
        level=derived_level,
        char_class="NPC",
        hp_max=npc.hp_max,
        hp_current=npc.hp_current,
        armor_class=npc.armor_class,
        strength=12, dexterity=12, constitution=12,
        intelligence=10, wisdom=10, charisma=10,
        is_dead=False, is_unconscious=False,
        conditions=[],
        class_resources={
            "attack_bonus": npc.attack_bonus,
            "damage_dice": npc.damage_dice,
            "damage_bonus": npc.damage_bonus,
            "xp_value": npc.xp_value or 50,
        },
        weapon="melee",
    )


def _build_boss_combatant(boss: BossTemplate) -> Combatant:
    derived_level = max(1, (boss.xp_value or 500) // 100)
    return Combatant(
        id=f"boss:{boss.id}",
        name=boss.title or boss.name,
        is_player=False,
        level=derived_level,
        char_class="Boss",
        hp_max=boss.hp_max,
        hp_current=boss.hp_max,
        armor_class=boss.armor_class,
        strength=18, dexterity=14, constitution=16,
        intelligence=12, wisdom=12, charisma=14,
        is_dead=False, is_unconscious=False,
        conditions=[],
        class_resources={
            "attack_bonus": boss.attack_bonus,
            "damage_dice": boss.damage_dice,
            "damage_bonus": boss.damage_bonus,
            "xp_value": boss.xp_value or 500,
        },
        weapon="melee",
    )


# ── Dice Helper ───────────────────────────────────────────────────────────────

def _roll_damage(dice_str: str, bonus: int = 0, double: bool = False) -> int:
    match = re.match(r"(\d+)d(\d+)", dice_str)
    if match:
        count, sides = int(match.group(1)), int(match.group(2))
        if double:
            count *= 2
        return sum(roll(sides) for _ in range(count)) + bonus
    return roll(6) + bonus


# ── NPC Auto-Turn ─────────────────────────────────────────────────────────────

async def _do_npc_attack(session, npc_c: Combatant, channel: discord.TextChannel):
    """Resolve one NPC auto-attack against a random living player."""
    from cogs.combat import _end_combat, _update_status_and_prompt

    targets = [c for c in session.turn_order if c.is_player and c.is_alive]
    if not targets:
        await _end_combat(session, npc_c)
        return

    target = random.choice(targets)
    atk_bonus = npc_c.class_resources.get("attack_bonus", 2)
    dmg_dice = npc_c.class_resources.get("damage_dice", "1d6")
    dmg_bonus = npc_c.class_resources.get("damage_bonus", 0)

    natural = roll(20)
    atk_total = natural + atk_bonus
    is_crit = natural == 20
    is_fumble = natural == 1

    if is_fumble:
        line = f"💨 **{npc_c.name}** swings wildly at **{target.name}** — **critical miss!** The attack fails."
        session.add_log(line)
        await channel.send(line)
    elif atk_total >= target.armor_class:
        dmg = _roll_damage(dmg_dice, dmg_bonus, double=is_crit)
        result_str = target.take_damage(dmg)
        crit_tag = " 💥 **CRIT!**" if is_crit else ""
        line = (
            f"⚔️ **{npc_c.name}** attacks **{target.name}**!{crit_tag} "
            f"[{atk_total} vs AC {target.armor_class}] → **{dmg} damage**! "
            f"({target.hp_current}/{target.hp_max} HP remaining)"
        )
        session.add_log(line)
        await channel.send(line)

        if not target.is_alive:
            living_players = [c for c in session.turn_order if c.is_player and c.is_alive]
            if not living_players:
                await _end_combat(session, npc_c)
                return
    else:
        line = (
            f"🛡️ **{npc_c.name}** strikes at **{target.name}** but misses! "
            f"[{atk_total} vs AC {target.armor_class}]"
        )
        session.add_log(line)
        await channel.send(line)

    await asyncio.sleep(0.5)
    session.advance_turn()
    await _update_status_and_prompt(session, session.current_combatant)


async def _npc_watcher(session, channel: discord.TextChannel):
    """Background task: auto-resolves NPC turns in an encounter."""
    _npc_channels.add(channel.id)
    try:
        while session.state == "active":
            await asyncio.sleep(2)
            if session.state != "active":
                break
            if not session.turn_order:
                continue
            if channel.id in _npc_processing:
                continue

            c = session.current_combatant
            if c.is_player or c.is_dead or c.is_unconscious:
                continue

            _npc_processing.add(channel.id)
            try:
                await _do_npc_attack(session, c, channel)
            except Exception as e:
                print(f"[Encounter] NPC auto-turn error: {e}")
            finally:
                _npc_processing.discard(channel.id)
    finally:
        _npc_channels.discard(channel.id)
        _npc_processing.discard(channel.id)


# ── Encounter Launcher ────────────────────────────────────────────────────────

async def _launch_encounter(
    interaction: discord.Interaction,
    enemy_combatant: Combatant,
    player_user: discord.Member,
    title: str,
    xp_on_win: int,
):
    """Start an instant combat session between enemy_combatant and player_user's active character."""
    from cogs.combat import CombatSession, _sessions, _set_combat_active, _update_status_and_prompt, _build_combatant

    # Check channel isn't already in combat
    if interaction.channel_id in _sessions:
        await interaction.followup.send("A combat session is already active in this channel.", ephemeral=True)
        return

    # Get player's active character
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == player_user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()

    if not char:
        await interaction.followup.send(
            f"{player_user.mention} has no active living character.", ephemeral=True
        )
        return

    player_c = await _build_combatant(char, player_user.id)

    # Build session — skip lobby, go straight to active
    session = CombatSession(
        title=title,
        fight_type="dnd",
        channel_id=interaction.channel_id,
        guild_id=interaction.guild_id,
        initiator_id=interaction.user.id,
    )
    # Add both combatants (enemy first in players list, NPC gets user_id 0)
    session.players = [enemy_combatant, player_c]
    session.player_user_ids = [0, player_user.id]

    # Store XP value for when player wins (NPC/boss xp_value)
    session._encounter_xp = xp_on_win

    # Roll initiative and start immediately
    session.state = "active"
    session.turn_order = roll_initiative(session.players)
    first = session.turn_order[0]
    session.add_log(f"⚡ **Encounter triggered!** {enemy_combatant.name} attacks {player_c.name}!")
    session.add_log(f"🎲 Initiative: **{first.name}** goes first.")

    _sessions[interaction.channel_id] = session
    await _set_combat_active(interaction.guild_id, interaction.channel_id)

    # Post the opening message
    encounter_embed = discord.Embed(
        title=f"⚔️ {title}",
        description=f"**{enemy_combatant.name}** has engaged **{player_c.name}** in combat!",
        color=0xDC2626,
    )
    encounter_embed.add_field(
        name=enemy_combatant.name,
        value=f"❤️ {enemy_combatant.hp_current}/{enemy_combatant.hp_max} HP | 🛡️ AC {enemy_combatant.armor_class}",
        inline=True,
    )
    encounter_embed.add_field(
        name=f"{player_c.name} (Lv{player_c.level} {player_c.char_class})",
        value=f"❤️ {player_c.hp_current}/{player_c.hp_max} HP | 🛡️ AC {player_c.armor_class}",
        inline=True,
    )
    encounter_embed.set_footer(text="Type your actions in chat • Use /combat buttons to attack, defend, or use abilities")

    session.status_message = await interaction.channel.send(
        content=f"🚨 {player_user.mention} — you're under attack!",
        embed=encounter_embed,
    )

    # Prompt first combatant
    await _update_status_and_prompt(session, first)

    # Start NPC watcher if first or any combatant is non-player
    if any(not c.is_player for c in session.turn_order):
        asyncio.get_event_loop().create_task(
            _npc_watcher(session, interaction.channel)
        )

    await interaction.followup.send(
        f"✅ Encounter started: **{enemy_combatant.name}** vs **{player_c.name}**", ephemeral=True
    )


# ── Commands ──────────────────────────────────────────────────────────────────

encounter_group = app_commands.Group(name="encounter", description="Start NPC and boss combat encounters")


@encounter_group.command(name="npc", description="Trigger an NPC attack on a player, starting a combat encounter (GM only)")
@app_commands.describe(
    npc_name="Name of the NPC who attacks",
    player="The player being attacked",
)
async def encounter_npc(interaction: discord.Interaction, npc_name: str, player: discord.Member):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(npc_name.strip()),
                NPC.is_dead == False,
            )
        )
        npc = result.scalar_one_or_none()

    if not npc:
        await interaction.followup.send(f"No living NPC named **{npc_name}** found.", ephemeral=True)
        return

    enemy_c = _build_npc_combatant(npc)
    await _launch_encounter(
        interaction,
        enemy_c,
        player,
        title=f"{npc.proxy_name or npc.name} Encounter",
        xp_on_win=npc.xp_value or 50,
    )


@encounter_group.command(name="boss", description="Pit a boss template against a player (GM only)")
@app_commands.describe(
    boss_name="Name of the boss template",
    player="The player being attacked",
)
async def encounter_boss(interaction: discord.Interaction, boss_name: str, player: discord.Member):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        result = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                BossTemplate.name.ilike(boss_name.strip()),
            )
        )
        boss = result.scalar_one_or_none()

    if not boss:
        await interaction.followup.send(f"No boss template named **{boss_name}** found.", ephemeral=True)
        return

    enemy_c = _build_boss_combatant(boss)
    await _launch_encounter(
        interaction,
        enemy_c,
        player,
        title=f"Boss Fight — {boss.title or boss.name}",
        xp_on_win=boss.xp_value or 500,
    )


@encounter_group.command(name="add-npc", description="Add an NPC to the active combat in this channel (GM only)")
@app_commands.describe(npc_name="Name of the NPC to add to combat")
async def encounter_add_npc(interaction: discord.Interaction, npc_name: str):
    if not await gm_only(interaction):
        return

    from cogs.combat import _sessions
    session = _sessions.get(interaction.channel_id)
    if not session or session.state != "active":
        await interaction.response.send_message("No active combat in this channel.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)

    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(npc_name.strip()),
                NPC.is_dead == False,
            )
        )
        npc = result.scalar_one_or_none()

    if not npc:
        await interaction.followup.send(f"No living NPC named **{npc_name}** found.", ephemeral=True)
        return

    npc_c = _build_npc_combatant(npc)
    npc_c.initiative = roll(20) + modifier(npc_c.dexterity)

    session.players.append(npc_c)
    session.player_user_ids.append(0)
    session.turn_order.append(npc_c)
    session.turn_order.sort(key=lambda c: c.initiative, reverse=True)
    session.add_log(f"⚡ **{npc_c.name}** joins the battle! (Initiative {npc_c.initiative})")

    if interaction.channel_id not in _npc_channels:
        asyncio.get_event_loop().create_task(
            _npc_watcher(session, interaction.channel)
        )

    await interaction.followup.send(
        f"✅ **{npc_c.name}** added to combat. Initiative: {npc_c.initiative}", ephemeral=True
    )
    if session.status_message:
        await session.status_message.channel.send(
            f"⚡ **{npc_c.name}** charges into the battle!"
        )


class EncounterCog(commands.Cog, name="Encounter"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(encounter_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("encounter")


async def setup(bot):
    await bot.add_cog(EncounterCog(bot))
