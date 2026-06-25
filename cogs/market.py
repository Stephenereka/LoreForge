import asyncio
import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import select, and_
from datetime import datetime, timedelta
from database.session import get_db
from database.models import Character, MarketListing, AuctionListing

MAX_ACTIVE_LISTINGS = 5

# ── Shared helpers ───────────────────────────────────────────────────────────

async def _get_char(interaction: discord.Interaction) -> Character | None:
    """Resolve the interacting user's character, or send ephemeral error."""
    db_session = get_db()
    async with db_session as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        return result.scalar_one_or_none()


# ── /market command group ────────────────────────────────────────────────────

market_group = app_commands.Group(name="market", description="Player marketplace for Spirit Stones")


@market_group.command(name="post", description="List an item for sale")
@app_commands.describe(
    item_name="Name of the item you're selling",
    price="Price in Spirit Stones",
    quantity="How many (default: 1)",
    description="Optional description of the item",
)
async def market_post(interaction: discord.Interaction, item_name: str, price: int, quantity: int = 1, description: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if price < 1:
        await interaction.response.send_message("Price must be at least 1 Spirit Stone.", ephemeral=True)
        return
    if quantity < 1:
        await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
        return

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        # Count active listings
        count_result = await db.execute(
            select(MarketListing).where(
                MarketListing.seller_id == char.id,
                MarketListing.sold == False,
            )
        )
        active_count = len(list(count_result.scalars().all()))
        if active_count >= MAX_ACTIVE_LISTINGS:
            await interaction.response.send_message(
                f"You already have **{MAX_ACTIVE_LISTINGS}** active listings. Cancel one first with `/market cancel`.",
                ephemeral=True,
            )
            return

        listing = MarketListing(
            seller_id=char.id,
            item_name=item_name.strip(),
            description=description.strip() if description else None,
            quantity=quantity,
            price=price,
        )
        db.add(listing)
        await db.flush()

    embed = discord.Embed(
        title="📦 Item Listed!",
        description=f"**{item_name.strip()}** x{quantity} for **{price}** Spirit Stones each",
        color=0xD97706,
    )
    if description:
        embed.add_field(name="Description", value=description.strip(), inline=False)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@market_group.command(name="browse", description="Browse all active market listings")
async def market_browse(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(MarketListing).where(MarketListing.sold == False).order_by(MarketListing.created_at.desc())
        )
        listings = list(result.scalars().all())

    if not listings:
        await interaction.response.send_message("🛒 The market is empty. Be the first to post with `/market post`!", ephemeral=True)
        return

    # Paginate — 8 per page
    per_page = 8
    pages = [listings[i:i + per_page] for i in range(0, len(listings), per_page)]

    async def build_page(page_idx: int) -> discord.Embed:
        embed = discord.Embed(
            title="🛒 Market Listings",
            description=f"Page {page_idx + 1}/{len(pages)}",
            color=0xD97706,
        )
        for listing in pages[page_idx]:
            # Get seller name
            seller_result = await db.execute(select(Character).where(Character.id == listing.seller_id))
            seller = seller_result.scalar_one_or_none()
            seller_name = seller.name if seller else "Unknown"
            embed.add_field(
                name=f"`#{listing.id}` {listing.item_name}",
                value=f"👤 **{seller_name}**  ·  🔮 **{listing.price}** each  ·  📦 x{listing.quantity}",
                inline=False,
            )
        embed.set_footer(text=interaction.user.display_name)
        return embed

    class MarketBrowseView(discord.ui.View):
        def __init__(self, page: int = 0):
            super().__init__(timeout=300)
            self.page = page
            self.pages = pages
            self._update_buttons()

        def _update_buttons(self):
            self.prev_btn.disabled = self.page == 0
            self.next_btn.disabled = self.page == len(self.pages) - 1

        @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
        async def prev_btn(self, inter: discord.Interaction, button: discord.ui.Button):
            self.page -= 1
            self._update_buttons()
            await inter.response.edit_message(embed=await build_page(self.page), view=self)

        @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
        async def next_btn(self, inter: discord.Interaction, button: discord.ui.Button):
            self.page += 1
            self._update_buttons()
            await inter.response.edit_message(embed=await build_page(self.page), view=self)

    view = MarketBrowseView(page=0)
    await interaction.response.send_message(embed=await build_page(0), view=view)


@market_group.command(name="buy", description="Buy an item from the market")
@app_commands.describe(listing_id="The listing ID (use /market browse to find it)")
async def market_buy(interaction: discord.Interaction, listing_id: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_dead == False,
            )
        )
        buyer = char_result.scalar_one_or_none()
        if not buyer:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        listing_result = await db.execute(select(MarketListing).where(MarketListing.id == listing_id))
        listing = listing_result.scalar_one_or_none()

        if not listing or listing.sold:
            await interaction.response.send_message("That listing no longer exists or has been sold.", ephemeral=True)
            return

        if listing.seller_id == buyer.id:
            await interaction.response.send_message("You can't buy your own listing!", ephemeral=True)
            return

        total_cost = listing.price * listing.quantity
        if (buyer.balance or 0) < total_cost:
            await interaction.response.send_message(
                f"You need **{total_cost}** Spirit Stones. You have **{buyer.balance or 0}**.",
                ephemeral=True,
            )
            return

        # Get seller
        seller_result = await db.execute(select(Character).where(Character.id == listing.seller_id))
        seller = seller_result.scalar_one_or_none()
        if not seller:
            await interaction.response.send_message("The seller's character no longer exists.", ephemeral=True)
            return

        # Process transaction
        buyer.balance = (buyer.balance or 0) - total_cost
        seller.balance = (seller.balance or 0) + total_cost
        listing.sold = True

    embed = discord.Embed(
        title="✅ Purchase Complete!",
        description=f"Bought **{listing.item_name}** x{listing.quantity} for **{total_cost}** Spirit Stones",
        color=0xD97706,
    )
    embed.add_field(name="🔮 Your Balance", value=f"{buyer.balance or 0} Spirit Stones", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@market_group.command(name="cancel", description="Cancel one of your active listings")
@app_commands.describe(listing_id="The listing ID to cancel")
async def market_cancel(interaction: discord.Interaction, listing_id: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char = await _get_char(interaction)
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        listing_result = await db.execute(select(MarketListing).where(MarketListing.id == listing_id))
        listing = listing_result.scalar_one_or_none()

        if not listing or listing.sold:
            await interaction.response.send_message("Listing not found or already sold.", ephemeral=True)
            return

        if listing.seller_id != char.id:
            await interaction.response.send_message("That's not your listing!", ephemeral=True)
            return

        await db.delete(listing)

    embed = discord.Embed(
        title="✅ Listing Cancelled",
        description=f"**{listing.item_name}** x{listing.quantity} removed from the market.",
        color=0xD97706,
    )
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@market_group.command(name="mine", description="See your active market listings")
async def market_mine(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        char = await _get_char(interaction)
        if not char:
            await interaction.response.send_message(
                "You don't have a character. Use `/character create`.", ephemeral=True
            )
            return

        result = await db.execute(
            select(MarketListing).where(
                MarketListing.seller_id == char.id,
                MarketListing.sold == False,
            ).order_by(MarketListing.created_at.desc())
        )
        listings = list(result.scalars().all())

    if not listings:
        await interaction.response.send_message("You have no active listings. Use `/market post` to create one.", ephemeral=True)
        return

    embed = discord.Embed(
        title="📦 Your Market Listings",
        color=0xD97706,
    )
    for listing in listings:
        embed.add_field(
            name=f"`#{listing.id}` {listing.item_name}",
            value=f"🔮 **{listing.price}** each  ·  📦 x{listing.quantity}",
            inline=False,
        )
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ── /auction command group ────────────────────────────────────────────────────

auction_group = app_commands.Group(name="auction", description="Time-limited auctions")


@auction_group.command(name="create", description="Create a new auction")
@app_commands.describe(
    item_name="Name of the item being auctioned",
    start_price="Starting price in Spirit Stones",
    duration_hours="How long the auction runs (1-72 hours)",
    quantity="How many (default: 1)",
    description="Optional description",
)
async def auction_create(interaction: discord.Interaction, item_name: str, start_price: int, duration_hours: int, quantity: int = 1, description: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if start_price < 1:
        await interaction.response.send_message("Start price must be at least 1 Spirit Stone.", ephemeral=True)
        return
    if duration_hours < 1 or duration_hours > 72:
        await interaction.response.send_message("Duration must be between 1 and 72 hours.", ephemeral=True)
        return
    if quantity < 1:
        await interaction.response.send_message("Quantity must be at least 1.", ephemeral=True)
        return

    async with get_db() as db:
        char = await _get_char(interaction)
        if not char:
            await interaction.response.send_message("You don't have a character. Use `/character create`.", ephemeral=True)
            return

        ends_at = datetime.utcnow() + timedelta(hours=duration_hours)
        auction = AuctionListing(
            seller_id=char.id,
            item_name=item_name.strip(),
            description=description.strip() if description else None,
            quantity=quantity,
            start_price=start_price,
            ends_at=ends_at,
        )
        db.add(auction)
        await db.flush()

    embed = discord.Embed(
        title="🔨 Auction Created!",
        description=f"**{item_name.strip()}** x{quantity} — Starting at **{start_price}** Spirit Stones",
        color=0xD97706,
    )
    embed.add_field(name="⏱️ Duration", value=f"{duration_hours} hours", inline=True)
    embed.add_field(name="Auction ID", value=f"`#{auction.id}`", inline=True)
    ends_timestamp = int(discord.utils.utcnow().timestamp() + duration_hours * 3600)
    embed.add_field(name="Ends", value=f"<t:{ends_timestamp}:R>", inline=False)
    if description:
        embed.add_field(name="Description", value=description.strip(), inline=False)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


@auction_group.command(name="bid", description="Place a bid on an auction")
@app_commands.describe(auction_id="The auction ID to bid on", amount="Your bid amount in Spirit Stones")
async def auction_bid(interaction: discord.Interaction, auction_id: int, amount: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    if amount < 1:
        await interaction.response.send_message("Bid must be at least 1 Spirit Stone.", ephemeral=True)
        return

    async with get_db() as db:
        bidder = await _get_char(interaction)
        if not bidder:
            await interaction.response.send_message("You don't have a character. Use `/character create`.", ephemeral=True)
            return

        auction_result = await db.execute(select(AuctionListing).where(AuctionListing.id == auction_id))
        auction = auction_result.scalar_one_or_none()

        if not auction or auction.ended:
            await interaction.response.send_message("That auction doesn't exist or has ended.", ephemeral=True)
            return

        if auction.seller_id == bidder.id:
            await interaction.response.send_message("You can't bid on your own auction!", ephemeral=True)
            return

        if datetime.utcnow() > auction.ends_at:
            auction.ended = True
            await interaction.response.send_message("That auction has already ended.", ephemeral=True)
            return

        # Determine minimum bid
        min_bid = auction.current_bid if auction.current_bid is not None else auction.start_price
        if amount <= min_bid:
            await interaction.response.send_message(
                f"The current bid is **{min_bid}** Spirit Stones. You must bid higher than that.",
                ephemeral=True,
            )
            return

        if (bidder.balance or 0) < amount:
            await interaction.response.send_message(
                f"You need **{amount}** Spirit Stones but only have **{bidder.balance or 0}**.",
                ephemeral=True,
            )
            return

        # Refund previous bidder
        if auction.current_bidder_id and auction.current_bid:
            prev_result = await db.execute(select(Character).where(Character.id == auction.current_bidder_id))
            prev_bidder = prev_result.scalar_one_or_none()
            if prev_bidder:
                prev_bidder.balance = (prev_bidder.balance or 0) + auction.current_bid

        # Deduct new bid
        bidder.balance = (bidder.balance or 0) - amount
        auction.current_bid = amount
        auction.current_bidder_id = bidder.id

    embed = discord.Embed(
        title="🔨 Bid Placed!",
        description=f"You bid **{amount}** Spirit Stones on **{auction.item_name}**",
        color=0xD97706,
    )
    ends_timestamp = int(auction.ends_at.timestamp())
    embed.add_field(name="⏱️ Ends", value=f"<t:{ends_timestamp}:R>", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed, ephemeral=True)


@auction_group.command(name="view", description="View auction details")
@app_commands.describe(auction_id="The auction ID to view")
async def auction_view(interaction: discord.Interaction, auction_id: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        auction_result = await db.execute(select(AuctionListing).where(AuctionListing.id == auction_id))
        auction = auction_result.scalar_one_or_none()

        if not auction:
            await interaction.response.send_message("Auction not found.", ephemeral=True)
            return

        seller_result = await db.execute(select(Character).where(Character.id == auction.seller_id))
        seller = seller_result.scalar_one_or_none()

        bidder_name = "None"
        if auction.current_bidder_id:
            bidder_result = await db.execute(select(Character).where(Character.id == auction.current_bidder_id))
            bidder = bidder_result.scalar_one_or_none()
            if bidder:
                bidder_name = bidder.name

    embed = discord.Embed(
        title=f"🔨 Auction `#{auction.id}` — {auction.item_name}",
        color=0xD97706,
    )
    embed.add_field(name="👤 Seller", value=seller.name if seller else "Unknown", inline=True)
    embed.add_field(name="📦 Quantity", value=str(auction.quantity), inline=True)
    embed.add_field(name="💰 Starting Price", value=f"{auction.start_price} Spirit Stones", inline=True)

    current_bid = auction.current_bid if auction.current_bid is not None else "No bids yet"
    embed.add_field(name="🔮 Current Bid", value=f"{current_bid} Spirit Stones", inline=True)
    embed.add_field(name="🏆 Highest Bidder", value=bidder_name, inline=True)

    ends_timestamp = int(auction.ends_at.timestamp())
    embed.add_field(name="⏱️ Ends", value=f"<t:{ends_timestamp}:R>", inline=True)

    if auction.description:
        embed.add_field(name="Description", value=auction.description, inline=False)

    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


@auction_group.command(name="browse", description="Browse all active auctions")
async def auction_browse(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        result = await db.execute(
            select(AuctionListing).where(
                AuctionListing.ended == False,
                AuctionListing.ends_at > datetime.utcnow(),
            ).order_by(AuctionListing.ends_at.asc())
        )
        auctions = list(result.scalars().all())

    if not auctions:
        await interaction.response.send_message("No active auctions right now.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🔨 Active Auctions",
        color=0xD97706,
    )
    for a in auctions:
        current = a.current_bid if a.current_bid is not None else f"{a.start_price} (reserve)"
        ends_timestamp = int(a.ends_at.timestamp())
        embed.add_field(
            name=f"`#{a.id}` {a.item_name}",
            value=f"🔮 **{current}**  ·  📦 x{a.quantity}  ·  ⏱️ <t:{ends_timestamp}:R>",
            inline=False,
        )
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


@auction_group.command(name="end", description="Force-end an auction early (GM only)")
@app_commands.describe(auction_id="The auction ID to end")
@app_commands.checks.has_permissions(administrator=True)
async def auction_end(interaction: discord.Interaction, auction_id: int):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works inside a server.", ephemeral=True)
        return

    async with get_db() as db:
        auction_result = await db.execute(select(AuctionListing).where(AuctionListing.id == auction_id))
        auction = auction_result.scalar_one_or_none()
        if not auction or auction.ended:
            await interaction.response.send_message("Auction not found or already ended.", ephemeral=True)
            return

        # Finalize: if there's a winner, tell who won
        winner_name = "No one"
        win_amount = 0
        if auction.current_bidder_id:
            winner_result = await db.execute(select(Character).where(Character.id == auction.current_bidder_id))
            winner = winner_result.scalar_one_or_none()
            if winner:
                winner_name = winner.name
                win_amount = auction.current_bid or 0

        auction.ended = True
        auction.ends_at = datetime.utcnow()

    embed = discord.Embed(
        title="🔨 Auction Ended (GM)",
        description=f"Auction `#{auction.id}` — **{auction.item_name}** has been ended early.",
        color=0xD97706,
    )
    embed.add_field(name="🏆 Winner", value=winner_name, inline=True)
    embed.add_field(name="🔮 Final Price", value=f"{win_amount} Spirit Stones", inline=True)
    embed.set_footer(text=interaction.user.display_name)
    await interaction.response.send_message(embed=embed)


# ── Background auction checker ───────────────────────────────────────────────

class MarketCog(commands.Cog, name="Market"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(market_group)
        bot.tree.add_command(auction_group)
        self._auction_checker.start()

    async def cog_unload(self):
        self.bot.tree.remove_command("market")
        self.bot.tree.remove_command("auction")
        self._auction_checker.cancel()

    @tasks.loop(minutes=5)
    async def _auction_checker(self):
        """Check every 5 minutes for expired auctions and finalize them."""
        await self.bot.wait_until_ready()
        now = datetime.utcnow()
        async with get_db() as db:
            result = await db.execute(
                select(AuctionListing).where(
                    AuctionListing.ended == False,
                    AuctionListing.ends_at <= now,
                )
            )
            expired = list(result.scalars().all())
            for auction in expired:
                auction.ended = True

                if auction.current_bidder_id:
                    # Notify winner via DM if possible
                    winner_result = await db.execute(
                        select(Character).where(Character.id == auction.current_bidder_id)
                    )
                    winner = winner_result.scalar_one_or_none()
                    if winner:
                        user = self.bot.get_user(winner.user_id)
                        if not user:
                            try:
                                user = await self.bot.fetch_user(winner.user_id)
                            except Exception:
                                user = None
                        if user:
                            try:
                                await user.send(
                                    f"🎉 **Auction Won!**\n"
                                    f"You won **{auction.item_name}** x{auction.quantity} "
                                    f"for **{auction.current_bid}** Spirit Stones!"
                                )
                            except discord.Forbidden:
                                pass

    @_auction_checker.before_loop
    async def _before_auction_checker(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(MarketCog(bot))
