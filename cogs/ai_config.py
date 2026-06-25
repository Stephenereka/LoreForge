import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import AIConfig
from services.utils import gm_only

ai_group = app_commands.Group(name="ai", description="AI system configuration (GM only)")

_STYLE_CHOICES = [
    app_commands.Choice(name="Epic — cinematic, dramatic", value="epic"),
    app_commands.Choice(name="Gritty — brutal, realistic", value="gritty"),
    app_commands.Choice(name="Comedic — light, humorous", value="comedic"),
    app_commands.Choice(name="Minimal — one-liner only", value="minimal"),
]


async def _get_or_create_ai_config(guild_id: int) -> AIConfig:
    """Get or create an AIConfig row for the given guild."""
    async with get_db() as db:
        result = await db.execute(
            select(AIConfig).where(AIConfig.guild_id == guild_id)
        )
        config = result.scalar_one_or_none()
        if not config:
            config = AIConfig(guild_id=guild_id)
            db.add(config)
    return config


@ai_group.command(name="status", description="Show all AI feature toggles for this server (GM only)")
async def ai_status(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    config = await _get_or_create_ai_config(interaction.guild_id)
    embed = discord.Embed(
        title="🤖 AI System Status",
        description=f"Current AI configuration for **{interaction.guild.name}**",
        color=0x6366F1,
    )
    narration_status = "✅ ON" if config.narration_enabled else "❌ OFF"
    npc_status = "✅ ON" if config.npc_ai_enabled else "❌ OFF"
    summary_status = "✅ ON" if config.session_summary_enabled else "❌ OFF"

    embed.add_field(name="⚔️ Combat Narration", value=f"{narration_status}  — Style: **{config.narration_style}**", inline=False)
    embed.add_field(name="💬 NPC Dialogue (AI)", value=npc_status, inline=False)
    embed.add_field(name="📜 Session Summaries", value=summary_status, inline=False)
    embed.set_footer(text="Use /ai toggle and /ai style to configure")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── Toggle subgroup ───────────────────────────────────────────────────────────

ai_toggle = app_commands.Group(name="toggle", description="Toggle AI features", parent=ai_group)


@ai_toggle.command(name="narration", description="Toggle AI combat narration on/off (GM only)")
async def ai_toggle_narration(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    config = await _get_or_create_ai_config(interaction.guild_id)
    config.narration_enabled = not config.narration_enabled
    config.updated_by = interaction.user.id
    status = "enabled" if config.narration_enabled else "disabled"

    embed = discord.Embed(
        title="⚙️ AI Narration Toggled",
        description=f"Combat narration is now **{status}**.",
        color=0x22C55E if config.narration_enabled else 0xEF4444,
    )
    embed.add_field(name="Style", value=config.narration_style, inline=True)
    embed.add_field(name="Narration Status", value="✅ ON" if config.narration_enabled else "❌ OFF", inline=True)
    await interaction.response.send_message(embed=embed)


@ai_toggle.command(name="npc", description="Toggle AI NPC dialogue on/off (GM only)")
async def ai_toggle_npc(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    config = await _get_or_create_ai_config(interaction.guild_id)
    config.npc_ai_enabled = not config.npc_ai_enabled
    config.updated_by = interaction.user.id
    status = "enabled" if config.npc_ai_enabled else "disabled"

    embed = discord.Embed(
        title="⚙️ AI NPC Dialogue Toggled",
        description=f"AI NPC dialogue is now **{status}**.",
        color=0x22C55E if config.npc_ai_enabled else 0xEF4444,
    )
    await interaction.response.send_message(embed=embed)


@ai_toggle.command(name="summary", description="Toggle auto session summaries on/off (GM only)")
async def ai_toggle_summary(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    config = await _get_or_create_ai_config(interaction.guild_id)
    config.session_summary_enabled = not config.session_summary_enabled
    config.updated_by = interaction.user.id
    status = "enabled" if config.session_summary_enabled else "disabled"

    embed = discord.Embed(
        title="⚙️ Session Summaries Toggled",
        description=f"Auto session summaries are now **{status}**.",
        color=0x22C55E if config.session_summary_enabled else 0xEF4444,
    )
    await interaction.response.send_message(embed=embed)


# ── Style command ─────────────────────────────────────────────────────────────

@ai_group.command(name="style", description="Set the AI narration style (GM only)")
@app_commands.describe(style="The narration tone to use")
@app_commands.choices(style=_STYLE_CHOICES)
async def ai_style(interaction: discord.Interaction, style: app_commands.Choice[str]):
    if not await gm_only(interaction):
        return

    config = await _get_or_create_ai_config(interaction.guild_id)
    config.narration_style = style.value
    config.updated_by = interaction.user.id

    embed = discord.Embed(
        title="🎭 Narration Style Updated",
        description=f"Combat narration style set to **{style.name}**.",
        color=0x6366F1,
    )
    await interaction.response.send_message(embed=embed)


class AIConfigCog(commands.Cog, name="AIConfig"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(ai_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("ai")


async def setup(bot):
    await bot.add_cog(AIConfigCog(bot))
