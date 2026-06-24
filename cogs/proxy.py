import discord
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character

# Webhook cache: channel_id → discord.Webhook
_webhook_cache: dict[int, discord.Webhook] = {}

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
            await webhook.send(
                content=inner,
                username=char.name,
                avatar_url=avatar,
                allowed_mentions=discord.AllowedMentions(everyone=False, roles=False),
            )
        except discord.Forbidden:
            try:
                await message.author.send(
                    f"⚠️ **Proxy failed in #{message.channel.name}** — I need **Manage Webhooks** permission to post as your character.\nAsk a server admin to grant it to me."
                )
            except discord.Forbidden:
                pass
        except discord.HTTPException:
            pass


async def setup(bot):
    await bot.add_cog(ProxyCog(bot))
