import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from database.session import get_db
from database.models import NotificationConfig

NOTIFY_TYPES = [
    ("faction_changes", "Faction Changes", "🏛️"),
    ("quest_objectives", "Quest Objectives", "📜"),
    ("world_events", "World Events", "🌍"),
    ("npc_movements", "NPC Movements", "👤"),
    ("lore_unlocks", "Lore Unlocks", "📚"),
]


notifications_group = app_commands.Group(
    name="notifications", description="Manage your notification preferences"
)


async def _get_or_create_config(user_id: int, guild_id: int) -> NotificationConfig:
    async with get_db() as db:
        result = await db.execute(
            select(NotificationConfig).where(
                NotificationConfig.user_id == user_id,
                NotificationConfig.guild_id == guild_id,
            )
        )
        config = result.scalar_one_or_none()
        if not config:
            config = NotificationConfig(
                user_id=user_id,
                guild_id=guild_id,
                faction_changes=True,
                quest_objectives=True,
                world_events=False,
                npc_movements=False,
                lore_unlocks=True,
            )
            db.add(config)
            await db.flush()
        return config


def _build_config_embed(config: NotificationConfig) -> discord.Embed:
    embed = discord.Embed(
        title="🔔 Notification Preferences",
        description="Click the buttons below to toggle notification types on/off.",
        color=0x6366F1,
    )
    for field_key, label, emoji in NOTIFY_TYPES:
        value = getattr(config, field_key, False)
        status = "✅ **ON**" if value else "❌ **OFF**"
        embed.add_field(name=f"{emoji} {label}", value=status, inline=True)
    embed.set_footer(text="LoreForge Notifications")
    return embed


class NotifyToggleView(discord.ui.View):
    def __init__(self, config: NotificationConfig):
        super().__init__(timeout=300)
        self.config = config

    async def _toggle(self, interaction: discord.Interaction, field_key: str):
        async with get_db() as db:
            result = await db.execute(
                select(NotificationConfig).where(
                    NotificationConfig.user_id == self.config.user_id,
                    NotificationConfig.guild_id == self.config.guild_id,
                )
            )
            config = result.scalar_one_or_none()
            if config:
                current = getattr(config, field_key, False)
                setattr(config, field_key, not current)
                self.config = config

        await interaction.response.edit_message(
            embed=_build_config_embed(self.config), view=self
        )

    @discord.ui.button(label="🏛️ Faction", style=discord.ButtonStyle.secondary)
    async def faction_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "faction_changes")

    @discord.ui.button(label="📜 Quests", style=discord.ButtonStyle.secondary)
    async def quest_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "quest_objectives")

    @discord.ui.button(label="🌍 World", style=discord.ButtonStyle.secondary)
    async def world_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "world_events")

    @discord.ui.button(label="👤 NPCs", style=discord.ButtonStyle.secondary, row=1)
    async def npc_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "npc_movements")

    @discord.ui.button(label="📚 Lore", style=discord.ButtonStyle.secondary, row=1)
    async def lore_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._toggle(interaction, "lore_unlocks")


@notifications_group.command(name="configure", description="Manage your notification preferences")
async def notifications_configure(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    config = await _get_or_create_config(interaction.user.id, interaction.guild_id)
    embed = _build_config_embed(config)
    view = NotifyToggleView(config)
    await interaction.followup.send(embed=embed, view=view, ephemeral=True)


class NotificationsCog(commands.Cog, name="Notifications"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(notifications_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("notifications")


async def setup(bot):
    await bot.add_cog(NotificationsCog(bot))
