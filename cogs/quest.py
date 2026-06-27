import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from datetime import datetime
from database.session import get_db
from database.models import (
    Quest, QuestObjective, PlayerQuest, Character,
)
from services.quest_service import award_quest_rewards
from services.utils import is_gm

quest_group = app_commands.Group(name="quest", description="Quest commands")


async def _available_quest_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete for quests the player can accept."""
    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            return []
        # Get accepted quest IDs
        pq_result = await db.execute(
            select(PlayerQuest.quest_id).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.guild_id == interaction.guild_id,
            )
        )
        accepted_ids = {row[0] for row in pq_result.all()}
        result = await db.execute(
            select(Quest).where(
                Quest.guild_id == interaction.guild_id,
                Quest.is_active == True,
                Quest.is_hidden == False,
                Quest.min_level <= char.level,
            ).limit(25)
        )
        quests = result.scalars().all()
    return [
        app_commands.Choice(name=f"{q.name} (✨{q.reward_xp}XP)", value=q.name)
        for q in quests
        if q.id not in accepted_ids and current.lower() in q.name.lower()
    ][:25]


async def _pending_quest_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete for quests the player has pending completion."""
    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            return []
        result = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.guild_id == interaction.guild_id,
                PlayerQuest.status.in_(["accepted", "pending_approval"]),
            )
        )
        pqs = result.scalars().all()
    choices = []
    for pq in pqs:
        async with get_db() as db2:
            q_result = await db2.execute(select(Quest).where(Quest.id == pq.quest_id))
            q = q_result.scalar_one_or_none()
            if q and current.lower() in q.name.lower():
                choices.append(app_commands.Choice(name=q.name, value=q.name))
    return choices[:25]

# ── Shared Helpers ────────────────────────────────────────────────────────────

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


def progress_bar(current: int, needed: int, length: int = 10) -> str:
    if needed <= 0:
        return "✅ Complete"
    pct = max(0, min(1.0, current / needed))
    filled = round(pct * length)
    return f"{'█' * filled}{'░' * (length - filled)} ({current}/{needed})"


# ── Quest Create Wizard ───────────────────────────────────────────────────────

class QuestCreateView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=600)
        self.data = {
            "name": "",
            "description": "",
            "quest_type": "standard",
            "reward_xp": 0,
            "reward_gold": 0,
        }
        self.objectives = []

    @discord.ui.button(label="Step 1: Basic Info", style=discord.ButtonStyle.primary)
    async def step1(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create quests.", ephemeral=True)
            return
        await interaction.response.send_modal(QuestNameModal(self))

    @discord.ui.button(label="Step 2: Add Objective", style=discord.ButtonStyle.secondary)
    async def step2(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create quests.", ephemeral=True)
            return
        if not self.data["name"]:
            await interaction.response.send_message("Complete Step 1 first.", ephemeral=True)
            return
        await interaction.response.send_modal(QuestObjectiveModal(self))

    @discord.ui.button(label="Create Quest ✅", style=discord.ButtonStyle.success)
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await is_gm(interaction):
            await interaction.response.send_message("Only GMs can create quests.", ephemeral=True)
            return
        if not self.data["name"] or not self.data["description"]:
            await interaction.response.send_message("Complete all steps first.", ephemeral=True)
            return

        async with get_db() as db:
            quest = Quest(
                guild_id=interaction.guild_id,
                name=self.data["name"],
                description=self.data["description"],
                quest_type=self.data.get("quest_type", "standard"),
                reward_xp=self.data.get("reward_xp", 0),
                reward_gold=self.data.get("reward_gold", 0),
                min_level=self.data.get("min_level", 1),
                created_by=interaction.user.id,
            )
            db.add(quest)
            await db.flush()

            for obj in self.objectives:
                db.add(QuestObjective(
                    quest_id=quest.id,
                    guild_id=interaction.guild_id,
                    order=obj.get("order", 0),
                    description=obj["description"],
                    objective_type=obj["objective_type"],
                    required_count=obj.get("count", 1),
                ))

        embed = discord.Embed(
            title=f"📜 Quest Created: {self.data['name']}",
            description=self.data["description"],
            color=0x22C55E,
        )
        obj_lines = "\n".join(f"• {o['description']}" for o in self.objectives)
        if obj_lines:
            embed.add_field(name="Objectives", value=obj_lines, inline=False)
        embed.add_field(name="Rewards", value=f"✨ {self.data['reward_xp']} XP  ·  🪙 {self.data['reward_gold']} gold", inline=False)

        await interaction.response.edit_message(embed=embed, view=None)


class QuestNameModal(discord.ui.Modal, title="Quest Basic Info"):
    name = discord.ui.TextInput(label="Quest Name", max_length=200)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.long)
    quest_type = discord.ui.TextInput(label="Type (standard/daily/side)", max_length=30, default="standard")
    min_level = discord.ui.TextInput(label="Minimum Level", default="1", max_length=3)
    reward_xp = discord.ui.TextInput(label="XP Reward", default="100", max_length=5)
    reward_gold = discord.ui.TextInput(label="Gold Reward", default="50", max_length=5)

    def __init__(self, parent_view: QuestCreateView):
        super().__init__()
        self._parent = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self._parent.data["name"] = self.name.value
        self._parent.data["description"] = self.description.value
        self._parent.data["quest_type"] = self.quest_type.value
        try:
            self._parent.data["min_level"] = int(self.min_level.value)
            self._parent.data["reward_xp"] = int(self.reward_xp.value)
            self._parent.data["reward_gold"] = int(self.reward_gold.value)
        except ValueError:
            pass
        await interaction.response.send_message("✅ Step 1 complete! Add objectives with Step 2.", ephemeral=True)


class QuestObjectiveModal(discord.ui.Modal, title="Add Objective"):
    description = discord.ui.TextInput(label="Objective Description", style=discord.TextStyle.long)
    objective_type = discord.ui.TextInput(
        label="Type (kill_npc/kill_enemy/talk_to/travel/collect/explore/reach_level/faction_rep)",
        max_length=30, default="kill_enemy"
    )
    count = discord.ui.TextInput(label="Count needed", default="1", max_length=3)

    def __init__(self, parent_view: QuestCreateView):
        super().__init__()
        self._parent = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        self._parent.objectives.append({
            "description": self.description.value,
            "objective_type": self.objective_type.value,
            "count": int(self.count.value) if self.count.value.isdigit() else 1,
            "order": len(self._parent.objectives) + 1,
        })
        await interaction.response.send_message(
            f"✅ Objective added ({len(self._parent.objectives)} total). "
            "Add more or click 'Create Quest ✅' to finish.",
            ephemeral=True,
        )


# ── Commands ──────────────────────────────────────────────────────────────────

@quest_group.command(name="create", description="Create a new quest (GM only)")
async def quest_create(interaction: discord.Interaction):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can create quests.", ephemeral=True)
        return
    embed = discord.Embed(
        title="📜 Create a Quest",
        description="Use the buttons below to build your quest.",
        color=0x22C55E,
    )
    await interaction.response.send_message(embed=embed, view=QuestCreateView(), ephemeral=True)


@quest_group.command(name="list", description="List available quests")
async def quest_list(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Quest).where(
                Quest.guild_id == interaction.guild_id,
                Quest.is_active == True,
                Quest.is_hidden == False,
                Quest.min_level <= char.level,
            )
        )
        quests = result.scalars().all()

        # Filter out already accepted
        accepted = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.guild_id == interaction.guild_id,
                PlayerQuest.status == "accepted",
            )
        )
        accepted_ids = {pq.quest_id for pq in accepted.scalars().all()}
        available = [q for q in quests if q.id not in accepted_ids]

    if not available:
        await interaction.followup.send("No available quests right now.", ephemeral=True)
        return

    embed = discord.Embed(title="📜 Available Quests", color=0x22C55E)
    for q in available[:10]:
        embed.add_field(
            name=f"{q.name} (Min Lv{q.min_level})",
            value=f"{q.description[:100]}...\n✨ {q.reward_xp} XP  🪙 {q.reward_gold} gold",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@quest_group.command(name="accept", description="Accept a quest")
@app_commands.describe(name="Quest name")
@app_commands.autocomplete(name=_available_quest_autocomplete)
async def quest_accept(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Quest).where(
                Quest.guild_id == interaction.guild_id,
                Quest.is_active == True,
                Quest.name.ilike(name),
            )
        )
        quest = result.scalar_one_or_none()
        if not quest:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        existing = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.quest_id == quest.id,
            )
        )
        if existing.scalar_one_or_none():
            await interaction.followup.send("You've already accepted this quest.", ephemeral=True)
            return

        db.add(PlayerQuest(
            character_id=char.id,
            guild_id=interaction.guild_id,
            quest_id=quest.id,
            status="accepted",
        ))

    embed = discord.Embed(
        title=f"📜 Quest Accepted: {quest.name}",
        description=quest.description[:500],
        color=0x22C55E,
    )
    embed.add_field(name="Rewards", value=f"✨ {quest.reward_xp} XP  ·  🪙 {quest.reward_gold} gold", inline=False)

    await interaction.followup.send(embed=embed)


@quest_group.command(name="status", description="Check your active quests")
async def quest_status(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.guild_id == interaction.guild_id,
                PlayerQuest.status == "accepted",
            )
        )
        pqs = result.scalars().all()

    if not pqs:
        await interaction.followup.send("You have no active quests.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📜 Quest Status — {char.name}", color=0x22C55E)
    for pq in pqs:
        async with get_db() as db:
            quest_result = await db.execute(select(Quest).where(Quest.id == pq.quest_id))
            quest = quest_result.scalar_one_or_none()
            if not quest:
                continue

            obj_result = await db.execute(
                select(QuestObjective).where(QuestObjective.quest_id == quest.id)
            )
            objectives = obj_result.scalars().all()

        progress = pq.progress or {}
        obj_lines = []
        for obj in objectives:
            current = progress.get(str(obj.id), 0)
            bar = progress_bar(current, obj.required_count)
            obj_lines.append(f"• {obj.description}: {bar}")

        embed.add_field(
            name=quest.name,
            value="\n".join(obj_lines) or "In progress...",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


@quest_group.command(name="complete", description="Request quest completion (sends to GM for approval)")
@app_commands.describe(name="Quest name")
@app_commands.autocomplete(name=_pending_quest_autocomplete)
async def quest_complete(interaction: discord.Interaction, name: str):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(Quest).where(
                Quest.guild_id == interaction.guild_id,
                Quest.name.ilike(name),
            )
        )
        quest = result.scalar_one_or_none()
        if not quest:
            await interaction.followup.send("Quest not found.", ephemeral=True)
            return

        pq_result = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.quest_id == quest.id,
                PlayerQuest.status.in_(["accepted", "pending_approval"]),
            )
        )
        pq = pq_result.scalar_one_or_none()
        if not pq:
            await interaction.followup.send("You haven't accepted this quest.", ephemeral=True)
            return

    # Send approval embed to channel
    embed = discord.Embed(
        title=f"📜 Quest Completion Request",
        description=f"**{char.name}** wants to complete **{quest.name}**",
        color=0xF59E0B,
    )
    embed.add_field(name="Rewards", value=f"✨ {quest.reward_xp} XP  ·  🪙 {quest.reward_gold} gold", inline=False)

    view = QuestCompleteView(char.id, interaction.guild_id, quest.id, pq.id)
    await interaction.followup.send(embed=embed, view=view)


class QuestCompleteView(discord.ui.View):
    def __init__(self, char_id: int, guild_id: int, quest_id: int, pq_id: int):
        super().__init__(timeout=86400)
        self.char_id = char_id
        self.guild_id = guild_id
        self.quest_id = quest_id
        self.pq_id = pq_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        from services.utils import is_gm
        if not await is_gm(interaction):
            await interaction.response.send_message(
                "Only GMs can approve or deny quest completions.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Approve ✅", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: discord.ui.Button):
        await award_quest_rewards(self.char_id, self.guild_id, self.quest_id)

        async with get_db() as db:
            result = await db.execute(select(PlayerQuest).where(PlayerQuest.id == self.pq_id))
            pq = result.scalar_one_or_none()
            if pq:
                pq.status = "completed"
                pq.completed_at = datetime.utcnow()

        embed = discord.Embed(
            title="✅ Quest Completed!",
            description=f"Approved by {interaction.user.mention}",
            color=0x22C55E,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="Deny ❌", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="❌ Quest Completion Denied",
            description=f"Denied by {interaction.user.mention}",
            color=0xEF4444,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()


@quest_group.command(name="journal", description="View your quest history")
async def quest_journal(interaction: discord.Interaction):
    await interaction.response.defer()
    char = await get_active_character(interaction.user.id, interaction.guild_id)
    if not char:
        await interaction.followup.send("You need an active living character.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == char.id,
                PlayerQuest.guild_id == interaction.guild_id,
            ).order_by(PlayerQuest.accepted_at.desc())
        )
        pqs = result.scalars().all()

    if not pqs:
        await interaction.followup.send("Your quest journal is empty.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📖 {char.name}'s Quest Journal", color=0x22C55E)
    for pq in pqs[:15]:
        async with get_db() as db:
            q = await db.execute(select(Quest).where(Quest.id == pq.quest_id))
            quest = q.scalar_one_or_none()
        status_emoji = {"accepted": "📌", "completed": "✅", "failed": "❌"}.get(pq.status, "❓")
        embed.add_field(
            name=f"{status_emoji} {quest.name if quest else 'Unknown'}",
            value=f"Status: {pq.status}",
            inline=False,
        )

    await interaction.followup.send(embed=embed)


class QuestCog(commands.Cog, name="Quest"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(quest_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("quest")


async def setup(bot):
    await bot.add_cog(QuestCog(bot))
