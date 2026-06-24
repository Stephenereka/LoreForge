import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///loreforge.db")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ENV = os.getenv("ENV", "development")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

IS_DEV = ENV == "development"
