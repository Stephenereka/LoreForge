from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from contextlib import asynccontextmanager
from config import DATABASE_URL

engine = create_async_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

@asynccontextmanager
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise

async def init_db():
    from database import models  # noqa: F401 — registers all models
    from sqlalchemy import text
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add new columns to existing tables without breaking live data
        for stmt in [
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS avatar_url TEXT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS proxy_open VARCHAR(10)",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS proxy_close VARCHAR(10)",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS combat_active BOOLEAN DEFAULT FALSE",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS combat_channel_id BIGINT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS balance INTEGER DEFAULT 0",
        ]:
            await conn.execute(text(stmt))
