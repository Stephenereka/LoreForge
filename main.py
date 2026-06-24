import asyncio
import discord
from discord.ext import commands
from config import DISCORD_TOKEN, TEST_GUILD_ID, IS_DEV
from database.session import init_db

COGS = [
    "cogs.admin",
]

class LoreForge(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await init_db()

        for cog in COGS:
            await self.load_extension(cog)
            print(f"Loaded: {cog}")

        if IS_DEV and TEST_GUILD_ID:
            guild = discord.Object(id=int(TEST_GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"Slash commands synced to test guild {TEST_GUILD_ID}")
        else:
            await self.tree.sync()
            print("Slash commands synced globally")

    async def on_ready(self):
        print(f"LoreForge is online as {self.user} ({self.user.id})")
        print(f"Connected to {len(self.guilds)} server(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.playing,
                name="LoreForge | /ping"
            )
        )


async def main():
    bot = LoreForge()
    async with bot:
        await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
