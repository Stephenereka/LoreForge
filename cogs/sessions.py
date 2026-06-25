import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, desc
from datetime import datetime
from database.session import get_db
from database.models import SessionLog, AIConfig, Character
from services.utils import gm_only
from services.ai_service import summarize_session

session_group = app_commands.Group(name="session", description="Session management (GM only)")


async def _get_characters_at_location(guild_id: int) -> list[str]:
    """Get names of active characters in the guild."""
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        return [c.name for c in result.scalars().all()]


@session_group.command(name="start", description="Mark the start of a play session (GM only)")
@app_commands.describe(title="Optional title for this session")
async def session_start(interaction: discord.Interaction, title: str | None = None):
    if not await gm_only(interaction):
        return

    chars = await _get_characters_at_location(interaction.guild_id)
    async with get_db() as db:
        log = SessionLog(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            title=title or f"Session {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            started_at=datetime.utcnow(),
            characters_present=chars,
            created_by=interaction.user.id,
        )
        db.add(log)
        await db.flush()
        session_id = log.id

    embed = discord.Embed(
        title="📜 Session Started",
        description=f"**{title or 'Untitled Session'}** has begun!\n\n"
                    f"**Characters present:** {', '.join(chars) if chars else 'None yet'}\n"
                    f"Use `/session end` when the session is over.",
        color=0x22C55E,
    )
    embed.set_footer(text=f"Session ID: {session_id} • LoreForge")
    await interaction.response.send_message(embed=embed)
    # Pin the embed
    try:
        await interaction.channel.pins()
    except Exception:
        pass


@session_group.command(name="end", description="End the active session and generate a summary (GM only)")
async def session_end(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(SessionLog).where(
                SessionLog.guild_id == interaction.guild_id,
                SessionLog.channel_id == interaction.channel_id,
                SessionLog.ended_at.is_(None),
            ).order_by(desc(SessionLog.started_at)).limit(1)
        )
        log = result.scalar_one_or_none()

        if not log:
            await interaction.response.send_message(
                "No active session found in this channel. Use `/session start` first.",
                ephemeral=True,
            )
            return

        log.ended_at = datetime.utcnow()

        # Check if AI summaries are enabled
        ai_config = await db.execute(
            select(AIConfig).where(AIConfig.guild_id == interaction.guild_id)
        )
        config = ai_config.scalar_one_or_none()
        ai_enabled = config and config.session_summary_enabled

    # Try to generate summary
    summary_text = None
    if ai_enabled:
        last_messages = []
        try:
            async for msg in interaction.channel.history(limit=100):
                if not msg.author.bot:
                    last_messages.append(f"{msg.author.display_name}: {msg.content}")
                elif msg.embeds:
                    for e in msg.embeds:
                        if e.title and ("HP" in e.title or "HIT" in e.title or "damage" in (e.description or "")):
                            last_messages.append(f"[Combat Event] {e.title}: {e.description}")
        except Exception:
            pass

        message_text = "\n".join(last_messages[-80:])
        summary_text = await summarize_session(
            messages_text=message_text,
            characters=log.characters_present or [],
            location=interaction.channel.name,
            combat_count=log.combat_count or 0,
            quest_completions=log.quest_completions or 0,
            total_xp=log.total_xp or 0,
        )

    async with get_db() as db:
        result = await db.execute(
            select(SessionLog).where(SessionLog.id == log.id)
        )
        log = result.scalar_one_or_none()
        if log and summary_text:
            log.summary_text = summary_text

    embed = discord.Embed(
        title=f"📜 Session Ended — {log.title if log else 'Session'}",
        color=0x6366F1,
    )
    embed.add_field(name="⏱️ Duration", value="Active", inline=True)
    embed.add_field(name="⚔️ Combats", value=str(log.combat_count or 0), inline=True)
    embed.add_field(name="📋 Quests", value=str(log.quest_completions or 0), inline=True)
    embed.add_field(name="✨ XP Earned", value=str(log.total_xp or 0), inline=True)
    embed.add_field(name="🎭 Characters", value=", ".join(log.characters_present or []) or "None", inline=False)

    if summary_text:
        embed.add_field(name="📖 Summary", value=summary_text, inline=False)
    elif log.summary_text:
        embed.add_field(name="📖 Summary", value=log.summary_text, inline=False)
    else:
        embed.add_field(name="📖 Summary", value="*No AI summary available. Toggle summaries with `/ai toggle summary`.*", inline=False)

    embed.set_footer(text="LoreForge Session Log")
    await interaction.response.send_message(embed=embed)


@session_group.command(name="summary", description="Generate or regenerate the summary for the most recent session")
async def session_summary(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(SessionLog).where(
                SessionLog.guild_id == interaction.guild_id,
                SessionLog.channel_id == interaction.channel_id,
            ).order_by(desc(SessionLog.started_at)).limit(1)
        )
        log = result.scalar_one_or_none()

        if not log:
            await interaction.response.send_message(
                "No sessions found in this channel.", ephemeral=True
            )
            return

    # Get messages
    last_messages = []
    try:
        async for msg in interaction.channel.history(limit=100):
            if not msg.author.bot:
                last_messages.append(f"{msg.author.display_name}: {msg.content}")
    except Exception:
        pass

    message_text = "\n".join(last_messages[-80:])
    summary = await summarize_session(
        messages_text=message_text,
        characters=log.characters_present or [],
        location=interaction.channel.name,
        combat_count=log.combat_count or 0,
        quest_completions=log.quest_completions or 0,
        total_xp=log.total_xp or 0,
    )

    async with get_db() as db:
        result = await db.execute(
            select(SessionLog).where(SessionLog.id == log.id)
        )
        log = result.scalar_one_or_none()
        if log and summary:
            log.summary_text = summary

    embed = discord.Embed(
        title="📜 Session Summary",
        color=0x6366F1,
    )
    embed.add_field(name="🎭 Characters", value=", ".join(log.characters_present or []) or "None", inline=False)
    embed.add_field(name="⚔️ Combats", value=str(log.combat_count or 0), inline=True)
    embed.add_field(name="📋 Quests", value=str(log.quest_completions or 0), inline=True)
    embed.add_field(name="✨ XP", value=str(log.total_xp or 0), inline=True)

    if summary:
        embed.add_field(name="📖 Narrative", value=summary, inline=False)
    else:
        embed.add_field(name="📖 Narrative", value="*AI summary unavailable.*", inline=False)

    embed.set_footer(text="Use /session log to view past sessions")
    await interaction.response.send_message(embed=embed)


@session_group.command(name="log", description="View all past sessions (paginated)")
async def session_log(interaction: discord.Interaction):
    async with get_db() as db:
        result = await db.execute(
            select(SessionLog).where(
                SessionLog.guild_id == interaction.guild_id,
            ).order_by(desc(SessionLog.started_at)).limit(50)
        )
        sessions = list(result.scalars().all())

    if not sessions:
        await interaction.response.send_message("No sessions recorded yet.", ephemeral=True)
        return

    class SessionLogView(discord.ui.View):
        def __init__(self, pages, page=0):
            super().__init__(timeout=300)
            self.page = page
            self.pages = pages
            self._update_buttons()

        def _update_buttons(self):
            self.prev_btn.disabled = self.page == 0
            self.next_btn.disabled = self.page >= len(self.pages) - 1

        def _build_embed(self):
            s = self.pages[self.page]
            embed = discord.Embed(
                title=f"📜 Session Log — Page {self.page + 1}/{len(self.pages)}",
                color=0x6366F1,
            )
            embed.add_field(name="Title", value=s.title or "Untitled", inline=True)
            embed.add_field(name="Started", value=f"<t:{int(s.started_at.timestamp())}:f>" if s.started_at else "Unknown", inline=True)
            if s.ended_at:
                embed.add_field(name="Ended", value=f"<t:{int(s.ended_at.timestamp())}:f>", inline=True)
                duration_seconds = (s.ended_at - s.started_at).total_seconds()
                hours = int(duration_seconds // 3600)
                minutes = int((duration_seconds % 3600) // 60)
                embed.add_field(name="Duration", value=f"{hours}h {minutes}m", inline=True)
            embed.add_field(name="Characters", value=", ".join(s.characters_present or []) or "None", inline=False)
            embed.add_field(name="⚔️", value=str(s.combat_count or 0), inline=True)
            embed.add_field(name="📋", value=str(s.quest_completions or 0), inline=True)
            embed.add_field(name="✨ XP", value=str(s.total_xp or 0), inline=True)
            if s.summary_text:
                embed.add_field(name="Summary", value=s.summary_text[:500], inline=False)
            return embed

        @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
        async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.page -= 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

        @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.primary)
        async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
            self.page += 1
            self._update_buttons()
            await interaction.response.edit_message(embed=self._build_embed(), view=self)

    view = SessionLogView(pages=sessions[:20], page=0)
    await interaction.response.send_message(embed=view._build_embed(), view=view, ephemeral=True)


class SessionsCog(commands.Cog, name="Sessions"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(session_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("session")


async def setup(bot):
    await bot.add_cog(SessionsCog(bot))
