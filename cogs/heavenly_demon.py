import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from database.session import get_db
from database.models import Character
import random
import math

OWNER_ID = 849025341783408701

# ── Level tables ─────────────────────────────────────────────────────────────

_TAO_MAX_TABLE = {
    1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 7, 7: 8, 8: 9, 9: 10,
    10: 12, 11: 14, 12: 16, 13: 18, 14: 20, 15: 25,
    16: 30, 17: 35, 18: 40, 19: 45, 20: 50,
}
_SWORD_MAX_TABLE = {
    1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 4, 8: 4, 9: 5,
    10: 5, 11: 6, 12: 6, 13: 7, 14: 7, 15: 8,
    16: 8, 17: 10, 18: 12, 19: 15, 20: 20,
}
_PROF_BONUS = {1:2,2:2,3:2,4:2,5:3,6:3,7:3,8:3,9:4,10:4,11:4,12:4,13:5,14:5,15:5,16:5,17:6,18:6,19:6,20:6}

def _mod(score: int) -> int:
    return math.floor((score - 10) / 2)

def _sword_die(level: int) -> tuple[int, int]:
    if level <= 4:   return (1, 8)
    if level <= 10:  return (1, 10)
    if level <= 16:  return (1, 12)
    return (2, 6)

def _roll_die(sides: int) -> int:
    return random.randint(1, sides)

def _roll(count: int, sides: int) -> int:
    return sum(random.randint(1, sides) for _ in range(count))

def _roll_attack(char: Character) -> tuple[int, int]:
    pb = _PROF_BONUS.get(char.level, 2)
    dex = _mod(char.dexterity)
    d20 = _roll_die(20)
    return d20, d20 + pb + dex

def _is_crit(char: Character, roll: int) -> bool:
    if char.level >= 20:
        return roll >= 18
    return roll == 20

def _sword_dmg(char: Character) -> int:
    cnt, sides = _sword_die(char.level)
    return _roll(cnt, sides) + _mod(char.dexterity)

def _tao_max(char: Character) -> int:
    base = _TAO_MAX_TABLE.get(char.level, 2)
    wis = _mod(char.wisdom)
    intel = _mod(char.intelligence)
    return max(base, char.level + wis + intel)

# ── 24 Forms data ────────────────────────────────────────────────────────────

FORMS = {
    # Basic — level 1
    "Demonic Strike":    {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "After hitting, make 1 additional attack vs same target. +1d6 damage.",
        "attacks": 2, "bonus_dice": (1,6)},
    "Bloody Sequence":   {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Make 2 additional attacks after your original attack. +1d6 damage each.",
        "attacks": 3, "bonus_dice": (1,6)},
    "Phantom Cut":       {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "Attack ignores half target's AC (rounded down). +1d6 damage.",
        "attacks": 1, "bonus_dice": (1,6), "ignore_half_ac": True},
    "Shadow Step":       {"tier": "Basic", "tao": 1, "unlock": 1,
        "desc": "Teleport up to 15 ft before attacking.",
        "attacks": 1, "teleport": 15},
    "Demonic Fang":      {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Single powerful strike. +1d8 damage.",
        "attacks": 1, "bonus_dice": (1,8)},
    "Black Moon Strike": {"tier": "Basic", "tao": 2, "unlock": 1,
        "desc": "Attack all enemies within 15 ft. +1d8 damage each.",
        "attacks": 1, "bonus_dice": (1,8), "aoe": True},

    # Intermediate — level 5
    "Cross Slash":       {"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Make 2 attacks. In Dual Wield Stance: make 4 instead. +1d8 each.",
        "attacks": 2, "dual_attacks": 4, "bonus_dice": (1,8)},
    "Demon Beast Strike":{"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Single devastating strike. +2d8 damage.",
        "attacks": 1, "bonus_dice": (2,8)},
    "Demonic Dance":     {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Make 4 consecutive attacks. +1d8 each.",
        "attacks": 4, "bonus_dice": (1,8)},
    "Demonic Pressure":  {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Enemies within 30 ft make WIS save (DC=8+prof+WIS mod) or become frightened.",
        "attacks": 0, "save_effect": "frightened"},
    "Demonic Tempest":   {"tier": "Intermediate", "tao": 3, "unlock": 5,
        "desc": "Make 3 attacks instantly. In Dual Wield Stance: 6 attacks. +1d8 each.",
        "attacks": 3, "dual_attacks": 6, "bonus_dice": (1,8)},
    "Lightning Cut":     {"tier": "Intermediate", "tao": 2, "unlock": 5,
        "desc": "Make 2 attacks. If both hit same target, make 1 additional attack. +1d8 each.",
        "attacks": 2, "lightning_cut": True, "bonus_dice": (1,8)},

    # Advanced — level 9
    "Abyss Cut":         {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Attack ignores resistance. +2d10 damage.",
        "attacks": 1, "bonus_dice": (2,10), "ignore_resistance": True},
    "Demonic Domain":    {"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "Your next attack deals +2d6 damage. All allies gain 1 extra attack this turn (+1d6).",
        "attacks": 1, "bonus_dice": (2,6), "ally_bonus": True},
    "Demonic Fury":      {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Gain 2 additional attacks this turn.",
        "attacks": 3, "bonus_dice": None},
    "Demonic Massacre":  {"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "Make 5 attacks instantly. +2d6 each.",
        "attacks": 5, "bonus_dice": (2,6)},
    "Heavenly Demon Dance":{"tier": "Advanced", "tao": 4, "unlock": 9,
        "desc": "All attacks this turn generate 1 additional attack.",
        "attacks": 2, "bonus_dice": None, "chain": True},
    "Invisible Cut":     {"tier": "Advanced", "tao": 3, "unlock": 9,
        "desc": "Attack cannot be reacted to (no opportunity attacks, no Shield spell). +2d6 damage.",
        "attacks": 1, "bonus_dice": (2,6), "no_reaction": True},

    # Supreme — level 15
    "Absolute Demonic Destruction": {"tier": "Supreme", "tao": 8, "unlock": 15,
        "desc": "Make 12 attacks instantly. +1d10 per hit.",
        "attacks": 12, "bonus_dice": (1,10)},
    "Bloody Tempest":    {"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Make 8 consecutive attacks.",
        "attacks": 8, "bonus_dice": None},
    "Heavenly Demon Slash":{"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Single strike. +1d6 per Tao spent (including base 5). Spend extra Tao for more damage.",
        "attacks": 1, "per_tao": True},
    "Heavenly Demon Domain":{"tier": "Supreme", "tao": 6, "unlock": 15,
        "desc": "Attack ALL enemies within 45 ft. +3d10 damage each.",
        "attacks": 1, "bonus_dice": (3,10), "aoe": True},
    "Hundred Blade Massacre":{"tier": "Supreme", "tao": 6, "unlock": 15,
        "desc": "Make 10 attacks instantly.",
        "attacks": 10, "bonus_dice": None},
    "Void Slash":        {"tier": "Supreme", "tao": 5, "unlock": 15,
        "desc": "Ignores ALL defenses (treat AC as 10, ignore resistance and immunity). +1d10 damage.",
        "attacks": 1, "bonus_dice": (1,10), "void": True},
}

TIER_EMOJI = {"Basic": "⚪", "Intermediate": "🟡", "Advanced": "🔴", "Supreme": "🌌"}
PATH_NAMES = ["Heavenly Demon", "Blood Demon", "Elemental Demon"]
ELEMENTS = ["Fire", "Lightning", "Wind", "Cold"]
ELEMENT_EMOJI = {"Fire": "🔥", "Lightning": "⚡", "Wind": "🌪️", "Cold": "❄️"}

# ── DB helpers ────────────────────────────────────────────────────────────────

async def _get_hd_char(interaction: discord.Interaction) -> Character | None:
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.char_class == "Heavenly Demon Heir",
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
        if char is None:
            result2 = await db.execute(
                select(Character).where(
                    Character.user_id == interaction.user.id,
                    Character.guild_id == interaction.guild_id,
                    Character.char_class == "Heavenly Demon Heir",
                    Character.is_dead == False,
                ).limit(1)
            )
            char = result2.scalar_one_or_none()
    return char

async def _update_resources(char_id: int, updates: dict):
    async with get_db() as db:
        result = await db.execute(select(Character).where(Character.id == char_id))
        char = result.scalar_one_or_none()
        if char is None:
            return
        res = dict(char.class_resources or {})
        res.update(updates)
        char.class_resources = res
        flag_modified(char, "class_resources")
        await db.commit()

def _res(char: Character) -> dict:
    return dict(char.class_resources or {})

def _tao(char: Character) -> int:
    return _res(char).get("tao_current", 0)

def _hd_embed(title: str, desc: str = "") -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=0x8B0000)
    return e

# ── Cog ──────────────────────────────────────────────────────────────────────

class HeavenlyDemonCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /tao group ───────────────────────────────────────────────────────────

    tao_group = app_commands.Group(name="tao", description="Tao point management for the Heavenly Demon Heir")

    @tao_group.command(name="status", description="View your current Tao and class status")
    async def tao_status(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir character found.", ephemeral=True)
            return
        res = _res(char)
        cur = res.get("tao_current", 0)
        tao_mx = _tao_max(char)
        path = res.get("hd_path") or "None chosen"
        element = res.get("elemental_type") or "—"
        swords = res.get("controlled_swords", 0)
        dual = "Active 🗡️🗡️" if res.get("hd_dual_wield") else "Off"
        exhausted = res.get("tao_exhausted", False)
        pb = _PROF_BONUS.get(char.level, 2)
        dc = 8 + pb + _mod(char.wisdom)
        e = _hd_embed(f"🌀 {char.name} — Heavenly Demon Heir", f"*Level {char.level} | {char.race}*")
        bar_filled = round((cur / max(tao_mx, 1)) * 10)
        bar = "█" * bar_filled + "░" * (10 - bar_filled)
        status = "💀 TAO EXHAUSTED" if exhausted else "✅ Active"
        e.add_field(name="⚡ Tao", value=f"`{bar}` **{cur}/{tao_mx}**\n{status}", inline=False)
        e.add_field(name="📚 Path", value=path, inline=True)
        e.add_field(name="🌪️ Element", value=element, inline=True)
        e.add_field(name="🗡️ Controlled Swords", value=f"{swords} / {_SWORD_MAX_TABLE.get(char.level, 1)}", inline=True)
        e.add_field(name="⚔️ Dual Wield Stance", value=dual, inline=True)
        e.add_field(name="📊 Stats", value=f"DEX: {char.dexterity} ({_mod(char.dexterity):+d}) | WIS: {char.wisdom} ({_mod(char.wisdom):+d})\nProf: +{pb} | Save DC: {dc}", inline=False)
        features = []
        if char.level >= 2: features.append("Sword Flight")
        if char.level >= 6: features.append("Tao Empowered Strikes")
        if char.level >= 10: features.append("Perfect Tao Circulation")
        if char.level >= 15: features.append("Heavenly Demon Body")
        if char.level >= 20: features.append("Heavenly Demon Ascension")
        if features:
            e.add_field(name="✨ Active Features", value=" · ".join(features), inline=False)
        loot_flags = []
        if res.get("absolute_state_used"): loot_flags.append("Absolute State used")
        if res.get("catastrophe_used"): loot_flags.append("Catastrophe used")
        if res.get("sword_rain_used"): loot_flags.append("Sword Rain used")
        if loot_flags:
            e.add_field(name="🔒 Used (1/long rest)", value=", ".join(loot_flags), inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @tao_group.command(name="restore", description="Restore all Tao (simulates long rest)")
    async def tao_restore(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        tao_mx = _tao_max(char)
        await _update_resources(char.id, {
            "tao_current": tao_mx, "tao_max": tao_mx, "tao_exhausted": False,
            "absolute_state_used": False, "catastrophe_used": False, "sword_rain_used": False,
        })
        e = _hd_embed("🌀 Tao Restored", f"**{char.name}**'s Tao has been fully restored.\n**{tao_mx}/{tao_mx}** Tao · All cooldowns reset.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @tao_group.command(name="tick", description="Apply Perfect Tao Circulation regen (level 10+)")
    async def tao_tick(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 10:
            await interaction.response.send_message("Perfect Tao Circulation unlocks at level 10.", ephemeral=True)
            return
        res = _res(char)
        cur = res.get("tao_current", 0)
        tao_mx = _tao_max(char)
        regen = max(1, _mod(char.wisdom))
        new_tao = min(tao_mx, cur + regen)
        await _update_resources(char.id, {"tao_current": new_tao, "tao_exhausted": False})
        e = _hd_embed("🌀 Perfect Tao Circulation", f"Tao regened from **{cur}** → **{new_tao}/{tao_mx}**\n*(+{regen} from WIS modifier)*")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── /form group ──────────────────────────────────────────────────────────

    form_group = app_commands.Group(name="form", description="Demonic Sword Forms")

    @form_group.command(name="list", description="View all 24 Demonic Sword Forms")
    async def form_list(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        level = char.level if char else 1
        embeds = []
        for tier in ["Basic", "Intermediate", "Advanced", "Supreme"]:
            tier_forms = {n: f for n, f in FORMS.items() if f["tier"] == tier}
            lines = []
            for name, f in tier_forms.items():
                unlocked = level >= f["unlock"]
                lock = "✅" if unlocked else f"🔒 Lv{f['unlock']}"
                lines.append(f"{TIER_EMOJI[tier]} **{name}** {lock} — {f['tao']} Tao\n> {f['desc']}")
            e = _hd_embed(f"{TIER_EMOJI[tier]} {tier} Forms", "\n\n".join(lines))
            e.set_footer(text=f"Your level: {level}")
            embeds.append(e)
        await interaction.response.send_message(embeds=embeds[:4], ephemeral=True)

    @form_group.command(name="use", description="Use a Demonic Sword Form")
    @app_commands.describe(
        form_name="Name of the form to activate",
        extra_tao="Extra Tao to spend (only for Heavenly Demon Slash)",
    )
    async def form_use(self, interaction: discord.Interaction, form_name: str, extra_tao: int = 0):
        if interaction.user.id != OWNER_ID:
            return
        await interaction.response.defer(ephemeral=True)
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.followup.send("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        # Find form (case-insensitive)
        matched = next((n for n in FORMS if n.lower() == form_name.lower()), None)
        if not matched:
            close = [n for n in FORMS if form_name.lower() in n.lower()]
            if close:
                await interaction.followup.send(f"Form not found. Did you mean: {', '.join(close[:3])}?", ephemeral=True)
            else:
                await interaction.followup.send(f"Unknown form: `{form_name}`. Use `/form list` to see all forms.", ephemeral=True)
            return
        form = FORMS[matched]
        if char.level < form["unlock"]:
            await interaction.followup.send(f"**{matched}** unlocks at level {form['unlock']}. You are level {char.level}.", ephemeral=True)
            return
        res = _res(char)
        cur = res.get("tao_current", 0)
        tao_cost = form["tao"] + max(0, extra_tao)
        if cur < tao_cost:
            await interaction.followup.send(f"Not enough Tao. Need **{tao_cost}**, have **{cur}**.", ephemeral=True)
            return
        # Deduct Tao
        new_tao = cur - tao_cost
        exhausted = new_tao <= 0
        pb = _PROF_BONUS.get(char.level, 2)
        dex_mod = _mod(char.dexterity)
        dual = res.get("hd_dual_wield", False)
        # Resolve form
        attack_count = form.get("attacks", 1)
        if dual and form.get("dual_attacks"):
            attack_count = form["dual_attacks"]
        bonus_dice = form.get("bonus_dice")  # (count, sides) or None
        per_tao = form.get("per_tao", False)
        lines = []
        total_dmg = 0
        hits = 0
        for i in range(attack_count):
            if attack_count == 0:
                break
            d20 = _roll_die(20)
            atk = d20 + pb + dex_mod
            base_dmg = _sword_dmg(char)
            bonus_dmg = 0
            if bonus_dice:
                bonus_dmg = _roll(*bonus_dice)
            elif per_tao:
                bonus_dmg = _roll(tao_cost, 6)
            hit = d20 >= 2  # nearly always hits in simulation; DM adjudicates AC
            crit = _is_crit(char, d20)
            if crit:
                base_dmg *= 2
                bonus_dmg *= 2
            total = base_dmg + bonus_dmg
            total_dmg += total
            hits += 1 if hit else 0
            crit_tag = " 💥 CRIT!" if crit else ""
            lines.append(f"  Attack {i+1}: `d20={d20}` → **{atk}** | Dmg: **{total}**{crit_tag}")
        # Special effects
        special_lines = []
        if form.get("save_effect") == "frightened":
            dc = 8 + pb + _mod(char.wisdom)
            special_lines.append(f"🫥 **WIS Save DC {dc}** — fail = Frightened until start of their next turn")
        if form.get("teleport"):
            special_lines.append(f"💨 Teleport up to **{form['teleport']} ft** before attacking")
        if form.get("aoe"):
            special_lines.append("🌐 **Area Effect** — hits ALL enemies in range")
        if form.get("ignore_half_ac"):
            special_lines.append("🛡️ Ignores half of target's AC")
        if form.get("ignore_resistance"):
            special_lines.append("🔓 Ignores damage resistance")
        if form.get("void"):
            special_lines.append("⚫ **VOID** — Treat all AC as 10. Ignores resistance AND immunity.")
        if form.get("no_reaction"):
            special_lines.append("👁️ Cannot be reacted to (no opportunity attacks, no Shield)")
        if form.get("ally_bonus"):
            special_lines.append("⚔️ All allies gain **+1 attack** this turn (+1d6 damage)")
        if form.get("lightning_cut") and hits >= 2:
            bonus_d20 = _roll_die(20)
            bonus_atk = bonus_d20 + pb + dex_mod
            bonus_final = _sword_dmg(char) + (bonus_dice and _roll(*bonus_dice) or 0)
            special_lines.append(f"⚡ **Both hit** → Bonus attack: `d20={bonus_d20}` → **{bonus_atk}** | Dmg: **{bonus_final}**")
            total_dmg += bonus_final
        e = _hd_embed(
            f"{TIER_EMOJI[form['tier']]} {matched}",
            f"*{form['tier']} Form · Tao cost: {tao_cost}*\n{form['desc']}"
        )
        if lines:
            e.add_field(name="⚔️ Attacks", value="\n".join(lines), inline=False)
            e.add_field(name="💥 Total Damage", value=f"**{total_dmg}** slashing", inline=True)
        if special_lines:
            e.add_field(name="✨ Effects", value="\n".join(special_lines), inline=False)
        e.add_field(name="🌀 Tao", value=f"{cur} → **{new_tao}**{' 💀 Exhausted!' if exhausted else ''}", inline=True)
        await _update_resources(char.id, {"tao_current": new_tao, "tao_exhausted": exhausted})
        await interaction.followup.send(embed=e, ephemeral=True)

    @form_use.autocomplete("form_name")
    async def form_autocomplete(self, interaction: discord.Interaction, current: str):
        if interaction.user.id != OWNER_ID:
            return []
        char = await _get_hd_char(interaction)
        level = char.level if char else 1
        return [
            app_commands.Choice(name=f"{TIER_EMOJI[f['tier']]} {n} ({f['tao']} Tao)", value=n)
            for n, f in FORMS.items()
            if current.lower() in n.lower() and level >= f["unlock"]
        ][:25]

    # ── /hd group ────────────────────────────────────────────────────────────

    hd_group = app_commands.Group(name="hd", description="Heavenly Demon Heir abilities and management")

    @hd_group.command(name="path", description="Choose your Heavenly Demon Path (level 3+)")
    @app_commands.describe(path="Your cultivation path")
    @app_commands.choices(path=[
        app_commands.Choice(name="Path of the Heavenly Demon — Telekinetic sword master", value="Heavenly Demon"),
        app_commands.Choice(name="Path of the Blood Demon — Form combo specialist", value="Blood Demon"),
        app_commands.Choice(name="Path of the Elemental Demon — Elemental devastation", value="Elemental Demon"),
    ])
    async def hd_path(self, interaction: discord.Interaction, path: str):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 3:
            await interaction.response.send_message("Path selection unlocks at level 3.", ephemeral=True)
            return
        res = _res(char)
        old_path = res.get("hd_path")
        if old_path and old_path != path:
            await interaction.response.send_message(
                f"You already chose **{old_path}**. Contact a GM to change your path.", ephemeral=True)
            return
        await _update_resources(char.id, {"hd_path": path})
        path_descs = {
            "Heavenly Demon": "You command blades as extensions of your will. Telekinetic sword control, orbital defense, and Sword Storm become your signature.",
            "Blood Demon": "You chain Demonic Forms at terrifying speed. 10 forms in a single turn. Your enemies cannot react.",
            "Elemental Demon": "Your Tao takes elemental form — fire, lightning, wind, or cold. Every strike burns the world.",
        }
        e = _hd_embed(f"⚔️ Path Chosen: {path}", path_descs.get(path, ""))
        e.set_footer(text="Your path is now set. Path improvements unlock at levels 6, 11, and 17.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="elemental", description="Choose your element (Elemental Demon path, level 3+)")
    @app_commands.choices(element=[
        app_commands.Choice(name="🔥 Fire", value="Fire"),
        app_commands.Choice(name="⚡ Lightning", value="Lightning"),
        app_commands.Choice(name="🌪️ Wind", value="Wind"),
        app_commands.Choice(name="❄️ Cold", value="Cold"),
    ])
    async def hd_elemental(self, interaction: discord.Interaction, element: str):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        if res.get("hd_path") != "Elemental Demon":
            await interaction.response.send_message("Only the Path of the Elemental Demon can choose an element.", ephemeral=True)
            return
        await _update_resources(char.id, {"elemental_type": element})
        emoji = ELEMENT_EMOJI.get(element, "")
        e = _hd_embed(f"{emoji} Element: {element}", f"Your Tao now resonates with **{element}**. All weapon attacks deal bonus {element.lower()} damage.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="stance", description="Toggle Demonic Dual Wield Stance")
    async def hd_stance(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        current = res.get("hd_dual_wield", False)
        new_val = not current
        await _update_resources(char.id, {"hd_dual_wield": new_val})
        if new_val:
            e = _hd_embed("🗡️🗡️ Demonic Dual Wield Stance — ACTIVE",
                "You draw your second blade. Martial techniques that grant extra attacks are **doubled**. Certain forms become significantly stronger.")
        else:
            e = _hd_embed("🗡️ Demonic Dual Wield Stance — Deactivated",
                "You sheathe your off-hand blade and return to standard combat posture.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="flight", description="Activate Sword Flight (level 2+)")
    async def hd_flight(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 2:
            await interaction.response.send_message("Sword Flight unlocks at level 2.", ephemeral=True)
            return
        e = _hd_embed("⚔️✈️ Sword Flight Active",
            f"**{char.name}** channels Tao into their blade and rises into the air.\n\n"
            f"Flying speed: **{30} ft** (equal to walking speed).\n"
            "Concentration required — if incapacitated, the sword falls.")
        e.set_footer(text="At level 7, this evolves into Tao Sword Control — command multiple blades telekinetically.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="phantom", description="Use Phantom Step — spend 1 Tao to teleport 30 ft (level 4+)")
    async def hd_phantom(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 4:
            await interaction.response.send_message("Phantom Step unlocks at level 4.", ephemeral=True)
            return
        res = _res(char)
        cur = res.get("tao_current", 0)
        if cur < 1:
            await interaction.response.send_message("Not enough Tao (need 1).", ephemeral=True)
            return
        await _update_resources(char.id, {"tao_current": cur - 1})
        e = _hd_embed("💨 Phantom Step",
            f"**{char.name}** releases Tao beneath their feet and vanishes — reappearing up to **30 ft** away in an instant.\n\n"
            f"Tao: {cur} → **{cur-1}**")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── Sword commands ────────────────────────────────────────────────────────

    swords_group = app_commands.Group(name="swords", description="Telekinetic sword control", parent=hd_group)

    @swords_group.command(name="control", description="Spend Tao to control flying swords (2 Tao each, level 7+)")
    @app_commands.describe(count="Number of swords to control")
    async def swords_control(self, interaction: discord.Interaction, count: int):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 7:
            await interaction.response.send_message("Tao Sword Control unlocks at level 7.", ephemeral=True)
            return
        max_swords = _SWORD_MAX_TABLE.get(char.level, 1)
        if count < 1 or count > max_swords:
            await interaction.response.send_message(f"You can control 1 to {max_swords} swords at your level.", ephemeral=True)
            return
        tao_cost = count * 2
        res = _res(char)
        cur = res.get("tao_current", 0)
        if cur < tao_cost:
            await interaction.response.send_message(f"Not enough Tao. Need **{tao_cost}** ({count} swords × 2), have **{cur}**.", ephemeral=True)
            return
        new_tao = cur - tao_cost
        await _update_resources(char.id, {"tao_current": new_tao, "controlled_swords": count})
        e = _hd_embed(f"🗡️ {count} Sword{'s' if count > 1 else ''} Under Control",
            f"**{char.name}** extends Tao into {count} blade{'s' if count > 1 else ''}, suspending {'them' if count > 1 else 'it'} in orbital formation.\n\n"
            f"Each sword orbits within **90 ft**. Attack using `/hd swords attack <target>`.\n"
            f"Tao: {cur} → **{new_tao}** *(spent {tao_cost} Tao)*")
        if char.level >= 6 and res.get("hd_path") == "Heavenly Demon":
            e.add_field(name="🛡️ Sword Orbit", value=f"+2 AC while controlling {count} sword{'s' if count > 1 else ''}. Reaction available to strike attackers.", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @swords_group.command(name="attack", description="Command controlled swords to strike a target")
    @app_commands.describe(target="Name of the target")
    async def swords_attack(self, interaction: discord.Interaction, target: str):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        count = res.get("controlled_swords", 0)
        if count == 0:
            await interaction.response.send_message("You have no controlled swords. Use `/hd swords control <count>` first.", ephemeral=True)
            return
        pb = _PROF_BONUS.get(char.level, 2)
        dex_mod = _mod(char.dexterity)
        cnt, sides = _sword_die(char.level)
        lines = []
        total_dmg = 0
        for i in range(count):
            d20 = _roll_die(20)
            atk = d20 + pb + dex_mod
            dmg = _roll(cnt, sides) + dex_mod
            crit = _is_crit(char, d20)
            if crit:
                dmg += _roll(cnt, sides)
            total_dmg += dmg
            crit_tag = " 💥 CRIT!" if crit else ""
            lines.append(f"  Sword {i+1}: `d20={d20}` → **{atk}** | Dmg: **{dmg}**{crit_tag}")
        e = _hd_embed(f"🗡️ Sword Storm — {target}", f"**{count}** telekinetic blade{'s' if count > 1 else ''} strike at {target}!")
        e.add_field(name="⚔️ Attacks", value="\n".join(lines[:20]) + (f"\n  *(+{count-20} more)*" if count > 20 else ""), inline=False)
        e.add_field(name="💥 Total Damage", value=f"**{total_dmg}** slashing (magical)", inline=True)
        e.add_field(name="🗡️ Swords", value=f"{count} controlled", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @swords_group.command(name="dismiss", description="Dismiss all controlled swords")
    async def swords_dismiss(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        count = res.get("controlled_swords", 0)
        await _update_resources(char.id, {"controlled_swords": 0})
        e = _hd_embed("🗡️ Swords Dismissed", f"**{count}** sword{'s' if count != 1 else ''} fall inert to the ground as the Tao connection severs.")
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── Path-specific abilities ───────────────────────────────────────────────

    @hd_group.command(name="burst", description="Elemental Burst — spend 3 Tao for area elemental damage (level 6+)")
    async def hd_burst(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        if res.get("hd_path") != "Elemental Demon":
            await interaction.response.send_message("Elemental Burst requires the Path of the Elemental Demon.", ephemeral=True)
            return
        if char.level < 6:
            await interaction.response.send_message("Elemental Burst unlocks at level 6.", ephemeral=True)
            return
        cur = res.get("tao_current", 0)
        if cur < 3:
            await interaction.response.send_message("Not enough Tao (need 3).", ephemeral=True)
            return
        element = res.get("elemental_type") or "Force"
        emoji = ELEMENT_EMOJI.get(element, "💫")
        cnt, sides = _sword_die(char.level)
        dmg = _roll(cnt * 5, sides)
        half_dmg = dmg // 2
        pb = _PROF_BONUS.get(char.level, 2)
        dc = 8 + pb + _mod(char.wisdom)
        await _update_resources(char.id, {"tao_current": cur - 3})
        e = _hd_embed(f"{emoji} Elemental Burst — {element}",
            f"**{char.name}** releases explosive waves of {element.lower()} Tao!\n\n"
            f"All creatures within **20 ft**: DEX Save **DC {dc}**")
        e.add_field(name=f"❌ Failed Save", value=f"**{dmg}** {element.lower()} damage + pushed **15 ft**", inline=True)
        e.add_field(name="✅ Passed Save", value=f"**{half_dmg}** {element.lower()} damage", inline=True)
        e.add_field(name="🌀 Tao", value=f"{cur} → **{cur-3}**", inline=False)
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="manifest", description="Heavenly Demon Manifestation — 8 Tao, transform 1 min (Elemental Demon lvl 17+)")
    async def hd_manifest(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        if res.get("hd_path") != "Elemental Demon":
            await interaction.response.send_message("Heavenly Demon Manifestation requires the Path of the Elemental Demon.", ephemeral=True)
            return
        if char.level < 17:
            await interaction.response.send_message("Heavenly Demon Manifestation unlocks at level 17.", ephemeral=True)
            return
        cur = res.get("tao_current", 0)
        if cur < 8:
            await interaction.response.send_message(f"Not enough Tao (need 8, have {cur}).", ephemeral=True)
            return
        element = res.get("elemental_type") or "Force"
        emoji = ELEMENT_EMOJI.get(element, "💫")
        await _update_resources(char.id, {"tao_current": cur - 8})
        e = _hd_embed(f"{emoji} Heavenly Demon Manifestation ACTIVE",
            f"**{char.name}** channels the full power of the Heavenly Demon — {element.lower()} energy erupts from their body.")
        e.add_field(name="✨ For 1 Minute", value=
            "• **+3 AC**\n"
            "• Advantage on **all attack rolls**\n"
            "• **+1 extra action** per turn\n"
            "• **+3 martial arts dice** damage per attack\n"
            f"• **Flying speed** equal to movement speed", inline=False)
        e.add_field(name="⚠️ Cost", value="When the transformation ends: **1 level of Exhaustion**", inline=False)
        e.add_field(name="🌀 Tao", value=f"{cur} → **{cur-8}**", inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)

    # ── Level 20 abilities ────────────────────────────────────────────────────

    @hd_group.command(name="ascend", description="Enter Absolute Heavenly Demon State (level 20, 1/long rest)")
    async def hd_ascend(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 20:
            await interaction.response.send_message("Heavenly Demon Ascension requires level 20.", ephemeral=True)
            return
        res = _res(char)
        if res.get("absolute_state_used"):
            await interaction.response.send_message("Absolute Heavenly Demon State has already been used this rest.", ephemeral=True)
            return
        await _update_resources(char.id, {"absolute_state_used": True})
        e = _hd_embed("🌌 ABSOLUTE HEAVENLY DEMON STATE",
            f"**{char.name}** unleashes the absolute peak of their Tao cultivation. The air itself trembles.")
        e.add_field(name="⚡ For 1 Minute", value=
            "• All weapon attacks deal **+2d10** damage\n"
            "• On hit: chain up to **5 additional attacks per turn**\n"
            "• All Demonic Forms cost **-2 Tao** (min 1)\n"
            "• Control **twice** the normal sword count", inline=False)
        e.add_field(name="⚠️ When It Ends", value="Tao drops to **0**. DC 15 CON save or fall unconscious for 1 minute.", inline=False)
        e.set_footer(text="1/long rest · Use /tao restore to reset")
        await interaction.response.send_message(embed=e, ephemeral=True)

    @hd_group.command(name="catastrophe", description="Forbidden Form: Heavenly Demon Catastrophe (level 20, 20 Tao, 1/rest)")
    async def hd_catastrophe(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        await interaction.response.defer(ephemeral=True)
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.followup.send("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 20:
            await interaction.followup.send("Heavenly Demon Catastrophe requires level 20.", ephemeral=True)
            return
        res = _res(char)
        if res.get("catastrophe_used"):
            await interaction.followup.send("Heavenly Demon Catastrophe has already been used this rest.", ephemeral=True)
            return
        cur = res.get("tao_current", 0)
        if cur < 20:
            await interaction.followup.send(f"Not enough Tao. Need **20**, have **{cur}**.", ephemeral=True)
            return
        count = res.get("controlled_swords", 0)
        pb = _PROF_BONUS.get(char.level, 2)
        dex_mod = _mod(char.dexterity)
        # Sword attacks
        sword_lines = []
        sword_total = 0
        for i in range(max(1, count)):
            d20 = _roll_die(20)
            atk = d20 + pb + dex_mod
            dmg = _roll(3, 10) + dex_mod
            crit = _is_crit(char, d20)
            if crit:
                dmg += _roll(3, 10)
            sword_total += dmg
            crit_t = " 💥" if crit else ""
            sword_lines.append(f"  Sword {i+1}: `{d20}` → **{atk}** | **{dmg}** slashing{crit_t}")
        # Area damage
        area_dmg = _roll(12, 10)
        area_half = area_dmg // 2
        con_dc = 15
        await _update_resources(char.id, {
            "tao_current": 0, "catastrophe_used": True, "tao_exhausted": True
        })
        e = _hd_embed("☠️ FORBIDDEN FORM — HEAVENLY DEMON CATASTROPHE",
            f"Every sword under {char.name}'s control rises and descends simultaneously in a cataclysm of steel.")
        if sword_lines:
            display = sword_lines[:15]
            if len(sword_lines) > 15:
                display.append(f"  *... and {len(sword_lines)-15} more*")
            e.add_field(name=f"⚔️ {count or 1} Sword Strike{'s' if (count or 1) != 1 else ''}", value="\n".join(display), inline=False)
            e.add_field(name="💥 Sword Total", value=f"**{sword_total}** slashing", inline=True)
        e.add_field(name="🌊 Area Blast (50 ft radius)", value=f"CON Save **DC {con_dc}**\n❌ Fail: **{area_dmg}** force + Prone\n✅ Pass: **{area_half}** force", inline=False)
        e.add_field(name="🌀 Tao", value=f"{cur} → **0** 💀 Tao Exhausted", inline=False)
        e.set_footer(text="After use: DC 15 CON save or unconscious 1 min · 1/long rest")
        await interaction.followup.send(embed=e, ephemeral=True)

    @hd_group.command(name="sword-rain", description="Sword Rain: Heavenly Demon Cataclysm (level 20, 30 Tao, 1/rest)")
    async def hd_sword_rain(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        await interaction.response.defer(ephemeral=True)
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.followup.send("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        if char.level < 20:
            await interaction.followup.send("Sword Rain requires level 20.", ephemeral=True)
            return
        res = _res(char)
        if res.get("sword_rain_used"):
            await interaction.followup.send("Sword Rain has already been used this rest.", ephemeral=True)
            return
        cur = res.get("tao_current", 0)
        if cur < 30:
            await interaction.followup.send(f"Not enough Tao. Need **30**, have **{cur}**.", ephemeral=True)
            return
        pb = _PROF_BONUS.get(char.level, 2)
        dex_mod = _mod(char.dexterity)
        dc = 8 + pb + dex_mod
        initial_slash = _roll(20, 10)
        initial_force = _roll(10, 10)
        field_dmg = _roll(6, 10)
        await _update_resources(char.id, {
            "tao_current": 0, "sword_rain_used": True, "tao_exhausted": True
        })
        e = _hd_embed("🌧️ SWORD RAIN: HEAVENLY DEMON CATACLYSM",
            f"**{char.name}** gazes upon the battlefield and the sky darkens.\nA rain of demonic swords descends upon a **120-ft radius × 150-ft cylinder**.")
        e.add_field(name="⚔️ Initial Strike", value=
            f"DEX Save **DC {dc}**\n"
            f"❌ Fail: **{initial_slash}** slashing + **{initial_force}** force + Prone\n"
            f"✅ Pass: **{(initial_slash + initial_force) // 2}** total (half)", inline=False)
        e.add_field(name="🗡️ Field of Blades (until end of your next turn)",
            value=f"Difficult terrain. Any creature entering or starting turn there: **{field_dmg}** slashing", inline=False)
        e.add_field(name="🌀 Tao", value=f"{cur} → **0** 💀 Tao Exhausted", inline=False)
        e.set_footer(text="1/long rest · When the Heavenly Demon gazes upon the battlefield, even the sky trembles.")
        await interaction.followup.send(embed=e, ephemeral=True)

    @hd_group.command(name="sheet", description="View your full Heavenly Demon Heir class sheet")
    async def hd_sheet(self, interaction: discord.Interaction):
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        if not char:
            await interaction.response.send_message("No active Heavenly Demon Heir found.", ephemeral=True)
            return
        res = _res(char)
        pb = _PROF_BONUS.get(char.level, 2)
        dex_mod = _mod(char.dexterity)
        wis_mod = _mod(char.wisdom)
        tao_mx = _tao_max(char)
        cur = res.get("tao_current", 0)
        dc = 8 + pb + wis_mod
        cnt, sides = _sword_die(char.level)
        dmg_die = f"{cnt}d{sides}"
        e = _hd_embed(f"📜 {char.name} — Heavenly Demon Heir",
            f"Level {char.level} {char.race} | {char.hp_current}/{char.hp_max} HP | AC {char.armor_class}")
        e.add_field(name="🌀 Tao", value=f"{cur}/{tao_mx}", inline=True)
        e.add_field(name="⚔️ Path", value=res.get("hd_path") or "None", inline=True)
        e.add_field(name="🗡️ Swords", value=f"{res.get('controlled_swords',0)} active", inline=True)
        e.add_field(name="📊 Combat Stats", value=
            f"Attack: d20 +{pb + dex_mod} | Sword Die: {dmg_die} +{dex_mod}\n"
            f"Save DC: {dc} | Crit: {'18-20' if char.level >= 20 else '20'}", inline=False)
        # Unlocked forms
        unlocked = [n for n, f in FORMS.items() if char.level >= f["unlock"]]
        e.add_field(name=f"✅ Unlocked Forms ({len(unlocked)}/24)",
            value=", ".join(unlocked[:12]) + (f" *(+{len(unlocked)-12} more)*" if len(unlocked) > 12 else ""),
            inline=False)
        # Key features
        features = ["Nano System (advantage on initiative, reroll 1 atk/turn)"]
        if char.level >= 2: features.append("Sword Flight")
        if char.level >= 4: features.append("Phantom Step (1 Tao, 30 ft teleport)")
        if char.level >= 5: features.append("Extra Attack")
        if char.level >= 6: features.append("Tao Empowered Strikes (magical attacks)")
        if char.level >= 7: features.append("Tao Sword Control")
        if char.level >= 10: features.append("Perfect Tao Circulation (regen WIS mod/turn)")
        if char.level >= 15: features.append("Heavenly Demon Body")
        if char.level >= 20: features.append("Heavenly Demon Ascension (crit 18-20, free bonus attack)")
        e.add_field(name="✨ Class Features", value="\n".join(f"• {f}" for f in features), inline=False)
        if res.get("elemental_type"):
            emoji = ELEMENT_EMOJI.get(res["elemental_type"], "")
            e.add_field(name="🌪️ Element", value=f"{emoji} {res['elemental_type']}", inline=True)
        stance = "🗡️🗡️ Active" if res.get("hd_dual_wield") else "Off"
        e.add_field(name="⚔️ Dual Wield Stance", value=stance, inline=True)
        await interaction.response.send_message(embed=e, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(HeavenlyDemonCog(bot))
