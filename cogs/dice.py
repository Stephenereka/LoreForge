import re
import random
import discord
from discord import app_commands
from discord.ext import commands


# ── Constants ────────────────────────────────────────────────────────────────

MAX_DICE = 20
MAX_SIDES = 1000

# Matches: optional number + d + number + optional modifier
# Examples: d20, 2d6, 4d6, 2d6+3, 3d8-1, 1d100
DICE_PATTERN = re.compile(r"^(\d*)d(\d+)([+-]\d+)?$", re.IGNORECASE)


def parse_dice(expression: str) -> tuple[int, int, int] | None:
    """
    Parse a dice expression like '2d6+3', 'd20', '4d6', '3d8-2'.
    Returns (num_dice, sides, modifier) or None if invalid/out of range.
    """
    expression = expression.strip().lower()
    match = DICE_PATTERN.match(expression)
    if not match:
        return None

    num_dice_str, sides_str, mod_str = match.groups()

    # If num_dice is empty, it's 1 (e.g. "d20" = 1d20)
    num_dice = int(num_dice_str) if num_dice_str else 1
    sides = int(sides_str)
    modifier = int(mod_str) if mod_str else 0

    # Validation
    if num_dice < 1 or num_dice > MAX_DICE:
        return None
    if sides < 2 or sides > MAX_SIDES:
        return None

    return num_dice, sides, modifier


def roll_dice(num_dice: int, sides: int) -> list[int]:
    """Roll num_dice d(sides) and return the list of results."""
    return [random.randint(1, sides) for _ in range(num_dice)]


# ── Cog ───────────────────────────────────────────────────────────────────────

class DiceCog(commands.Cog, name="Dice"):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="roll", description="Roll dice using standard RPG notation (e.g. 2d6+3, d20, 4d6)")
    @app_commands.describe(dice="Dice expression — e.g. d20, 2d6+3, 4d6, 3d8-1")
    async def roll(self, interaction: discord.Interaction, dice: str):
        parsed = parse_dice(dice)
        if not parsed:
            await interaction.response.send_message(
                f"Invalid dice notation. Use formats like `d20`, `2d6`, `4d6`, `2d6+3`, `3d8-1`.\n"
                f"Max **{MAX_DICE}** dice, max **{MAX_SIDES}** sides.",
                ephemeral=True,
            )
            return

        num_dice, sides, modifier = parsed
        results = roll_dice(num_dice, sides)
        total = sum(results) + modifier

        # ── Build embed ──────────────────────────────────────────────────────
        embed = discord.Embed(
            title="🎲 Dice Roll",
            color=0xF59E0B,  # Gold / yellow
        )

        # What was rolled
        formatted = f"{num_dice}d{sides}"
        if modifier:
            mod_sign = "+" if modifier > 0 else ""
            formatted += f"{mod_sign}{modifier}"
        embed.add_field(name="Roll", value=formatted, inline=True)

        # Individual results
        results_str = ", ".join(str(r) for r in results)
        embed.add_field(name="Results", value=f"[{results_str}]", inline=True)

        # Total (show breakdown if modifier present)
        if modifier:
            base_sum = sum(results)
            mod_sign = "+" if modifier > 0 else ""
            total_str = f"{base_sum} ({mod_sign}{modifier}) = **{total}**"
        else:
            total_str = f"**{total}**"
        embed.add_field(name="Total", value=total_str, inline=False)

        embed.set_footer(text=f"Rolled by {interaction.user.display_name}")

        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(DiceCog(bot))
