import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, and_
from sqlalchemy.orm.attributes import flag_modified
from database.session import get_db
from database.models import Investigation, Clue, GuildGM
from services.utils import is_gm


investigation_group = app_commands.Group(
    name="investigation", description="Investigation and mystery system"
)


async def _autocomplete_investigations(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        return []
    async with get_db() as db:
        result = await db.execute(
            select(Investigation).where(
                Investigation.guild_id == interaction.guild_id,
                Investigation.name.ilike(f"%{current}%"),
                Investigation.status == "open",
            )
        )
        invs = result.scalars().all()
    return [app_commands.Choice(name=i.name[:80], value=str(i.id)) for i in invs[:25]]


@investigation_group.command(name="start", description="GM only: Start a new investigation")
@app_commands.describe(name="Investigation name", description="What's the mystery about?")
async def investigation_start(interaction: discord.Interaction, name: str, description: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can start investigations.", ephemeral=True)
        return
    async with get_db() as db:
        inv = Investigation(
            guild_id=interaction.guild_id,
            name=name,
            description=description,
            created_by=interaction.user.id,
        )
        db.add(inv)
        await db.commit()
        await db.refresh(inv)
    embed = discord.Embed(
        title=f"🔍 Investigation: {name}",
        description=description,
        color=0x8B5CF6,
    )
    embed.set_footer(text=f"Case #{inv.id} — Open")
    await interaction.followup.send(embed=embed)


@investigation_group.command(name="clue", description="Add a clue to an investigation")
@app_commands.describe(investigation_name="Investigation name", text="Clue text discovered")
async def investigation_clue(interaction: discord.Interaction, investigation_name: str, text: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(Investigation).where(
                Investigation.guild_id == interaction.guild_id,
                Investigation.name.ilike(f"%{investigation_name}%"),
            )
        )
        inv = result.scalar_one_or_none()
        if not inv or inv.status != "open":
            await interaction.followup.send(f"No open investigation found for '{investigation_name}'.", ephemeral=True)
            return
        clue = Clue(
            investigation_id=inv.id,
            guild_id=interaction.guild_id,
            discovered_by=interaction.user.id,
            text=text,
        )
        db.add(clue)
        await db.commit()
        await db.refresh(clue)
    embed = discord.Embed(
        title=f"🔍 Clue #{clue.id} Discovered",
        description=f"**Investigation:** {inv.name}\n\n{text}",
        color=0xFBBF24,
    )
    embed.set_footer(text=f"Discovered by {interaction.user.display_name}")
    await interaction.followup.send(embed=embed)


@investigation_group.command(name="board", description="Show the evidence board for an investigation")
@app_commands.describe(investigation_name="Investigation name")
async def investigation_board(interaction: discord.Interaction, investigation_name: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    async with get_db() as db:
        if investigation_name:
            result = await db.execute(
                select(Investigation).where(
                    Investigation.guild_id == interaction.guild_id,
                    Investigation.name.ilike(f"%{investigation_name}%"),
                )
            )
        else:
            result = await db.execute(
                select(Investigation).where(
                    Investigation.guild_id == interaction.guild_id,
                    Investigation.status == "open",
                ).order_by(Investigation.created_at.desc())
            )
        inv = result.scalar_one_or_none()
        if not inv:
            await interaction.followup.send("No investigation found.", ephemeral=True)
            return

        clues_result = await db.execute(
            select(Clue).where(Clue.investigation_id == inv.id).order_by(Clue.discovered_at)
        )
        clues = list(clues_result.scalars().all())

    embed = discord.Embed(
        title=f"🔍 Evidence Board: {inv.name}",
        description=inv.description or "No description.",
        color=0x8B5CF6,
    )
    embed.add_field(name="Status", value=inv.status.capitalize(), inline=True)
    embed.add_field(name="Clues Found", value=str(len(clues)), inline=True)

    for i, clue in enumerate(clues[:10], 1):
        connections_text = ""
        if clue.connections:
            conn_ids = ", ".join(str(c) for c in clue.connections)
            connections_text = f"\n🔗 Connected to clue(s): {conn_ids}"
        embed.add_field(
            name=f"Clue #{clue.id}",
            value=f"{clue.text[:200]}{connections_text}",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@investigation_group.command(name="connect", description="Link two clues together")
@app_commands.describe(clue_id_a="First clue ID", clue_id_b="Second clue ID")
async def investigation_connect(interaction: discord.Interaction, clue_id_a: int, clue_id_b: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        clue_a = await db.execute(select(Clue).where(Clue.id == clue_id_a))
        clue_a = clue_a.scalar_one_or_none()
        clue_b = await db.execute(select(Clue).where(Clue.id == clue_id_b))
        clue_b = clue_b.scalar_one_or_none()

        if not clue_a or not clue_b or clue_a.investigation_id != clue_b.investigation_id:
            await interaction.followup.send("Both clues must exist and belong to the same investigation.", ephemeral=True)
            return

        if clue_id_b not in clue_a.connections:
            clue_a.connections = clue_a.connections + [clue_id_b]
            flag_modified(clue_a, "connections")
        if clue_id_a not in clue_b.connections:
            clue_b.connections = clue_b.connections + [clue_id_a]
            flag_modified(clue_b, "connections")
        await db.commit()

    await interaction.followup.send(f"🔗 Linked Clue #{clue_id_a} ↔ Clue #{clue_id_b}!")


@investigation_group.command(name="theory", description="Submit a theory to the GM for review")
@app_commands.describe(investigation_name="Investigation name", text="Your theory")
async def investigation_theory(interaction: discord.Interaction, investigation_name: str, text: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        result = await db.execute(
            select(Investigation).where(
                Investigation.guild_id == interaction.guild_id,
                Investigation.name.ilike(f"%{investigation_name}%"),
            )
        )
        inv = result.scalar_one_or_none()
        if not inv:
            await interaction.followup.send("Investigation not found.", ephemeral=True)
            return

        # Find GMs to notify
        gm_result = await db.execute(
            select(GuildGM).where(GuildGM.guild_id == interaction.guild_id)
        )
        gms = list(gm_result.scalars().all())

    embed = discord.Embed(
        title=f"🧠 Theory Submitted: {inv.name}",
        description=text,
        color=0x6366F1,
    )
    embed.set_footer(text=f"Submitted by {interaction.user.display_name}")

    # DM all GMs
    for gm in gms:
        try:
            user = await interaction.client.fetch_user(gm.user_id)
            await user.send(embed=embed)
        except Exception:
            pass

    await interaction.followup.send("📨 Your theory has been sent to the GMs for review!", ephemeral=True)


@investigation_group.command(name="reveal", description="GM only: Reveal the truth")
@app_commands.describe(investigation_name="Investigation name", revelation_text="The big reveal")
async def investigation_reveal(interaction: discord.Interaction, investigation_name: str, revelation_text: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can reveal investigations.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(Investigation).where(
                Investigation.guild_id == interaction.guild_id,
                Investigation.name.ilike(f"%{investigation_name}%"),
            )
        )
        inv = result.scalar_one_or_none()
        if not inv:
            await interaction.followup.send("Investigation not found.", ephemeral=True)
            return
        inv.status = "solved"
        await db.commit()

    embed = discord.Embed(
        title=f"🎭 Case Closed: {inv.name}",
        description=revelation_text,
        color=0x10B981,
    )
    embed.set_footer(text=f"Solved by {interaction.user.display_name}")

    await interaction.followup.send(embed=embed)


@investigation_group.command(name="list", description="List all open investigations")
async def investigation_list(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Investigation).where(
                Investigation.guild_id == interaction.guild_id,
            ).order_by(Investigation.created_at.desc())
        )
        invs = list(result.scalars().all())

    if not invs:
        await interaction.followup.send("No investigations found in this world.")
        return

    embed = discord.Embed(title="🔍 Investigations", color=0x8B5CF6)
    for inv in invs[:10]:
        status_icon = {"open": "🔍", "solved": "✅", "closed": "❌"}.get(inv.status, "❓")
        embed.add_field(
            name=f"{status_icon} {inv.name}",
            value=f"Status: {inv.status.capitalize()}\n{inv.description or ''}",
            inline=False,
        )
    await interaction.followup.send(embed=embed)


class InvestigationCog(commands.Cog, name="Investigation"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(investigation_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("investigation")


async def setup(bot):
    await bot.add_cog(InvestigationCog(bot))
