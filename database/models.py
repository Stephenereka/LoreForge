from sqlalchemy import BigInteger, Integer, String, Text, Boolean, DateTime, JSON, UniqueConstraint, Float, ForeignKey
from sqlalchemy.orm import mapped_column, Mapped, relationship
from datetime import datetime, timezone
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
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)

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

    # Economy
    balance: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_dead: Mapped[bool] = mapped_column(Boolean, default=False)
    is_unconscious: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    death_saves_success: Mapped[int] = mapped_column(Integer, default=0)
    death_saves_failure: Mapped[int] = mapped_column(Integer, default=0)

    # JSON fields for complex data
    inventory: Mapped[dict] = mapped_column(JSON, default=list)
    conditions: Mapped[dict] = mapped_column(JSON, default=list)
    skill_proficiencies: Mapped[dict] = mapped_column(JSON, default=list)
    class_resources: Mapped[dict] = mapped_column(JSON, default=dict)

    # Class-specific resources (Phase 4)
    ki_points: Mapped[int] = mapped_column(Integer, default=0)
    ki_max: Mapped[int] = mapped_column(Integer, default=0)
    bardic_inspiration_dice: Mapped[int] = mapped_column(Integer, default=0)
    hunter_mark_target_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    wild_shape_active: Mapped[bool] = mapped_column(Boolean, default=False)
    wild_shape_form: Mapped[str] = mapped_column(String(30), nullable=True)
    wild_shape_hp: Mapped[int] = mapped_column(Integer, default=0)

    # Lore & proxy
    backstory: Mapped[str] = mapped_column(Text, nullable=True)
    avatar_url: Mapped[str] = mapped_column(Text, nullable=True)
    proxy_open: Mapped[str] = mapped_column(String(10), nullable=True)
    proxy_close: Mapped[str] = mapped_column(String(10), nullable=True)

    # Phase 6: Relationships & tracking
    relationships: Mapped[dict] = mapped_column(JSON, default=list)
    proxy_count: Mapped[int] = mapped_column(Integer, default=0)

    # Phase 6 Tier 2: Languages & Religion
    languages: Mapped[dict] = mapped_column(JSON, default=list)  # list of language names
    religion: Mapped[str] = mapped_column(String(200), nullable=True)

    # Phase 6 Tier 3: Generational Play
    age: Mapped[int] = mapped_column(Integer, default=25)
    lifespan: Mapped[int] = mapped_column(Integer, default=80)
    retired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    parent_character_id: Mapped[int] = mapped_column(Integer, nullable=True)
    legacy_items: Mapped[dict] = mapped_column(JSON, default=list)

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
    combat_active: Mapped[bool] = mapped_column(Boolean, default=False)
    combat_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    log_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    gm_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    session_recap_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    current_era: Mapped[str] = mapped_column(String(200), nullable=True)
    world_map_url: Mapped[str] = mapped_column(Text, nullable=True)
    default_spawn_location_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GuildGM(Base):
    """DB-backed GM roster per guild (supplements the role-based check)."""
    __tablename__ = "guild_gms"
    __table_args__ = (UniqueConstraint("guild_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    added_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    added_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PendingApproval(Base):
    """Stat change requests waiting for GM approval."""
    __tablename__ = "pending_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    character_name: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(50), nullable=False)
    old_value: Mapped[str] = mapped_column(Text, nullable=True)
    new_value: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    reviewed_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 4: AI Config ────────────────────────────────────────────────────────

class AIConfig(Base):
    """Per-guild AI feature toggles — all OFF by default."""
    __tablename__ = "ai_configs"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    narration_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    narration_style: Mapped[str] = mapped_column(String(20), default="epic")
    npc_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    session_summary_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Phase 4: Session Log ──────────────────────────────────────────────────────

class SessionLog(Base):
    """Record of a play session with auto-summary."""
    __tablename__ = "session_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    characters_present: Mapped[dict] = mapped_column(JSON, default=list)
    summary_text: Mapped[str] = mapped_column(Text, nullable=True)
    combat_count: Mapped[int] = mapped_column(Integer, default=0)
    quest_completions: Mapped[int] = mapped_column(Integer, default=0)
    total_xp: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 4: Boss System ──────────────────────────────────────────────────────

class BossTemplate(Base):
    """Reusable boss encounter template."""
    __tablename__ = "boss_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=True)

    hp_max: Mapped[int] = mapped_column(Integer, nullable=False)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False)
    attack_bonus: Mapped[int] = mapped_column(Integer, default=4)
    damage_dice: Mapped[str] = mapped_column(String(20), nullable=False)
    damage_bonus: Mapped[int] = mapped_column(Integer, default=0)
    xp_value: Mapped[int] = mapped_column(Integer, default=500)
    gold_drop: Mapped[int] = mapped_column(Integer, default=0)

    loot_table: Mapped[dict] = mapped_column(JSON, default=list)
    phase_count: Mapped[int] = mapped_column(Integer, default=1)
    phase_thresholds: Mapped[dict] = mapped_column(JSON, default=list)
    phase_abilities: Mapped[dict] = mapped_column(JSON, default=dict)

    legendary_actions: Mapped[dict] = mapped_column(JSON, default=list)
    legendary_action_count: Mapped[int] = mapped_column(Integer, default=3)

    minion_template_id: Mapped[int] = mapped_column(Integer, nullable=True)
    minion_count_per_summon: Mapped[int] = mapped_column(Integer, default=2)

    is_lair_boss: Mapped[bool] = mapped_column(Boolean, default=False)
    lair_actions: Mapped[dict] = mapped_column(JSON, default=list)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SpawnedBoss(Base):
    """An active boss encounter in a channel."""
    __tablename__ = "spawned_bosses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    combat_session_id: Mapped[str] = mapped_column(String(100), nullable=True)

    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hp_current: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_max: Mapped[int] = mapped_column(Integer, nullable=False)
    armor_class: Mapped[int] = mapped_column(Integer, nullable=False)
    attack_bonus: Mapped[int] = mapped_column(Integer, default=4)
    damage_dice: Mapped[str] = mapped_column(String(20), nullable=False)
    damage_bonus: Mapped[int] = mapped_column(Integer, default=0)
    xp_value: Mapped[int] = mapped_column(Integer, default=500)
    gold_drop: Mapped[int] = mapped_column(Integer, default=0)
    loot_table: Mapped[dict] = mapped_column(JSON, default=list)

    current_phase: Mapped[int] = mapped_column(Integer, default=1)
    phase_thresholds: Mapped[dict] = mapped_column(JSON, default=list)
    phase_abilities: Mapped[dict] = mapped_column(JSON, default=dict)

    legendary_actions: Mapped[dict] = mapped_column(JSON, default=list)
    legendary_actions_remaining: Mapped[int] = mapped_column(Integer, default=3)
    legendary_action_count: Mapped[int] = mapped_column(Integer, default=3)

    minion_template_id: Mapped[int] = mapped_column(Integer, nullable=True)
    minion_count_per_summon: Mapped[int] = mapped_column(Integer, default=2)
    parent_boss_id: Mapped[int] = mapped_column(Integer, nullable=True)

    is_lair_boss: Mapped[bool] = mapped_column(Boolean, default=False)
    lair_actions: Mapped[dict] = mapped_column(JSON, default=list)

    conditions: Mapped[dict] = mapped_column(JSON, default=list)
    forced_target_id: Mapped[int] = mapped_column(BigInteger, nullable=True)

    spawned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    spawned_by: Mapped[int] = mapped_column(BigInteger, nullable=False)


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


# ── Phase 3: Location System ─────────────────────────────────────────────

class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    short_description: Mapped[str] = mapped_column(String(200), nullable=True)
    location_type: Mapped[str] = mapped_column(String(30), nullable=False)
    parent_id: Mapped[int] = mapped_column(Integer, nullable=True)

    image_url: Mapped[str] = mapped_column(Text, nullable=True)
    map_x: Mapped[float] = mapped_column(Float, default=0.0)
    map_y: Mapped[float] = mapped_column(Float, default=0.0)

    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_safe: Mapped[bool] = mapped_column(Boolean, default=False)
    is_indoors: Mapped[bool] = mapped_column(Boolean, default=False)

    biome: Mapped[str] = mapped_column(String(30), nullable=True)
    danger_level: Mapped[int] = mapped_column(Integer, default=0)
    population_density: Mapped[str] = mapped_column(String(20), default="sparse")
    lighting: Mapped[str] = mapped_column(String(20), default="bright")
    ambient_texts: Mapped[dict] = mapped_column(JSON, default=list)
    ambient_sounds: Mapped[str] = mapped_column(String(200), nullable=True)

    required_key_item: Mapped[str] = mapped_column(String(100), nullable=True)
    required_quest_id: Mapped[int] = mapped_column(Integer, nullable=True)
    discovered_by: Mapped[int] = mapped_column(BigInteger, nullable=True)

    ground_items: Mapped[dict] = mapped_column(JSON, default=list)
    hazards: Mapped[dict] = mapped_column(JSON, default=list)
    resources: Mapped[dict] = mapped_column(JSON, default=dict)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class LocationConnection(Base):
    __tablename__ = "location_connections"
    __table_args__ = (UniqueConstraint("guild_id", "from_location_id", "to_location_id", "direction"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    from_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    to_location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=True)

    is_locked: Mapped[bool] = mapped_column(Boolean, default=False)
    required_key_item: Mapped[str] = mapped_column(String(100), nullable=True)

    is_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    search_dc: Mapped[int] = mapped_column(Integer, default=15)

    travel_time_minutes: Mapped[int] = mapped_column(Integer, default=0)
    cross_guild_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    cross_location_id: Mapped[int] = mapped_column(Integer, nullable=True)


class CharacterLocation(Base):
    __tablename__ = "character_locations"
    __table_args__ = (UniqueConstraint("character_id", "guild_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    arrived_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: NPC System ──────────────────────────────────────────────────

class NPC(Base):
    __tablename__ = "npcs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(100), nullable=True)
    race: Mapped[str] = mapped_column(String(50), nullable=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=True)
    age: Mapped[str] = mapped_column(String(20), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    appearance: Mapped[str] = mapped_column(Text, nullable=True)

    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    is_roaming: Mapped[bool] = mapped_column(Boolean, default=False)

    disposition: Mapped[str] = mapped_column(String(20), default="neutral")
    is_hostile: Mapped[bool] = mapped_column(Boolean, default=False)
    is_killable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_dead: Mapped[bool] = mapped_column(Boolean, default=False)

    hp_max: Mapped[int] = mapped_column(Integer, default=20)
    hp_current: Mapped[int] = mapped_column(Integer, default=20)
    armor_class: Mapped[int] = mapped_column(Integer, default=10)
    attack_bonus: Mapped[int] = mapped_column(Integer, default=2)
    damage_dice: Mapped[str] = mapped_column(String(20), default="1d6")
    damage_bonus: Mapped[int] = mapped_column(Integer, default=0)
    xp_value: Mapped[int] = mapped_column(Integer, default=50)

    gold: Mapped[int] = mapped_column(Integer, default=0)
    shop_inventory: Mapped[dict] = mapped_column(JSON, default=dict)

    faction_id: Mapped[int] = mapped_column(Integer, nullable=True)

    greeting: Mapped[str] = mapped_column(Text, nullable=True)
    dialogue_topics: Mapped[dict] = mapped_column(JSON, default=dict)

    image_url: Mapped[str] = mapped_column(Text, nullable=True)
    proxy_name: Mapped[str] = mapped_column(String(100), nullable=True)
    proxy_avatar: Mapped[str] = mapped_column(Text, nullable=True)
    proxy_prefix: Mapped[str] = mapped_column(String(20), nullable=True)
    proxy_mode: Mapped[str] = mapped_column(String(20), default="manual")

    gm_user_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class NPCMemory(Base):
    __tablename__ = "npc_memories"
    __table_args__ = (UniqueConstraint("npc_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    npc_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    first_met: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_spoke: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    interaction_count: Mapped[int] = mapped_column(Integer, default=0)
    attitude: Mapped[int] = mapped_column(Integer, default=0)
    favors_done: Mapped[int] = mapped_column(Integer, default=0)
    knows_name: Mapped[bool] = mapped_column(Boolean, default=False)
    topics_discussed: Mapped[dict] = mapped_column(JSON, default=list)
    last_topic: Mapped[str] = mapped_column(String(100), nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=True)


class NPCWebhookCache(Base):
    __tablename__ = "npc_webhook_caches"
    __table_args__ = (UniqueConstraint("guild_id", "channel_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    webhook_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(100), nullable=False)
    npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: Quest System ────────────────────────────────────────────────

class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    journal_entry: Mapped[str] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_repeatable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    min_level: Mapped[int] = mapped_column(Integer, default=1)

    required_quest_id: Mapped[int] = mapped_column(Integer, nullable=True)
    required_faction: Mapped[str] = mapped_column(String(100), nullable=True)
    required_reputation: Mapped[str] = mapped_column(String(20), nullable=True)

    quest_type: Mapped[str] = mapped_column(String(30), default="standard")

    reward_xp: Mapped[int] = mapped_column(Integer, default=0)
    reward_gold: Mapped[int] = mapped_column(Integer, default=0)
    reward_items: Mapped[dict] = mapped_column(JSON, default=list)
    reward_faction_rep: Mapped[dict] = mapped_column(JSON, default=dict)

    start_location_id: Mapped[int] = mapped_column(Integer, nullable=True)
    end_location_id: Mapped[int] = mapped_column(Integer, nullable=True)
    giver_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    turnin_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class QuestObjective(Base):
    __tablename__ = "quest_objectives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quest_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    objective_type: Mapped[str] = mapped_column(String(30), nullable=False)

    target_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    target_enemy_type: Mapped[str] = mapped_column(String(100), nullable=True)
    required_count: Mapped[int] = mapped_column(Integer, default=1)

    talk_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    target_location_id: Mapped[int] = mapped_column(Integer, nullable=True)

    item_name: Mapped[str] = mapped_column(String(100), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=1)

    explore_location_id: Mapped[int] = mapped_column(Integer, nullable=True)

    use_item: Mapped[str] = mapped_column(String(100), nullable=True)
    use_location_id: Mapped[int] = mapped_column(Integer, nullable=True)

    escort_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    escort_destination_id: Mapped[int] = mapped_column(Integer, nullable=True)

    is_optional: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden_until: Mapped[int] = mapped_column(Integer, nullable=True)


class PlayerQuest(Base):
    __tablename__ = "player_quests"
    __table_args__ = (UniqueConstraint("character_id", "quest_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    quest_id: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="accepted")

    progress: Mapped[dict] = mapped_column(JSON, default=dict)

    accepted_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    turned_in_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ── Phase 3: Faction System ──────────────────────────────────────────────

class Faction(Base):
    __tablename__ = "factions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    faction_type: Mapped[str] = mapped_column(String(30), default="guild")

    color: Mapped[str] = mapped_column(String(7), default="#6366F1")
    icon_emoji: Mapped[str] = mapped_column(String(10), nullable=True)

    starting_rep: Mapped[int] = mapped_column(Integer, default=0)
    leader_npc_id: Mapped[int] = mapped_column(Integer, nullable=True)
    headquarters_location_id: Mapped[int] = mapped_column(Integer, nullable=True)

    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FactionReputation(Base):
    __tablename__ = "faction_reputations"
    __table_args__ = (UniqueConstraint("character_id", "faction_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    faction_id: Mapped[int] = mapped_column(Integer, nullable=False)

    reputation: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FactionPerk(Base):
    __tablename__ = "faction_perks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    faction_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    required_tier: Mapped[str] = mapped_column(String(20), nullable=False)
    perk_type: Mapped[str] = mapped_column(String(30), nullable=False)
    perk_data: Mapped[dict] = mapped_column(JSON, nullable=False)


# ── Phase 3: Weather & Time ──────────────────────────────────────────────

class WeatherState(Base):
    __tablename__ = "weather_states"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    weather_type: Mapped[str] = mapped_column(String(20), default="clear")
    temperature: Mapped[str] = mapped_column(String(20), default="moderate")
    changed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorldTime(Base):
    __tablename__ = "world_times"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    mode: Mapped[str] = mapped_column(String(20), default="automatic")
    current_hour: Mapped[int] = mapped_column(Integer, default=8)
    current_day: Mapped[int] = mapped_column(Integer, default=1)
    current_month: Mapped[int] = mapped_column(Integer, default=3)
    current_year: Mapped[int] = mapped_column(Integer, default=847)
    last_real_timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    manual_offset_hours: Mapped[int] = mapped_column(Integer, default=0)
    season: Mapped[str] = mapped_column(String(20), default="spring")


# ── Phase 3: Tutorial ────────────────────────────────────────────────────

class TutorialProgress(Base):
    __tablename__ = "tutorial_progress"
    __table_args__ = (UniqueConstraint("user_id", "guild_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    completed_steps: Mapped[dict] = mapped_column(JSON, default=list)
    current_step: Mapped[int] = mapped_column(Integer, default=0)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ── Phase 3: Lore ────────────────────────────────────────────────────────

class LoreEntry(Base):
    __tablename__ = "lore_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(30), default="lore")
    tags: Mapped[dict] = mapped_column(JSON, default=list)
    is_canon: Mapped[bool] = mapped_column(Boolean, default=True)
    is_rumor: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(20), default="public")
    linked_entry_ids: Mapped[dict] = mapped_column(JSON, default=list)
    # Phase 6: Player-specific lore secrets & player submissions
    visibility_whitelist: Mapped[dict] = mapped_column(JSON, default=list)
    submitted_by: Mapped[int] = mapped_column(BigInteger, nullable=True)
    importance: Mapped[int] = mapped_column(Integer, default=5)
    image_url: Mapped[str] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ── Phase 3: Party ───────────────────────────────────────────────────────

class PartyGroup(Base):
    __tablename__ = "party_groups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    leader_character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PartyMember(Base):
    __tablename__ = "party_members"
    __table_args__ = (UniqueConstraint("party_id", "character_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    party_id: Mapped[int] = mapped_column(Integer, nullable=False)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: Housing ─────────────────────────────────────────────────────

class PlayerHousing(Base):
    __tablename__ = "player_housings"
    __table_args__ = (UniqueConstraint("character_id", "guild_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    location_id: Mapped[int] = mapped_column(Integer, nullable=False)
    purchase_price: Mapped[int] = mapped_column(Integer, default=500)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: Crafting ────────────────────────────────────────────────────

class CraftingRecipe(Base):
    __tablename__ = "crafting_recipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    output_item: Mapped[str] = mapped_column(String(100), nullable=False)
    output_qty: Mapped[int] = mapped_column(Integer, default=1)
    ingredients: Mapped[dict] = mapped_column(JSON, default=list)
    required_location_type: Mapped[str] = mapped_column(String(30), nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 3: Events ──────────────────────────────────────────────────────

class WorldScheduledEvent(Base):
    __tablename__ = "world_scheduled_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    event_type: Mapped[str] = mapped_column(String(30), default="session")
    location_id: Mapped[int] = mapped_column(Integer, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class EventRSVP(Base):
    __tablename__ = "event_rsvps"
    __table_args__ = (UniqueConstraint("event_id", "user_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="attending")


# ── Phase 3: Training ────────────────────────────────────────────────────

class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    character_id: Mapped[int] = mapped_column(Integer, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    rounds_survived: Mapped[int] = mapped_column(Integer, default=0)
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0)
    damage_taken: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[str] = mapped_column(String(20), nullable=True)


# ── Phase 3: World Template ──────────────────────────────────────────────

class WorldTemplate(Base):
    __tablename__ = "world_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    template_data: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Map Consistency ────────────────────────────────────────────────────

class GuildMapCache(Base):
    """Persistent world map cache so the same map survives bot restarts."""
    __tablename__ = "guild_map_cache"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    map_url: Mapped[str] = mapped_column(Text, nullable=True)
    map_bytes_b64: Mapped[str] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GuildMapAnnotation(Base):
    """Overlay annotations on the world map (road blocks, danger zones, icons, labels)."""
    __tablename__ = "guild_map_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    annotation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False)
    y: Mapped[float] = mapped_column(Float, nullable=False)
    color: Mapped[str] = mapped_column(String(7), default="#EF4444")
    label: Mapped[str] = mapped_column(String(100), nullable=True)
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Economy: Houses ──────────────────────────────────────────────────────────

class House(Base):
    """Player-owned dwellings with tier upgrades in a Murim world."""
    __tablename__ = "houses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), unique=True, nullable=False)
    tier: Mapped[int] = mapped_column(Integer, default=1)
    purchased_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    upgraded_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)


# ── Economy: Market ──────────────────────────────────────────────────────────

class MarketListing(Base):
    """Player-to-player item listings."""
    __tablename__ = "market_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    sold: Mapped[bool] = mapped_column(Boolean, default=False)


class AuctionListing(Base):
    """Time-limited auctions with bidding."""
    __tablename__ = "auction_listings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    seller_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=False)
    item_name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    start_price: Mapped[int] = mapped_column(Integer, nullable=False)
    current_bid: Mapped[int] = mapped_column(Integer, nullable=True)
    current_bidder_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), nullable=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    ended: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Economy: Daily Rewards ───────────────────────────────────────────────────

class DailyReward(Base):
    """Streak-based daily Spirit Stone rewards."""
    __tablename__ = "daily_rewards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(ForeignKey("characters.id"), unique=True, nullable=False)
    last_claimed: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    streak: Mapped[int] = mapped_column(Integer, default=0)


# ── Phase 4: Title System ─────────────────────────────────────────────────

class Title(Base):
    """A title that can be awarded to characters (e.g. 'The Undying', 'Dragon Slayer')."""
    __tablename__ = "titles"
    __table_args__ = (UniqueConstraint("guild_id", "name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, default="common")
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_unique: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_unlock_condition: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CharacterTitle(Base):
    """Junction table linking characters to titles they hold."""
    __tablename__ = "character_titles"
    __table_args__ = (UniqueConstraint("character_id", "title_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id", ondelete="CASCADE"), nullable=False)
    title_id: Mapped[int] = mapped_column(Integer, ForeignKey("titles.id", ondelete="CASCADE"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    awarded_by: Mapped[str] = mapped_column(String, nullable=True)
    awarded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 6: Achievements ─────────────────────────────────────────────────

class Achievement(Base):
    """Achievements earned by characters."""
    __tablename__ = "achievements"
    __table_args__ = (UniqueConstraint("character_id", "achievement_key"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id"))
    guild_id: Mapped[int] = mapped_column(BigInteger)
    achievement_key: Mapped[str] = mapped_column(String(100))
    achieved_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ── Phase 6: Visions ─────────────────────────────────────────────────────

class Vision(Base):
    """Dreams and visions received by characters."""
    __tablename__ = "visions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    character_id: Mapped[int] = mapped_column(Integer, ForeignKey("characters.id"))
    guild_id: Mapped[int] = mapped_column(BigInteger)
    vision_text: Mapped[str] = mapped_column(Text)
    received_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    trigger: Mapped[str] = mapped_column(String(50), default="rest")


# ── Phase 6: Notification Config ──────────────────────────────────────────

class NotificationConfig(Base):
    """Per-user notification preferences."""
    __tablename__ = "notification_configs"
    __table_args__ = (UniqueConstraint("user_id", "guild_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    guild_id: Mapped[int] = mapped_column(BigInteger)
    faction_changes: Mapped[bool] = mapped_column(Boolean, default=True)
    quest_objectives: Mapped[bool] = mapped_column(Boolean, default=True)
    world_events: Mapped[bool] = mapped_column(Boolean, default=False)
    npc_movements: Mapped[bool] = mapped_column(Boolean, default=False)
    lore_unlocks: Mapped[bool] = mapped_column(Boolean, default=True)


# ── Phase 6 Tier 2: Investigation ─────────────────────────────────────────

class Investigation(Base):
    """Player investigation/mystery case."""
    __tablename__ = "investigations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")  # open, solved, closed
    created_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Clue(Base):
    """A clue discovered during an investigation."""
    __tablename__ = "clues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    investigation_id: Mapped[int] = mapped_column(Integer, ForeignKey("investigations.id"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    discovered_by: Mapped[int] = mapped_column(BigInteger, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    connections: Mapped[dict] = mapped_column(JSON, default=list)  # list of connected clue_ids
    discovered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Phase 6 Tier 2: Language System ───────────────────────────────────────

class Language(Base):
    """A custom language in the world."""
    __tablename__ = "languages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    script_type: Mapped[str] = mapped_column(String(100), nullable=True)
    common_phrases: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


# ── Phase 6 Tier 2: Religion System ───────────────────────────────────────

class Religion(Base):
    """A religion/pantheon in the world."""
    __tablename__ = "religions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    deity_name: Mapped[str] = mapped_column(String(200), nullable=True)
    domains: Mapped[dict] = mapped_column(JSON, default=list)
    holy_symbol: Mapped[str] = mapped_column(String(500), nullable=True)
    tenets: Mapped[dict] = mapped_column(JSON, default=list)
    clergy_notes: Mapped[str] = mapped_column(Text, nullable=True)
    associated_faction_id: Mapped[int] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
