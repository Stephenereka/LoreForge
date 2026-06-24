from sqlalchemy import BigInteger, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.orm import mapped_column, Mapped
from datetime import datetime
from database.session import Base


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    race: Mapped[str] = mapped_column(String(50), nullable=False)
    char_class: Mapped[str] = mapped_column(String(50), nullable=False)
    background: Mapped[str] = mapped_column(String(50), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)

    # Ability scores (raw — modifiers calculated in code)
    strength: Mapped[int] = mapped_column(Integer, default=10)
    dexterity: Mapped[int] = mapped_column(Integer, default=10)
    constitution: Mapped[int] = mapped_column(Integer, default=10)
    intelligence: Mapped[int] = mapped_column(Integer, default=10)
    wisdom: Mapped[int] = mapped_column(Integer, default=10)
    charisma: Mapped[int] = mapped_column(Integer, default=10)

    # HP
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_temp: Mapped[int] = mapped_column(Integer, default=0)

    # Combat
    armor_class: Mapped[int] = mapped_column(Integer, default=10)
    gold: Mapped[int] = mapped_column(Integer, default=100)

    # Status
    is_dead: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unconscious: Mapped[bool] = mapped_column(Boolean, default=False)
    death_saves_success: Mapped[int] = mapped_column(Integer, default=0)
    death_saves_failure: Mapped[int] = mapped_column(Integer, default=0)

    # JSON fields for complex data
    inventory: Mapped[dict] = mapped_column(JSON, default=list)
    conditions: Mapped[dict] = mapped_column(JSON, default=list)
    skill_proficiencies: Mapped[dict] = mapped_column(JSON, default=list)
    class_resources: Mapped[dict] = mapped_column(JSON, default=dict)

    # Lore
    backstory: Mapped[str] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class GuildConfig(Base):
    """Per-server settings — AI mode, GM role, world name, etc."""
    __tablename__ = "guild_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    world_name: Mapped[str] = mapped_column(String(100), default="LoreForge World")
    gm_role_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    ai_mode_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    world_data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldEvent(Base):
    """Append-only log of everything that happens in the world."""
    __tablename__ = "world_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    character_id: Mapped[int] = mapped_column(Integer, nullable=True)
    narrative: Mapped[str] = mapped_column(Text, nullable=True)
    event_data: Mapped[dict] = mapped_column(JSON, default=dict)
    importance: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
