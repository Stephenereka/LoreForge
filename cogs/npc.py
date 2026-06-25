import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete
from database.session import get_db
from database.models import (
    NPC, NPCMemory, NPCWebhookCache, Location, CharacterLocation, Character,
)
from services.utils import is_gm
from services.npc_service import get_npc_response, update_npc_memory, send_npc_proxy_message
import datetime
import re

npc_group = app_commands.Group(name="npc", description="NPC management and interaction")


async def get_active_char(user_id: int, guild_id: int):
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


async def _npc_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(f"%{current}%"),
            ).limit(25)
        )
        npcs = result.scalars().all()
    return [app_commands.Choice(name=f"{n.name} ({n.title or 'No title'})", value=n.name) for n in npcs]


@npc_group.command(name="create", description="Create a new NPC (GM only)")
@app_commands.describe(name="NPC name", location="Location name")
@app_commands.autocomplete(location=_npc_autocomplete)
async def npc_create(interaction: discord.Interaction, name: str, location: str = None):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can create NPCs.", ephemeral=True)
        return

    location_id = None
    if location:
        async with get_db() as db:
            loc_result = await db.execute(
                select(Location).where(
                    Location.guild_id == interaction.guild_id,
                    Location.name.ilike(location),
                )
            )
            loc_obj = loc_result.scalar_one_or_none()
            if loc_obj:
                location_id = loc_obj.id

    await interaction.response.send_modal(NPCCreateModal(name, location_id, interaction.guild_id, interaction.user.id))


class NPCCreateModal(discord.ui.Modal, title="Create NPC"):
    title_ = discord.ui.TextInput(label="Title", required=False, max_length=100)
    race = discord.ui.TextInput(label="Race", required=False, max_length=50)
    gender = discord.ui.TextInput(label="Gender", required=False, max_length=20)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)
    appearance = discord.ui.TextInput(label="Appearance", style=discord.TextStyle.long, required=False)
    disposition = discord.ui.TextInput(label="Disposition (friendly/neutral/hostile)", max_length=20, default="neutral")
    greeting = discord.ui.TextInput(label="Greeting text", style=discord.TextStyle.short, required=False)
    image_url = discord.ui.TextInput(label="Image URL", required=False, max_length=500)

    def __init__(self, name: str, location_id: int, guild_id: int, user_id: int):
        super().__init__()
        self._name = name
        self._location_id = location_id
        self._guild_id = guild_id
        self._user_id = user_id

    async def on_submit(self, interaction: discord.Interaction):
        async with get_db() as db:
            db.add(NPC(
                guild_id=self._guild_id,
                name=self._name,
                title=self.title_.value or None,
                race=self.race.value or None,
                gender=self.gender.value or None,
                description=self.description.value,
                appearance=self.appearance.value or None,
                location_id=self._location_id or 0,
                disposition=self.disposition.value or "neutral",
                greeting=self.greeting.value or None,
                image_url=self.image_url.value or None,
                is_hostile=self.disposition.value == "hostile",
                created_by=self._user_id,
            ))

        await interaction.response.send_message(f"✅ NPC **{self._name}** created!", ephemeral=True)


@npc_group.command(name="edit", description="Edit an NPC (GM only)")
@app_commands.describe(name="NPC name")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_edit(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can edit NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
    await interaction.response.send_modal(NPCEditModal(npc))


class NPCEditModal(discord.ui.Modal, title="Edit NPC"):
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)
    appearance = discord.ui.TextInput(label="Appearance", style=discord.TextStyle.long, required=False)
    greeting = discord.ui.TextInput(label="Greeting", required=False)
    disposition = discord.ui.TextInput(label="Disposition", max_length=20)

    def __init__(self, npc: NPC):
        super().__init__()
        self._npc_id = npc.id
        self.description.default = npc.description
        self.appearance.default = npc.appearance or ""
        self.greeting.default = npc.greeting or ""
        self.disposition.default = npc.disposition

    async def on_submit(self, interaction: discord.Interaction):
        async with get_db() as db:
            result = await db.execute(select(NPC).where(NPC.id == self._npc_id))
            npc = result.scalar_one_or_none()
            if npc:
                npc.description = self.description.value
                npc.appearance = self.appearance.value or None
                npc.greeting = self.greeting.value or None
                npc.disposition = self.disposition.value
        await interaction.response.send_message("✅ NPC updated.", ephemeral=True)


@npc_group.command(name="move", description="Move an NPC to a different location (GM only)")
@app_commands.describe(name="NPC name", location="Destination location")
async def npc_move(interaction: discord.Interaction, name: str, location: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can move NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        npc_result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = npc_result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        loc_result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.name.ilike(location),
            )
        )
        loc = loc_result.scalar_one_or_none()
        if not loc:
            await interaction.response.send_message("Location not found.", ephemeral=True)
            return
        npc.location_id = loc.id
    await interaction.response.send_message(f"✅ **{name}** moved to **{loc.name}**.")


@npc_group.command(name="kill", description="Mark an NPC as dead (GM only)")
@app_commands.describe(name="NPC name")
async def npc_kill(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can kill NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        if not npc.is_killable:
            await interaction.response.send_message("This NPC cannot be killed.", ephemeral=True)
            return
        npc.is_dead = True
    await interaction.response.send_message(f"💀 **{name}** has been killed.")


@npc_group.command(name="revive", description="Revive a dead NPC (GM only)")
@app_commands.describe(name="NPC name")
async def npc_revive(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can revive NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        npc.is_dead = False
        npc.hp_current = npc.hp_max
    await interaction.response.send_message(f"✨ **{name}** has been revived.")


@npc_group.command(name="list", description="List NPCs")
@app_commands.describe(location="Filter by location name (optional)")
async def npc_list(interaction: discord.Interaction, location: str = None):
    async with get_db() as db:
        query = select(NPC).where(NPC.guild_id == interaction.guild_id, NPC.is_dead == False)
        if location:
            loc_result = await db.execute(
                select(Location).where(
                    Location.guild_id == interaction.guild_id,
                    Location.name.ilike(location),
                )
            )
            loc = loc_result.scalar_one_or_none()
            if loc:
                query = query.where(NPC.location_id == loc.id)
        query = query.order_by(NPC.name).limit(25)
        result = await db.execute(query)
        npcs = result.scalars().all()

    if not npcs:
        await interaction.response.send_message("No NPCs found.", ephemeral=True)
        return

    embed = discord.Embed(title="👥 NPCs", color=0xA855F7)
    for npc in npcs:
        loc_name = "Unknown"
        if npc.location_id:
            async with get_db() as db2:
                lr = await db2.execute(select(Location).where(Location.id == npc.location_id))
                lo = lr.scalar_one_or_none()
                if lo:
                    loc_name = lo.name
        name_str = f"{'💀 ' if npc.is_dead else ''}{npc.name}"
        if npc.title:
            name_str += f" ({npc.title})"
        embed.add_field(
            name=name_str,
            value=f"{npc.race or 'Unknown'}  ·  {npc.disposition}  ·  📍 {loc_name}",
            inline=False,
        )

    await interaction.response.send_message(embed=embed)


@npc_group.command(name="info", description="View full NPC info (GM only)")
@app_commands.describe(name="NPC name")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_info(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can view full NPC info.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return

        loc_name = "Unknown"
        if npc.location_id:
            lr = await db.execute(select(Location).where(Location.id == npc.location_id))
            lo = lr.scalar_one_or_none()
            if lo:
                loc_name = lo.name

    embed = discord.Embed(
        title=f"👤 {npc.name}",
        description=npc.description[:1000],
        color=0xA855F7,
    )
    embed.add_field(name="Title", value=npc.title or "None", inline=True)
    embed.add_field(name="Race", value=npc.race or "Unknown", inline=True)
    embed.add_field(name="Gender", value=npc.gender or "Unknown", inline=True)
    embed.add_field(name="Location", value=loc_name, inline=True)
    embed.add_field(name="Disposition", value=npc.disposition, inline=True)
    embed.add_field(name="Dead", value="💀 Yes" if npc.is_dead else "✅ No", inline=True)
    embed.add_field(name="HP", value=f"{npc.hp_current}/{npc.hp_max}", inline=True)
    embed.add_field(name="AC", value=npc.armor_class, inline=True)
    embed.add_field(name="Attack", value=f"+{npc.attack_bonus}  {npc.damage_dice}+{npc.damage_bonus}", inline=True)
    if npc.greeting:
        embed.add_field(name="Greeting", value=npc.greeting, inline=False)
    if npc.dialogue_topics:
        topics = list(npc.dialogue_topics.keys())[:5]
        embed.add_field(name="Dialogue Topics", value=", ".join(topics), inline=False)
    if npc.image_url:
        embed.set_thumbnail(url=npc.image_url)
    if npc.appearance:
        embed.add_field(name="Appearance", value=npc.appearance[:500], inline=False)

    embed.set_footer(text=f"Proxy: {npc.proxy_mode}  ·  Prefix: {npc.proxy_prefix or 'None'}")
    await interaction.response.send_message(embed=embed)


@npc_group.command(name="set-attitude", description="Set your attitude toward an NPC")
@app_commands.describe(name="NPC name", user="Target user", value="Attitude value (-10 to 10)")
async def npc_set_attitude(interaction: discord.Interaction, name: str, user: discord.Member, value: int):
    value = max(-10, min(10, value))
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return

        mem_result = await db.execute(
            select(NPCMemory).where(
                NPCMemory.npc_id == npc.id,
                NPCMemory.user_id == user.id,
            )
        )
        mem = mem_result.scalar_one_or_none()
        if mem:
            mem.attitude = value
        else:
            db.add(NPCMemory(
                npc_id=npc.id,
                user_id=user.id,
                guild_id=interaction.guild_id,
                first_met=datetime.datetime.utcnow(),
                last_spoke=datetime.datetime.utcnow(),
                interaction_count=0,
                attitude=value,
            ))

    await interaction.response.send_message(f"✅ Attitude toward {user.mention} set to **{value}** for **{name}**.")


@npc_group.command(name="add-dialogue", description="Add a dialogue topic to an NPC (GM only)")
@app_commands.describe(name="NPC name", keyword="Keyword to trigger the response", response="NPC's response text")
async def npc_add_dialogue(interaction: discord.Interaction, name: str, keyword: str, response: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can add dialogue.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        topics = dict(npc.dialogue_topics or {})
        topics[keyword.lower()] = response
        npc.dialogue_topics = topics
    await interaction.response.send_message(f"✅ Added dialogue keyword **{keyword}** for **{name}**.")


@npc_group.command(name="talk", description="Talk to an NPC")
@app_commands.describe(name="NPC name", message="What you want to say")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_talk(interaction: discord.Interaction, name: str, message: str = None):
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
                NPC.is_dead == False,
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.followup.send("NPC not found or is dead.", ephemeral=True)
            return

        # Get or create NPC memory
        mem_result = await db.execute(
            select(NPCMemory).where(
                NPCMemory.npc_id == npc.id,
                NPCMemory.user_id == interaction.user.id,
            )
        )
        mem = mem_result.scalar_one_or_none()
        if not mem:
            mem = NPCMemory(
                npc_id=npc.id,
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                first_met=datetime.datetime.utcnow(),
                last_spoke=datetime.datetime.utcnow(),
            )
            db.add(mem)
            await db.flush()
            # First meeting — use greeting
            response = npc.greeting or f"Hello there, traveler."
        else:
            mem.last_spoke = datetime.datetime.utcnow()
            mem.interaction_count = (mem.interaction_count or 0) + 1

            # AI dialogue if enabled
            from database.models import AIConfig
            ai_result = await db.execute(
                select(AIConfig).where(AIConfig.guild_id == interaction.guild_id)
            )
            ai_config = ai_result.scalar_one_or_none()

            if ai_config and ai_config.npc_ai_enabled and message:
                from services import ai_service
                # Get lore snippets
                lore_snippets = ""
                try:
                    from database.models import LoreEntry
                    lore_result = await db.execute(
                        select(LoreEntry).where(
                            LoreEntry.guild_id == interaction.guild_id,
                            LoreEntry.visibility == "public",
                        ).limit(3)
                    )
                    lore_entries = lore_result.scalars().all()
                    lore_snippets = ". ".join(e.title + ": " + e.content[:100] for e in lore_entries)
                except Exception:
                    pass

                # Get player character name
                player_char = await get_active_char(interaction.user.id, interaction.guild_id)
                player_name = player_char.name if player_char else interaction.user.display_name

                ai_response = await ai_service.generate_npc_dialogue(
                    npc_name=npc.name,
                    race=npc.race or "unknown",
                    title=npc.title or "",
                    personality_traits=npc.description[:200] if npc.description else "",
                    speaking_style=npc.disposition or "neutral",
                    attitude=mem.attitude or 0,
                    interaction_count=mem.interaction_count or 0,
                    last_topic=mem.last_topic or "",
                    lore_snippets=lore_snippets,
                    player_name=player_name,
                    player_message=message,
                )
                if ai_response:
                    response = ai_response
                    mem.last_topic = message[:100]
                else:
                    # AI returned empty — fall through to keyword matching
                    response = get_npc_response(npc, message, mem) if message else (npc.greeting or "Yes? What is it?")
            elif message:
                response = get_npc_response(npc, message, mem)
            else:
                response = npc.greeting or "Yes? What is it?"

    # Send as embed if no proxy
    embed = discord.Embed(
        title=f"💬 {npc.name}" + (f" ({npc.title})" if npc.title else ""),
        description=f"> {message or '...'}\n\n*{response}*" if response else "*The NPC says nothing.*",
        color=0xA855F7,
    )
    if npc.image_url:
        embed.set_thumbnail(url=npc.image_url)

    # If automatic proxy mode, send as webhook
    if npc.proxy_mode == "automatic" and npc.proxy_name:
        await send_npc_proxy_message(
            interaction.client, interaction.channel, npc, response or "..."
        )
        await interaction.followup.send(
            embed=discord.Embed(description=f"💬 You speak to **{npc.name}**.", color=0xA855F7),
            ephemeral=True,
        )
    else:
        await interaction.followup.send(embed=embed)


@npc_group.command(name="look", description="Look at an NPC's appearance")
@app_commands.describe(name="NPC name")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_look(interaction: discord.Interaction, name: str):
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
                NPC.is_dead == False,
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return

    embed = discord.Embed(
        title=f"👀 {npc.name}" + (f" ({npc.title})" if npc.title else ""),
        description=npc.appearance or npc.description[:500] or "No visible details.",
        color=0xA855F7,
    )
    if npc.image_url:
        embed.set_image(url=npc.image_url)

    await interaction.response.send_message(embed=embed)


@npc_group.command(name="nearby", description="See all NPCs at your current location")
async def npc_nearby(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    char = await get_active_char(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send(
            "No active character. Use `/character create` first.", ephemeral=True
        )
        return

    async with get_db() as db:
        cl_result = await db.execute(
            select(CharacterLocation).where(
                CharacterLocation.character_id == char.id,
                CharacterLocation.guild_id == interaction.guild_id,
            )
        )
        cl = cl_result.scalar_one_or_none()
        if not cl:
            await interaction.followup.send(
                "You're not at any location yet. Use `/travel` to explore.", ephemeral=True
            )
            return

        npc_result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.location_id == cl.location_id,
                NPC.is_dead == False,
            )
        )
        npcs = npc_result.scalars().all()

        loc_result = await db.execute(select(Location).where(Location.id == cl.location_id))
        loc = loc_result.scalar_one_or_none()

    if not npcs:
        await interaction.followup.send(
            f"No one notable is at **{loc.name if loc else 'your location'}** right now.",
            ephemeral=True,
        )
        return

    DISPOSITION_ICON = {
        "friendly": "😊", "neutral": "😐", "hostile": "😠",
        "wary": "😒", "fearful": "😨",
    }
    embed = discord.Embed(
        title=f"👥 People at {loc.name if loc else 'Your Location'}",
        color=0xA855F7,
    )
    for n in npcs:
        icon = DISPOSITION_ICON.get(n.disposition, "😐")
        lines = []
        if n.race:
            lines.append(f"*{n.race}*")
        if n.title:
            lines.append(n.title)
        if n.is_hostile:
            lines.append("⚠️ **Hostile**")
        lines.append(f"{icon} {n.disposition.capitalize()}")
        if n.greeting:
            lines.append(f'*"{n.greeting[:80]}{"..." if len(n.greeting) > 80 else ""}"*')
        embed.add_field(name=n.name, value="\n".join(lines), inline=True)

    embed.set_footer(text="Use /npc talk <name> to speak with them · LoreForge")
    await interaction.followup.send(embed=embed, ephemeral=True)


@npc_group.command(name="proxy-set", description="Configure NPC webhook display name, avatar, and prefix (GM only)")
@app_commands.describe(name="NPC name", proxy_name="Webhook display name", avatar_url="Avatar image URL", prefix="Prefix for manual mode (e.g. aldric>)")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_proxy_set(interaction: discord.Interaction, name: str, proxy_name: str, avatar_url: str = None, prefix: str = None):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can configure NPC proxies.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        npc.proxy_name = proxy_name
        if avatar_url:
            npc.proxy_avatar = avatar_url
        if prefix:
            npc.proxy_prefix = prefix

    embed = discord.Embed(
        title=f"✅ Proxy configured for {npc.name}",
        color=0x22C55E,
    )
    embed.add_field(name="Display Name", value=proxy_name, inline=True)
    if avatar_url:
        embed.add_field(name="Avatar", value="Set ✓", inline=True)
        embed.set_thumbnail(url=avatar_url)
    if prefix:
        embed.add_field(name="Prefix", value=f"`{prefix}`", inline=True)
    embed.set_footer(text="Use /npc mode to switch between automatic and manual · LoreForge")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@npc_group.command(name="speak", description="Speak as an NPC via webhook (GM only)")
@app_commands.describe(name="NPC name", message="What the NPC says")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_speak(interaction: discord.Interaction, name: str, message: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can speak as NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return

    success = await send_npc_proxy_message(interaction.client, interaction.channel, npc, message)
    if success:
        await interaction.response.send_message(f"✅ Spoke as **{npc.name}**.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ Failed to send — make sure the bot has **Manage Webhooks** permission in this channel.",
            ephemeral=True,
        )


@npc_group.command(name="act", description="Post a roleplay action as an NPC (GM only)")
@app_commands.describe(name="NPC name", action="What the NPC does (e.g. 'draws her sword')")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_act(interaction: discord.Interaction, name: str, action: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can act as NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return

    text = f"*{npc.proxy_name or npc.name} {action}*"
    success = await send_npc_proxy_message(interaction.client, interaction.channel, npc, text)
    if success:
        await interaction.response.send_message(f"✅ Action posted as **{npc.name}**.", ephemeral=True)
    else:
        await interaction.response.send_message(
            "❌ Failed to post — check **Manage Webhooks** permission.",
            ephemeral=True,
        )


@npc_group.command(name="possess", description="Claim an NPC to control via prefix (GM only)")
@app_commands.describe(name="NPC name — you'll then type its prefix to speak as it")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_possess(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can possess NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        npc.gm_user_id = interaction.user.id
        npc.proxy_mode = "manual"
        prefix = npc.proxy_prefix or f"{npc.name.lower().split()[0]}>"

    embed = discord.Embed(
        title=f"🎭 Possessing {npc.name}",
        description=(
            f"You are now controlling **{npc.name}**.\n\n"
            f"Type `{prefix} <message>` in any channel to speak as them.\n"
            f"Your original message will be deleted automatically.\n\n"
            f"Use `/npc release {npc.name}` to stop."
        ),
        color=0x8B5CF6,
    )
    embed.set_footer(text="Proxy mode set to Manual · LoreForge")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@npc_group.command(name="release", description="Stop controlling an NPC (GM only)")
@app_commands.describe(name="NPC name")
@app_commands.autocomplete(name=_npc_autocomplete)
async def npc_release(interaction: discord.Interaction, name: str):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can release NPCs.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        npc.gm_user_id = None
    await interaction.response.send_message(
        f"✅ Released control of **{npc.name}**.", ephemeral=True
    )


@npc_group.command(name="mode", description="Switch NPC proxy between automatic and manual (GM only)")
@app_commands.describe(name="NPC name", mode="automatic = AI/keyword responds on /npc talk; manual = GM types prefix to speak")
@app_commands.autocomplete(name=_npc_autocomplete)
@app_commands.choices(mode=[
    app_commands.Choice(name="Automatic — bot responds on /npc talk", value="automatic"),
    app_commands.Choice(name="Manual — GM controls via prefix", value="manual"),
])
async def npc_mode(interaction: discord.Interaction, name: str, mode: app_commands.Choice[str]):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can change NPC mode.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(NPC).where(
                NPC.guild_id == interaction.guild_id,
                NPC.name.ilike(name),
            )
        )
        npc = result.scalar_one_or_none()
        if not npc:
            await interaction.response.send_message("NPC not found.", ephemeral=True)
            return
        npc.proxy_mode = mode.value

    if mode.value == "manual":
        prefix = npc.proxy_prefix or f"{npc.name.lower().split()[0]}>"
        detail = f"Type `{prefix} <message>` to speak as them (use `/npc possess` to claim control)."
    else:
        detail = "The NPC will respond automatically when players use `/npc talk`."

    embed = discord.Embed(
        title=f"🔄 {npc.name} — Mode Updated",
        description=f"Proxy mode set to **{mode.value}**.\n{detail}",
        color=0x22C55E,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


class NPCCog(commands.Cog, name="NPC"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(npc_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("npc")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild or message.author.bot:
            return

        # Check for NPC proxy prefix matching (manual mode)
        prefix_result = None
        async with get_db() as db:
            result = await db.execute(
                select(NPC).where(
                    NPC.guild_id == message.guild.id,
                    NPC.proxy_prefix.isnot(None),
                    NPC.proxy_mode == "manual",
                    NPC.gm_user_id == message.author.id,
                )
            )
            npcs = result.scalars().all()

        for npc in npcs:
            prefix = npc.proxy_prefix
            if prefix and message.content.startswith(prefix):
                content = message.content[len(prefix):].strip()
                if content:
                    await send_npc_proxy_message(
                        self.bot, message.channel, npc, content
                    )
                    try:
                        await message.delete()
                    except Exception:
                        pass
                break


async def setup(bot):
    await bot.add_cog(NPCCog(bot))
