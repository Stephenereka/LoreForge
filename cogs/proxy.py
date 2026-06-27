import discord
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, GuildGM

# Webhook cache: channel_id → discord.Webhook
_webhook_cache: dict[int, discord.Webhook] = {}

# Proxy message tracking for ❌ deletion: message_id → (user_id, channel_id)
_proxy_msg_authors: dict[int, int] = {}  # message_id → user_id
_proxy_msg_channels: dict[int, int] = {}  # message_id → channel_id
_MAX_PROXY_TRACKED = 1000

WEBHOOK_NAME = "LoreForge Proxy"


async def _get_or_create_webhook(channel: discord.TextChannel) -> discord.Webhook | None:
    if channel.id in _webhook_cache:
        return _webhook_cache[channel.id]
    try:
        existing = await channel.webhooks()
        for wh in existing:
            if wh.name == WEBHOOK_NAME:
                _webhook_cache[channel.id] = wh
                return wh
        wh = await channel.create_webhook(name=WEBHOOK_NAME)
        _webhook_cache[channel.id] = wh
        return wh
    except (discord.Forbidden, discord.HTTPException):
        return None


def _match_proxy(content: str, proxy_open: str, proxy_close: str | None) -> str | None:
    """Return the inner message if content matches the proxy pattern, else None."""
    if not proxy_open:
        return None
    if proxy_close:
        if content.startswith(proxy_open) and content.endswith(proxy_close) and len(content) > len(proxy_open) + len(proxy_close):
            return content[len(proxy_open):-len(proxy_close)].strip()
    else:
        # Prefix-only
        if content.startswith(proxy_open) and len(content) > len(proxy_open):
            return content[len(proxy_open):].strip()
    return None


class ProxyCog(commands.Cog, name="Proxy"):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, DMs, empty messages
        if message.author.bot:
            return
        if not message.guild:
            return
        if not message.content:
            return

        content = message.content

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(
                    Character.user_id == message.author.id,
                    Character.guild_id == message.guild.id,
                    Character.is_dead == False,
                    Character.proxy_open.isnot(None),
                )
            )
            candidates = list(result.scalars().all())

        # Find which character's proxy brackets match this message
        char = None
        inner = None
        for c in candidates:
            matched = _match_proxy(content, c.proxy_open, c.proxy_close)
            if matched is not None:
                char = c
                inner = matched
                break

        if not char or inner is None:
            return
        if not inner:
            return

        # Requires Manage Webhooks permission in the channel
        if not isinstance(message.channel, discord.TextChannel):
            return

        webhook = await _get_or_create_webhook(message.channel)
        if not webhook:
            try:
                await message.author.send(
                    f"⚠️ **Proxy failed in #{message.channel.name}** — I need **Manage Webhooks** permission.\nAsk a server admin to grant it to me."
                )
            except discord.Forbidden:
                pass
            return

        avatar = char.avatar_url or message.author.display_avatar.url

        try:
            await message.delete()
        except discord.Forbidden:
            try:
                await message.author.send(
                    f"⚠️ **Proxy failed in #{message.channel.name}** — I need **Manage Messages** permission to delete your original message.\nAsk a server admin to grant it to me."
                )
            except discord.Forbidden:
                pass
            return
        except discord.HTTPException:
            return

        try:
            msg = await webhook.send(
                content=inner,
                username=char.name,
                avatar_url=avatar,
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
                wait=True,
            )
            # Track the proxy message for ❌ deletion (LRU evict if full)
            if len(_proxy_msg_authors) >= _MAX_PROXY_TRACKED:
                oldest_id = next(iter(_proxy_msg_authors))
                _proxy_msg_authors.pop(oldest_id, None)
                _proxy_msg_channels.pop(oldest_id, None)
            _proxy_msg_authors[msg.id] = message.author.id
            _proxy_msg_channels[msg.id] = message.channel.id
        except discord.NotFound:
            # Webhook was deleted — clear cache and recreate
            _webhook_cache.pop(message.channel.id, None)
            webhook = await _get_or_create_webhook(message.channel)
            if webhook:
                try:
                    msg = await webhook.send(
                        content=inner,
                        username=char.name,
                        avatar_url=avatar,
                        allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
                        wait=True,
                    )
                    _proxy_msg_authors[msg.id] = message.author.id
                    _proxy_msg_channels[msg.id] = message.channel.id
                except discord.HTTPException:
                    pass
        except discord.Forbidden:
            try:
                await message.author.send(
                    f"⚠️ **Proxy failed in #{message.channel.name}** — I need **Manage Webhooks** permission to post as your character.\nAsk a server admin to grant it to me."
                )
            except discord.Forbidden:
                pass
        except discord.HTTPException:
            pass


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        """Delete a proxy message when the author or a GM reacts with ❌."""
        if payload.emoji.name != '❌':
            return
        if payload.user_id == self.bot.user.id:
            return
        if payload.message_id not in _proxy_msg_authors:
            return

        original_author_id = _proxy_msg_authors[payload.message_id]
        channel_id = _proxy_msg_channels[payload.message_id]

        # Reactor is the original author — OK
        if payload.user_id == original_author_id:
            await self._delete_proxy_message(payload.message_id, channel_id)
            return

        # Reactor is the server owner — OK
        guild = self.bot.get_guild(payload.guild_id)
        if guild and payload.user_id == guild.owner_id:
            await self._delete_proxy_message(payload.message_id, channel_id)
            return

        # Reactor is a DB-registered GM — OK
        async with get_db() as db:
            gm_row = await db.execute(
                select(GuildGM).where(
                    GuildGM.guild_id == payload.guild_id,
                    GuildGM.user_id == payload.user_id,
                )
            )
            if gm_row.scalar_one_or_none():
                await self._delete_proxy_message(payload.message_id, channel_id)
                return

    async def _delete_proxy_message(self, message_id: int, channel_id: int) -> None:
        """Delete a tracked proxy webhook message and clean up tracking."""
        # Remove from tracking immediately so duplicate reactions don't race
        _proxy_msg_authors.pop(message_id, None)
        _proxy_msg_channels.pop(message_id, None)

        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return

        webhook = _webhook_cache.get(channel_id)
        if webhook is None:
            webhook = await _get_or_create_webhook(channel)
        if webhook is None:
            return

        try:
            await webhook.delete_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    @commands.Cog.listener()
    async def on_raw_message_delete(self, payload: discord.RawMessageDeleteEvent):
        """Clean up tracking when a message is deleted by other means."""
        _proxy_msg_authors.pop(payload.message_id, None)
        _proxy_msg_channels.pop(payload.message_id, None)


async def setup(bot):
    await bot.add_cog(ProxyCog(bot))
