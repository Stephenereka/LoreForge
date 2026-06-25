from datetime import datetime
from sqlalchemy import select, update
from database.session import get_db
from database.models import Quest, QuestObjective, PlayerQuest, Character, Faction
from services.leveling import check_level_up, hp_gain_on_level, xp_bar, ASI_LEVELS
from services.faction_service import change_reputation


async def check_quest_objectives(db, guild_id: int, character_id: int, trigger_type: str, trigger_data: dict) -> list[str]:
    """
    Check all active quests for this character against a trigger.
    Returns list of quest names that were completed.
    """
    result = await db.execute(
        select(PlayerQuest).where(
            PlayerQuest.character_id == character_id,
            PlayerQuest.guild_id == guild_id,
            PlayerQuest.status == "accepted",
        )
    )
    player_quests = list(result.scalars().all())
    completed_quest_names = []

    for pq in player_quests:
        quest_result = await db.execute(
            select(Quest).where(Quest.id == pq.quest_id, Quest.guild_id == guild_id)
        )
        quest = quest_result.scalar_one_or_none()
        if not quest:
            continue

        objs_result = await db.execute(
            select(QuestObjective).where(
                QuestObjective.quest_id == quest.id,
                QuestObjective.guild_id == guild_id,
            ).order_by(QuestObjective.order)
        )
        objectives = list(objs_result.scalars().all())

        progress = dict(pq.progress or {})
        changed = False

        for obj in objectives:
            obj_key = str(obj.id)
            current = progress.get(obj_key, 0)
            target = obj.required_count
            if current >= target:
                continue

            if trigger_type != obj.objective_type:
                continue

            matched = False

            if trigger_type == "kill_enemy":
                enemy_type = trigger_data.get("enemy_type", "")
                if obj.target_enemy_type and obj.target_enemy_type.lower() in enemy_type.lower():
                    matched = True
            elif trigger_type == "kill_npc":
                npc_id = trigger_data.get("npc_id")
                if npc_id and npc_id == obj.target_npc_id:
                    matched = True
            elif trigger_type == "travel_to":
                target_loc = trigger_data.get("location_id")
                if target_loc and target_loc == obj.target_location_id:
                    matched = True
            elif trigger_type == "collect_item":
                item = trigger_data.get("item_name", "")
                if obj.item_name and obj.item_name.lower() == item.lower():
                    matched = True
                    progress[obj_key] = min(target, current + trigger_data.get("qty", 1))
            elif trigger_type == "reach_level":
                new_level = trigger_data.get("level", 0)
                if obj.required_count and new_level >= obj.required_count:
                    matched = True
            elif trigger_type == "faction_rep":
                faction_id = trigger_data.get("faction_id")
                tier = trigger_data.get("tier", "")
                if obj.explore_location_id == faction_id:  # using explore_location_id as faction_rep target
                    matched = True

            if matched:
                progress[obj_key] = target  # Set to target (one-time or counted)
                changed = True

        if changed:
            pq.progress = progress

        # Check if all non-optional objectives are complete
        all_complete = all(
            progress.get(str(o.id), 0) >= o.required_count
            for o in objectives if not o.is_optional
        )
        if all_complete and pq.status == "accepted":
            pq.status = "completed"
            pq.completed_at = datetime.utcnow()
            completed_quest_names.append(quest.name)

            # Auto-award rewards
            char_result = await db.execute(
                select(Character).where(Character.id == character_id)
            )
            char = char_result.scalar_one_or_none()
            if char:
                if quest.reward_xp > 0:
                    char.xp = (char.xp or 0) + quest.reward_xp
                    new_level = check_level_up(char.xp, char.level)
                    if new_level:
                        hp_gain = hp_gain_on_level(char.char_class, char.constitution)
                        char.level = new_level
                        char.hp_max = char.hp_max + hp_gain
                        char.hp_current = min(char.hp_current + hp_gain, char.hp_max)
                if quest.reward_gold > 0:
                    char.gold = (char.gold or 0) + quest.reward_gold
                # Items
                reward_items = quest.reward_items or []
                for item_entry in reward_items:
                    inv = list(char.inventory or [])
                    inv.append({"key": item_entry.get("item_name", "unknown"), "qty": item_entry.get("qty", 1), "type": "item"})
                    char.inventory = inv
                # Faction rep
                faction_rep = quest.reward_faction_rep or {}
                for faction_name, rep_amount in faction_rep.items():
                    faction_result = await db.execute(
                        select(Faction).where(Faction.name == faction_name, Faction.guild_id == guild_id)
                    )
                    faction = faction_result.scalar_one_or_none()
                    if faction:
                        await change_reputation(character_id, guild_id, faction.id, rep_amount, f"Quest: {quest.name}")

    return completed_quest_names


async def check_objective_progress(character_id: int, guild_id: int, event_type: str, event_data: dict):
    """Legacy wrapper — calls check_quest_objectives."""
    async with get_db() as db:
        await check_quest_objectives(db, guild_id, character_id, event_type, event_data)


async def award_quest_rewards(character_id: int, guild_id: int, quest_id: int) -> list[str]:
    """Award XP, gold, items, faction rep, location/quest unlocks for a completed quest."""
    messages = []

    async with get_db() as db:
        quest_result = await db.execute(
            select(Quest).where(Quest.id == quest_id, Quest.guild_id == guild_id)
        )
        quest = quest_result.scalar_one_or_none()
        if not quest:
            return ["Quest not found."]

        char_result = await db.execute(
            select(Character).where(Character.id == character_id, Character.guild_id == guild_id)
        )
        char = char_result.scalar_one_or_none()
        if not char:
            return ["Character not found."]

        # XP
        if quest.reward_xp > 0:
            char.xp = (char.xp or 0) + quest.reward_xp
            messages.append(f"✨ **+{quest.reward_xp} XP**")

            new_level = check_level_up(char.xp, char.level)
            if new_level:
                hp_gain = hp_gain_on_level(char.char_class, char.constitution)
                char.level = new_level
                char.hp_max = char.hp_max + hp_gain
                char.hp_current = min(char.hp_current + hp_gain, char.hp_max)
                messages.append(f"🎉 **Level Up!** → Lv{new_level} (+{hp_gain} HP)")

        # Gold
        if quest.reward_gold > 0:
            char.gold = (char.gold or 0) + quest.reward_gold
            messages.append(f"💰 **+{quest.reward_gold} gold**")

        # Items
        reward_items = quest.reward_items or []
        for item_entry in reward_items:
            if not item_entry.get("is_choice", False):
                inv = list(char.inventory or [])
                inv.append({"key": item_entry["item_name"], "qty": item_entry.get("qty", 1), "type": "item"})
                char.inventory = inv
                messages.append(f"📦 Received **{item_entry['item_name']}** x{item_entry.get('qty', 1)}")

        # Faction rep
        faction_rep = quest.reward_faction_rep or {}
        for faction_name, rep_amount in faction_rep.items():
            faction_result = await db.execute(
                select(Faction).where(Faction.name == faction_name, Faction.guild_id == guild_id)
            )
            faction = faction_result.scalar_one_or_none()
            if faction:
                rep_result = await change_reputation(character_id, guild_id, faction.id, rep_amount, f"Quest: {quest.name}")
                tier_info = ""
                if rep_result["tier_changed"]:
                    tier_info = f" (new tier: **{rep_result['new_tier']}**)"
                messages.append(f"{'👍' if rep_amount > 0 else '👎'} {rep_amount:+} rep with **{faction_name}**{tier_info}")

        # Update PlayerQuest
        pq_result = await db.execute(
            select(PlayerQuest).where(
                PlayerQuest.character_id == character_id,
                PlayerQuest.quest_id == quest_id,
            )
        )
        pq = pq_result.scalar_one_or_none()
        if pq:
            pq.status = "turned_in"
            pq.turned_in_at = datetime.utcnow()

        return messages


async def get_available_quests(character_id: int, guild_id: int) -> list[Quest]:
    """Get quests available for a character (filtered by level, prerequisites, faction)."""
    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(Character.id == character_id, Character.guild_id == guild_id)
        )
        char = char_result.scalar_one_or_none()
        if not char:
            return []

        # Get completed quest IDs
        completed = await db.execute(
            select(PlayerQuest.quest_id).where(
                PlayerQuest.character_id == character_id,
                PlayerQuest.status.in_(["completed", "turned_in"]),
            )
        )
        completed_ids = {row[0] for row in completed.all()}

        # Get all active quests
        result = await db.execute(
            select(Quest).where(
                Quest.guild_id == guild_id,
                Quest.is_active == True,
            )
        )
        all_quests = list(result.scalars().all())

    available = []
    for q in all_quests:
        if q.id in completed_ids and not q.is_repeatable:
            continue
        if q.min_level > char.level:
            continue
        if q.required_quest_id and q.required_quest_id not in completed_ids:
            continue
        available.append(q)

    return available
