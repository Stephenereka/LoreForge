import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildConfig
import math

# ── Constants ────────────────────────────────────────────────────────────────

RACES = {
    "Human":     {"str": 1, "dex": 1, "con": 1, "int": 1, "wis": 1, "cha": 1},
    "Elf":       {"dex": 2, "wis": 1},
    "Dwarf":     {"con": 2, "wis": 1},
    "Halfling":  {"dex": 2, "cha": 1},
    "Half-Orc":  {"str": 2, "con": 1},
    "Dragonborn":{"str": 2, "cha": 1},
    "Tiefling":  {"int": 1, "cha": 2},
}

CLASSES = {
    "Fighter":   {"hit_die": 10, "primary": "str", "saves": ["str", "con"]},
    "Rogue":     {"hit_die": 8,  "primary": "dex", "saves": ["dex", "int"]},
    "Cleric":    {"hit_die": 8,  "primary": "wis", "saves": ["wis", "cha"]},
    "Wizard":    {"hit_die": 6,  "primary": "int", "saves": ["int", "wis"]},
    "Barbarian": {"hit_die": 12, "primary": "str", "saves": ["str", "con"]},
    "Warlock":   {"hit_die": 8,  "primary": "cha", "saves": ["wis", "cha"]},
}

BACKGROUNDS = ["Acolyte", "Criminal", "Soldier", "Noble", "Sage", "Folk Hero"]

STANDARD_ARRAY = [15, 14, 13, 12, 10, 8]

STAT_LABELS = {
    "str": "Strength", "dex": "Dexterity", "con": "Constitution",
    "int": "Intelligence", "wis": "Wisdom", "cha": "Charisma",
}

CLASS_STAT_ORDER = {
    "Fighter":   ["str", "con", "dex", "wis", "int", "cha"],
    "Rogue":     ["dex", "int", "con", "cha", "str", "wis"],
    "Cleric":    ["wis", "con", "str", "cha", "dex", "int"],
    "Wizard":    ["int", "dex", "con", "wis", "cha", "str"],
    "Barbarian": ["str", "con", "dex", "wis", "cha", "int"],
    "Warlock":   ["cha", "con", "dex", "wis", "int", "str"],
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def modifier(score: int) -> int:
    return math.floor((score - 10) / 2)

def mod_str(score: int) -> str:
    m = modifier(score)
    return f"+{m}" if m >= 0 else str(m)

def calc_hp(char_class: str, con_score: int) -> int:
    hit_die = CLASSES[char_class]["hit_die"]
    return hit_die + modifier(con_score)

def calc_ac(dex_score: int) -> int:
    return 10 + modifier(dex_score)

def assign_stats(char_class: str, race: str) -> dict:
    order = CLASS_STAT_ORDER[char_class]
    base = dict(zip(order, STANDARD_ARRAY))
    bonuses = RACES[race]
    return {stat: base[stat] + bonuses.get(stat, 0) for stat in base}

def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1

def build_sheet_embed(char: Character) -> discord.Embed:
    stats = {
        "str": char.strength, "dex": char.dexterity, "con": char.constitution,
        "int": char.intelligence, "wis": char.wisdom, "cha": char.charisma,
    }
    pb = proficiency_bonus(char.level)
    saves = CLASSES[char.char_class]["saves"]

    embed = discord.Embed(
        title=f"{char.name}",
        description=f"*{char.race} {char.char_class} — Level {char.level}*",
        color=0x8B5CF6,
    )
    embed.add_field(
        name="HP / AC",
        value=f"❤️ `{char.hp_current}/{char.hp_max}`  🛡️ `{char.armor_class}`",
        inline=False,
    )

    stat_lines = []
    for abbr, label in STAT_LABELS.items():
        score = stats[abbr]
        m = mod_str(score)
        save_mark = " ✦" if abbr in saves else ""
        stat_lines.append(f"**{label[:3].upper()}** {score} ({m}){save_mark}")
    embed.add_field(name="Ability Scores  (✦ = save prof.)", value="\n".join(stat_lines), inline=True)

    embed.add_field(
        name="Economy",
        value=f"💰 {char.gold} gp\n📦 {len(char.inventory or [])} item(s)",
        inline=True,
    )
    embed.add_field(
        name="Progress",
        value=f"XP: `{char.xp}`\nProf. Bonus: `+{pb}`",
        inline=True,
    )

    if char.backstory:
        embed.add_field(name="Backstory", value=char.backstory[:500], inline=False)

    embed.set_footer(text=f"Background: {char.background or 'None'}  •  LoreForge")
    return embed

# ── Step 1: Race select ───────────────────────────────────────────────────────

class RaceSelect(discord.ui.Select):
    def __init__(self, char_name: str):
        self.char_name = char_name
        options = [
            discord.SelectOption(
                label=race,
                description=f"Bonuses: {', '.join(f'+{v} {k.upper()}' for k, v in bonuses.items())}"
            )
            for race, bonuses in RACES.items()
        ]
        super().__init__(placeholder="Choose your race...", options=options)

    async def callback(self, interaction: discord.Interaction):
        race = self.values[0]
        await interaction.response.edit_message(
            embed=step2_embed(race),
            view=ClassView(race, self.char_name),
        )


class RaceView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=300)
        self.add_item(RaceSelect(char_name))

# ── Step 2: Class select ──────────────────────────────────────────────────────

CLASS_DESCRIPTIONS = {
    "Fighter":   "Tank & damage — Action Surge",
    "Rogue":     "Sneaky damage — Sneak Attack",
    "Cleric":    "Healer & support — Channel Divinity",
    "Wizard":    "Spell caster — Spellbook & Arcane Recovery",
    "Barbarian": "Rage machine — Bonus damage & resistance",
    "Warlock":   "Pact caster — Eldritch Blast & short-rest slots",
}

class ClassSelect(discord.ui.Select):
    def __init__(self, race: str, char_name: str):
        self.race = race
        self.char_name = char_name
        options = [
            discord.SelectOption(label=cls, description=CLASS_DESCRIPTIONS[cls])
            for cls in CLASSES
        ]
        super().__init__(placeholder="Choose your class...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char_class = self.values[0]
        await interaction.response.edit_message(
            embed=step3_embed(self.race, char_class),
            view=BackgroundView(self.char_name, self.race, char_class),
        )


class ClassView(discord.ui.View):
    def __init__(self, race: str, char_name: str):
        super().__init__(timeout=300)
        self.add_item(ClassSelect(race, char_name))

# ── Step 3: Background select ─────────────────────────────────────────────────

BACKGROUND_DESCRIPTIONS = {
    "Acolyte":   "Temple servant — Religion & Insight",
    "Criminal":  "Life outside the law — Stealth & Deception",
    "Soldier":   "Military service — Athletics & Intimidation",
    "Noble":     "Privilege & power — History & Persuasion",
    "Sage":      "Scholarly pursuits — Arcana & History",
    "Folk Hero": "Humble origins, great deeds — Survival & Animal Handling",
}

class BackgroundSelect(discord.ui.Select):
    def __init__(self, char_name: str, race: str, char_class: str):
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        options = [
            discord.SelectOption(label=bg, description=BACKGROUND_DESCRIPTIONS[bg])
            for bg in BACKGROUNDS
        ]
        super().__init__(placeholder="Choose your background...", options=options)

    async def callback(self, interaction: discord.Interaction):
        background = self.values[0]
        await interaction.response.edit_message(
            embed=step4_embed(self.race, self.char_class, background),
            view=ConfirmView(self.char_name, self.race, self.char_class, background),
        )


class BackgroundView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str):
        super().__init__(timeout=300)
        self.add_item(BackgroundSelect(char_name, race, char_class))

# ── Step 4: Confirm ───────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background

    @discord.ui.button(label="Create Character", style=discord.ButtonStyle.success, emoji="⚔️")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.is_dead == False,
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                await interaction.edit_original_response(
                    content=f"You already have a character: **{existing.name}**. Use `/character sheet` to view them.",
                    embed=None, view=None,
                )
                return

            stats = assign_stats(self.char_class, self.race)
            hp = calc_hp(self.char_class, stats["con"])
            ac = calc_ac(stats["dex"])

            char = Character(
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                name=self.char_name,
                race=self.race,
                char_class=self.char_class,
                background=self.background,
                level=1,
                xp=0,
                strength=stats["str"],
                dexterity=stats["dex"],
                constitution=stats["con"],
                intelligence=stats["int"],
                wisdom=stats["wis"],
                charisma=stats["cha"],
                hp_max=hp,
                hp_current=hp,
                armor_class=ac,
                gold=100,
                inventory=[],
                conditions=[],
                skill_proficiencies=[],
                class_resources=_starting_resources(self.char_class),
                is_dead=False,
                is_unconscious=False,
            )
            db.add(char)

        embed = build_sheet_embed(char)
        embed.title = f"⚔️ {char.name} has entered the world!"
        await interaction.edit_original_response(content=None, embed=embed, view=None)

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.secondary, emoji="↩️")
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step1_embed(self.char_name),
            view=RaceView(self.char_name),
        )


def _starting_resources(char_class: str) -> dict:
    if char_class == "Fighter":
        return {"action_surge": 1}
    elif char_class == "Barbarian":
        return {"rages": 2, "rage_active": False}
    elif char_class == "Warlock":
        return {"spell_slots": 1}
    elif char_class == "Cleric":
        return {"channel_divinity": 1}
    elif char_class == "Wizard":
        return {"spell_slots": 2, "arcane_recovery": 1}
    elif char_class == "Rogue":
        return {"sneak_attack_dice": 1}
    return {}

# ── Embed builders ────────────────────────────────────────────────────────────

def step1_embed(char_name: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 1 of 3",
        description=f"Creating **{char_name}**\n\nChoose your **race**. Each race provides ability score bonuses.",
        color=0x8B5CF6,
    )
    lines = [f"**{race}** — {', '.join(f'+{v} {k.upper()}' for k, v in bonuses.items())}" for race, bonuses in RACES.items()]
    embed.add_field(name="Available Races", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 1 of 3 — Race")
    return embed


def step2_embed(race: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 2 of 3",
        description=f"Race: **{race}** ✓\n\nChoose your **class**. Stats are auto-assigned from the Standard Array (15, 14, 13, 12, 10, 8) in the optimal order for your class.",
        color=0x8B5CF6,
    )
    lines = [f"**{cls}** — {desc}" for cls, desc in CLASS_DESCRIPTIONS.items()]
    embed.add_field(name="Available Classes", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 2 of 3 — Class")
    return embed


def step3_embed(race: str, char_class: str) -> discord.Embed:
    stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    hp = calc_hp(char_class, stats["con"])
    ac = calc_ac(stats["dex"])

    embed = discord.Embed(
        title="⚔️ Character Creation — Step 3 of 3",
        description=f"Race: **{race}** ✓\nClass: **{char_class}** ✓\n\nChoose your **background**.",
        color=0x8B5CF6,
    )
    embed.add_field(name="Your Stats (auto-assigned)", value=stat_preview, inline=False)
    embed.add_field(name="Starting HP / AC", value=f"❤️ {hp}  🛡️ {ac}", inline=False)
    embed.set_footer(text="Step 3 of 3 — Background")
    return embed


def step4_embed(race: str, char_class: str, background: str) -> discord.Embed:
    stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    hp = calc_hp(char_class, stats["con"])
    ac = calc_ac(stats["dex"])

    embed = discord.Embed(
        title="✅ Ready to Create!",
        description=f"**Race:** {race}\n**Class:** {char_class}\n**Background:** {background}",
        color=0x22C55E,
    )
    embed.add_field(name="Stats", value=stat_preview, inline=False)
    embed.add_field(name="HP / AC / Gold", value=f"❤️ {hp}  🛡️ {ac}  💰 100 gp", inline=False)
    embed.set_footer(text="Hit Create Character to confirm — this cannot be undone.")
    return embed

# ── Command Group ─────────────────────────────────────────────────────────────

character_group = app_commands.Group(
    name="character",
    description="Create and manage your character",
)


@character_group.command(name="create", description="Create your character in this world")
@app_commands.describe(name="Your character's name")
async def character_create(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    name = name.strip()
    if len(name) < 2 or len(name) > 32:
        await interaction.response.send_message("Name must be 2–32 characters.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        existing = result.scalar_one_or_none()

    if existing:
        await interaction.response.send_message(
            f"You already have a character: **{existing.name}**. Use `/character sheet` to view them.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        embed=step1_embed(name),
        view=RaceView(name),
        ephemeral=True,
    )


@character_group.command(name="sheet", description="View your character sheet (private)")
async def character_sheet(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
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
            "You don't have a character yet. Use `/character create` to make one.",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(embed=build_sheet_embed(char), ephemeral=True)


@character_group.command(name="show", description="Show your character sheet to the server")
async def character_show(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
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
            "You don't have a character yet. Use `/character create` to make one.",
            ephemeral=True,
        )
        return

    embed = build_sheet_embed(char)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)


# ── Cog ───────────────────────────────────────────────────────────────────────

class CharacterCog(commands.Cog, name="Character"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(character_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("character")


async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
