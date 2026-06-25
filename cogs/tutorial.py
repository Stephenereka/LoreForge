import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete
from database.session import get_db
from database.models import TutorialProgress, Character
from services.utils import is_gm

tutorial_group = app_commands.Group(name="tutorial", description="Learn how to play LoreForge")

TUTORIAL_STEPS = [
    {
        "title": "👋 Welcome to LoreForge!",
        "content": (
            "LoreForge turns your Discord server into a **living RPG world**.\n\n"
            "📖 **What you can do:**\n"
            "• Create a character and go on adventures\n"
            "• Fight monsters with D&D-style combat\n"
            "• Travel between locations in a vast world\n"
            "• Level up and unlock new abilities\n"
            "• Interact with NPCs and complete quests\n\n"
            "Let's get you started!"
        ),
        "color": 0x8B5CF6,
    },
    {
        "title": "🧙 Step 1: Create Your Character",
        "content": (
            "First things first — you need a character!\n\n"
            "Use **`/character create <name>`** to begin.\n"
            "You can choose:\n"
            "• **DnD Mode** — Pick race, class, background, roll stats (4d6 drop lowest), and choose starting attacks\n"
            "• **Custom Mode** — Free-form; you write your own stats and description\n\n"
            "After creation, check your sheet with `/character sheet`.\n"
            "Set your active character with `/character use <name>`."
        ),
        "color": 0x6366F1,
    },
    {
        "title": "📚 Step 2: Read the Lore",
        "content": (
            "Every world has a story.\n\n"
            "Use **`/lore list`** to browse your world's lore entries.\n"
            "Search for specific topics with **`/lore search <query>`**.\n"
            "Get a random fact with **`/lore random`**.\n\n"
            "The lore of your world shapes the quests, NPCs, and locations you'll encounter. "
            "Knowledge is power — especially in an RPG!"
        ),
        "color": 0x22C55E,
    },
    {
        "title": "🗺️ Step 3: Explore the World",
        "content": (
            "The world is vast and waiting.\n\n"
            "• **`/look`** — See your current location, who's there, and nearby exits\n"
            "• **`/travel <direction>`** — Move to a connected location\n"
            "• **`/travel fast <location>`** — Fast travel to places you've discovered\n"
            "• **`/map`** — See the world map with your position\n"
            "• **`/discoveries`** — See everywhere you've been\n\n"
            "Some locations have secrets — try **`/search`** to find hidden exits or items!"
        ),
        "color": 0xF59E0B,
    },
    {
        "title": "⚔️ Step 4: Combat Demo",
        "content": (
            "When battle starts, the GM or another player will begin a **combat encounter**.\n\n"
            "**In DnD fights:**\n"
            "• Just type your action in RP (e.g., *\"I swing my sword at the goblin\"*)\n"
            "• The bot reads your message, confirms it, then rolls the dice\n"
            "• Use your named attacks like *Power Strike* or *Eldritch Blast* for special effects\n\n"
            "**Practice first:**\n"
            "Use **`/combat training`** to fight an AI dummy at your own pace!\n"
            "Choose Easy, Medium, Hard, or Impossible difficulty."
        ),
        "color": 0xEF4444,
    },
    {
        "title": "🎯 Step 5: What's Next?",
        "content": (
            "You're ready to adventure! Here's what to do next:\n\n"
            "• Talk to NPCs with **`/npc talk <name> [message]`**\n"
            "• Check available quests with **`/quest list`**\n"
            "• Accept and track quests with **`/quest accept`** and **`/quest status`**\n"
            "• Buy gear at **`/shop browse`**\n"
            "• Rest up with **`/rest long`** or **`/rest short`**\n"
            "• Form a party with **`/party create`**\n"
            "• Visit `/help` anytime to see all commands\n\n"
            "🌟 **Tutorial complete!** You earned **50 XP**!"
        ),
        "color": 0xA855F7,
    },
]


async def get_or_create_tutorial(user_id: int, guild_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(TutorialProgress).where(
                TutorialProgress.user_id == user_id,
                TutorialProgress.guild_id == guild_id,
            )
        )
        prog = result.scalar_one_or_none()
        if not prog:
            prog = TutorialProgress(
                user_id=user_id,
                guild_id=guild_id,
                completed_steps=[],
                current_step=0,
                is_completed=False,
            )
            db.add(prog)
            await db.flush()
        return prog


def _build_step_embed(step_index: int) -> discord.Embed:
    step = TUTORIAL_STEPS[step_index]
    embed = discord.Embed(
        title=step["title"],
        description=step["content"],
        color=step["color"],
    )
    embed.set_footer(text=f"Step {step_index + 1} of {len(TUTORIAL_STEPS)}  ·  LoreForge Tutorial")
    return embed


class TutorialView(discord.ui.View):
    def __init__(self, user_id: int, start_step: int = 0):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.current_step = start_step
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current_step == 0
        self.next_btn.disabled = self.current_step == len(TUTORIAL_STEPS) - 1
        if self.current_step == len(TUTORIAL_STEPS) - 1:
            self.complete_btn.label = "✅ Complete Tutorial"
            self.complete_btn.style = discord.ButtonStyle.success
        else:
            self.complete_btn.label = f"Skip to End ({len(TUTORIAL_STEPS) - self.current_step - 1} steps left)"
            self.complete_btn.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_step_embed(self.current_step), view=self)
        await _save_progress(self.user_id, interaction.guild_id, self.current_step)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_step_embed(self.current_step), view=self)
        await _save_progress(self.user_id, interaction.guild_id, self.current_step)

    @discord.ui.button(label="Skip to End", style=discord.ButtonStyle.secondary)
    async def complete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        await _complete_tutorial(self.user_id, interaction.guild_id)
        embed = discord.Embed(
            title="🎉 Tutorial Complete!",
            description="You've completed the LoreForge tutorial!\n\nUse `/help` to see all commands.\n\n**+50 XP awarded!**",
            color=0xA855F7,
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    async def on_timeout(self):
        self.stop()


async def _save_progress(user_id: int, guild_id: int, step: int):
    async with get_db() as db:
        result = await db.execute(
            select(TutorialProgress).where(
                TutorialProgress.user_id == user_id,
                TutorialProgress.guild_id == guild_id,
            )
        )
        prog = result.scalar_one_or_none()
        if prog:
            if step not in prog.completed_steps:
                completed = list(prog.completed_steps or [])
                completed.append(step)
                prog.completed_steps = completed
            prog.current_step = step


async def _complete_tutorial(user_id: int, guild_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(TutorialProgress).where(
                TutorialProgress.user_id == user_id,
                TutorialProgress.guild_id == guild_id,
            )
        )
        prog = result.scalar_one_or_none()
        if prog and not prog.is_completed:
            prog.is_completed = True
            prog.completed_steps = list(range(len(TUTORIAL_STEPS)))
            prog.current_step = len(TUTORIAL_STEPS) - 1

            # Award 50 XP
            char_result = await db.execute(
                select(Character).where(
                    Character.user_id == user_id,
                    Character.guild_id == guild_id,
                    Character.is_active == True,
                )
            )
            char = char_result.scalar_one_or_none()
            if char:
                char.xp = (char.xp or 0) + 50


async def auto_trigger_tutorial(user_id: int, guild_id: int) -> bool:
    """Returns True if a tutorial needs to be shown."""
    async with get_db() as db:
        result = await db.execute(
            select(TutorialProgress).where(
                TutorialProgress.user_id == user_id,
                TutorialProgress.guild_id == guild_id,
            )
        )
        prog = result.scalar_one_or_none()
        return prog is None or not prog.is_completed


@tutorial_group.command(name="start", description="Start or resume the tutorial")
async def tutorial_start(interaction: discord.Interaction):
    prog = await get_or_create_tutorial(interaction.user.id, interaction.guild_id)
    start_step = prog.current_step
    if prog.is_completed:
        start_step = 0

    view = TutorialView(interaction.user.id, start_step)
    await interaction.response.send_message(
        embed=_build_step_embed(start_step),
        view=view,
        ephemeral=True,
    )


@tutorial_group.command(name="reset", description="Reset a user's tutorial progress (GM only)")
@app_commands.describe(user="The user to reset")
async def tutorial_reset(interaction: discord.Interaction, user: discord.Member):
    if not await is_gm(interaction):
        await interaction.response.send_message("Only GMs can reset tutorials.", ephemeral=True)
        return

    async with get_db() as db:
        await db.execute(
            delete(TutorialProgress).where(
                TutorialProgress.user_id == user.id,
                TutorialProgress.guild_id == interaction.guild_id,
            )
        )

    await interaction.response.send_message(f"✅ Tutorial reset for {user.mention}.")


class TutorialCog(commands.Cog, name="Tutorial"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(tutorial_group)
        self._notified_users = set()

    async def cog_unload(self):
        self.bot.tree.remove_command("tutorial")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        key = (message.author.id, message.guild.id)
        if key in self._notified_users:
            return

        if await auto_trigger_tutorial(message.author.id, message.guild.id):
            self._notified_users.add(key)
            await message.channel.send(
                f"👋 Welcome to LoreForge, {message.author.mention}! "
                f"Run `/tutorial` to learn the ropes and earn **50 XP**!"
            )


async def setup(bot):
    await bot.add_cog(TutorialCog(bot))
