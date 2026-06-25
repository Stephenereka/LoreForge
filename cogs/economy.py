import math
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, desc
from datetime import datetime, timedelta
from database.session import get_db
from database.models import Character, DailyReward


# ── Daily reward config ──────────────────────────────────────────────────────

DAILY_REWARDS = {
    1: 200,
    2: 350,
    3: 500,
    4: 750,  # max — day 4+
}


def _daily_amount(streak: int) -> int:
    if streak >= 4:
        return DAILY_REWARDS[4]
    return DAILY_REWARDS.get(streak, DAILY_REWARDS[1])


# ── Economy command group ────────────────────────────────────────────────────

economy_group = app_commands.Group(name="economy", description="Spirit Stone economy commands")


@economy_group.command(name="balance", description="Check your Spirit Stone balance")
async def economy_balance(interaction: discord.Interaction):
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
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        embed = discord.Embed(
            title=f"🔮 {char.name}'s Balance",
            description=f"**{char.balance or 0}** Spirit Stones",
            color=0x6B21A8,
        )
        embed.add_field(name="📦 Inventory Items", value=str(len(char.inventory or [])), inline=True)
        embed.add_field(name="💰 Gold", value=f"{char.gold} gp", inline=True)
        embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@economy_group.command(name="pay", description="Send Spirit Stones to another player")
@app_commands.describe(user="The player to pay", amount="Amount of Spirit Stones to send")
async def economy_pay(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if user.id == interaction.user.id:
        await interaction.response.send_message("You can't pay yourself.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("Amount must be at least 1 Spirit Stone.", ephemeral=True)
        return

    async with get_db() as db:
        # Get sender's character
        sender_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        sender = sender_result.scalar_one_or_none()
        if not sender:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        if (sender.balance or 0) < amount:
            await interaction.response.send_message(
                f"You only have **{sender.balance or 0}** Spirit Stones, but you need **{amount}**.", ephemeral=True
            )
            return

        # Get receiver's character
        receiver_result = await db.execute(
            select(Character).where(
                Character.user_id == user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        receiver = receiver_result.scalar_one_or_none()
        if not receiver:
            await interaction.response.send_message(
                f"**{user.display_name}** doesn't have a character in this server.", ephemeral=True
            )
            return

        # Transfer
        sender.balance = (sender.balance or 0) - amount
        receiver.balance = (receiver.balance or 0) + amount

    embed = discord.Embed(
        title="🔮 Spirit Stones Sent!",
        description=f"**{amount}** Spirit Stones sent to **{receiver.name}** (owned by {user.mention}).",
        color=0x6B21A8,
    )
    embed.add_field(name="Your Balance", value=f"🔮 {sender.balance or 0}", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@economy_group.command(name="daily", description="Claim your daily Spirit Stone reward")
async def economy_daily(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        # Get character
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

        # Get or create daily reward record
        dr_result = await db.execute(
            select(DailyReward).where(DailyReward.character_id == char.id)
        )
        daily = dr_result.scalar_one_or_none()

        now = datetime.utcnow()

        if daily and daily.last_claimed:
            time_since = now - daily.last_claimed
            if time_since < timedelta(hours=24):
                remaining = timedelta(hours=24) - time_since
                hours, remainder = divmod(int(remaining.total_seconds()), 3600)
                minutes = remainder // 60
                await interaction.response.send_message(
                    f"You already claimed your daily reward! Come back in **{hours}h {minutes}m**.",
                    ephemeral=True,
                )
                return

            # Check if streak should reset (>48h gap)
            if time_since > timedelta(hours=48):
                daily.streak = 0

            daily.streak += 1
            daily.last_claimed = now
        else:
            if not daily:
                daily = DailyReward(character_id=char.id, streak=1, last_claimed=now)
                db.add(daily)
            else:
                daily.streak = 1
                daily.last_claimed = now

        streak = daily.streak
        amount = _daily_amount(streak)
        char.balance = (char.balance or 0) + amount

        await db.flush()

    # Next reward preview
    next_streak = streak + 1
    next_amount = _daily_amount(next_streak)

    embed = discord.Embed(
        title="🔮 Daily Reward Claimed!",
        description=f"You received **{amount}** Spirit Stones!",
        color=0x6B21A8,
    )
    embed.add_field(name="🔥 Streak", value=f"Day **{streak}**", inline=True)
    embed.add_field(name="🔮 New Balance", value=f"{char.balance or 0} Spirit Stones", inline=True)
    if next_streak <= 4:
        embed.add_field(name="📈 Next Reward", value=f"Day {next_streak}: **{next_amount}** Spirit Stones", inline=False)
    else:
        embed.add_field(name="📈 Max Streak", value=f"You're at max rewards! Come back tomorrow for **{next_amount}** Spirit Stones.", inline=False)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


@economy_group.command(name="leaderboard", description="Top 10 richest cultivators")
async def economy_leaderboard(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character)
            .where(Character.guild_id == interaction.guild_id, Character.is_dead == False)
            .order_by(desc(Character.balance))
            .limit(10)
        )
        top = list(result.scalars().all())

    if not top:
        await interaction.response.send_message("No characters found on this server.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔮 Spirit Stone Leaderboard",
        description="Top 10 richest cultivators in this realm.",
        color=0x6B21A8,
    )

    medals = ["🥇", "🥈", "🥉"]
    lines = []
    for i, char in enumerate(top):
        medal = medals[i] if i < 3 else f"`#{i + 1}`"
        balance = char.balance or 0
        lines.append(f"{medal} **{char.name}** — 🔮 {balance} Spirit Stones  *(Lv{char.level} {char.char_class})*")

    embed.description = "\n".join(lines)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


# ── Cog ───────────────────────────────────────────────────────────────────────

class EconomyCog(commands.Cog, name="Economy"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(economy_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("economy")


async def setup(bot):
    await bot.add_cog(EconomyCog(bot))
