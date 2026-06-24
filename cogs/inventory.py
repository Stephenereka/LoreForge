import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character
from cogs.shop import ITEMS, calc_ac_with_armor, owned_item_autocomplete
import random
import math

# ── Helpers ───────────────────────────────────────────────────────────────────

def roll_heal(formula: str) -> int:
    """Parse '2d4+2' or '4d4+4' and roll it."""
    bonus = 0
    if "+" in formula:
        parts = formula.split("+")
        formula = parts[0]
        bonus = int(parts[1])
    count, sides = map(int, formula.split("d"))
    return sum(random.randint(1, sides) for _ in range(count)) + bonus

def inventory_embed(char: Character) -> discord.Embed:
    inventory = char.inventory or []
    embed = discord.Embed(
        title=f"🎒 {char.name}'s Inventory",
        description=f"💰 **{char.gold} gp**",
        color=0x8B5CF6,
    )

    if not inventory:
        embed.add_field(name="Empty", value="Nothing here. Visit `/shop browse` to buy items.", inline=False)
        return embed

    weapons  = [i for i in inventory if i.get("type") == "weapon"]
    armors   = [i for i in inventory if i.get("type") == "armor"]
    potions  = [i for i in inventory if i.get("type") == "potion"]

    if weapons:
        lines = []
        for item in weapons:
            equipped = " *(equipped)*" if item.get("equipped") else ""
            key = item.get("key", "")
            dmg = ITEMS[key]["damage"] if key in ITEMS else "?"
            lines.append(f"⚔️ **{item['name']}** — {dmg}{equipped}")
        embed.add_field(name="Weapons", value="\n".join(lines), inline=False)

    if armors:
        lines = []
        for item in armors:
            equipped = " *(equipped)*" if item.get("equipped") else ""
            lines.append(f"🛡️ **{item['name']}**{equipped}")
        embed.add_field(name="Armor", value="\n".join(lines), inline=False)

    if potions:
        potion_counts: dict[str, int] = {}
        for item in potions:
            potion_counts[item["name"]] = potion_counts.get(item["name"], 0) + 1
        lines = [f"🧪 **{name}** ×{count}" for name, count in potion_counts.items()]
        embed.add_field(name="Potions", value="\n".join(lines), inline=False)

    embed.set_footer(text="Use /inventory equip <item> or /inventory use <item>")
    return embed

# ── Autocomplete for equippable items only ────────────────────────────────────

async def equippable_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
    if not char or not char.inventory:
        return []
    seen = set()
    choices = []
    for item in char.inventory:
        k = item.get("key", "")
        t = item.get("type", "")
        if k in seen or t == "potion" or k not in ITEMS:
            continue
        seen.add(k)
        if current.lower() in k or current.lower() in item["name"].lower():
            choices.append(app_commands.Choice(name=item["name"], value=k))
    return choices[:25]

async def usable_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = result.scalar_one_or_none()
    if not char or not char.inventory:
        return []
    seen = set()
    choices = []
    for item in char.inventory:
        k = item.get("key", "")
        if k in seen or item.get("type") != "potion":
            continue
        seen.add(k)
        if current.lower() in k or current.lower() in item["name"].lower():
            choices.append(app_commands.Choice(name=item["name"], value=k))
    return choices[:25]

# ── Command group ─────────────────────────────────────────────────────────────

inventory_group = app_commands.Group(name="inventory", description="Manage your items")


@inventory_group.command(name="view", description="View your inventory and gold")
async def inventory_view(interaction: discord.Interaction):
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
        await interaction.response.send_message("You don't have a character. Use `/character create`.", ephemeral=True)
        return

    await interaction.response.send_message(embed=inventory_embed(char), ephemeral=True)


@inventory_group.command(name="equip", description="Equip a weapon or piece of armor")
@app_commands.describe(item="Item to equip")
@app_commands.autocomplete(item=equippable_autocomplete)
async def inventory_equip(interaction: discord.Interaction, item: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if item not in ITEMS or ITEMS[item]["type"] == "potion":
        await interaction.response.send_message("That's not an equippable item.", ephemeral=True)
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
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
            return

        inventory = list(char.inventory or [])
        item_type = ITEMS[item]["type"]

        # Check ownership
        owned_idx = next((i for i, it in enumerate(inventory) if it.get("key") == item), None)
        if owned_idx is None:
            await interaction.response.send_message(
                f"You don't own a **{ITEMS[item]['name']}**. Buy it at `/shop browse`.", ephemeral=True
            )
            return

        # Unequip current item of same type
        for it in inventory:
            if it.get("type") == item_type and it.get("equipped"):
                it["equipped"] = False

        inventory[owned_idx]["equipped"] = True

        # Apply armor AC immediately
        if item_type == "armor":
            char.armor_class = calc_ac_with_armor(item, char.dexterity)

        char.inventory = inventory

    item_data = ITEMS[item]
    if item_type == "armor":
        desc = f"AC is now **{char.armor_class}**."
    else:
        desc = f"You'll deal **{item_data['damage']}** damage in combat."

    await interaction.response.send_message(
        f"✅ Equipped **{item_data['name']}**. {desc}",
        ephemeral=True,
    )


@inventory_group.command(name="use", description="Use a consumable item (potions)")
@app_commands.describe(item="Item to use")
@app_commands.autocomplete(item=usable_autocomplete)
async def inventory_use(interaction: discord.Interaction, item: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if item not in ITEMS or ITEMS[item]["type"] != "potion":
        await interaction.response.send_message("That item can't be used this way.", ephemeral=True)
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
            await interaction.response.send_message("You don't have a character.", ephemeral=True)
            return

        inventory = list(char.inventory or [])
        idx = next((i for i, it in enumerate(inventory) if it.get("key") == item), None)
        if idx is None:
            await interaction.response.send_message(
                f"You don't have a **{ITEMS[item]['name']}**.", ephemeral=True
            )
            return

        inventory.pop(idx)
        heal_formula = ITEMS[item]["heal"]
        healed = roll_heal(heal_formula)
        before = char.hp_current
        char.hp_current = min(char.hp_max, char.hp_current + healed)
        char.is_unconscious = False
        actual = char.hp_current - before
        char.inventory = inventory

    embed = discord.Embed(
        title=f"🧪 Used {ITEMS[item]['name']}",
        description=f"Restored **{actual} HP** ({heal_formula} roll).\n❤️ `{char.hp_current}/{char.hp_max} HP`",
        color=0x22C55E,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Cog ───────────────────────────────────────────────────────────────────────

class InventoryCog(commands.Cog, name="Inventory"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(inventory_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("inventory")


async def setup(bot):
    await bot.add_cog(InventoryCog(bot))
