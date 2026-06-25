import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character

trade_sessions = {}


class TradeSession:
    def __init__(self, interaction: discord.Interaction, target: discord.Member):
        self.initiator = interaction
        self.target_user = target
        self.initiator_uid = interaction.user.id
        self.target_uid = target.id
        self.initiator_items = {}
        self.target_items = {}
        self.initiator_gold = 0
        self.target_gold = 0
        self.initiator_ready = False
        self.target_ready = False
        self.state = "active"

    def is_participant(self, uid: int) -> bool:
        return uid in (self.initiator_uid, self.target_uid)

    def summary(self) -> str:
        lines = [f"**{self.initiator.user.display_name}** offers:", "```"]
        for item, qty in self.initiator_items.items():
            lines.append(f"  {item} x{qty}")
        if self.initiator_gold > 0:
            lines.append(f"  {self.initiator_gold} gold")
        lines.append("```")
        lines.append(f"**{self.target_user.display_name}** offers:", "```")
        for item, qty in self.target_items.items():
            lines.append(f"  {item} x{qty}")
        if self.target_gold > 0:
            lines.append(f"  {self.target_gold} gold")
        lines.append("```")
        if self.initiator_ready and self.target_ready:
            lines.append("\n✅ **Both ready!** Confirm below.")
        else:
            status = []
            if self.initiator_ready:
                status.append(f"✅ {self.initiator.user.display_name} ready")
            else:
                status.append(f"⏳ {self.initiator.user.display_name} not ready")
            if self.target_ready:
                status.append(f"✅ {self.target_user.display_name} ready")
            else:
                status.append(f"⏳ {self.target_user.display_name} not ready")
            lines.append("\n" + "  ·  ".join(status))
        return "\n".join(lines)


class TradeView(discord.ui.View):
    def __init__(self, session: TradeSession):
        super().__init__(timeout=300)
        self.session = session

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success, emoji="✅")
    async def accept_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if interaction.user.id == session.initiator_uid:
            session.initiator_ready = True
        elif interaction.user.id == session.target_uid:
            session.target_ready = True
        else:
            await interaction.response.send_message("You're not part of this trade.", ephemeral=True)
            return

        if session.initiator_ready and session.target_ready:
            await self._execute_trade(interaction)
        else:
            await interaction.response.edit_message(content=session.summary(), view=self)

    async def _execute_trade(self, interaction: discord.Interaction):
        session = self.session
        session.state = "completed"

        # Exchange gold
        async with get_db() as db:
            for uid, gold in [(session.initiator_uid, session.initiator_gold),
                              (session.target_uid, session.target_gold)]:
                if gold <= 0:
                    continue
                result = await db.execute(
                    select(Character).where(Character.user_id == uid, Character.guild_id == interaction.guild_id)
                )
                char = result.scalar_one_or_none()
                if char:
                    char.gold -= gold

            # Add gold to recipients
            if session.initiator_gold > 0:
                result = await db.execute(
                    select(Character).where(
                        Character.user_id == session.target_uid,
                        Character.guild_id == interaction.guild_id,
                    )
                )
                char = result.scalar_one_or_none()
                if char:
                    char.gold += session.initiator_gold

            if session.target_gold > 0:
                result = await db.execute(
                    select(Character).where(
                        Character.user_id == session.initiator_uid,
                        Character.guild_id == interaction.guild_id,
                    )
                )
                char = result.scalar_one_or_none()
                if char:
                    char.gold += session.target_gold

        await interaction.response.edit_message(
            content=f"✅ **Trade complete!**\n{session.summary()}",
            view=None,
        )
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌")
    async def cancel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        session = self.session
        if not session.is_participant(interaction.user.id):
            await interaction.response.send_message("You're not part of this trade.", ephemeral=True)
            return
        session.state = "cancelled"
        await interaction.response.edit_message(content="❌ **Trade cancelled.**", view=None)
        self.stop()

    async def on_timeout(self):
        self.session.state = "cancelled"


trade_group = app_commands.Group(name="trade", description="Trade items and gold with other players")


@trade_group.command(name="request", description="Request a trade with another player")
@app_commands.describe(user="The player to trade with")
async def trade_request(interaction: discord.Interaction, user: discord.Member):
    if user.id == interaction.user.id:
        await interaction.response.send_message("You can't trade with yourself.", ephemeral=True)
        return

    trade_id = f"{interaction.user.id}-{user.id}"
    if trade_id in trade_sessions:
        await interaction.response.send_message("A trade is already active between you two.", ephemeral=True)
        return

    session = TradeSession(interaction, user)
    trade_sessions[trade_id] = session

    embed = discord.Embed(
        title="🤝 Trade Request",
        description=f"{interaction.user.mention} wants to trade with {user.mention}!",
        color=0x6366F1,
    )
    embed.add_field(name="How it works", value="Use `/trade offer <item> [qty]` and `/trade gold <amount>` to add items. Both sides click Accept when ready.", inline=False)

    await interaction.response.send_message(
        content=f"{user.mention} — incoming trade request!",
        embed=embed,
        view=TradeView(session),
    )


@trade_group.command(name="offer", description="Add an item to the current trade")
@app_commands.describe(item="Name of the item to offer", qty="Quantity to offer (default: 1)")
async def trade_offer(interaction: discord.Interaction, item: str, qty: int = 1):
    trade_id = None
    for tid, session in trade_sessions.items():
        if session.is_participant(interaction.user.id) and session.state == "active":
            trade_id = tid
            break

    if not trade_id:
        await interaction.response.send_message("No active trade. Start one with `/trade request`.", ephemeral=True)
        return

    session = trade_sessions[trade_id]
    if interaction.user.id == session.initiator_uid:
        session.initiator_items[item] = session.initiator_items.get(item, 0) + qty
    else:
        session.target_items[item] = session.target_items.get(item, 0) + qty

    await interaction.response.send_message(
        f"✅ Added **{item} x{qty}** to your trade offer.", ephemeral=True
    )


@trade_group.command(name="gold", description="Add gold to the current trade")
@app_commands.describe(amount="Amount of gold to offer")
async def trade_gold(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("Amount must be positive.", ephemeral=True)
        return

    trade_id = None
    for tid, session in trade_sessions.items():
        if session.is_participant(interaction.user.id) and session.state == "active":
            trade_id = tid
            break

    if not trade_id:
        await interaction.response.send_message("No active trade.", ephemeral=True)
        return

    session = trade_sessions[trade_id]
    if interaction.user.id == session.initiator_uid:
        session.initiator_gold += amount
    else:
        session.target_gold += amount

    await interaction.response.send_message(
        f"✅ Added **{amount} gold** to your trade offer.", ephemeral=True
    )


@trade_group.command(name="accept", description="Accept and finalize the current trade")
async def trade_accept(interaction: discord.Interaction):
    trade_id = None
    for tid, session in trade_sessions.items():
        if session.is_participant(interaction.user.id) and session.state == "active":
            trade_id = tid
            break

    if not trade_id:
        await interaction.response.send_message("No active trade.", ephemeral=True)
        return

    session = trade_sessions[trade_id]
    if interaction.user.id == session.initiator_uid:
        session.initiator_ready = True
    else:
        session.target_ready = True

    await interaction.response.send_message("✅ You confirmed the trade. Waiting for the other side...", ephemeral=True)

    if session.initiator_ready and session.target_ready:
        # Execute via the view's method
        await interaction.delete_original_response()
        del trade_sessions[trade_id]


@trade_group.command(name="cancel", description="Cancel the current trade")
async def trade_cancel(interaction: discord.Interaction):
    to_del = None
    for tid, session in list(trade_sessions.items()):
        if session.is_participant(interaction.user.id) and session.state == "active":
            session.state = "cancelled"
            to_del = tid
            break

    if to_del:
        del trade_sessions[to_del]
        await interaction.response.send_message("❌ Trade cancelled.")
    else:
        await interaction.response.send_message("No active trade to cancel.", ephemeral=True)


class TradeCog(commands.Cog, name="Trade"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(trade_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("trade")


async def setup(bot):
    await bot.add_cog(TradeCog(bot))
