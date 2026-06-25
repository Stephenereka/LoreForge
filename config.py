import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/loreforge")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
ENV = os.getenv("ENV", "development")
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

IS_DEV = ENV == "development"

# DeepSeek integration
DEEPSEEK_API_URL = os.getenv("DEEPSEEK_API_URL", "http://localhost:8082")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "freecc")

# Vector store
CHROMADB_PATH = os.getenv("CHROMADB_PATH", "./chroma_db")

# Map generation
WORLD_MAP_IMAGE_SIZE = (1024, 1024)
