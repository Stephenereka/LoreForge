import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, House

# ── Housing Tier Data ────────────────────────────────────────────────────────

HOUSING_TIERS = {
    1: {"name": "Cave Dwelling",       "cost": 500,   "xp_bonus": 0.05, "desc": "A humble cave dwelling — dry and defensible."},
    2: {"name": "Riverside Cottage",    "cost": 1500,  "xp_bonus": 0.10, "desc": "A peaceful cottage by a flowing stream."},
    3: {"name": "Courtyard Manor",     "cost": 5000,  "xp_bonus": 0.15, "desc": "A spacious manor with a training courtyard."},
    4: {"name": "Sect Elder Estate",   "cost": 15000, "xp_bonus": 0.25, "desc": "An estate worthy of a sect elder."},
    5: {"name": "Sovereign Palace",    "cost": 50000, "xp_bonus": 0.40, "desc": "A palace fit for a sovereign of the Murim."},
}


async def get_housing_xp_bonus(character_id: int, db) -> float:
    """
    Return the XP multiplier from housing (e.g. 1.05 for tier 1).
    Returns 1.0 (no bonus) if the character has no house.
    """
    result = await db.execute(
        select(House).where(House.character_id == character_id)
    )
    house = result.scalar_one_or_none()
    if not house:
        return 1.0
    tier_data = HOUSING_TIERS.get(house.tier)
    if not tier_data:
        return 1.0
    return 1.0 + tier_data["xp_bonus"]


# ── Housing command group ────────────────────────────────────────────────────

housing_group = app_commands.Group(name="house", description="Manage your Murim dwelling")


@housing_group.command(name="view", description="View your current dwelling")
async def house_view(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        house_result = await db.execute(
            select(House).where(House.character_id == char.id)
        )
        house = house_result.scalar_one_or_none()

    embed = discord.Embed(color=0x92400E)
    embed.set_footer(text=interaction.user.display_name)

    if not house:
        embed.title = f"🏚️ {char.name} — Homeless"
        embed.description = "You have no dwelling. Use `/house buy` to purchase a Cave Dwelling for **500** Spirit Stones."
    else:
        tier_data = HOUSING_TIERS.get(house.tier)
        if not tier_data:
            await interaction.response.send_message("Unknown house tier.", ephemeral=True)
            return

        embed.title = f"🏠 {char.name}'s Dwelling"
        embed.description = f"**{tier_data['name']}** (Tier {house.tier})\n*{tier_data['desc']}*"
        embed.add_field(name="💰 Cost Paid", value=f"{tier_data['cost']} Spirit Stones", inline=True)
        embed.add_field(name="✨ Perk", value=f"+{int(tier_data['xp_bonus'] * 100)}% XP from rest", inline=True)

        # Next tier info
        next_tier = house.tier + 1
        if next_tier in HOUSING_TIERS:
            next_data = HOUSING_TIERS[next_tier]
            upgrade_cost = next_data["cost"] - tier_data["cost"]
            if upgrade_cost < 0:
                upgrade_cost = next_data["cost"]
            embed.add_field(
                name="⬆️ Upgrade Available",
                value=f"**{next_data['name']}** — **{upgrade_cost}** Spirit Stones\n+{int(next_data['xp_bonus'] * 100)}% XP from rest",
                inline=False,
            )
        else:
            embed.add_field(name="⭐ Max Tier", value="Your dwelling is already at its peak.", inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


@housing_group.command(name="buy", description="Buy a Cave Dwelling (Tier 1) for 500 Spirit Stones")
async def house_buy(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        # Check if already own a house
        existing_result = await db.execute(
            select(House).where(House.character_id == char.id)
        )
        if existing_result.scalar_one_or_none():
            await interaction.response.send_message(
                "You already own a dwelling! Use `/house upgrade` to upgrade it or `/house view` to see it.",
                ephemeral=True,
            )
            return

        tier_data = HOUSING_TIERS[1]
        cost = tier_data["cost"]

        if (char.balance or 0) < cost:
            await interaction.response.send_message(
                f"You need **{cost}** Spirit Stones to buy a Cave Dwelling. You have **{char.balance or 0}**.",
                ephemeral=True,
            )
            return

        char.balance = (char.balance or 0) - cost
        house = House(character_id=char.id, tier=1)
        db.add(house)

    embed = discord.Embed(
        title="🏠 Dwelling Purchased!",
        description=f"You now own a **{tier_data['name']}** for **{cost}** Spirit Stones!",
        color=0x92400E,
    )
    embed.add_field(name="✨ Perk", value=f"+{int(tier_data['xp_bonus'] * 100)}% XP from rest", inline=True)
    embed.add_field(name="🔮 Remaining", value=f"{char.balance} Spirit Stones", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@housing_group.command(name="upgrade", description="Upgrade your dwelling to the next tier")
async def house_upgrade(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        house_result = await db.execute(
            select(House).where(House.character_id == char.id)
        )
        house = house_result.scalar_one_or_none()
        if not house:
            await interaction.response.send_message(
                "You don't own a dwelling. Use `/house buy` first.", ephemeral=True
            )
            return

        current_tier = house.tier
        if current_tier >= 5:
            await interaction.response.send_message(
                "Your dwelling is already at **Tier 5 (Sovereign Palace)** — the highest possible!",
                ephemeral=True,
            )
            return

        next_tier = current_tier + 1
        current_data = HOUSING_TIERS[current_tier]
        next_data = HOUSING_TIERS[next_tier]

        upgrade_cost = next_data["cost"] - current_data["cost"]
        if upgrade_cost < 0:
            upgrade_cost = next_data["cost"]

        if (char.balance or 0) < upgrade_cost:
            await interaction.response.send_message(
                f"Upgrading to **{next_data['name']}** costs **{upgrade_cost}** Spirit Stones. "
                f"You have **{char.balance or 0}**.",
                ephemeral=True,
            )
            return

        char.balance = (char.balance or 0) - upgrade_cost
        house.tier = next_tier
        house.upgraded_at = discord.utils.utcnow()

    embed = discord.Embed(
        title="🏠 Dwelling Upgraded!",
        description=f"**{current_data['name']}** → **{next_data['name']}**",
        color=0x92400E,
    )
    embed.add_field(name="💰 Cost", value=f"{upgrade_cost} Spirit Stones", inline=True)
    embed.add_field(name="✨ New Perk", value=f"+{int(next_data['xp_bonus'] * 100)}% XP from rest", inline=True)
    embed.add_field(name="🔮 Remaining", value=f"{char.balance} Spirit Stones", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@housing_group.command(name="browse", description="Browse all available housing tiers")
async def house_browse(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🏠 Murim Housing Tiers",
        description="Your home in the cultivation world. Higher tiers grant better rest bonuses.",
        color=0x92400E,
    )

    for tier, data in sorted(HOUSING_TIERS.items()):
        name = data["name"]
        cost = data["cost"]
        pct = int(data["xp_bonus"] * 100)
        desc = data["desc"]
        embed.add_field(
            name=f"**Tier {tier}** — {name}",
            value=f"💰 **{cost}** Spirit Stones  ·  ✨ **+{pct}%** XP from rest\n*{desc}*",
            inline=False,
        )

    embed.set_footer(text="Use /house buy to purchase Tier 1  •  /house upgrade to improve")
    await interaction.response.send_message(embed=embed)


# ── Cog ───────────────────────────────────────────────────────────────────────

class HousingCog(commands.Cog, name="Housing"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(housing_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("house")


async def setup(bot):
    await bot.add_cog(HousingCog(bot))
