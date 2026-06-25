from datetime import datetime
from sqlalchemy import select
from database.session import get_db
from database.models import NPC, NPCMemory, NPCWebhookCache


async def get_npc_response(npc: NPC, player_message: str, npc_memory: NPCMemory | None = None) -> str:
    """Get NPC response using keyword matching. Returns response text."""
    msg_lower = player_message.lower()
    topics = npc.dialogue_topics or {}

    # Check for direct keyword matches
    best_keyword = None
    best_score = 0
    for keyword in topics:
        if keyword.lower() in msg_lower:
            score = len(keyword)
            if score > best_score:
                best_score = score
                best_keyword = keyword

    if best_keyword:
        return topics[best_keyword]

    # Default responses based on memory
    if npc_memory and npc_memory.interaction_count > 0:
        if npc_memory.attitude >= 5:
            return f"Good to see you again, friend! What can I do for you?"
        elif npc_memory.attitude <= -3:
            return f"...I have nothing to say to you."
        elif npc_memory.knows_name:
            return f"Ah, it's you again. What brings you back?"
        else:
            return f"I don't believe we've met properly. What do you want?"

    if npc.greeting:
        return npc.greeting

    return "...they look at you expectantly, waiting for you to speak."


async def update_npc_memory(npc_id: int, user_id: int, guild_id: int, interaction_type: str, topic: str | None = None):
    """Update or create an NPC memory record for a player interaction."""
    async with get_db() as db:
        result = await db.execute(
            select(NPCMemory).where(
                NPCMemory.npc_id == npc_id,
                NPCMemory.user_id == user_id,
                NPCMemory.guild_id == guild_id,
            )
        )
        mem = result.scalar_one_or_none()

        now = datetime.utcnow()
        if not mem:
            mem = NPCMemory(
                npc_id=npc_id,
                user_id=user_id,
                guild_id=guild_id,
                first_met=now,
                last_spoke=now,
                interaction_count=1,
                knows_name=True,
                last_topic=topic,
                topics_discussed=[topic] if topic else [],
            )
            db.add(mem)
        else:
            mem.last_spoke = now
            mem.interaction_count += 1
            mem.last_topic = topic
            if topic:
                topics = list(mem.topics_discussed or [])
                if topic not in topics:
                    topics.append(topic)
                mem.topics_discussed = topics

            if interaction_type == "favor":
                mem.favors_done += 1
                mem.attitude = min(10, mem.attitude + 2)
            elif interaction_type == "help":
                mem.attitude = min(10, mem.attitude + 1)
            elif interaction_type == "insult":
                mem.attitude = max(-10, mem.attitude - 2)
            elif interaction_type == "talk":
                pass


async def get_or_create_npc_webhook(guild_id: int, channel_id: int, bot_http) -> tuple[int, str] | None:
    """
    Get or create a shared NPC webhook for a channel.
    Returns (webhook_id, webhook_token) or None if failed.
    Strategy: ONE shared webhook per channel named 'LoreForge NPC'.
    Override name/avatar per message using execute params.
    """
    from database.session import get_db
    from sqlalchemy import select

    async with get_db() as db:
        result = await db.execute(
            select(NPCWebhookCache).where(
                NPCWebhookCache.guild_id == guild_id,
                NPCWebhookCache.channel_id == channel_id,
                NPCWebhookCache.npc_id.is_(None),
            )
        )
        cached = result.scalar_one_or_none()

    if cached:
        return cached.webhook_id, cached.webhook_token

    # Create new webhook
    try:
        from discord import Webhook, AsyncWebhookAdapter
        import aiohttp

        channel = bot_http.get_channel(channel_id)
        if not channel:
            return None

        # Use bot's HTTP to create webhook
        webhook = await channel.create_webhook(name="LoreForge NPC")
        wh_id = webhook.id
        wh_token = webhook.token

        # Cache it
        async with get_db() as db:
            cache = NPCWebhookCache(
                guild_id=guild_id,
                channel_id=channel_id,
                webhook_id=wh_id,
                webhook_token=wh_token,
            )
            db.add(cache)

        return wh_id, wh_token
    except Exception:
        return None


async def send_npc_proxy_message(bot, channel, npc: NPC, content: str) -> bool:
    """Send a message as an NPC using the shared webhook with per-message override."""
    import aiohttp

    wh_id, wh_token = await get_or_create_npc_webhook(
        npc.guild_id, channel.id, bot.http
    )
    if not wh_id or not wh_token:
        return False

    proxy_name = npc.proxy_name or npc.name
    proxy_avatar = npc.proxy_avatar or npc.image_url

    webhook_url = f"https://discord.com/api/webhooks/{wh_id}/{wh_token}"

    payload = {
        "content": content,
        "username": proxy_name[:80],
        "allowed_mentions": {"parse": []},
    }
    if proxy_avatar:
        payload["avatar_url"] = proxy_avatar

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=payload) as resp:
                if resp.status == 404:
                    # Webhook was deleted, remove cache and retry
                    async with get_db() as db:
                        await db.execute(
                            select(NPCWebhookCache).where(
                                NPCWebhookCache.webhook_id == wh_id
                            )
                        )
                    return await send_npc_proxy_message(bot, channel, npc, content)
                return resp.status in (200, 204)
    except Exception:
        return False
