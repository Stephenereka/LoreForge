import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import AIConfig
from services.utils import gm_only

ai_group = app_commands.Group(name="ai", description="AI system configuration (GM only)")

_STYLE_CHOICES = [
    app_commands.Choice(name="Epic â€” cinematic, dramatic", value="epic"),
    app_commands.Choice(name="Gritty â€” brutal, realistic", value="gritty"),
    app_commands.Choice(name="Comedic â€” light, humorous", value="comedic"),
    app_commands.Choice(name="Minimal â€” one-liner only", value="minimal"),
]


@ai_group.command(name="status", description="Show all AI feature toggles for this server (GM only)")
async def ai_status(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        config = await db.scalar(select(AIConfig).where(AIConfig.guild_id == interaction.guild_id))
        if not config:
            config = AIConfig(guild_id=str(interaction.guild_id))
            db.add(config)
            await db.flush()
        narration_status = "âœ… ON" if config.narration_enabled else "âŒ OFF"
        npc_status = "âœ… ON" if config.npc_ai_enabled else "âŒ OFF"
        summary_status = "âœ… ON" if config.session_summary_enabled else "âŒ OFF"
        style = config.narration_style
    embed = discord.Embed(
        title="ðŸ¤– AI System Status",
        description=f"Current AI configuration for **{interaction.guild.name}**",
        color=0x6366F1,
    )
    embed.add_field(name="âš”ï¸ Combat Narration", value=f"{narration_status}  â€” Style: **{style}**", inline=False)
    embed.add_field(name="ðŸ’¬ NPC Dialogue (AI)", value=npc_status, inline=False)
    embed.add_field(name="ðŸ“œ Session Summaries", value=summary_status, inline=False)
    embed.set_footer(text="Use /ai toggle and /ai style to configure")
    await interaction.followup.send(embed=embed, ephemeral=True)


# â”€â”€ Toggle subgroup â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

ai_toggle = app_commands.Group(name="toggle", description="Toggle AI features", parent=ai_group)


@ai_toggle.command(name="narration", description="Toggle AI combat narration on/off (GM only)")
async def ai_toggle_narration(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        config = await db.scalar(select(AIConfig).where(AIConfig.guild_id == interaction.guild_id))
        if not config:
            config = AIConfig(guild_id=str(interaction.guild_id))
            db.add(config)
            await db.flush()
        config.narration_enabled = not config.narration_enabled
        config.updated_by = str(interaction.user.id)
        narration_enabled = config.narration_enabled
        narration_style = config.narration_style
    status = "enabled" if narration_enabled else "disabled"
    embed = discord.Embed(
        title="âš™ï¸ AI Narration Toggled",
        description=f"Combat narration is now **{status}**.",
        color=0x22C55E if narration_enabled else 0xEF4444,
    )
    embed.add_field(name="Style", value=narration_style, inline=True)
    embed.add_field(name="Narration Status", value="âœ… ON" if narration_enabled else "âŒ OFF", inline=True)
    await interaction.followup.send(embed=embed)


@ai_toggle.command(name="npc", description="Toggle AI NPC dialogue on/off (GM only)")
async def ai_toggle_npc(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        config = await db.scalar(select(AIConfig).where(AIConfig.guild_id == interaction.guild_id))
        if not config:
            config = AIConfig(guild_id=str(interaction.guild_id))
            db.add(config)
            await db.flush()
        config.npc_ai_enabled = not config.npc_ai_enabled
        config.updated_by = str(interaction.user.id)
        npc_ai_enabled = config.npc_ai_enabled
    status = "enabled" if npc_ai_enabled else "disabled"
    embed = discord.Embed(
        title="âš™ï¸ AI NPC Dialogue Toggled",
        description=f"AI NPC dialogue is now **{status}**.",
        color=0x22C55E if npc_ai_enabled else 0xEF4444,
    )
    await interaction.followup.send(embed=embed)


@ai_toggle.command(name="summary", description="Toggle auto session summaries on/off (GM only)")
async def ai_toggle_summary(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        config = await db.scalar(select(AIConfig).where(AIConfig.guild_id == interaction.guild_id))
        if not config:
            config = AIConfig(guild_id=str(interaction.guild_id))
            db.add(config)
            await db.flush()
        config.session_summary_enabled = not config.session_summary_enabled
        config.updated_by = str(interaction.user.id)
        summary_enabled = config.session_summary_enabled
    status = "enabled" if summary_enabled else "disabled"
    embed = discord.Embed(
        title="âš™ï¸ Session Summaries Toggled",
        description=f"Auto session summaries are now **{status}**.",
        color=0x22C55E if summary_enabled else 0xEF4444,
    )
    await interaction.followup.send(embed=embed)


# â”€â”€ Style command â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@ai_group.command(name="style", description="Set the AI narration style (GM only)")
@app_commands.describe(style="The narration tone to use")
@app_commands.choices(style=_STYLE_CHOICES)
async def ai_style(interaction: discord.Interaction, style: app_commands.Choice[str]):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        config = await db.scalar(select(AIConfig).where(AIConfig.guild_id == interaction.guild_id))
        if not config:
            config = AIConfig(guild_id=str(interaction.guild_id))
            db.add(config)
            await db.flush()
        config.narration_style = style.value
        config.updated_by = str(interaction.user.id)
    embed = discord.Embed(
        title="ðŸŽ­ Narration Style Updated",
        description=f"Combat narration style set to **{style.name}**.",
        color=0x6366F1,
    )
    await interaction.followup.send(embed=embed)


class AIConfigCog(commands.Cog, name="AIConfig"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(ai_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("ai")


async def setup(bot):
    await bot.add_cog(AIConfigCog(bot))
