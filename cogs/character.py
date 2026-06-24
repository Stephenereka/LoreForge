import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from services.combat_engine import STARTER_WEAPONS, STARTER_ATTACKS, WEAPON_DAMAGE
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

CLASS_DESCRIPTIONS = {
    "Fighter":   "Tank & damage — Action Surge",
    "Rogue":     "Sneaky damage — Sneak Attack",
    "Cleric":    "Healer & support — Channel Divinity",
    "Wizard":    "Spell caster — Spellbook & Arcane Recovery",
    "Barbarian": "Rage machine — Bonus damage & resistance",
    "Warlock":   "Pact caster — Eldritch Blast & short-rest slots",
}

BACKGROUND_DESCRIPTIONS = {
    "Acolyte":   "Temple servant — Religion & Insight",
    "Criminal":  "Life outside the law — Stealth & Deception",
    "Soldier":   "Military service — Athletics & Intimidation",
    "Noble":     "Privilege & power — History & Persuasion",
    "Sage":      "Scholarly pursuits — Arcana & History",
    "Folk Hero": "Humble origins, great deeds — Survival & Animal Handling",
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def modifier(score: int) -> int:
    return math.floor((score - 10) / 2)

def mod_str(score: int) -> str:
    m = modifier(score)
    return f"+{m}" if m >= 0 else str(m)

def calc_hp(char_class: str, con_score: int) -> int:
    return CLASSES[char_class]["hit_die"] + modifier(con_score)

def calc_ac(dex_score: int) -> int:
    return 10 + modifier(dex_score)

def assign_stats(char_class: str, race: str) -> dict:
    order = CLASS_STAT_ORDER[char_class]
    base = dict(zip(order, STANDARD_ARRAY))
    return {stat: base[stat] + RACES[race].get(stat, 0) for stat in base}

def proficiency_bonus(level: int) -> int:
    return math.ceil(level / 4) + 1

def _starting_resources(char_class: str) -> dict:
    return {
        "Fighter":   {"action_surge": 1},
        "Barbarian": {"rages": 2, "rage_active": False},
        "Warlock":   {"spell_slots": 1},
        "Cleric":    {"channel_divinity": 1},
        "Wizard":    {"spell_slots": 2, "arcane_recovery": 1},
        "Rogue":     {"sneak_attack_dice": 1},
    }.get(char_class, {})

# ── Sheet embed ───────────────────────────────────────────────────────────────

def build_sheet_embed(char: Character) -> discord.Embed:
    stats = {
        "str": char.strength, "dex": char.dexterity, "con": char.constitution,
        "int": char.intelligence, "wis": char.wisdom, "cha": char.charisma,
    }
    pb = proficiency_bonus(char.level)
    saves = CLASSES[char.char_class]["saves"]

    embed = discord.Embed(
        title=char.name,
        description=f"*{char.race} {char.char_class} — Level {char.level}*",
        color=0x8B5CF6,
    )

    if char.avatar_url:
        embed.set_thumbnail(url=char.avatar_url)

    embed.add_field(
        name="HP / AC",
        value=f"❤️ `{char.hp_current}/{char.hp_max}`  🛡️ `{char.armor_class}`",
        inline=False,
    )

    stat_lines = []
    for abbr, label in STAT_LABELS.items():
        score = stats[abbr]
        save_mark = " ✦" if abbr in saves else ""
        stat_lines.append(f"**{label[:3].upper()}** {score} ({mod_str(score)}){save_mark}")
    embed.add_field(name="Ability Scores  (✦ = save prof.)", value="\n".join(stat_lines), inline=True)

    embed.add_field(
        name="Economy",
        value=f"💰 {char.gold} gp\n📦 {len(char.inventory or [])} item(s)",
        inline=True,
    )
    embed.add_field(name="Progress", value=f"XP: `{char.xp}`\nProf. Bonus: `+{pb}`", inline=True)

    attacks = (char.class_resources or {}).get("attacks", [])
    if attacks:
        weapon_key = next(
            (it["key"] for it in (char.inventory or []) if it.get("type") == "weapon" and it.get("equipped")),
            "unarmed",
        )
        dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
        weapon_line = f"🗡️ **{weapon_key.replace('_', ' ').title()}** ({dice[0]}d{dice[1]})"
        attack_lines = [weapon_line] + [f"• {a}" for a in attacks]
        embed.add_field(name="Loadout", value="\n".join(attack_lines), inline=False)

    if char.backstory:
        embed.add_field(name="Backstory", value=char.backstory[:500], inline=False)

    proxy_text = ""
    if char.proxy_open or char.proxy_close:
        proxy_text = f"`{char.proxy_open or ''}text{char.proxy_close or ''}`"
        embed.add_field(name="Proxy", value=proxy_text, inline=False)

    embed.set_footer(text=f"Background: {char.background or 'None'}  •  LoreForge")
    return embed

# ── Step embeds ───────────────────────────────────────────────────────────────

def step1_embed(char_name: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 1 of 5",
        description=f"Creating **{char_name}**\n\nChoose your **race**.",
        color=0x8B5CF6,
    )
    lines = [f"**{race}** — {', '.join(f'+{v} {k.upper()}' for k, v in bonuses.items())}" for race, bonuses in RACES.items()]
    embed.add_field(name="Available Races", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 1 of 5 — Race")
    return embed

def step2_embed(race: str) -> discord.Embed:
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 2 of 5",
        description=f"Race: **{race}** ✓\n\nChoose your **class**.",
        color=0x8B5CF6,
    )
    lines = [f"**{cls}** — {desc}" for cls, desc in CLASS_DESCRIPTIONS.items()]
    embed.add_field(name="Available Classes", value="\n".join(lines), inline=False)
    embed.set_footer(text="Step 2 of 5 — Class")
    return embed

def step3_embed(race: str, char_class: str) -> discord.Embed:
    stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    embed = discord.Embed(
        title="⚔️ Character Creation — Step 3 of 5",
        description=f"Race: **{race}** ✓\nClass: **{char_class}** ✓\n\nChoose your **background**.",
        color=0x8B5CF6,
    )
    embed.add_field(name="Your Stats", value=stat_preview, inline=False)
    embed.add_field(name="Starting HP / AC", value=f"❤️ {calc_hp(char_class, stats['con'])}  🛡️ {calc_ac(stats['dex'])}", inline=False)
    embed.set_footer(text="Step 3 of 5 — Background")
    return embed

def step4_embed(char_name: str, race: str, char_class: str, background: str) -> discord.Embed:
    stats = assign_stats(char_class, race)
    stat_preview = "  ".join(f"**{k.upper()}** {v}" for k, v in stats.items())
    hp = calc_hp(char_class, stats["con"])
    ac = calc_ac(stats["dex"])

    weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
    attacks = STARTER_ATTACKS.get(char_class, [])
    dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
    weapon_label = f"{weapon_key.replace('_', ' ').title()} ({dice[0]}d{dice[1]})"
    attack_list = "  •  ".join(a["name"] for a in attacks)

    embed = discord.Embed(
        title="⚔️ Character Creation — Step 5 of 5",
        description=(
            f"Almost done, **{char_name}**! Here's everything you chose.\n"
            "Add a backstory, avatar, and proxy below — or skip and set them later."
        ),
        color=0x8B5CF6,
    )
    embed.add_field(
        name="Your Character",
        value=f"🧬 **{race}**  ·  ⚔️ **{char_class}**  ·  📜 **{background}**",
        inline=False,
    )
    embed.add_field(
        name="Stats",
        value=stat_preview,
        inline=False,
    )
    embed.add_field(name="HP / AC", value=f"❤️ {hp}  🛡️ {ac}", inline=True)
    embed.add_field(name="Starting Weapon", value=f"🗡️ {weapon_label}", inline=True)
    embed.add_field(name="Attacks", value=attack_list, inline=False)
    embed.set_footer(text="Step 5 of 5 — Details & Proxy")
    return embed

# ── Starting Kit step (between Background and Details) ───────────────────────

def step_kit_embed(char_name: str, race: str, char_class: str, background: str) -> discord.Embed:
    weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
    attacks = STARTER_ATTACKS.get(char_class, [])

    embed = discord.Embed(
        title="⚔️ Character Creation — Step 4 of 5",
        description=(
            f"Race: **{race}** ✓  Class: **{char_class}** ✓  Background: **{background}** ✓\n\n"
            "Here's your starting loadout."
        ),
        color=0x8B5CF6,
    )

    dice = WEAPON_DAMAGE.get(weapon_key, (1, 4))
    embed.add_field(
        name="Starting Weapon",
        value=f"**{weapon_key.replace('_', ' ').title()}** ({dice[0]}d{dice[1]})",
        inline=False,
    )

    lines = []
    for atk in attacks:
        tags = []
        if atk.get("is_spell"):
            tags.append("spell")
        if atk.get("is_defend"):
            tags.append("defensive")
        if atk.get("is_heal"):
            tags.append("heal")
        tag_str = f" *[{', '.join(tags)}]*" if tags else ""
        lines.append(f"**{atk['name']}**{tag_str}\n*{atk['flavor']}*")
    embed.add_field(name="Starting Attacks", value="\n\n".join(lines), inline=False)

    embed.set_footer(text="Step 4 of 5 — Starting Loadout  •  Unlock more through quests and the shop.")
    return embed


class StarterKitView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background

    @discord.ui.button(label="Looks Good →", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def proceed(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step4_embed(self.char_name, self.race, self.char_class, self.background),
            view=Step4View(self.char_name, self.race, self.char_class, self.background),
        )

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="↩️")
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step1_embed(self.char_name),
            view=RaceView(self.char_name),
        )


# ── Step 4: Details modal ─────────────────────────────────────────────────────

class DetailsModal(discord.ui.Modal, title="Character Details"):
    backstory = discord.ui.TextInput(
        label="Backstory / Lore",
        style=discord.TextStyle.paragraph,
        placeholder="Write your character's history, personality, motivations...",
        required=False,
        max_length=1000,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (image link)",
        style=discord.TextStyle.short,
        placeholder="https://i.imgur.com/yourimage.png",
        required=False,
        max_length=500,
    )
    proxy_open = discord.ui.TextInput(
        label="Proxy opening bracket",
        style=discord.TextStyle.short,
        placeholder="e.g.  [  or  char>",
        required=False,
        max_length=10,
    )
    proxy_close = discord.ui.TextInput(
        label="Proxy closing bracket (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g.  ]  — leave blank if using a prefix only",
        required=False,
        max_length=10,
    )

    def __init__(self, char_name: str, race: str, char_class: str, background: str):
        super().__init__()
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background

    async def on_submit(self, interaction: discord.Interaction):
        new_open = self.proxy_open.value.strip() or None
        # Conflict check during creation
        if new_open:
            async with get_db() as db:
                conflict = await db.execute(
                    select(Character).where(
                        Character.guild_id == interaction.guild_id,
                        Character.proxy_open == new_open,
                        Character.is_dead == False,
                    )
                )
                if conflict.scalar_one_or_none():
                    await interaction.response.send_message(
                        f"Another character already uses `{new_open}` as their proxy. Your character will be created without a proxy — set one later with `/character proxy`.",
                        ephemeral=True,
                    )
                    new_open = None

        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race,
            char_class=self.char_class,
            background=self.background,
            backstory=self.backstory.value.strip() or None,
            avatar_url=self.avatar_url.value.strip() or None,
            proxy_open=new_open,
            proxy_close=self.proxy_close.value.strip() or None,
        )


class Step4View(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str, background: str):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.race = race
        self.char_class = char_class
        self.background = background

    @discord.ui.button(label="Add Backstory & Proxy →", style=discord.ButtonStyle.primary, emoji="📖")
    async def add_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            DetailsModal(self.char_name, self.race, self.char_class, self.background)
        )

    @discord.ui.button(label="Skip & Create", style=discord.ButtonStyle.secondary, emoji="⚔️")
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race,
            char_class=self.char_class,
            background=self.background,
        )

    @discord.ui.button(label="Start Over", style=discord.ButtonStyle.danger, emoji="↩️", row=1)
    async def restart(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            embed=step1_embed(self.char_name),
            view=RaceView(self.char_name),
        )

# ── Shared character creation ──────────────────────────────────────────────────

async def _create_character(
    interaction: discord.Interaction,
    char_name: str,
    race: str,
    char_class: str,
    background: str,
    backstory: str | None = None,
    avatar_url: str | None = None,
    proxy_open: str | None = None,
    proxy_close: str | None = None,
):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        if result.scalar_one_or_none():
            msg = "You already have a character. Use `/character sheet` to view them."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        stats = assign_stats(char_class, race)

        weapon_key = STARTER_WEAPONS.get(char_class, "unarmed")
        starting_inventory = (
            [{"key": weapon_key, "type": "weapon", "equipped": True}]
            if weapon_key != "unarmed" else []
        )

        resources = _starting_resources(char_class)
        resources["attacks"] = [atk["name"] for atk in STARTER_ATTACKS.get(char_class, [])]

        char = Character(
            user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            name=char_name,
            race=race,
            char_class=char_class,
            background=background,
            level=1,
            xp=0,
            strength=stats["str"],
            dexterity=stats["dex"],
            constitution=stats["con"],
            intelligence=stats["int"],
            wisdom=stats["wis"],
            charisma=stats["cha"],
            hp_max=calc_hp(char_class, stats["con"]),
            hp_current=calc_hp(char_class, stats["con"]),
            armor_class=calc_ac(stats["dex"]),
            gold=100,
            inventory=starting_inventory,
            conditions=[],
            skill_proficiencies=[],
            class_resources=resources,
            backstory=backstory,
            avatar_url=avatar_url,
            proxy_open=proxy_open,
            proxy_close=proxy_close,
            is_dead=False,
            is_unconscious=False,
        )
        db.add(char)

    embed = build_sheet_embed(char)
    embed.title = f"⚔️ {char.name} has entered the world!"
    if proxy_open:
        brackets = f"`{proxy_open}text{proxy_close or ''}`"
        embed.set_footer(text=f"Proxy active — type {brackets} to speak as {char.name}")

    if interaction.response.is_done():
        await interaction.followup.send(embed=embed, ephemeral=True)
    else:
        await interaction.edit_original_response(embed=embed, view=None)

# ── Steps 1-3: Race → Class → Background ─────────────────────────────────────

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
        await interaction.response.edit_message(embed=step2_embed(race), view=ClassView(race, self.char_name))


class RaceView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=300)
        self.add_item(RaceSelect(char_name))


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
            embed=step_kit_embed(self.char_name, self.race, self.char_class, background),
            view=StarterKitView(self.char_name, self.race, self.char_class, background),
        )


class BackgroundView(discord.ui.View):
    def __init__(self, char_name: str, race: str, char_class: str):
        super().__init__(timeout=300)
        self.add_item(BackgroundSelect(char_name, race, char_class))

# ── /character proxy commands ─────────────────────────────────────────────────

# ── /character delete ─────────────────────────────────────────────────────────

class DeleteConfirmView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=60)
        self.char_name = char_name

    @discord.ui.button(label="Yes, delete forever", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
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
                await interaction.response.edit_message(content="No character found.", view=None, embed=None)
                return
            await db.delete(char)
        await interaction.response.edit_message(
            content=f"**{self.char_name}** has been permanently deleted. Use `/character create` to start fresh.",
            view=None, embed=None,
        )

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None, embed=None)


# ── /character proxy set modal ────────────────────────────────────────────────

class ProxySetModal(discord.ui.Modal, title="Set Proxy"):
    proxy_open = discord.ui.TextInput(
        label="Opening bracket / prefix",
        style=discord.TextStyle.short,
        placeholder="e.g.  [  or  char>",
        required=True,
        max_length=10,
    )
    proxy_close = discord.ui.TextInput(
        label="Closing bracket (optional)",
        style=discord.TextStyle.short,
        placeholder="e.g.  ]  — leave blank for prefix-only",
        required=False,
        max_length=10,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (optional, updates existing)",
        style=discord.TextStyle.short,
        placeholder="https://i.imgur.com/yourimage.png",
        required=False,
        max_length=500,
    )

    async def on_submit(self, interaction: discord.Interaction):
        new_open = self.proxy_open.value.strip()
        async with get_db() as db:
            # Conflict check — no two characters in the same server share the same open bracket
            conflict = await db.execute(
                select(Character).where(
                    Character.guild_id == interaction.guild_id,
                    Character.proxy_open == new_open,
                    Character.user_id != interaction.user.id,
                    Character.is_dead == False,
                )
            )
            if conflict.scalar_one_or_none():
                await interaction.response.send_message(
                    f"Another character in this server already uses `{new_open}` as their proxy. Choose a different bracket.",
                    ephemeral=True,
                )
                return

            result = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.is_dead == False,
                )
            )
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("You don't have a character.", ephemeral=True)
                return
            char.proxy_open = new_open
            char.proxy_close = self.proxy_close.value.strip() or None
            if self.avatar_url.value.strip():
                char.avatar_url = self.avatar_url.value.strip()

        brackets = f"`{char.proxy_open}text{char.proxy_close or ''}`"
        await interaction.response.send_message(
            f"✅ Proxy set for **{char.name}**.\nType {brackets} in any channel to speak as them.",
            ephemeral=True,
        )

# ── Command group ─────────────────────────────────────────────────────────────

character_group = app_commands.Group(name="character", description="Create and manage your character")


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
        if result.scalar_one_or_none():
            await interaction.response.send_message(
                "You already have a character. Use `/character sheet` to view them.", ephemeral=True
            )
            return

    await interaction.response.send_message(embed=step1_embed(name), view=RaceView(name), ephemeral=True)


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
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
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
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return

    embed = build_sheet_embed(char)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)


@character_group.command(name="proxy", description="Set or update your character's proxy brackets")
async def character_proxy(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    await interaction.response.send_modal(ProxySetModal())


@character_group.command(name="delete", description="Permanently delete your character")
async def character_delete(interaction: discord.Interaction):
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
        await interaction.response.send_message("You don't have a character to delete.", ephemeral=True)
        return

    embed = discord.Embed(
        title="⚠️ Delete Character?",
        description=f"**{char.name}** — Level {char.level} {char.race} {char.char_class}\n\nThis is **permanent**. All XP, gold, and inventory will be lost.",
        color=0xEF4444,
    )
    await interaction.response.send_message(embed=embed, view=DeleteConfirmView(char.name), ephemeral=True)


@character_group.command(name="proxy_remove", description="Remove your character's proxy")
async def character_proxy_remove(interaction: discord.Interaction):
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
            await interaction.response.send_message("No character found.", ephemeral=True)
            return
        char.proxy_open = None
        char.proxy_close = None

    await interaction.response.send_message(f"Proxy removed from **{char.name}**.", ephemeral=True)


# ── Cog ───────────────────────────────────────────────────────────────────────

class CharacterCog(commands.Cog, name="Character"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(character_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("character")


async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
