import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from services.combat_engine import modifier
from cogs.combat import _sessions
from cogs.character import resolve_character
from cogs.housing import get_housing_xp_bonus
from services.ai_service import generate_vision
from database.models import Vision, WorldEvent, Quest
from datetime import timezone
import random
import math

HIT_DICE = {
    "Fighter": 10, "Barbarian": 12, "Rogue": 8,
    "Cleric": 8, "Wizard": 6, "Warlock": 8,
    "Paladin": 10, "Ranger": 10, "Druid": 8,
    "Bard": 8, "Monk": 8, "Sorcerer": 6,
}

def _full_resources(char_class: str, level: int) -> dict:
    rages = 2 + max(0, (level - 1) // 4)
    return {
        "Fighter":   {"action_surge": 1},
        "Barbarian": {"rages": rages, "rage_active": False},
        "Warlock":   {"spell_slots": math.ceil(level / 4)},
        "Cleric":    {"channel_divinity": 1},
        "Wizard":    {"spell_slots": 2 + (level // 4), "arcane_recovery": 1},
        "Rogue":     {"sneak_attack_dice": math.ceil(level / 2)},
        "Paladin":   {"spell_slots": max(1, level // 3), "divine_smite_slots": 1 + level // 5},
        "Ranger":    {"spell_slots": max(1, level // 3), "hunter_mark_uses": 3},
        "Druid":     {"spell_slots": max(1, level // 3), "wild_shape_uses": 2},
        "Bard":      {"spell_slots": max(1, level // 3), "bardic_inspiration": level // 3 + 1},
        "Monk":      {"ki_points": level},
        "Sorcerer":  {"spell_slots": max(1, level // 3), "sorcery_points": level},
    }.get(char_class, {})

def _short_rest_resources(char_class: str, level: int, current: dict) -> dict:
    updated = dict(current)
    # Warlocks recover spell slots on short rest
    if char_class == "Warlock":
        updated["spell_slots"] = math.ceil(level / 4)
    # Monks recover ki on short rest
    if char_class == "Monk":
        updated["ki_points"] = min(current.get("ki_points", 0) + level // 2, level)
    return updated

rest_group = app_commands.Group(name="rest", description="Rest to recover HP and class resources")


@rest_group.command(name="short", description="Take a short rest — roll hit dice to recover some HP")
async def rest_short(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    from cogs.combat import _sessions as combat_sessions
    session = combat_sessions.get(interaction.channel_id)
    if session and session.state == "active":
        await interaction.response.send_message("You can't rest during combat!", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters. Use `/character use` to set an active one first.", ephemeral=True
        )
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(Character.id == char.id)
        )
        char = result.scalar_one_or_none()
        if char.hp_current == char.hp_max:
            await interaction.response.send_message("You're already at full HP — no need to rest.", ephemeral=True)
            return

        hit_die = HIT_DICE.get(char.char_class, 8)
        con_mod = modifier(char.constitution)
        roll = random.randint(1, hit_die)
        heal = max(1, roll + con_mod)
        before = char.hp_current
        char.hp_current = min(char.hp_max, char.hp_current + heal)
        char.is_unconscious = False
        actual = char.hp_current - before

        # Short rest resource recovery
        char.class_resources = _short_rest_resources(char.char_class, char.level, char.class_resources or {})

        # Housing XP bonus — award XP based on dwelling tier
        xp_mult = await get_housing_xp_bonus(char.id, db)
        base_xp = random.randint(10, 25)
        housing_xp = round(base_xp * (xp_mult - 1))
        total_xp = base_xp + housing_xp
        char.xp = (char.xp or 0) + total_xp

    embed = discord.Embed(
        title="💤 Short Rest",
        description=f"**{char.name}** rests briefly and tends to their wounds.",
        color=0x6366F1,
    )
    embed.add_field(
        name="HP Recovered",
        value=f"Rolled **{roll}** (1d{hit_die}) {'+' if con_mod >= 0 else ''}{con_mod} CON = **+{actual} HP**\n❤️ `{char.hp_current}/{char.hp_max}`",
        inline=False,
    )
    xp_text = f"✨ Earned **{total_xp} XP** (base: {base_xp}"
    if housing_xp > 0:
        xp_text += f" + **{housing_xp}** from dwelling)"
    else:
        xp_text += ")"
    embed.add_field(name="Cultivation Progress", value=xp_text, inline=False)
    if char.char_class == "Warlock":
        slots = char.class_resources.get("spell_slots", 0)
        embed.add_field(name="⚡ Warlock", value=f"Spell slots restored: `{slots}`", inline=False)
    embed.set_footer(text="Use /rest long for full recovery.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@rest_group.command(name="long", description="Take a long rest — full HP and all class resources restored")
async def rest_long(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    from cogs.combat import _sessions as combat_sessions
    session = combat_sessions.get(interaction.channel_id)
    if session and session.state == "active":
        await interaction.response.send_message("You can't rest during combat!", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters. Use `/character use` to set an active one first.", ephemeral=True
        )
        return

    async with get_db() as db:
        result = await db.execute(select(Character).where(Character.id == char.id))
        char = result.scalar_one_or_none()

        # Preserve starter attacks across long rest
        saved_attacks = (char.class_resources or {}).get("attacks", [])
        before = char.hp_current
        char.hp_current = char.hp_max
        char.hp_temp = 0
        char.is_unconscious = False
        char.death_saves_success = 0
        char.death_saves_failure = 0
        new_resources = _full_resources(char.char_class, char.level)
        if saved_attacks:
            new_resources["attacks"] = saved_attacks
        char.class_resources = new_resources

    recovered = char.hp_max - before
    embed = discord.Embed(
        title="🌙 Long Rest",
        description=f"**{char.name}** takes a full rest. All wounds healed, all resources restored.",
        color=0x4F46E5,
    )
    embed.add_field(
        name="HP",
        value=f"❤️ `{char.hp_max}/{char.hp_max}` (+{recovered} HP)",
        inline=True,
    )
    resources = char.class_resources
    if resources:
        res_lines = []
        if "action_surge" in resources:
            res_lines.append(f"Action Surge: `{resources['action_surge']}`")
        if "rages" in resources:
            res_lines.append(f"Rages: `{resources['rages']}`")
        if "spell_slots" in resources:
            res_lines.append(f"Spell Slots: `{resources['spell_slots']}`")
        if "channel_divinity" in resources:
            res_lines.append(f"Channel Divinity: `{resources['channel_divinity']}`")
        if res_lines:
            embed.add_field(name="Class Resources", value="\n".join(res_lines), inline=True)

    embed.set_footer(text="LoreForge — Well rested and ready.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

    # ── Phase 6: Vision on long rest (20% chance) ─────────────────────────
    try:
        if random.random() < 0.20:
            async with get_db() as db:
                # Get last 5 WorldEvents
                we_result = await db.execute(
                    select(WorldEvent).where(
                        WorldEvent.guild_id == interaction.guild_id,
                    ).order_by(WorldEvent.created_at.desc()).limit(5)
                )
                world_events = list(we_result.scalars().all())
                event_descs = [f"{e.event_type}: {e.narrative or ''}" for e in world_events]

                # Get active quests
                q_result = await db.execute(
                    select(Quest).where(
                        Quest.guild_id == interaction.guild_id,
                        Quest.is_active == True,
                    ).limit(5)
                )
                quests = list(q_result.scalars().all())
                quest_titles = [q.name for q in quests]

                location_name = "their current location"

            vision_text = await generate_vision(
                char.name, location_name, event_descs, quest_titles
            )

            async with get_db() as db:
                db.add(Vision(
                    character_id=char.id,
                    guild_id=interaction.guild_id,
                    vision_text=vision_text,
                    trigger="long_rest",
                ))

            vision_embed = discord.Embed(
                title="💫 A Vision Comes to You...",
                description=vision_text,
                color=0x6366F1,
            )
            vision_embed.set_footer(text="Only you can see this.")
            try:
                await interaction.followup.send(embed=vision_embed, ephemeral=True)
            except Exception:
                pass
    except Exception as e:
        print(f"[VisionRest] Error: {e}")


class RestCog(commands.Cog, name="Rest"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(rest_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("rest")


async def setup(bot):
    await bot.add_cog(RestCog(bot))
