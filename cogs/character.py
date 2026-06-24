import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, PendingApproval, GuildConfig
from services.combat_engine import STARTER_WEAPONS, STARTER_ATTACKS, WEAPON_DAMAGE
from services.leveling import xp_bar, xp_for_next_level, check_level_up
import math

# ── Constants ────────────────────────────────────────────────────────────────

MAX_CHARACTERS = 3

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

async def _is_valid_image_url(url: str) -> bool:
    if not url:
        return True
    if not url.lower().startswith("https://"):
        return False
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, allow_redirects=True, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                ct = resp.headers.get("Content-Type", "")
                return ct.startswith("image/")
    except Exception:
        return False

def _starting_resources(char_class: str) -> dict:
    return {
        "Fighter":   {"action_surge": 1},
        "Barbarian": {"rages": 2, "rage_active": False},
        "Warlock":   {"spell_slots": 1},
        "Cleric":    {"channel_divinity": 1},
        "Wizard":    {"spell_slots": 2, "arcane_recovery": 1},
        "Rogue":     {"sneak_attack_dice": 1},
    }.get(char_class, {})


# ── DB helpers (exported for use in combat.py / rest.py) ─────────────────────

async def get_characters(user_id: int, guild_id: int) -> list[Character]:
    """Return all living characters for this user in this guild."""
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == user_id,
                Character.guild_id == guild_id,
                Character.is_dead == False,
            )
        )
        return list(result.scalars().all())


async def resolve_character(user_id: int, guild_id: int) -> tuple:
    """
    Returns (selected_char, all_chars).
    selected_char is the active char (or the only char if solo).
    If multiple chars and none is active, selected_char is None — caller shows picker.
    """
    chars = await get_characters(user_id, guild_id)
    if not chars:
        return None, []
    if len(chars) == 1:
        return chars[0], chars
    active = next((c for c in chars if c.is_active), None)
    return active, chars


# ── Sheet embed ───────────────────────────────────────────────────────────────

def build_sheet_embed(char: Character) -> discord.Embed:
    stats = {
        "str": char.strength, "dex": char.dexterity, "con": char.constitution,
        "int": char.intelligence, "wis": char.wisdom, "cha": char.charisma,
    }
    pb = proficiency_bonus(char.level)
    saves = CLASSES.get(char.char_class, {}).get("saves", [])

    active_tag = "  ★" if char.is_active else ""
    embed = discord.Embed(
        title=f"{char.name}{active_tag}",
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
    xp_display = xp_bar(char.xp, char.level)
    embed.add_field(name="Progress", value=f"{xp_display}\nProf. Bonus: `+{pb}`", inline=True)

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
    embed.add_field(name="Stats", value=stat_preview, inline=False)
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
        super().__init__(timeout=600)
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


# ── Character picker (for multi-char users) ───────────────────────────────────

def pick_embed(action_label: str) -> discord.Embed:
    return discord.Embed(
        title="📋 Choose a Character",
        description=f"You have multiple characters. Which one do you want to **{action_label}**?\n\n*Tip: use `/character use` to set a default so you never have to choose.*",
        color=0x8B5CF6,
    )


class CharacterPickSelect(discord.ui.Select):
    def __init__(self, chars: list, action: str):
        self._chars = chars
        self._action = action
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                description=f"Lv{c.level} {c.race} {c.char_class}" + ("  ★ active" if c.is_active else ""),
            )
            for c in chars
        ]
        super().__init__(placeholder="Choose a character...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char_id = int(self.values[0])
        char = next((c for c in self._chars if c.id == char_id), None)
        if not char:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return

        action = self._action

        if action == "sheet":
            await interaction.response.edit_message(embed=build_sheet_embed(char), view=None)

        elif action == "show":
            embed = build_sheet_embed(char)
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            await interaction.response.edit_message(content="✅ Posted to channel!", embed=None, view=None)
            await interaction.channel.send(embed=embed)

        elif action == "delete":
            embed = discord.Embed(
                title="⚠️ Delete Character?",
                description=f"**{char.name}** — Level {char.level} {char.race} {char.char_class}\n\nThis is **permanent**. All XP, gold, and inventory will be lost.",
                color=0xEF4444,
            )
            await interaction.response.edit_message(embed=embed, view=DeleteConfirmView(char.name, char.id))

        elif action == "proxy":
            await interaction.response.send_modal(ProxySetModal(char.id))

        elif action == "proxy_remove":
            async with get_db() as db:
                result = await db.execute(select(Character).where(Character.id == char_id))
                c = result.scalar_one_or_none()
                if c:
                    c.proxy_open = None
                    c.proxy_close = None
            await interaction.response.edit_message(
                content=f"Proxy removed from **{char.name}**.", embed=None, view=None
            )

        elif action == "use":
            async with get_db() as db:
                result = await db.execute(
                    select(Character).where(
                        Character.user_id == interaction.user.id,
                        Character.guild_id == interaction.guild_id,
                        Character.is_dead == False,
                    )
                )
                for c in result.scalars().all():
                    c.is_active = (c.id == char_id)
            await interaction.response.edit_message(
                content=f"✅ **{char.name}** is now your active character. All commands will use them automatically.",
                embed=None,
                view=None,
            )


class CharacterPickView(discord.ui.View):
    def __init__(self, chars: list, action: str):
        super().__init__(timeout=300)
        self.add_item(CharacterPickSelect(chars, action))


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
        placeholder="https://example.com/image.png  (.jpg/.png/.gif/.webp)",
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
        raw_url = self.avatar_url.value.strip() or None
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        new_open = self.proxy_open.value.strip() or None
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
        super().__init__(timeout=600)
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
    is_custom: bool = False,
):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        existing = list(result.scalars().all())
        if len(existing) >= MAX_CHARACTERS:
            msg = f"You already have {MAX_CHARACTERS} characters. Delete one with `/character delete` first."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return

        # First character is auto-set as active
        is_first = len(existing) == 0

        if is_custom:
            # Custom characters: flat 10 in all stats, base HP/AC, no starter gear
            char = Character(
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                name=char_name,
                race=race,
                char_class=char_class,
                background=background,
                level=1,
                xp=0,
                is_custom=True,
                strength=10,
                dexterity=10,
                constitution=10,
                intelligence=10,
                wisdom=10,
                charisma=10,
                hp_max=10,
                hp_current=10,
                armor_class=10,
                gold=100,
                inventory=[],
                conditions=[],
                skill_proficiencies=[],
                class_resources={},
                backstory=backstory,
                avatar_url=avatar_url,
                proxy_open=proxy_open,
                proxy_close=proxy_close,
                is_dead=False,
                is_unconscious=False,
                is_active=is_first,
            )
        else:
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
                is_custom=False,
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
                is_active=is_first,
            )
        db.add(char)

    embed = build_sheet_embed(char)
    embed.title = f"⚔️ {char.name} has entered the world!"
    if is_first:
        embed.description = (embed.description or "") + "\n\n★ Set as your active character automatically."
    else:
        embed.description = (embed.description or "") + "\n\nUse `/character use` to make this your active character."
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
        super().__init__(timeout=600)
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
        super().__init__(timeout=600)
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
        super().__init__(timeout=600)
        self.add_item(BackgroundSelect(char_name, race, char_class))

# ── Delete confirm ────────────────────────────────────────────────────────────

class DeleteConfirmView(discord.ui.View):
    def __init__(self, char_name: str, char_id: int):
        super().__init__(timeout=300)
        self.char_name = char_name
        self.char_id = char_id

    @discord.ui.button(label="Yes, delete forever", style=discord.ButtonStyle.danger, emoji="💀")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.edit_message(content="No character found.", view=None, embed=None)
                return
            was_active = char.is_active
            await db.delete(char)

        msg = f"**{self.char_name}** has been permanently deleted."
        if was_active:
            msg += " Use `/character use` to set another active character."
        await interaction.response.edit_message(content=msg, view=None, embed=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Deletion cancelled.", view=None, embed=None)


# ── Proxy set modal ───────────────────────────────────────────────────────────

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
        placeholder="https://example.com/image.png  (.jpg/.png/.gif/.webp)",
        required=False,
        max_length=500,
    )

    def __init__(self, char_id: int):
        super().__init__()
        self.char_id = char_id

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.avatar_url.value.strip()
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        new_open = self.proxy_open.value.strip()
        async with get_db() as db:
            conflict = await db.execute(
                select(Character).where(
                    Character.guild_id == interaction.guild_id,
                    Character.proxy_open == new_open,
                    Character.id != self.char_id,
                    Character.is_dead == False,
                )
            )
            if conflict.scalar_one_or_none():
                await interaction.response.send_message(
                    f"Another character in this server already uses `{new_open}` as their proxy. Choose a different bracket.",
                    ephemeral=True,
                )
                return

            result = await db.execute(select(Character).where(Character.id == self.char_id))
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message("Character not found.", ephemeral=True)
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

# ── Custom character creation ─────────────────────────────────────────────────

class CustomCharacterModal(discord.ui.Modal, title="Create Custom Character"):
    char_class = discord.ui.TextInput(
        label="Class / Role",
        placeholder="e.g. Shadow Assassin, Arcane Archer",
        max_length=50,
    )
    race = discord.ui.TextInput(
        label="Race / Species",
        placeholder="e.g. Aasimar, Kitsune, Half-Dragon",
        max_length=50,
    )
    background = discord.ui.TextInput(
        label="Background",
        placeholder="e.g. Fallen Noble, Street Rat, War Veteran",
        max_length=50,
    )
    backstory = discord.ui.TextInput(
        label="Backstory (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000,
    )
    avatar_url = discord.ui.TextInput(
        label="Avatar URL (optional)",
        required=False,
        max_length=500,
    )

    def __init__(self, char_name: str):
        super().__init__()
        self.char_name = char_name

    async def on_submit(self, interaction: discord.Interaction):
        raw_url = self.avatar_url.value.strip() or None
        if raw_url and not await _is_valid_image_url(raw_url):
            await interaction.response.send_message(
                "That URL doesn't point to an image. Make sure it's a direct link to a `.jpg`, `.png`, `.gif`, `.webp`, or any image hosted online.",
                ephemeral=True,
            )
            return

        await _create_character(
            interaction,
            char_name=self.char_name,
            race=self.race.value.strip(),
            char_class=self.char_class.value.strip(),
            background=self.background.value.strip(),
            backstory=self.backstory.value.strip() or None,
            avatar_url=raw_url,
            is_custom=True,
        )


class CharTypeView(discord.ui.View):
    def __init__(self, char_name: str):
        super().__init__(timeout=300)
        self.char_name = char_name

    @discord.ui.button(label="DnD Character", style=discord.ButtonStyle.primary, emoji="⚔️")
    async def dnd_char(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(embed=step1_embed(self.char_name), view=RaceView(self.char_name))

    @discord.ui.button(label="Custom Character", style=discord.ButtonStyle.secondary, emoji="✏️")
    async def custom_char(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CustomCharacterModal(self.char_name))


# ── Command group ─────────────────────────────────────────────────────────────

character_group = app_commands.Group(name="character", description="Create and manage your character")


@character_group.command(name="create", description="Create a new character (max 3 per server)")
@app_commands.describe(name="Your character's name")
async def character_create(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    name = name.strip()
    if len(name) < 2 or len(name) > 32:
        await interaction.response.send_message("Name must be 2–32 characters.", ephemeral=True)
        return

    chars = await get_characters(interaction.user.id, interaction.guild_id)
    if len(chars) >= MAX_CHARACTERS:
        await interaction.response.send_message(
            f"You already have {MAX_CHARACTERS} characters. Delete one with `/character delete` first.",
            ephemeral=True,
        )
        return

    type_embed = discord.Embed(
        title="⚔️ Create Character — Choose Type",
        description=(
            f"**{name}**\n\n"
            "What kind of character do you want to create?\n\n"
            "**DnD Character** — Standard races, classes, and stat system (5-step wizard)\n"
            "**Custom Character** — Completely free-form: any race, class, and background you imagine"
        ),
        color=0x8B5CF6,
    )
    type_embed.set_footer(text="Custom characters can only do manual combat (no AI resolution)")
    await interaction.response.send_message(embed=type_embed, view=CharTypeView(name), ephemeral=True)


@character_group.command(name="use", description="Set your active character — all commands use them automatically")
async def character_use(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    chars = await get_characters(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No characters found. Use `/character create`.", ephemeral=True)
        return

    if len(chars) == 1:
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == chars[0].id))
            c = result.scalar_one_or_none()
            if c:
                c.is_active = True
        await interaction.response.send_message(
            f"✅ **{chars[0].name}** is your active character.", ephemeral=True
        )
        return

    await interaction.response.send_message(
        embed=pick_embed("set as active"),
        view=CharacterPickView(chars, "use"),
        ephemeral=True,
    )


@character_group.command(name="unuse", description="Clear your active character — you'll be asked to choose each time")
async def character_unuse(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
        if not char:
            await interaction.response.send_message("You don't have an active character set.", ephemeral=True)
            return
        name = char.name
        char.is_active = False

    await interaction.response.send_message(
        f"**{name}** is no longer your active character. You'll be asked to choose each time.",
        ephemeral=True,
    )


@character_group.command(name="sheet", description="View your character sheet (private)")
async def character_sheet(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        await interaction.response.send_message(embed=build_sheet_embed(char), ephemeral=True)
    else:
        await interaction.response.send_message(
            embed=pick_embed("view sheet for"), view=CharacterPickView(chars, "sheet"), ephemeral=True
        )


@character_group.command(name="show", description="Show your character sheet to the server")
async def character_show(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        embed = build_sheet_embed(char)
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message(
            embed=pick_embed("show"), view=CharacterPickView(chars, "show"), ephemeral=True
        )


@character_group.command(name="proxy", description="Set or update a character's proxy brackets")
async def character_proxy(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if char:
        await interaction.response.send_modal(ProxySetModal(char.id))
    else:
        await interaction.response.send_message(
            embed=pick_embed("set proxy for"), view=CharacterPickView(chars, "proxy"), ephemeral=True
        )


@character_group.command(name="delete", description="Permanently delete a character")
async def character_delete(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("You don't have any characters to delete.", ephemeral=True)
        return
    if char:
        embed = discord.Embed(
            title="⚠️ Delete Character?",
            description=f"**{char.name}** — Level {char.level} {char.race} {char.char_class}\n\nThis is **permanent**. All XP, gold, and inventory will be lost.",
            color=0xEF4444,
        )
        await interaction.response.send_message(embed=embed, view=DeleteConfirmView(char.name, char.id), ephemeral=True)
    else:
        await interaction.response.send_message(
            embed=pick_embed("delete"), view=CharacterPickView(chars, "delete"), ephemeral=True
        )


@character_group.command(name="list", description="List all your characters in this server")
@app_commands.describe(public="Show the list publicly in the channel (default: private)")
async def character_list(interaction: discord.Interaction, public: bool = False):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            ).order_by(Character.is_active.desc(), Character.id)
        )
        chars = list(result.scalars().all())

    if not chars:
        await interaction.response.send_message(
            "You have no characters in this server. Use `/character create` to make one.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title=f"📋 {interaction.user.display_name}'s Characters",
        color=0x8B5CF6,
    )
    for char in chars:
        if char.is_dead:
            status = "💀 Dead"
        elif char.is_unconscious:
            status = "😵 Unconscious"
        elif char.is_active:
            status = "★ Active"
        else:
            status = "✅ Alive"
        embed.add_field(
            name=f"{char.name}  —  {status}",
            value=f"Lv{char.level} {char.race} {char.char_class}  ·  ❤️ {char.hp_current}/{char.hp_max}  ·  💰 {char.gold} gp  ·  XP: {char.xp}",
            inline=False,
        )
    embed.set_footer(text=f"{len(chars)}/{MAX_CHARACTERS} character slots used  •  LoreForge")

    await interaction.response.send_message(embed=embed, ephemeral=not public)


@character_group.command(name="proxy_remove", description="Remove a character's proxy")
async def character_proxy_remove(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found.", ephemeral=True)
        return
    if char:
        async with get_db() as db:
            result = await db.execute(select(Character).where(Character.id == char.id))
            c = result.scalar_one_or_none()
            if c:
                c.proxy_open = None
                c.proxy_close = None
        await interaction.response.send_message(f"Proxy removed from **{char.name}**.", ephemeral=True)
    else:
        await interaction.response.send_message(
            embed=pick_embed("remove proxy from"), view=CharacterPickView(chars, "proxy_remove"), ephemeral=True
        )


@character_group.command(name="edit", description="Request a stat change (requires GM approval)")
@app_commands.describe(field="Which stat to change", value="New value for the stat")
@app_commands.choices(field=[
    app_commands.Choice(name="Strength", value="strength"),
    app_commands.Choice(name="Dexterity", value="dexterity"),
    app_commands.Choice(name="Constitution", value="constitution"),
    app_commands.Choice(name="Intelligence", value="intelligence"),
    app_commands.Choice(name="Wisdom", value="wisdom"),
    app_commands.Choice(name="Charisma", value="charisma"),
    app_commands.Choice(name="Gold", value="gold"),
    app_commands.Choice(name="XP", value="xp"),
    app_commands.Choice(name="HP Max", value="hp_max"),
])
async def character_edit(interaction: discord.Interaction, field: app_commands.Choice[str], value: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    # Validate value is a positive integer
    try:
        new_value_int = int(value)
        if new_value_int < 0:
            raise ValueError
    except ValueError:
        await interaction.response.send_message(
            "Value must be a positive whole number (e.g. `15`, `250`, `10`).",
            ephemeral=True,
        )
        return

    char, chars = await resolve_character(interaction.user.id, interaction.guild_id)
    if not chars:
        await interaction.response.send_message("No character found. Use `/character create`.", ephemeral=True)
        return
    if not char:
        await interaction.response.send_message(
            "You have multiple characters — use `/character use` to set an active one first.",
            ephemeral=True,
        )
        return

    # Get old value
    old_value = str(getattr(char, field.value, "?"))

    # Create PendingApproval record
    async with get_db() as db:
        approval = PendingApproval(
            guild_id=interaction.guild_id,
            user_id=interaction.user.id,
            character_id=char.id,
            character_name=char.name,
            field_name=field.value,
            old_value=old_value,
            new_value=str(new_value_int),
            status="pending",
        )
        db.add(approval)
        await db.flush()
        approval_id = approval.id

    # Try to notify GM channel
    gm_channel = None
    try:
        async with get_db() as db:
            result = await db.execute(
                select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id)
            )
            config = result.scalar_one_or_none()
            if config and config.gm_channel_id:
                gm_channel = interaction.guild.get_channel(config.gm_channel_id)
    except Exception:
        pass

    if gm_channel:
        gm_embed = discord.Embed(
            title="📋 Stat Change Request",
            color=0xF59E0B,
        )
        gm_embed.add_field(name="Character", value=char.name, inline=True)
        gm_embed.add_field(name="Player", value=interaction.user.mention, inline=True)
        gm_embed.add_field(name="Field", value=field.name, inline=True)
        gm_embed.add_field(name="Change", value=f"`{old_value}` → `{new_value_int}`", inline=True)
        gm_embed.add_field(name="Request ID", value=f"`#{approval_id}`", inline=True)
        gm_embed.set_footer(text=f"Use /gm approve {approval_id} or /gm deny {approval_id}")
        try:
            await gm_channel.send(embed=gm_embed)
        except Exception:
            pass

    await interaction.response.send_message(
        f"Your request to change **{field.name}** from `{old_value}` to `{new_value_int}` has been submitted. "
        "A GM will review it.",
        ephemeral=True,
    )


# ── Cog ───────────────────────────────────────────────────────────────────────

class CharacterCog(commands.Cog, name="Character"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(character_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("character")


async def setup(bot):
    await bot.add_cog(CharacterCog(bot))
