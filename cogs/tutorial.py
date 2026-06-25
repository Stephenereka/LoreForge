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


GM_TUTORIAL_STEPS = [
    {
        "title": "🎮 Welcome, Game Master!",
        "content": (
            "Welcome to the **LoreForge GM Tutorial**!\n\n"
            "As a **Game Master**, you control the world. You build locations, write lore, "
            "manage NPCs, run quests, control time and weather, and manage players.\n\n"
            "**What you control:**\n"
            "• 🗺️ Locations & World Map\n"
            "• 📖 Lore & History\n"
            "• 🤝 NPCs & Factions\n"
            "• 📜 Quests & Storylines\n"
            "• 🌦️ Weather & Time\n"
            "• ⚔️ Combat Encounters\n"
            "• 👑 Player Management\n\n"
            "The bot handles dice rolls, XP tracking, and combat mechanics. "
            "**You** handle the narrative. Let's get you set up!"
        ),
        "color": 0x8B5CF6,
    },
    {
        "title": "👑 Setting Up Your GM Team",
        "content": (
            "First — grant GM powers to your trusted team.\n\n"
            "**Commands (server owner only):**\n"
            "• `/gm add @user` — Grant GM status to a user\n"
            "• `/gm remove @user` — Remove GM status from a user\n"
            "• `/gm list` — See all current GMs on the server\n\n"
            "ℹ️ The **server owner** is always a GM automatically and cannot be removed.\n\n"
            "**Tip:** Start with a small GM team (2-3 people) while you build the world, "
            "then expand as your player base grows."
        ),
        "color": 0x6366F1,
    },
    {
        "title": "🗺️ Creating Locations",
        "content": (
            "Every adventure needs a setting.\n\n"
            "**Manual creation:**\n"
            "• `/location create <name> <type> <biome>` — Create a new location\n"
            "• Types: city, town, village, dungeon, tavern, shrine, fortress, ruins, cave, "
            "forest, lake, mountain, bridge, port, tower, library, arena, wilderness\n\n"
            "**Connecting locations:**\n"
            "• `/location connect <loc1> <loc2> <direction>` — Link two locations\n"
            "• Directions: north, south, east, west, northeast, northwest, southeast, southwest\n\n"
            "**Viewing locations:**\n"
            "• `/location info <name>` — See details of a location\n"
            "• `/location list` — See all locations in the world\n"
            "• `/location edit <name>` — Update existing location details"
        ),
        "color": 0x22C55E,
    },
    {
        "title": "⚡ Auto-Generating the World",
        "content": (
            "Don't want to build every location by hand? Use the world generator.\n\n"
            "**Commands:**\n"
            "• `/world generate <count>` — Instantly create up to **50 random locations**\n"
            "  (Names, types, biomes, and map positions are all randomized)\n"
            "• `/world link` — Auto-connect nearby locations based on map distance\n"
            "• `/world info` — Overview of your world (location count, NPCs, quests, factions)\n\n"
            "**Pro tip — bootstrap fast:**\n"
            "1️⃣ `/world generate 15` — Create 15 locations\n"
            "2️⃣ `/world link` — Connect them all automatically\n"
            "3️⃣ `/location edit <name>` — Customize the key locations\n\n"
            "You'll have a functional world in under a minute."
        ),
        "color": 0xF59E0B,
    },
    {
        "title": "🌦️ Weather & Time Control",
        "content": (
            "Set the mood with dynamic weather and time.\n\n"
            "**Weather:**\n"
            "• `/location set-weather <type>` — Force the weather in any location\n"
            "• Types: clear, cloudy, rainy, stormy, foggy, snowy, **magical**\n"
            "• Players see the weather when they use `/look` at their location\n\n"
            "**Time:**\n"
            "• Time is tracked automatically for your world\n"
            "• GMs can advance or set the in-world clock using time commands\n\n"
            "**Dramatic use:**\n"
            "• A sudden storm during a boss fight\n"
            "• Midnight fog for a stealth heist\n"
            "• Magical aurora when players discover a hidden temple"
        ),
        "color": 0x0EA5E9,
    },
    {
        "title": "📖 Writing World Lore",
        "content": (
            "Give your world depth with rich lore.\n\n"
            "**Commands:**\n"
            "• `/lore add <title> <content>` — Write a lore entry (history, myths, faction "
            "backstory, character legends, etc.)\n"
            "• `/lore edit <title>` — Edit an existing entry\n"
            "• `/lore delete <title>` — Remove a lore entry\n\n"
            "**Player access:**\n"
            "• `/lore list` — Browse all lore entries\n"
            "• `/lore search <query>` — Search for specific topics\n"
            "• `/lore random` — Get a random lore fact\n\n"
            "**Tip:** Start with lore for your major factions, key locations, and the "
            "world's creation myth. Players actually read this stuff — it makes the "
            "world feel alive and rewards their curiosity."
        ),
        "color": 0xA855F7,
    },
    {
        "title": "📜 Creating Quests",
        "content": (
            "Drive the story with quests.\n\n"
            "**Creation:**\n"
            "• `/quest create <title> <description> <xp_reward> <gold_reward>` — "
            "Create a new quest\n\n"
            "**Objectives:**\n"
            "• `/quest objective add <quest> <description>` — Add objectives to a quest\n\n"
            "**Player flow:**\n"
            "• `/quest accept` — Players accept a quest\n"
            "• `/quest status` — Track current quest progress\n"
            "• `/quest complete` — Mark a quest complete\n\n"
            "**GM control:**\n"
            "• `/quest complete <player>` — GMs can mark quests complete for any player\n\n"
            "**Tip:** Chain quests into storylines. Reference NPCs and locations players "
            "have already visited. A three-quest chain feels like a real campaign arc."
        ),
        "color": 0xEF4444,
    },
    {
        "title": "🤝 Factions & NPCs",
        "content": (
            "Populate your world with factions and characters.\n\n"
            "**Factions:**\n"
            "• `/faction create <name> <description>` — Create a faction\n"
            "• Players gain/lose reputation through quests and choices\n"
            "• `/faction status` — See a player's standing with all factions\n\n"
            "**NPCs:**\n"
            "• `/npc create <name> <description> <location>` — Create an NPC at a location\n"
            "• `/npc edit <name>` — Update an NPC's details\n"
            "• Players interact via `/npc talk <name> [message]` — the AI generates "
            "responses based on the NPC description\n\n"
            "**Tip:** Write detailed NPC descriptions. The AI uses them to generate "
            "personality, voice, and dialogue. A well-written NPC is unforgettable."
        ),
        "color": 0xF97316,
    },
    {
        "title": "📋 Managing Player Characters",
        "content": (
            "Keep tabs on your players.\n\n"
            "**Viewing:**\n"
            "• `/sheet view @player` — View any player's full character sheet\n\n"
            "**Editing:**\n"
            "• `/sheet edit @player` — Open an edit panel to change stats\n"
            "  (HP, AC, XP, class, race, level, stats — full control)\n\n"
            "**Pending approvals:**\n"
            "• `/gm pending` — See all pending stat-change requests from players\n"
            "• `/gm approve <id>` — Approve a request\n"
            "• `/gm deny <id> [reason]` — Deny a request with a reason\n\n"
            "**Tip:** Use the pending approval system! Let players submit character "
            "upgrade proposals, then review and approve them. It keeps you in control "
            "without being a bottleneck."
        ),
        "color": 0x14B8A6,
    },
    {
        "title": "⚡ GM Powers: XP, Revival & Teleport",
        "content": (
            "Direct powers to reward and manage players.\n\n"
            "**Awarding XP:**\n"
            "• `/gm xp @player <amount>` — Award XP to a player's active character\n"
            "• Use this for: great roleplay, solving puzzles, memorable moments, session rewards\n"
            "• Recommended: 1-25 XP per award (50 for major story milestones)\n\n"
            "**Revival:**\n"
            "• `/gm revive @player` — Bring a dead character back to life\n\n"
            "**Teleport:**\n"
            "• `/location teleport @player <location>` — Move any player to any location instantly\n\n"
            "**Dashboard:**\n"
            "• `/gm dashboard` — Full world overview: player count, locations, active quests, "
            "recent activity\n\n"
            "⚠️ Use these powers responsibly — XP and revivals shape game balance."
        ),
        "color": 0xEAB308,
    },
    {
        "title": "⚔️ Running Combat as GM",
        "content": (
            "When battle breaks out, you're in control.\n\n"
            "**Starting combat:**\n"
            "• `/combat start` — Begin a combat encounter in the current channel\n"
            "• Players join with `/combat join`\n\n"
            "**During combat:**\n"
            "• `/combat hp edit <character> <amount>` — Adjust any character's HP mid-fight\n"
            "• `/gm edit @player` — Open the full edit panel for emergency stat changes\n"
            "• `/combat pause` / `/combat resume` — Pause and resume combat\n"
            "• `/combat end` — End the encounter (awards XP, logs results)\n\n"
            "**Tip:** Let players describe their attacks in RP first, then use combat "
            "commands to resolve them mechanically. Best of both worlds — narrative "
            "freedom with mechanical structure."
        ),
        "color": 0xDC2626,
    },
    {
        "title": "🛠️ GM Tools & Tips",
        "content": (
            "Final tools and golden rules for running your world.\n\n"
            "**Extra tools:**\n"
            "• `/embed` — Build custom styled embeds for announcements, lore reveals, "
            "world events, NPC letters\n"
            "• `/event create` — Schedule world events players can RSVP to\n"
            "• `/gm dashboard` — Your home base — check world health at a glance\n\n"
            "**🥇 Golden GM Rules:**\n"
            "1. **Build first, invite later** — Create locations, lore, factions, NPCs, "
            "and quests before opening the gates\n"
            "2. **Bootstrap fast** — Use `/world generate + /world link` then customize "
            "with `/location edit`\n"
            "3. **Reward roleplay** — Award bonus XP (1-25) for great roleplay moments. "
            "It encourages engagement\n"
            "4. **Detail your NPCs** — Write NPC descriptions like character bibles. "
            "The AI needs detail to shine\n\n"
            "🌟 **You are ready to run your world!**\n"
            "Use `/gm dashboard` anytime to check your world status."
        ),
        "color": 0x8B5CF6,
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


def _build_step_embed(step_index: int, steps: list = None) -> discord.Embed:
    steps = steps or TUTORIAL_STEPS
    step = steps[step_index]
    embed = discord.Embed(
        title=step["title"],
        description=step["content"],
        color=step["color"],
    )
    embed.set_footer(text=f"Step {step_index + 1} of {len(steps)}  ·  LoreForge Tutorial")
    return embed


def _build_gm_step_embed(step_index: int) -> discord.Embed:
    step = GM_TUTORIAL_STEPS[step_index]
    embed = discord.Embed(
        title=step["title"],
        description=step["content"],
        color=step["color"],
    )
    embed.set_footer(text=f"Step {step_index + 1} of {len(GM_TUTORIAL_STEPS)}  ·  LoreForge GM Tutorial")
    return embed


class TutorialView(discord.ui.View):
    def __init__(self, user_id: int, start_step: int = 0, steps: list = None):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.current_step = start_step
        self.steps = steps or TUTORIAL_STEPS
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current_step == 0
        self.next_btn.disabled = self.current_step == len(self.steps) - 1
        if self.current_step == len(self.steps) - 1:
            self.complete_btn.label = "✅ Complete Tutorial"
            self.complete_btn.style = discord.ButtonStyle.success
        else:
            self.complete_btn.label = f"Skip to End ({len(self.steps) - self.current_step - 1} steps left)"
            self.complete_btn.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_step_embed(self.current_step, self.steps), view=self)
        await _save_progress(self.user_id, interaction.guild_id, self.current_step)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_step_embed(self.current_step, self.steps), view=self)
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


class GmTutorialView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=600)
        self.user_id = user_id
        self.current_step = 0
        self._update_buttons()

    def _update_buttons(self):
        self.prev_btn.disabled = self.current_step == 0
        self.next_btn.disabled = self.current_step == len(GM_TUTORIAL_STEPS) - 1
        if self.current_step == len(GM_TUTORIAL_STEPS) - 1:
            self.complete_btn.label = "✅ Done"
            self.complete_btn.style = discord.ButtonStyle.success
        else:
            self.complete_btn.label = f"Skip to End ({len(GM_TUTORIAL_STEPS) - self.current_step - 1} steps left)"
            self.complete_btn.style = discord.ButtonStyle.secondary

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_gm_step_embed(self.current_step), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        self.current_step += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=_build_gm_step_embed(self.current_step), view=self)

    @discord.ui.button(label="Skip to End", style=discord.ButtonStyle.secondary)
    async def complete_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your tutorial.", ephemeral=True)
            return
        embed = discord.Embed(
            title="🎮 GM Tutorial Complete!",
            description=(
                "You've completed the LoreForge GM tutorial!\n\n"
                "**You're ready to run your world.**\n\n"
                "• Use `/gm dashboard` to check your world anytime\n"
                "• Use `/help` to see all commands\n"
                "• Re-run this tutorial anytime with `/tutorial gm`"
            ),
            color=0x8B5CF6,
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


@tutorial_group.command(name="gm", description="GM tutorial — learn all GM commands (GM only)")
async def tutorial_gm(interaction: discord.Interaction):
    if not await is_gm(interaction):
        await interaction.response.send_message(
            "❌ Only Game Masters can use this tutorial.",
            ephemeral=True,
        )
        return

    view = GmTutorialView(interaction.user.id)
    await interaction.response.send_message(
        embed=_build_gm_step_embed(0),
        view=view,
        ephemeral=True,
    )


class TutorialCog(commands.Cog, name="Tutorial"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(tutorial_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("tutorial")


async def setup(bot):
    await bot.add_cog(TutorialCog(bot))
