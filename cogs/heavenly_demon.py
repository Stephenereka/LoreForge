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

# ── Path descriptions with level upgrades ──────────────────────────────────────

PATH_FULL = {
    "Heavenly Demon": {
        "flavor": "You command blades as extensions of your will. Telekinetic sword control, orbital defense, and Sword Storm become your signature. The sword does not merely obey — it anticipates.",
        "level_6": "**Sword Orbit (Passive):** While controlling 1+ flying swords, gain **+2 AC** and a reaction to strike attackers who hit you.",
        "level_11": "**Sword Storm (Action, 4 Tao):** All controlled swords strike every enemy in a 30-ft radius. Each sword deals full damage and your AC bonus doubles to +4.",
        "level_17": "**Hundred Blade Domain (Active, 8 Tao, 1/rest):** Fill a 60-ft radius with orbiting blades. You automatically hit every enemy in the domain for **3d10** slashing at the start of your turn. Domain lasts 1 minute.",
    },
    "Blood Demon": {
        "flavor": "You chain Demonic Forms at terrifying speed — turning combat into a seamless massacre. Each strike births the next. Your enemies cannot find a gap between your attacks.",
        "level_6": "**Form Cascade (Passive):** When you use a Demonic Form that makes 3+ attacks, you may chain it into another form by paying its Tao cost. Chain up to **2 forms** per turn.",
        "level_11": "**Form Torrent (Passive):** Increase chain limit to **5 forms** per turn. Each form in a chain deals +1d6 bonus damage.",
        "level_17": "**Blood Moon Massacre (Active, 10 Tao, 1/rest):** Chain up to **10 forms** in a single turn. Every 5th attack in the chain is an automatic critical hit.",
    },
    "Elemental Demon": {
        "flavor": "Your Tao takes elemental form — fire, lightning, wind, or cold. Every strike ignites the air, freezes the ground, or tears the sky. The elements obey the Heavenly Demon.",
        "level_6": "**Elemental Burst (Active, 3 Tao):** Release a 20-ft radius explosion of your element. Creatures take full damage (DEX save halves) and are pushed 15 ft + knocked prone on failure.",
        "level_11": "**Elemental Aura (Passive):** While Tao ≥ 4, elemental damage radiates 15 ft around you. Creatures entering or starting turn there take **2d6** elemental damage. Your weapon attacks deal +1d8 elemental damage.",
        "level_17": "**Heavenly Demon Manifestation (Active, 8 Tao, 1/rest, 1 min):** Your body becomes elemental energy. +3 AC, advantage on all attacks, +1 extra action per turn, +3 martial arts dice per hit. When it ends: 1 level of exhaustion.",
    },
}

ELEMENT_DETAILS = {
    "Fire": {
        "desc": "Burning damage over time. Targets hit take 1d6 fire at start of your next turn (stacks up to 3 times).",
        "burst_extra": "Creatures that fail the save are also **Burning** (1d6 at start of their turn, save ends).",
    },
    "Lightning": {
        "desc": "Stun chance on hit. Targets hit must make CON save (DC = your save DC) or be Stunned until end of your next turn.",
        "burst_extra": "Creatures that fail the save are **Stunned** until the end of your next turn.",
    },
    "Wind": {
        "desc": "Extra attack per turn. After using a Demonic Form, make 1 additional basic attack against a different target. +10 ft movement.",
        "burst_extra": "Creatures that fail the save are knocked **Prone** and pushed an additional **30 ft**.",
    },
    "Cold": {
        "desc": "Slow on hit. Target's speed is halved until end of your next turn (save ends). Stacking slows can freeze.",
        "burst_extra": "Creatures that fail the save have their **speed reduced to 0** and cannot take reactions until the end of your next turn.",
    },
}

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

    # ── Comprehensive Codex Viewer ──────────────────────────────────────────

    @hd_group.command(name="codex", description="📖 View the complete Heavenly Demon Heir class compendium")
    async def hd_codex(self, interaction: discord.Interaction):
        """Comprehensive 10-page class viewer showing every system, form, path, and feature."""
        if interaction.user.id != OWNER_ID:
            return
        char = await _get_hd_char(interaction)
        level = char.level if char else 1
        dex_mod = _mod(char.dexterity) if char else 0
        wis_mod = _mod(char.wisdom) if char else 0
        pb = _PROF_BONUS.get(level, 2)
        dc = 8 + pb + wis_mod
        cnt, sides = _sword_die(level)
        dmg_die = f"{cnt}d{sides}"
        tao_mx = _tao_max(char) if char else _TAO_MAX_TABLE.get(level, 2)
        max_swords = _SWORD_MAX_TABLE.get(level, 1)

        pages = []

        # ── Page 1: Class Overview ──────────────────────────────────────────────
        e = discord.Embed(
            title="📖 Heavenly Demon Heir — Class Codex",
            description=(
                "A martial cultivator who combines sword mastery, demonic martial arts, "
                "and an internal **Tao system** that enhances every facet of combat. Through "
                "cultivation of Tao, you unleash rapid sequences of attacks, manipulate blades "
                "through the air with your mind, and ascend to supernatural dominance.\n\n"
                "*\"The blade does not merely obey — it fears the Heavenly Demon.\"*"
            ),
            color=0x8B0000,
        )
        e.add_field(name="🎲 Hit Die", value="d8", inline=True)
        e.add_field(name="⭐ Primary Stat", value="Dexterity", inline=True)
        e.add_field(name="🛡️ Saving Throws", value="DEX & WIS", inline=True)
        e.add_field(name="🗡️ Weapon Die", value=f"{dmg_die} + DEX mod", inline=True)
        e.add_field(name="🌀 Tao Capacity", value=f"{tao_mx} at level {level}", inline=True)
        e.add_field(name="🗡️ Max Controlled Swords", value=f"{max_swords}", inline=True)
        e.add_field(name="📊 Stats at Your Level", value=f"DEX: {_mod(char.dexterity) if char else 0:+d} | WIS: {wis_mod:+d}\nProf: +{pb} | Save DC: {dc} | Crit: {'18-20' if level >= 20 else '20'}", inline=False)
        e.add_field(
            name="🧩 Three Paths (choose at level 3)",
            value=(
                "**Path of the Heavenly Demon** — Telekinetic sword master. Orbital defense, Sword Storm.\n"
                "**Path of the Blood Demon** — Form combo specialist. Chain up to 10 forms per turn.\n"
                "**Path of the Elemental Demon** — Elemental devastation. Fire, Lightning, Wind, or Cold."
            ),
            inline=False,
        )
        e.set_footer(text="Page 1/10 — Class Overview · Use /hd codex at any level to see your current progression")
        pages.append(e)

        # ── Page 2: Tao & Nano Systems ──────────────────────────────────────────
        e = discord.Embed(
            title="🌀 Tao System — The Fuel of the Heavenly Demon",
            description=(
                "Tao is your internal cultivation energy — the lifeblood of every Demonic Sword Form, "
                "every telekinetic blade, and every path-specific ability. Managing Tao is the core "
                "of the Heavenly Demon Heir gameplay."
            ),
            color=0x8B0000,
        )
        e.add_field(
            name="⚡ Tao Points",
            value=(
                f"**Maximum:** `{tao_mx}` at level {level}\n"
                f"**Formula:** `max(level_table, level + WIS_mod + INT_mod)`\n"
                "**Recovery:** All Tao restored on **long rest**\n"
                "**Exhaustion:** If Tao hits 0, you fall **unconscious** 💀\n\n"
                "Spend Tao to activate Demonic Sword Forms. Each form has a cost from 1 to 8+ Tao. "
                "Higher-tier forms cost more but deal exponentially more damage."
            ),
            inline=False,
        )
        e.add_field(
            name="🔋 Perfect Tao Circulation (Level 10+)",
            value=(
                "At the start of each of your turns, regenerate **WIS modifier** (minimum 1) Tao.\n"
                "This keeps you fighting turn after turn without running dry."
            ),
            inline=False,
        )
        e.add_field(
            name="🤖 Nano System (Passive — Always Active)",
            value=(
                "Your internal combat AI enhances your body:\n"
                "• **Advantage on initiative rolls** — you almost always strike first\n"
                "• **Reroll one attack roll per turn** — use after seeing the result\n"
                "• Upgrades at level 20: **crit range becomes 18-20**"
            ),
            inline=False,
        )
        e.set_footer(text="Page 2/10 — Tao & Nano Systems")
        pages.append(e)

        # ── Page 3: Subclass Paths ──────────────────────────────────────────────
        path_lines = []
        for path_name, path_data in PATH_FULL.items():
            p_desc = path_data["flavor"]
            l6 = path_data["level_6"]
            l11 = path_data["level_11"]
            l17 = path_data["level_17"]
            lock6 = "✅" if level >= 6 else "🔒 Lv6"
            lock11 = "✅" if level >= 11 else "🔒 Lv11"
            lock17 = "✅" if level >= 17 else "🔒 Lv17"
            path_lines.append(
                f"### ⚔️ {path_name}\n"
                f"{p_desc}\n\n"
                f"{lock6} **Level 6:** {l6}\n"
                f"{lock11} **Level 11:** {l11}\n"
                f"{lock17} **Level 17:** {l17}"
            )
        e = discord.Embed(
            title="⚔️ Subclass Paths — Choose at Level 3",
            description="\n\n".join(path_lines),
            color=0x8B0000,
        )
        # Add element details if Elemental Demon
        elem_lines = []
        for elem, data in ELEMENT_DETAILS.items():
            emoji = ELEMENT_EMOJI[elem]
            elem_lines.append(f"{emoji} **{elem}** — {data['desc']}")
        e.add_field(
            name="🌪️ Elemental Demon Elements",
            value="\n".join(elem_lines),
            inline=False,
        )
        e.set_footer(text="Page 3/10 — Subclass Paths · Path improvements at levels 6, 11, and 17")
        pages.append(e)

        # ── Page 4: Level Progression ───────────────────────────────────────────
        LEVEL_FEATURES = {
            1: "**Demonic Forms (Basic)** — Unlock 6 Basic forms. Nano System active. Tao capacity: 2.",
            2: "**Sword Flight** — Channel Tao into your blade to fly. Speed: 30 ft. Concentration.",
            3: "**Choose Your Path** — Heavenly Demon, Blood Demon, or Elemental Demon. Path sets your playstyle.",
            4: "**Phantom Step** — Spend 1 Tao to teleport 30 ft as a bonus action. **ASI +2** (STR/DEX/CON/INT/WIS/CHA).",
            5: "**Extra Attack** — Attack twice per turn. **Intermediate Forms** unlock. Tao capacity: 6.",
            6: "**Tao Empowered Strikes** — Weapon attacks count as magical. **Path upgrade: Level 6 ability**.",
            7: "**Tao Sword Control** — Spend 2 Tao per sword to control blades telekinetically. 90-ft range.",
            8: "**ASI +2** — Increase two ability scores or one by 2. Swords max +1.",
            9: "**Advanced Forms** — 6 Advanced Demonic Forms unlock. Forms cost 3-4 Tao.",
            10: "**Perfect Tao Circulation** — Regenerate WIS mod Tao at start of each turn. Tao capacity: 12.",
            11: "**Path Upgrade: Level 11** — Major path ability upgrade. Swords max: 6.",
            12: "**ASI +2** — Increase ability scores. Stronger sword damage.",
            13: "**Tao Capacity Boost** — Tao max increases significantly. Sword damage die upgrades.",
            14: "**ASI +2** — Increase ability scores.",
            15: "**Supreme Forms** — 6 Supreme Forms unlock (cost 5-8 Tao). **Heavenly Demon Body**: +2 AC, resistance to non-magical damage. Tao capacity: 25.",
            16: "**ASI +2** — Increase ability scores. Swords max: 8.",
            17: "**Path Upgrade: Level 17** — Capstone path ability. Swords max: 10. Massive power spike.",
            18: "**Heavenly Demon Body (Improved)** — Resistance to ALL damage. +3 AC.",
            19: "**ASI +2** — Increase ability scores. Swords max: 15. Crit range: 19-20.",
            20: "**Heavenly Demon Ascension** — Crit range: **18-20**. Free bonus attack per turn. **Absolute Heavenly Demon State**, **Heavenly Demon Catastrophe**, **Sword Rain: Heavenly Demon Cataclysm**. Tao capacity: 50.",
        }
        lines = []
        for lvl in range(1, 21):
            locked = "🔒" if level < lvl else "✅"
            feature = LEVEL_FEATURES.get(lvl, "")
            lines.append(f"{locked} **Lv{lvl}** — {feature}")
        e = discord.Embed(
            title="📈 Level Progression — Level 1 to 20",
            description="\n".join(lines),
            color=0x8B0000,
        )
        e.set_footer(text=f"Page 4/10 — Level Progression · Your level: {level}")
        pages.append(e)

        # ── Page 5-8: Forms by Tier ────────────────────────────────────────────
        for tier, tier_emoji, tier_label in [
            ("Basic", "⚪", "Basic Forms (Lv1)"),
            ("Intermediate", "🟡", "Intermediate Forms (Lv5)"),
            ("Advanced", "🔴", "Advanced Forms (Lv9)"),
            ("Supreme", "🌌", "Supreme Forms (Lv15)"),
        ]:
            tier_forms = {n: f for n, f in FORMS.items() if f["tier"] == tier}
            form_lines = []
            for name, f in tier_forms.items():
                unlocked = level >= f["unlock"]
                lock = "✅" if unlocked else f"🔒"
                tags = []
                if f.get("aoe"): tags.append("AOE")
                if f.get("void"): tags.append("VOID")
                if f.get("per_tao"): tags.append("variable")
                if f.get("dual_attacks"): tags.append("dual")
                if f.get("ally_bonus"): tags.append("support")
                if f.get("save_effect"): tags.append("debuff")
                if f.get("no_reaction"): tags.append("stealth")
                if f.get("ignore_resistance"): tags.append("pierce")
                if f.get("ignore_half_ac"): tags.append("pierce")
                if f.get("lightning_cut"): tags.append("chain")
                tag_str = f" *[{', '.join(tags)}]*" if tags else ""
                atk_str = f" {f['attacks']} atk{'s' if f['attacks'] != 1 else ''}"
                bonus = ""
                if f.get("bonus_dice"):
                    bonus = f" +{f['bonus_dice'][0]}d{f['bonus_dice'][1]} each"
                elif f.get("per_tao"):
                    bonus = " +1d6/Tao spent"
                form_lines.append(
                    f"{lock} **{name}**{tag_str} — {f['tao']} Tao{atk_str}{bonus}\n"
                    f"> {f['desc']}"
                )
            e = discord.Embed(
                title=f"{tier_emoji} {tier_label} ({len(tier_forms)} Forms)",
                description="\n\n".join(form_lines),
                color=0x8B0000,
            )
            e.set_footer(text=f"Page {5 + ['Basic','Intermediate','Advanced','Supreme'].index(tier)}/10 · Your level: {level}")
            pages.append(e)

        # ── Page 9: Sword Control System ────────────────────────────────────────
        e = discord.Embed(
            title="🗡️ Tao Sword Control — Telekinetic Blade Mastery",
            description=(
                "At **level 7**, your Sword Flight evolves into **Tao Sword Control** — the ability "
                "to suspend and command multiple blades telekinetically. Each sword orbits within a "
                "**90-ft radius** and attacks on your mental command."
            ),
            color=0x8B0000,
        )
        e.add_field(
            name="⚡ Mechanics",
            value=(
                f"• **Cost:** 2 Tao per controlled sword\n"
                f"• **Max Swords at your level:** {max_swords}\n"
                f"• **Range:** 90 ft for each sword\n"
                f"• **Sword Die:** {dmg_die} + DEX mod per hit\n"
                f"• **Attack:** d20 + {pb + dex_mod} + DEX\n"
                f"• **Crit range:** {'18-20' if level >= 20 else '20'}"
            ),
            inline=False,
        )
        e.add_field(
            name="🔹 Heavenly Demon Path Bonus",
            value=(
                "**Sword Orbit (Lv6, Passive):** +2 AC while controlling 1+ swords. "
                "Reaction available to strike attackers who hit you.\n"
                "**Sword Storm (Lv11, 4 Tao):** All swords hit every enemy in 30 ft. AC bonus doubles to +4.\n"
                "**Hundred Blade Domain (Lv17, 8 Tao):** 60-ft radius domain auto-hits for 3d10/round."
            ),
            inline=False,
        )
        e.add_field(
            name="🗡️ Sword Control Table",
            value=(
                "Lv1-2: 1 sword · Lv3-4: 2 · Lv5-6: 3 · Lv7-8: 4 · Lv9-10: 5\n"
                "Lv11-12: 6 · Lv13-14: 7 · Lv15-16: 8 · Lv17: 10 · Lv18: 12 · Lv19: 15 · Lv20: 20"
            ),
            inline=False,
        )
        e.set_footer(text="Page 9/10 — Sword Control System · Use /hd swords control <count> to activate")
        pages.append(e)

        # ── Page 10: Ultimate Techniques ────────────────────────────────────────
        e = discord.Embed(
            title="🌌 Ultimate Techniques — Level 20 Capstone",
            description=(
                "At level 20, the Heavenly Demon Heir unlocks three world-ending techniques. "
                "Each can be used **once per long rest** and represents the absolute peak of Tao cultivation."
            ),
            color=0x8B0000,
        )
        ascend_locked = "✅" if level >= 20 else "🔒 Lv20"
        cat_locked = "✅" if level >= 20 else "🔒 Lv20"
        rain_locked = "✅" if level >= 20 else "🔒 Lv20"
        e.add_field(
            name=f"{ascend_locked} 🌌 Absolute Heavenly Demon State",
            value=(
                "**Duration:** 1 minute\n"
                "**Cooldown:** 1/long rest\n\n"
                "• All weapon attacks deal **+2d10** damage\n"
                "• On hit: chain **5 additional attacks** per turn\n"
                "• All Demonic Forms cost **-2 Tao** (min 1)\n"
                "• Control **twice** the normal sword count\n"
                "**After:** Tao drops to 0. DC 15 CON save or unconscious 1 minute."
            ),
            inline=False,
        )
        e.add_field(
            name=f"{cat_locked} ☠️ Forbidden Form: Heavenly Demon Catastrophe",
            value=(
                "**Cost:** 20 Tao\n"
                "**Cooldown:** 1/long rest\n\n"
                "• Every controlled sword strikes the target simultaneously\n"
                "• Area blast: **50-ft radius**, CON Save DC 15\n"
                "• Fail: full sword damage + **12d10 force** + Prone\n"
                "• Pass: half area damage\n"
                "**After:** Tao drops to 0. DC 15 CON save or unconscious 1 minute."
            ),
            inline=False,
        )
        e.add_field(
            name=f"{rain_locked} 🌧️ Sword Rain: Heavenly Demon Cataclysm",
            value=(
                "**Cost:** 30 Tao\n"
                "**Cooldown:** 1/long rest\n\n"
                "• **120-ft radius × 150-ft cylinder** of descending demonic swords\n"
                "• Initial DEX Save: **20d10 slashing + 10d10 force** (half on pass)\n"
                "• Field of Blades: difficult terrain, **6d10 slashing** per turn\n"
                "**After:** Tao drops to 0. This is the ultimate Heavenly Demon technique."
            ),
            inline=False,
        )
        e.set_footer(text="Page 10/10 — Ultimate Techniques · Use /hd ascend, /hd catastrophe, /hd sword-rain")
        pages.append(e)

        # Send with paginated view
        view = CodexView(pages, 0, char)
        await interaction.response.send_message(embed=pages[0], view=view, ephemeral=True)


class CodexView(discord.ui.View):
    """Paginated view for the 10-page HD Codex compendium."""
    def __init__(self, pages: list[discord.Embed], page: int = 0, char: Character | None = None):
        super().__init__(timeout=600)
        self.pages = pages
        self.page = page
        self.char = char
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.page <= 0
        self.next_btn.disabled = self.page >= len(self.pages) - 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.pages[self.page], view=self)

    @discord.ui.button(label="🔢 Jump to Page", style=discord.ButtonStyle.secondary, row=1)
    async def jump_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != OWNER_ID:
            return
        # Send a followup with page buttons
        jump_view = CodexJumpView(self.pages, self, self.char)
        await interaction.response.send_message(
            "**Select a page:**",
            view=jump_view,
            ephemeral=True,
        )


class CodexJumpView(discord.ui.View):
    """Row of 10 buttons to jump to any codex page."""
    def __init__(self, pages: list[discord.Embed], parent_view: CodexView, char: Character | None):
        super().__init__(timeout=120)
        self.pages = pages
        self.parent_view = parent_view
        self.char = char
        for i in range(len(pages)):
            btn = discord.ui.Button(label=str(i + 1), style=discord.ButtonStyle.secondary, row=i // 5)
            btn.callback = self._make_callback(i)
            self.add_item(btn)

    def _make_callback(self, page_idx: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != OWNER_ID:
                return
            self.parent_view.page = page_idx
            self.parent_view._update_buttons()
            await interaction.response.edit_message(
                content=None,
                embed=self.pages[page_idx],
                view=self.parent_view,
            )
        return callback


async def setup(bot: commands.Bot):
    await bot.add_cog(HeavenlyDemonCog(bot))
