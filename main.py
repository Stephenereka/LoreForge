import discord
from discord.ext import commands
import os
import asyncio
from dotenv import load_dotenv
from database.session import init_db

load_dotenv()

intents = discord.Intents.all()

bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

COGS = [
    "cogs.admin",
]

@bot.event
async def on_ready():
    await init_db()
    print(f"{bot.user} is online!")
    try:
        guild = discord.Object(id=1519154137017614427)
        bot.tree.copy_global_to(guild=guild)
        synced = await bot.tree.sync(guild=guild)
        bot.tree.clear_commands(guild=None)
        await bot.tree.sync()
        print(f"Synced {len(synced)} slash commands")
    except Exception as e:
        print(f"Failed to sync commands: {e}")
    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="LoreForge | /ping")
    )

async def main():
    async with bot:
        for cog in COGS:
            await bot.load_extension(cog)
            print(f"Loaded: {cog}")
        await bot.start(os.getenv("DISCORD_TOKEN"))

asyncio.run(main())
