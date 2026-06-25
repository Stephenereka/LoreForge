import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete
from database.session import get_db
from database.models import PartyGroup, PartyMember, Character, CharacterLocation
from services.utils import is_gm

party_group = app_commands.Group(name="party", description="Party commands")


async def get_active_character(user_id: int, guild_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == user_id,
                Character.guild_id == guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        return result.scalar_one_or_none()


async def get_player_party(character_id: int, guild_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(PartyMember).where(
                PartyMember.character_id == character_id,
                PartyMember.guild_id == guild_id,
            )
        )
        member = result.scalar_one_or_none()
        if not member:
            return None, None
        party_result = await db.execute(
            select(PartyGroup).where(PartyGroup.id == member.party_id)
        )
        party = party_result.scalar_one_or_none()
        return party, member


@party_group.command(name="create", description="Create a new party")
@app_commands.describe(name="Optional name for your party")
async def party_create(interaction: discord.Interaction, name: str = None):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character first.", ephemeral=True)
        return

    party, _ = await get_player_party(char.id, interaction.guild_id)
    if party:
        await interaction.followup.send("You're already in a party. Leave it first.", ephemeral=True)
        return

    async with get_db() as db:
        party = PartyGroup(
            guild_id=interaction.guild_id,
            leader_character_id=char.id,
            name=name or f"{char.name}'s Party",
        )
        db.add(party)
        await db.flush()
        db.add(PartyMember(
            party_id=party.id,
            character_id=char.id,
            guild_id=interaction.guild_id,
        ))

    await interaction.followup.send(
        f"✅ Party **{party.name}** created! Invite others with `/party invite @user`."
    )


@party_group.command(name="invite", description="Invite a user to your party")
@app_commands.describe(user="The user to invite")
async def party_invite(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    party, member = await get_player_party(char.id, interaction.guild_id)
    if not party or party.leader_character_id != char.id:
        await interaction.followup.send("Only the party leader can invite.", ephemeral=True)
        return

    target_char = await get_active_character(user.id, interaction.guild_id)
    if not target_char:
        await interaction.followup.send(f"{user.display_name} doesn't have an active character.", ephemeral=True)
        return

    target_party, _ = await get_player_party(target_char.id, interaction.guild_id)
    if target_party:
        await interaction.followup.send(f"{user.display_name} is already in a party.", ephemeral=True)
        return

    async with get_db() as db:
        db.add(PartyMember(
            party_id=party.id,
            character_id=target_char.id,
            guild_id=interaction.guild_id,
        ))

    await interaction.followup.send(
        f"✅ {user.mention} joined **{party.name}**!"
    )


@party_group.command(name="leave", description="Leave your current party")
async def party_leave(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    party, member = await get_player_party(char.id, interaction.guild_id)
    if not party:
        await interaction.followup.send("You're not in a party.", ephemeral=True)
        return

    async with get_db() as db:
        await db.execute(
            delete(PartyMember).where(PartyMember.id == member.id)
        )

        # Check if party is empty now
        remaining = await db.execute(
            select(PartyMember).where(PartyMember.party_id == party.id)
        )
        if not remaining.scalars().first():
            await db.execute(
                delete(PartyGroup).where(PartyGroup.id == party.id)
            )

    await interaction.followup.send("You left the party.")


@party_group.command(name="disband", description="Disband your party (leader only)")
async def party_disband(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    party, _ = await get_player_party(char.id, interaction.guild_id)
    if not party or party.leader_character_id != char.id:
        await interaction.followup.send("Only the party leader can disband.", ephemeral=True)
        return

    async with get_db() as db:
        await db.execute(
            delete(PartyMember).where(PartyMember.party_id == party.id)
        )
        await db.execute(
            delete(PartyGroup).where(PartyGroup.id == party.id)
        )

    await interaction.followup.send(f"✅ Party **{party.name}** disbanded.")


@party_group.command(name="status", description="See party status")
async def party_status(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    party, member = await get_player_party(char.id, interaction.guild_id)
    if not party:
        await interaction.followup.send("You're not in a party.", ephemeral=True)
        return

    async with get_db() as db:
        members = await db.execute(
            select(PartyMember).where(PartyMember.party_id == party.id)
        )
        member_rows = members.scalars().all()
        embed = discord.Embed(title=f"👥 {party.name}", color=0x6366F1)
        for mem in member_rows:
            char_result = await db.execute(
                select(Character).where(Character.id == mem.character_id)
            )
            c = char_result.scalar_one_or_none()
            if c:
                loc_result = await db.execute(
                    select(CharacterLocation).where(CharacterLocation.character_id == c.id)
                )
                loc = loc_result.scalar_one_or_none()
                loc_name = f"Location #{loc.location_id}" if loc else "Unknown"
                leader_mark = " 👑" if c.id == party.leader_character_id else ""
                embed.add_field(
                    name=f"{c.name}{leader_mark}",
                    value=f"❤️ {c.hp_current}/{c.hp_max}  🏠 {loc_name}",
                    inline=True,
                )

    await interaction.followup.send(embed=embed)


@party_group.command(name="travel", description="Travel as a party (leader only)")
@app_commands.describe(direction="Direction or location name to travel to")
async def party_travel(interaction: discord.Interaction, direction: str):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    party, member = await get_player_party(char.id, interaction.guild_id)
    if not party or party.leader_character_id != char.id:
        await interaction.followup.send("Only the party leader can lead travel.", ephemeral=True)
        return

    async with get_db() as db:
        members = await db.execute(
            select(PartyMember).where(PartyMember.party_id == party.id)
        )
        member_rows = members.scalars().all()

        # Find leader's current location
        loc_result = await db.execute(
            select(CharacterLocation).where(CharacterLocation.character_id == char.id)
        )
        leader_loc = loc_result.scalar_one_or_none()
        if not leader_loc:
            await interaction.followup.send("You don't have a location set.", ephemeral=True)
            return

        # For each member, update their location to match leader's destination
        for mem in member_rows:
            if mem.character_id == char.id:
                continue
            await db.execute(
                delete(CharacterLocation).where(CharacterLocation.character_id == mem.character_id)
            )
            db.add(CharacterLocation(
                character_id=mem.character_id,
                guild_id=interaction.guild_id,
                location_id=leader_loc.location_id,
            ))

    await interaction.followup.send(
        f"✅ The party follows you traveling **{direction}**!"
    )


class PartyCog(commands.Cog, name="Party"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(party_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("party")


async def setup(bot):
    await bot.add_cog(PartyCog(bot))
