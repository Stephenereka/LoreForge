"""
LoreForge Embed Builder Cog
GM-only embed creation tool with modals, templates, and live preview.
"""

import discord
from discord import app_commands
from discord.ext import commands
import re

from services.utils import gm_only

# ─── Templates ───────────────────────────────────────────────────────────────

EMBED_TEMPLATES = {
    "announcement": {
        "title": "📢 Announcement",
        "color": "#F1C40F",
        "description": "[Write your announcement here]",
        "footer": {"text": "Server Announcement", "icon_url": ""},
        "fields": [],
        "author": {},
        "thumbnail_url": "",
        "image_url": "",
    },
    "quest": {
        "title": "⚔️ Untitled Quest",
        "color": "#2ECC71",
        "description": "",
        "fields": [
            {"name": "Objective", "value": "[What must be done]", "inline": False},
            {"name": "Reward", "value": "[Gold / XP / Item]", "inline": True},
            {"name": "Danger Level", "value": "[Easy / Medium / Hard / Deadly]", "inline": True},
            {"name": "Location", "value": "[Where to go]", "inline": False},
        ],
        "footer": {},
        "author": {},
        "thumbnail_url": "",
        "image_url": "",
    },
    "lore": {
        "title": "📖 Lore Drop",
        "color": "#9B59B6",
        "description": "[Write your lore here]",
        "fields": [],
        "footer": {},
        "author": {},
        "thumbnail_url": "",
        "image_url": "",
    },
    "npc": {
        "title": "👤 NPC Introduction",
        "color": "#1ABC9C",
        "description": "",
        "fields": [
            {"name": "Name", "value": "[NPC name]", "inline": True},
            {"name": "Role", "value": "[Merchant / Quest Giver / Villager / ...]", "inline": True},
            {"name": "Personality", "value": "[Describe their demeanor]", "inline": False},
            {"name": "First Words", "value": "[What they say when approached]", "inline": False},
        ],
        "footer": {},
        "author": {},
        "thumbnail_url": "",
        "image_url": "",
    },
    "event": {
        "title": "🎉 Event",
        "color": "#3498DB",
        "description": "",
        "fields": [
            {"name": "Event Name", "value": "[Event name]", "inline": False},
            {"name": "Date & Time", "value": "[When it happens]", "inline": True},
            {"name": "Location", "value": "[Where to go]", "inline": True},
            {"name": "How to Join", "value": "[Sign-up / Show up / ...]", "inline": False},
        ],
        "footer": {},
        "author": {},
        "thumbnail_url": "",
        "image_url": "",
    },
    "news": {
        "title": "📰 Server News",
        "color": "#2C3E50",
        "description": "",
        "fields": [],
        "footer": {},
        "author": {"name": "[Category]", "icon_url": ""},
        "thumbnail_url": "",
        "image_url": "",
    },
}

# ─── Helpers ──────────────────────────────────────────────────────────────────

HEX_COLOR_RE = re.compile(r"^#?([0-9a-fA-F]{6})$")


def _parse_color(hex_str: str) -> int:
    """Parse a hex color string to an int. Returns default purple on failure."""
    if not hex_str:
        return 0x9B59B6
    match = HEX_COLOR_RE.match(hex_str.strip())
    if match:
        return int(match.group(1), 16)
    return 0x9B59B6


def _build_embed(embed_data: dict) -> discord.Embed:
    """Build a discord.Embed from the builder data dict."""
    color = _parse_color(embed_data.get("color", ""))
    embed = discord.Embed(
        title=embed_data.get("title") or None,
        description=embed_data.get("description") or None,
        color=color,
    )

    # Fields
    for field in embed_data.get("fields", []):
        name = field.get("name") or "\u200b"
        value = field.get("value") or "\u200b"
        inline = str(field.get("inline", "False")).lower() in ("yes", "true", "1")
        embed.add_field(name=name, value=value, inline=inline)

    # Thumbnail
    if embed_data.get("thumbnail_url"):
        embed.set_thumbnail(url=embed_data["thumbnail_url"])

    # Image
    if embed_data.get("image_url"):
        embed.set_image(url=embed_data["image_url"])

    # Footer
    footer = embed_data.get("footer") or {}
    if footer.get("text"):
        embed.set_footer(text=footer["text"], icon_url=footer.get("icon_url") or None)

    # Author
    author = embed_data.get("author") or {}
    if author.get("name"):
        embed.set_author(
            name=author["name"],
            url=author.get("url") or None,
            icon_url=author.get("icon_url") or None,
        )

    return embed


def _total_chars(embed_data: dict) -> int:
    """Count total characters in all embed text fields (title, desc, fields, footer, author)."""
    total = len(embed_data.get("title") or "")
    total += len(embed_data.get("description") or "")
    for field in embed_data.get("fields", []):
        total += len(field.get("name") or "")
        total += len(field.get("value") or "")
    footer = embed_data.get("footer") or {}
    total += len(footer.get("text") or "")
    author = embed_data.get("author") or {}
    total += len(author.get("name") or "")
    return total


async def _refresh_preview(interaction: discord.Interaction, embed_data: dict, view: discord.ui.View):
    """Edit the ephemeral message with an updated embed preview and status line."""
    embed = _build_embed(embed_data)
    field_count = len(embed_data.get("fields", []))
    char_count = _total_chars(embed_data)
    status = f"**Fields:** {field_count}/25 • **Chars:** {char_count}/6000"

    for child in view.children:
        if isinstance(child, discord.ui.Button) and child.label == "Add Field":
            child.disabled = field_count >= 25

    # edit_message only works for component interactions (buttons).
    # Modal submits must use defer() + message.edit() instead.
    if interaction.type == discord.InteractionType.modal_submit:
        await interaction.response.defer()
        await interaction.message.edit(content=status, embed=embed, view=view)
    else:
        await interaction.response.edit_message(content=status, embed=embed, view=view)


# ─── Modals ───────────────────────────────────────────────────────────────────

class EmbedStep1Modal(discord.ui.Modal, title="Embed Builder — Step 1"):
    title_ = discord.ui.TextInput(label="Title", required=False, max_length=256)
    description = discord.ui.TextInput(
        label="Description", style=discord.TextStyle.paragraph, required=False, max_length=4096
    )
    color = discord.ui.TextInput(
        label="Color (hex)", required=False, max_length=7, placeholder="#9B59B6"
    )
    thumbnail_url = discord.ui.TextInput(
        label="Thumbnail URL", required=False, max_length=500
    )
    image_url = discord.ui.TextInput(
        label="Image URL", required=False, max_length=500
    )

    def __init__(self, existing_data: dict | None = None):
        if existing_data:
            # Re-create TextInputs with defaults from template data
            self.title_ = discord.ui.TextInput(
                label="Title", required=False, max_length=256,
                default=existing_data.get("title") or "",
            )
            self.description = discord.ui.TextInput(
                label="Description", style=discord.TextStyle.paragraph,
                required=False, max_length=4096,
                default=existing_data.get("description") or "",
            )
            self.color = discord.ui.TextInput(
                label="Color (hex)", required=False, max_length=7,
                placeholder="#9B59B6",
                default=existing_data.get("color") or "",
            )
            self.thumbnail_url = discord.ui.TextInput(
                label="Thumbnail URL", required=False, max_length=500,
                default=existing_data.get("thumbnail_url") or "",
            )
            self.image_url = discord.ui.TextInput(
                label="Image URL", required=False, max_length=500,
                default=existing_data.get("image_url") or "",
            )
        super().__init__()

    async def on_submit(self, interaction: discord.Interaction):
        embed_data = {
            "title": self.title_.value.strip() if self.title_.value else "",
            "description": self.description.value.strip() if self.description.value else "",
            "color": self.color.value.strip() if self.color.value else "",
            "thumbnail_url": self.thumbnail_url.value.strip() if self.thumbnail_url.value else "",
            "image_url": self.image_url.value.strip() if self.image_url.value else "",
            "fields": [],
            "footer": {},
            "author": {},
        }
        view = BuilderView(embed_data)
        embed = _build_embed(embed_data)
        field_count = 0
        char_count = _total_chars(embed_data)
        status = f"**Fields:** {field_count}/25 • **Chars:** {char_count}/6000"
        await interaction.response.send_message(content=status, embed=embed, view=view, ephemeral=True)


class AddFieldModal(discord.ui.Modal, title="Add Field"):
    name = discord.ui.TextInput(label="Field Name", max_length=256)
    value = discord.ui.TextInput(
        label="Value", style=discord.TextStyle.paragraph, max_length=1024
    )
    inline = discord.ui.TextInput(
        label="Inline?", required=False, max_length=3, placeholder="yes or no"
    )

    def __init__(self, embed_data: dict, view: "BuilderView"):
        super().__init__()
        self._embed_data = embed_data
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        fields = self._embed_data.setdefault("fields", [])
        if len(fields) >= 25:
            await interaction.response.send_message(
                "❌ Max 25 fields reached.", ephemeral=True
            )
            return
        fields.append({
            "name": self.name.value.strip(),
            "value": self.value.value.strip(),
            "inline": self.inline.value.strip() if self.inline.value else "no",
        })
        await _refresh_preview(interaction, self._embed_data, self._view)


class FooterModal(discord.ui.Modal, title="Set Footer"):
    text = discord.ui.TextInput(label="Footer Text", max_length=2048)
    icon_url = discord.ui.TextInput(
        label="Icon URL (optional)", required=False, max_length=500
    )

    def __init__(self, embed_data: dict, view: "BuilderView"):
        super().__init__()
        self._embed_data = embed_data
        self._view = view
        # Pre-fill existing footer info
        footer = embed_data.get("footer") or {}
        if footer.get("text"):
            self.text.default = footer["text"]
        if footer.get("icon_url"):
            self.icon_url.default = footer["icon_url"]

    async def on_submit(self, interaction: discord.Interaction):
        self._embed_data["footer"] = {
            "text": self.text.value.strip() if self.text.value else "",
            "icon_url": self.icon_url.value.strip() if self.icon_url.value else "",
        }
        await _refresh_preview(interaction, self._embed_data, self._view)


class AuthorModal(discord.ui.Modal, title="Set Author"):
    name = discord.ui.TextInput(label="Author Name", max_length=256)
    url = discord.ui.TextInput(label="URL (optional)", required=False, max_length=500)
    icon_url = discord.ui.TextInput(
        label="Icon URL (optional)", required=False, max_length=500
    )

    def __init__(self, embed_data: dict, view: "BuilderView"):
        super().__init__()
        self._embed_data = embed_data
        self._view = view
        author = embed_data.get("author") or {}
        if author.get("name"):
            self.name.default = author["name"]
        if author.get("url"):
            self.url.default = author["url"]
        if author.get("icon_url"):
            self.icon_url.default = author["icon_url"]

    async def on_submit(self, interaction: discord.Interaction):
        self._embed_data["author"] = {
            "name": self.name.value.strip() if self.name.value else "",
            "url": self.url.value.strip() if self.url.value else "",
            "icon_url": self.icon_url.value.strip() if self.icon_url.value else "",
        }
        await _refresh_preview(interaction, self._embed_data, self._view)


class ChannelModal(discord.ui.Modal, title="Select Channel"):
    channel = discord.ui.TextInput(
        label="Channel Name or ID",
        max_length=100,
        placeholder="#channel-name or 123456789012345678",
    )

    def __init__(self, embed_data: dict, view: "BuilderView"):
        super().__init__()
        self._embed_data = embed_data
        self._view = view

    async def on_submit(self, interaction: discord.Interaction):
        channel_input = self.channel.value.strip()

        # Try to resolve channel by ID or mention
        channel: discord.TextChannel | None = None

        # Check for mention pattern
        mention_match = re.match(r"<#(\d+)>", channel_input)
        if mention_match:
            channel_id = int(mention_match.group(1))
            channel = interaction.guild.get_channel(channel_id)
        else:
            # Try as ID
            try:
                channel_id = int(channel_input)
                channel = interaction.guild.get_channel(channel_id)
            except ValueError:
                pass

        # Try by name
        if channel is None:
            name_clean = channel_input.lstrip("#").lower().replace(" ", "-")
            for ch in interaction.guild.text_channels:
                if ch.name.lower() == name_clean or ch.name.lower().replace("-", " ") == name_clean:
                    channel = ch
                    break

        if channel is None:
            await interaction.response.send_message(
                "❌ Could not find that channel. Use #mention or channel ID.",
                ephemeral=True,
            )
            return

        embed = _build_embed(self._embed_data)
        await channel.send(embed=embed)
        await interaction.response.send_message(
            f"✅ Embed posted to {channel.mention}", ephemeral=True
        )


# ─── Builder View ─────────────────────────────────────────────────────────────

class BuilderView(discord.ui.View):
    def __init__(self, embed_data: dict):
        super().__init__(timeout=600)
        self.embed_data = embed_data

    @discord.ui.button(label="Add Field", style=discord.ButtonStyle.green, row=0)
    async def add_field_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if len(self.embed_data.get("fields", [])) >= 25:
            await interaction.response.send_message(
                "❌ Max 25 fields reached.", ephemeral=True
            )
            return
        await interaction.response.send_modal(AddFieldModal(self.embed_data, self))

    @discord.ui.button(label="Set Footer", style=discord.ButtonStyle.grey, row=0)
    async def set_footer_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(FooterModal(self.embed_data, self))

    @discord.ui.button(label="Set Author", style=discord.ButtonStyle.grey, row=0)
    async def set_author_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AuthorModal(self.embed_data, self))

    @discord.ui.button(label="Post Here", style=discord.ButtonStyle.primary, row=1)
    async def post_here_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _build_embed(self.embed_data)
        title = self.embed_data.get("title", "")
        description = self.embed_data.get("description", "")

        if not title and not description:
            await interaction.response.send_message(
                "❌ Embed must have a title or a description.", ephemeral=True
            )
            return
        if _total_chars(self.embed_data) > 6000:
            await interaction.response.send_message(
                f"❌ Embed too long ({_total_chars(self.embed_data)}/6000 chars). Shorten it.",
                ephemeral=True,
            )
            return

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("✅ Embed posted!", ephemeral=True)

    @discord.ui.button(label="Post to Channel", style=discord.ButtonStyle.primary, row=1)
    async def post_to_channel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = _build_embed(self.embed_data)
        title = self.embed_data.get("title", "")
        description = self.embed_data.get("description", "")

        if not title and not description:
            await interaction.response.send_message(
                "❌ Embed must have a title or a description.", ephemeral=True
            )
            return
        if _total_chars(self.embed_data) > 6000:
            await interaction.response.send_message(
                f"❌ Embed too long ({_total_chars(self.embed_data)}/6000 chars). Shorten it.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(ChannelModal(self.embed_data, self))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=1)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="❌ Embed cancelled.", embed=None, view=None)


# ─── Cog ──────────────────────────────────────────────────────────────────────

class EmbedBuilder(commands.Cog):
    """GM-only embed creation and management tools."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    embed_group = app_commands.Group(
        name="embed",
        description="Build and post custom embeds (GM only)",
        guild_only=True,
    )

    @embed_group.command(name="create", description="Open the embed builder")
    async def embed_create(self, interaction: discord.Interaction):
        if not await gm_only(interaction):
            return
        await interaction.response.send_modal(EmbedStep1Modal())

    @embed_group.command(name="template", description="Start from a pre-built template")
    @app_commands.describe(type="Template type to use")
    @app_commands.choices(type=[
        app_commands.Choice(name="Announcement", value="announcement"),
        app_commands.Choice(name="Quest", value="quest"),
        app_commands.Choice(name="Lore", value="lore"),
        app_commands.Choice(name="NPC", value="npc"),
        app_commands.Choice(name="Event", value="event"),
        app_commands.Choice(name="News", value="news"),
    ])
    async def embed_template(self, interaction: discord.Interaction, type: str):
        if not await gm_only(interaction):
            return
        template_data = EMBED_TEMPLATES.get(type)
        if template_data is None:
            await interaction.response.send_message(
                f"❌ Unknown template type: {type}", ephemeral=True
            )
            return
        await interaction.response.send_modal(EmbedStep1Modal(existing_data=template_data))


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedBuilder(bot))
