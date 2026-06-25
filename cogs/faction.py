import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete
from database.session import get_db
from database.models import Faction, FactionReputation, FactionPerk, Character
from services.utils import is_gm
from services.faction_service import REPUTATION_TIERS, get_tier, change_reputation
import datetime

faction_group = app_commands.Group(name="faction", description="Manage factions and reputation")

# ── Create Wizard ──────────────────────────────────────────────────────────────

class FactionCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.data = {}

    @discord.ui.button(label="Step 1: Name & Description", style=discord.ButtonStyle.primary)
    async def step1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create factions.", ephemeral=True)
            return
        modal = FactionNameModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Step 2: Type & Color", style=discord.ButtonStyle.secondary)
    async def step2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create factions.", ephemeral=True)
            return
        if "name" not in self.data:
            await interaction.response.send_message("Complete Step 1 first.", ephemeral=True)
            return
        modal = FactionTypeModal(self)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Create Faction ✅", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create factions.", ephemeral=True)
            return
        required = {"name", "description", "faction_type"}
        if not required.issubset(self.data.keys()):
            await interaction.response.send_message("Complete all steps first.", ephemeral=True)
            return

        async with get_db() as db:
            db.add(Faction(
                guild_id=interaction.guild_id,
                name=self.data["name"],
                description=self.data["description"],
                faction_type=self.data["faction_type"],
                color=self.data.get("color", "#6366F1"),
                icon_emoji=self.data.get("icon_emoji"),
                starting_rep=self.data.get("starting_rep", 0),
                created_by=interaction.user.id,
            ))

        embed = discord.Embed(
            title=f"🏛️ Faction Created: {self.data['name']}",
            description=self.data["description"],
            color=int(self.data.get("color", "#6366F1").lstrip("#"), 16),
        )
        await interaction.response.edit_message(embed=embed, view=None)


class FactionNameModal(discord.ui.Modal, title="Faction Name & Description"):
    name = discord.ui.TextInput(label="Faction Name", max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)

    def __init__(self, parent_view: FactionCreateView):
        super().__init__()
        self._parent = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self._parent.data["name"] = self.name.value
        self._parent.data["description"] = self.description.value
        await interaction.response.send_message("✅ Step 1 complete! Move to Step 2.", ephemeral=True)


class FactionTypeModal(discord.ui.Modal, title="Faction Type & Appearance"):
    faction_type = discord.ui.TextInput(label="Type (guild/sect/kingdom/covenant)", max_length=30, default="guild")
    color = discord.ui.TextInput(label="Color hex (e.g., #6366F1)", max_length=7, default="#6366F1")
    icon_emoji = discord.ui.TextInput(label="Icon emoji (e.g., 🏛️)", max_length=10, required=False)
    starting_rep = discord.ui.TextInput(label="Starting reputation", default="0", max_length=5)

    def __init__(self, parent_view: FactionCreateView):
        super().__init__()
        self._parent = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self._parent.data["faction_type"] = self.faction_type.value
        self._parent.data["color"] = self.color.value
        self._parent.data["icon_emoji"] = self.icon_emoji.value or None
        try:
            self._parent.data["starting_rep"] = int(self.starting_rep.value)
        except ValueError:
            self._parent.data["starting_rep"] = 0
        await interaction.response.send_message("✅ Step 2 complete! Click 'Create Faction'.", ephemeral=True)


# ── Commands ──────────────────────────────────────────────────────────────────

@faction_group.command(name="create", description="Create a new faction (GM only)")
async def faction_create(interaction: discord.Interaction):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can create factions.", ephemeral=True)
        return
    embed = discord.Embed(
        title="🏛️ Create a Faction",
        description="Use the buttons below to set up your faction.",
        color=0x6366F1,
    )
    await interaction.response.send_message(embed=embed, view=FactionCreateView(), ephemeral=True)


@faction_group.command(name="edit", description="Edit a faction (GM only)")
@app_commands.describe(name="Faction name")
async def faction_edit(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can edit factions.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(
                Faction.guild_id == interaction.guild_id,
                Faction.name.ilike(name),
            )
        )
        faction = result.scalar_one_or_none()
        if not faction:
            await interaction.response.send_message("Faction not found.", ephemeral=True)
            return

    modal = FactionEditModal(faction)
    await interaction.response.send_modal(modal)


class FactionEditModal(discord.ui.Modal, title="Edit Faction"):
    name = discord.ui.TextInput(label="Name", max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)
    faction_type = discord.ui.TextInput(label="Type", max_length=30)
    color = discord.ui.TextInput(label="Color hex", max_length=7)

    def __init__(self, faction: Faction):
        super().__init__()
        self._faction_id = faction.id
        self.name.default = faction.name
        self.description.default = faction.description
        self.faction_type.default = faction.faction_type
        self.color.default = faction.color

    async def on_submit(self, interaction: discord.Interaction):
        async with get_db() as db:
            result = await db.execute(select(Faction).where(Faction.id == self._faction_id))
            f = result.scalar_one_or_none()
            if f:
                f.name = self.name.value
                f.description = self.description.value
                f.faction_type = self.faction_type.value
                f.color = self.color.value
        await interaction.response.send_message("✅ Faction updated.", ephemeral=True)


@faction_group.command(name="delete", description="Delete a faction (GM only)")
@app_commands.describe(name="Faction name")
async def faction_delete(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can delete factions.", ephemeral=True)
        return
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(
                Faction.guild_id == interaction.guild_id,
                Faction.name.ilike(name),
            )
        )
        faction = result.scalar_one_or_none()
        if not faction:
            await interaction.followup.send("Faction not found.", ephemeral=True)
            return
        await db.delete(faction)
    await interaction.followup.send(f"🗑️ Deleted faction **{name}**.")


@faction_group.command(name="list", description="List all factions")
async def faction_list(interaction: discord.Interaction):
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(Faction.guild_id == interaction.guild_id)
        )
        factions = result.scalars().all()

        # Get player's reputations
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        char = char_result.scalar_one_or_none()

    if not factions:
        await interaction.followup.send("No factions in this world.", ephemeral=True)
        return

    embed = discord.Embed(title="🏛️ Factions", color=0x6366F1)
    for f in factions:
        tier = "—"
        if char:
            async with get_db() as db2:
                rep_result = await db2.execute(
                    select(FactionReputation).where(
                        FactionReputation.character_id == char.id,
                        FactionReputation.faction_id == f.id,
                    )
                )
                rep = rep_result.scalar_one_or_none()
                if rep:
                    tier = get_tier(rep.reputation)

        embed.add_field(
            name=f"{f.icon_emoji or ''} {f.name}",
            value=f"{f.faction_type}  ·  Your tier: {tier}",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@faction_group.command(name="status", description="Check your reputation with a faction")
@app_commands.describe(name="Faction name")
async def faction_status(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(
                Faction.guild_id == interaction.guild_id,
                Faction.name.ilike(name),
            )
        )
        faction = result.scalar_one_or_none()
        if not faction:
            await interaction.followup.send("Faction not found.", ephemeral=True)
            return

        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need an active character.", ephemeral=True)
            return

        rep_result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == char.id,
                FactionReputation.faction_id == faction.id,
            )
        )
        rep = rep_result.scalar_one_or_none()
        rep_value = rep.reputation if rep else 0
        tier = get_tier(rep_value)

        # Find tier bounds for progress bar
        progress_bar = ""
        for tier_name, (low, high, emoji) in REPUTATION_TIERS.items():
            if low <= rep_value <= high:
                pct = (rep_value - low) / (high - low) if high != low else 1.0
                filled = max(0, min(10, int(pct * 10)))
                progress_bar = f"{emoji} {'█' * filled}{'░' * (10 - filled)}"
                break

        # Get perks
        perks_result = await db.execute(
            select(FactionPerk).where(
                FactionPerk.faction_id == faction.id,
                FactionPerk.guild_id == interaction.guild_id,
            )
        )
        perks = perks_result.scalars().all()
        unlocked = [p for p in perks if REPUTATION_TIERS.get(p.required_tier, (0, 0, ""))[0] <= rep_value]

        embed = discord.Embed(
            title=f"{faction.icon_emoji or ''} {faction.name} — Status",
            description=faction.description[:200] if faction.description else "",
            color=int(faction.color.lstrip("#"), 16),
        )
        embed.add_field(name="Current Reputation", value=f"**{rep_value}** — {tier}", inline=False)
        embed.add_field(name="Progress", value=progress_bar or "Neutral", inline=False)
        if unlocked:
            perks_text = "\n".join(f"• {p.perk_type}: {p.perk_data.get('description', '')}" for p in unlocked[:5])
            embed.add_field(name="Unlocked Perks", value=perks_text, inline=False)

        await interaction.followup.send(embed=embed)


@faction_group.command(name="history", description="View your recent reputation changes")
@app_commands.describe(name="Faction name")
async def faction_history(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(
                Faction.guild_id == interaction.guild_id,
                Faction.name.ilike(name),
            )
        )
        faction = result.scalar_one_or_none()
        if not faction:
            await interaction.followup.send("Faction not found.", ephemeral=True)
            return

        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need an active character.", ephemeral=True)
            return

        rep_result = await db.execute(
            select(FactionReputation).where(
                FactionReputation.character_id == char.id,
                FactionReputation.faction_id == faction.id,
            )
        )
        rep = rep_result.scalar_one_or_none()
        rep_value = rep.reputation if rep else 0

        embed = discord.Embed(
            title=f"{faction.name} — Reputation",
            description=f"**Current:** {rep_value}",
            color=int(faction.color.lstrip("#"), 16),
        )
        embed.set_footer(text="Use /gm faction award to change reputation")

        await interaction.followup.send(embed=embed)


@faction_group.command(name="award", description="Award faction reputation to a player (GM only)")
@app_commands.describe(
    faction_name="Faction name",
    user="Target player",
    amount="Reputation amount (positive or negative)",
    reason="Reason for the change",
)
async def faction_award(
    interaction: discord.Interaction,
    faction_name: str,
    user: discord.Member,
    amount: int,
    reason: str = None,
):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can award faction reputation.", ephemeral=True)
        return

    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Faction).where(
                Faction.guild_id == interaction.guild_id,
                Faction.name.ilike(faction_name),
            )
        )
        faction = result.scalar_one_or_none()
        if not faction:
            await interaction.followup.send("Faction not found.", ephemeral=True)
            return

        char_result = await db.execute(
            select(Character).where(
                Character.user_id == user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send(f"{user.display_name} doesn't have an active character.", ephemeral=True)
            return

    new_rep, old_tier, new_tier = await change_reputation(
        char.id, interaction.guild_id, faction.id, amount, reason or "GM award"
    )

    msg = f"✅ **{amount}** reputation with **{faction.name}** for {user.mention}"
    if old_tier != new_tier:
        msg += f"\n⚡ Tier changed: **{old_tier}** → **{new_tier}**!"

    await interaction.followup.send(msg)


class FactionCog(commands.Cog, name="Faction"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(faction_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("faction")


async def setup(bot):
    await bot.add_cog(FactionCog(bot))
