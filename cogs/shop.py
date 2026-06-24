import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character

# ── Item catalogue ────────────────────────────────────────────────────────────

ITEMS: dict[str, dict] = {
    # Weapons
    "dagger":       {"name": "Dagger",        "type": "weapon", "price": 2,    "damage": "1d4",  "desc": "Light blade — good for Rogues"},
    "handaxe":      {"name": "Handaxe",       "type": "weapon", "price": 5,    "damage": "1d6",  "desc": "Throwable axe"},
    "mace":         {"name": "Mace",          "type": "weapon", "price": 5,    "damage": "1d6",  "desc": "Blunt weapon, great for Clerics"},
    "quarterstaff": {"name": "Quarterstaff",  "type": "weapon", "price": 2,    "damage": "1d6",  "desc": "Wizard's walking stick / weapon"},
    "shortsword":   {"name": "Shortsword",    "type": "weapon", "price": 10,   "damage": "1d6",  "desc": "Fast and reliable"},
    "longsword":    {"name": "Longsword",     "type": "weapon", "price": 15,   "damage": "1d8",  "desc": "Versatile sword, Fighter staple"},
    "greataxe":     {"name": "Greataxe",      "type": "weapon", "price": 30,   "damage": "1d12", "desc": "Barbarian's best friend"},
    "greatsword":   {"name": "Greatsword",    "type": "weapon", "price": 50,   "damage": "2d6",  "desc": "Heaviest damage output"},
    # Armor
    "leather":      {"name": "Leather Armor", "type": "armor",  "price": 10,   "ac": 11, "ac_type": "dex", "desc": "Light armor — AC 11 + DEX mod"},
    "chain":        {"name": "Chain Shirt",   "type": "armor",  "price": 50,   "ac": 13, "ac_type": "dex2","desc": "Medium armor — AC 13 + DEX mod (max +2)"},
    # Potions
    "potion":       {"name": "Healing Potion","type": "potion", "price": 50,   "heal": "2d4+2",  "desc": "Restores 2d4+2 HP"},
    "potion_great": {"name": "Greater Healing Potion","type":"potion","price":100,"heal":"4d4+4","desc": "Restores 4d4+4 HP"},
}

WEAPONS  = {k: v for k, v in ITEMS.items() if v["type"] == "weapon"}
ARMORS   = {k: v for k, v in ITEMS.items() if v["type"] == "armor"}
POTIONS  = {k: v for k, v in ITEMS.items() if v["type"] == "potion"}

def sell_price(item_key: str) -> int:
    return max(1, ITEMS[item_key]["price"] // 2)

def calc_ac_with_armor(armor_key: str, dex_score: int) -> int:
    import math
    dex_mod = math.floor((dex_score - 10) / 2)
    item = ITEMS[armor_key]
    if item["ac_type"] == "dex":
        return item["ac"] + dex_mod
    elif item["ac_type"] == "dex2":
        return item["ac"] + min(dex_mod, 2)
    return item["ac"]

# ── Embeds ────────────────────────────────────────────────────────────────────

def browse_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🏪 LoreForge Shop",
        description="Use `/shop buy <item>` to purchase. Sell back for half price with `/shop sell <item>`.",
        color=0xF59E0B,
    )
    weapon_lines = [f"`{k}` — **{v['name']}** {v['damage']} dmg — {v['price']} gp — *{v['desc']}*" for k, v in WEAPONS.items()]
    armor_lines  = [f"`{k}` — **{v['name']}** — {v['price']} gp — *{v['desc']}*" for k, v in ARMORS.items()]
    potion_lines = [f"`{k}` — **{v['name']}** {v['heal']} HP — {v['price']} gp — *{v['desc']}*" for k, v in POTIONS.items()]

    embed.add_field(name="⚔️ Weapons", value="\n".join(weapon_lines), inline=False)
    embed.add_field(name="🛡️ Armor",   value="\n".join(armor_lines),  inline=False)
    embed.add_field(name="🧪 Potions", value="\n".join(potion_lines), inline=False)
    embed.set_footer(text="Prices in gold (gp)")
    return embed

# ── Item key autocomplete ─────────────────────────────────────────────────────

async def item_autocomplete(interaction: discord.Interaction, current: str):
    return [
        app_commands.Choice(name=f"{v['name']} ({v['price']} gp)", value=k)
        for k, v in ITEMS.items()
        if current.lower() in k or current.lower() in v["name"].lower()
    ][:25]

async def owned_item_autocomplete(interaction: discord.Interaction, current: str):
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
        if k in seen or k not in ITEMS:
            continue
        seen.add(k)
        if current.lower() in k or current.lower() in ITEMS[k]["name"].lower():
            choices.append(app_commands.Choice(name=ITEMS[k]["name"], value=k))
    return choices[:25]

# ── Command group ─────────────────────────────────────────────────────────────

shop_group = app_commands.Group(name="shop", description="Buy and sell items")


@shop_group.command(name="browse", description="See what's available in the shop")
async def shop_browse(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return
    await interaction.response.send_message(embed=browse_embed(), ephemeral=True)


@shop_group.command(name="buy", description="Buy an item from the shop")
@app_commands.describe(item="Item to buy")
@app_commands.autocomplete(item=item_autocomplete)
async def shop_buy(interaction: discord.Interaction, item: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if item not in ITEMS:
        await interaction.response.send_message("That item doesn't exist. Use `/shop browse` to see the catalogue.", ephemeral=True)
        return

    item_data = ITEMS[item]

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

        if char.gold < item_data["price"]:
            await interaction.response.send_message(
                f"Not enough gold. You have **{char.gold} gp**, need **{item_data['price']} gp**.",
                ephemeral=True,
            )
            return

        # Potions stack — weapons and armor are one-at-a-time checks
        inventory = list(char.inventory or [])
        if item_data["type"] != "potion":
            already_owned = any(i.get("key") == item for i in inventory)
            if already_owned:
                await interaction.response.send_message(
                    f"You already own a **{item_data['name']}**.", ephemeral=True
                )
                return

        char.gold -= item_data["price"]
        inventory.append({"key": item, "name": item_data["name"], "type": item_data["type"], "equipped": False})
        char.inventory = inventory

    embed = discord.Embed(
        title=f"✅ Purchased: {item_data['name']}",
        description=f"**{item_data['desc']}**\nYou paid **{item_data['price']} gp**. Remaining gold: **{char.gold} gp**.",
        color=0x22C55E,
    )
    if item_data["type"] != "potion":
        embed.set_footer(text="Use /inventory equip to equip it.")
    else:
        embed.set_footer(text="Use /inventory use to drink it.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@shop_group.command(name="sell", description="Sell an item for half its price")
@app_commands.describe(item="Item to sell")
@app_commands.autocomplete(item=owned_item_autocomplete)
async def shop_sell(interaction: discord.Interaction, item: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if item not in ITEMS:
        await interaction.response.send_message("Unknown item.", ephemeral=True)
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
            await interaction.response.send_message(f"You don't own a **{ITEMS[item]['name']}**.", ephemeral=True)
            return

        sold_item = inventory.pop(idx)

        # Unequip armor: reset AC to base (10 + DEX mod)
        if sold_item.get("equipped") and sold_item["type"] == "armor":
            import math
            char.armor_class = 10 + math.floor((char.dexterity - 10) / 2)

        price = sell_price(item)
        char.gold += price
        char.inventory = inventory

    await interaction.response.send_message(
        f"Sold **{ITEMS[item]['name']}** for **{price} gp**. You now have **{char.gold} gp**.",
        ephemeral=True,
    )


# ── Cog ───────────────────────────────────────────────────────────────────────

class ShopCog(commands.Cog, name="Shop"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(shop_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("shop")


async def setup(bot):
    await bot.add_cog(ShopCog(bot))
