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
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_custom BOOLEAN DEFAULT FALSE",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS gold INTEGER DEFAULT 100",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS armor_class INTEGER DEFAULT 10",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS xp INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS level INTEGER DEFAULT 1",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS background VARCHAR(50)",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS inventory JSONB DEFAULT '[]'",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            # Phase 4 — new class columns
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS ki_points INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS ki_max INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS bardic_inspiration_dice INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS hunter_mark_target_id BIGINT",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS wild_shape_active BOOLEAN DEFAULT FALSE",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS wild_shape_form VARCHAR(30)",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS wild_shape_hp INTEGER DEFAULT 0",
            # Combat state columns (safe no-op if already exist)
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_dead BOOLEAN DEFAULT FALSE",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS is_unconscious BOOLEAN DEFAULT FALSE",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS hp_temp INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS death_saves_success INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS death_saves_failure INTEGER DEFAULT 0",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS conditions JSONB DEFAULT '[]'",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS skill_proficiencies JSONB DEFAULT '[]'",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS class_resources JSONB DEFAULT '{}'",
            "ALTER TABLE characters ADD COLUMN IF NOT EXISTS backstory TEXT",
            # GuildConfig extras
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS log_channel_id BIGINT",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS gm_channel_id BIGINT",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS world_map_url TEXT",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS world_name VARCHAR(100) DEFAULT 'LoreForge World'",
            "ALTER TABLE guild_configs ADD COLUMN IF NOT EXISTS world_data JSONB DEFAULT '{}'",
            # Locations — columns added after initial schema
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS resources JSONB DEFAULT '{}'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS ground_items JSONB DEFAULT '[]'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS hazards JSONB DEFAULT '[]'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS ambient_texts JSONB DEFAULT '[]'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS ambient_sounds VARCHAR(200)",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS required_key_item VARCHAR(100)",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS required_quest_id INTEGER",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS discovered_by BIGINT",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS population_density VARCHAR(20) DEFAULT 'sparse'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS lighting VARCHAR(20) DEFAULT 'bright'",
            "ALTER TABLE locations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
            # NPCs — columns added after initial schema
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS shop_inventory JSONB DEFAULT '{}'",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS dialogue_topics JSONB DEFAULT '{}'",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS is_hostile BOOLEAN DEFAULT FALSE",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS is_killable BOOLEAN DEFAULT TRUE",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS hp_max INTEGER DEFAULT 20",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS hp_current INTEGER DEFAULT 20",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS armor_class INTEGER DEFAULT 10",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS attack_bonus INTEGER DEFAULT 2",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS damage_dice VARCHAR(20) DEFAULT '1d6'",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS damage_bonus INTEGER DEFAULT 0",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS xp_value INTEGER DEFAULT 50",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS gold INTEGER DEFAULT 0",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS faction_id INTEGER",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS proxy_name VARCHAR(100)",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS proxy_avatar TEXT",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS proxy_prefix VARCHAR(20)",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS proxy_mode VARCHAR(20) DEFAULT 'manual'",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS gm_user_id BIGINT",
            "ALTER TABLE npcs ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT NOW()",
        ]:
            await conn.execute(text(stmt))
