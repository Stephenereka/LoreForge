import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select, delete
from datetime import datetime

from database.session import get_db
from database.models import Character, GuildConfig, GuildGM, PendingApproval, BossTemplate, Location, NPC
from services.utils import gm_only, owner_only, is_gm
from cogs.character import _offer_attack_unlock
from services.leveling import check_level_up, hp_gain_on_level, xp_bar
from services.title_service import create_title, award_title, revoke_title, list_guild_titles, TIER_META
from database.models import Title, CharacterTitle

# ---------------------------------------------------------------------------
# Mechanical fields that PendingApproval can change
# ---------------------------------------------------------------------------
MECHANICAL_FIELDS: dict[str, str] = {
    "strength": "strength",
    "dexterity": "dexterity",
    "constitution": "constitution",
    "intelligence": "intelligence",
    "wisdom": "wisdom",
    "charisma": "charisma",
    "level": "level",
    "xp": "xp",
    "gold": "gold",
    "hp_max": "hp_max",
    "hp_current": "hp_current",
}

# ---------------------------------------------------------------------------
# Helper: post to audit log channel
# ---------------------------------------------------------------------------

async def _post_audit_log(
    bot: commands.Bot,
    guild_id: int,
    embed: discord.Embed,
) -> None:
    """Post embed to the guild's log_channel_id if configured."""
    async with get_db() as db:
        result = await db.execute(
            select(GuildConfig).where(GuildConfig.guild_id == guild_id)
        )
        config = result.scalar_one_or_none()
    if not config or not config.log_channel_id:
        return
    channel = bot.get_channel(config.log_channel_id)
    if channel:
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass


# ---------------------------------------------------------------------------
# Sheet-edit modal
# ---------------------------------------------------------------------------

class SheetEditModal(discord.ui.Modal, title="Edit Character Stats"):
    hp_current = discord.ui.TextInput(
        label="HP Current", required=False, placeholder="Leave blank to skip"
    )
    hp_max = discord.ui.TextInput(
        label="HP Max", required=False, placeholder="Leave blank to skip"
    )
    gold = discord.ui.TextInput(
        label="Gold", required=False, placeholder="Leave blank to skip"
    )
    strength = discord.ui.TextInput(
        label="Strength", required=False, placeholder="Leave blank to skip"
    )
    dexterity = discord.ui.TextInput(
        label="Dexterity", required=False, placeholder="Leave blank to skip"
    )

    def __init__(self, char: Character, editor: discord.Member, bot: commands.Bot):
        super().__init__()
        self.char = char
        self.editor = editor
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        changes: list[tuple[str, int, int]] = []  # (field, old, new)

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(Character.id == self.char.id)
            )
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message(
                    "Character not found.", ephemeral=True
                )
                return

            field_map = {
                "hp_current": self.hp_current.value.strip(),
                "hp_max": self.hp_max.value.strip(),
                "gold": self.gold.value.strip(),
                "strength": self.strength.value.strip(),
                "dexterity": self.dexterity.value.strip(),
            }

            for attr, raw in field_map.items():
                if not raw:
                    continue
                try:
                    new_val = int(raw)
                except ValueError:
                    await interaction.response.send_message(
                        f"Invalid value for **{attr}**: `{raw}` — must be a whole number.",
                        ephemeral=True,
                    )
                    return
                old_val = getattr(char, attr)
                if new_val != old_val:
                    changes.append((attr, old_val, new_val))
                    setattr(char, attr, new_val)

        if not changes:
            await interaction.response.send_message(
                "No changes were made.", ephemeral=True
            )
            return

        change_lines = "\n".join(
            f"• **{f}**: {o} → {n}" for f, o, n in changes
        )
        embed = discord.Embed(
            title="Character Edited",
            description=f"**{char.name}** was updated by {self.editor.display_name}.",
            color=0xF59E0B,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Changes", value=change_lines, inline=False)
        embed.set_footer(text="LoreForge GM Audit")

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Updated **{char.name}**:\n{change_lines}",
                color=0x22C55E,
            ),
            ephemeral=True,
        )
        await _post_audit_log(self.bot, interaction.guild_id, embed)


# ---------------------------------------------------------------------------
# Extended sheet-edit modal (remaining fields)
# ---------------------------------------------------------------------------

class SheetEditModal2(discord.ui.Modal, title="Edit Character Stats (cont.)"):
    constitution = discord.ui.TextInput(
        label="Constitution", required=False, placeholder="Leave blank to skip"
    )
    intelligence = discord.ui.TextInput(
        label="Intelligence", required=False, placeholder="Leave blank to skip"
    )
    wisdom = discord.ui.TextInput(
        label="Wisdom", required=False, placeholder="Leave blank to skip"
    )
    charisma = discord.ui.TextInput(
        label="Charisma", required=False, placeholder="Leave blank to skip"
    )
    level = discord.ui.TextInput(
        label="Level", required=False, placeholder="Leave blank to skip"
    )

    def __init__(self, char: Character, editor: discord.Member, bot: commands.Bot):
        super().__init__()
        self.char = char
        self.editor = editor
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:  # type: ignore[override]
        changes: list[tuple[str, int, int]] = []

        async with get_db() as db:
            result = await db.execute(
                select(Character).where(Character.id == self.char.id)
            )
            char = result.scalar_one_or_none()
            if not char:
                await interaction.response.send_message(
                    "Character not found.", ephemeral=True
                )
                return

            field_map = {
                "constitution": self.constitution.value.strip(),
                "intelligence": self.intelligence.value.strip(),
                "wisdom": self.wisdom.value.strip(),
                "charisma": self.charisma.value.strip(),
                "level": self.level.value.strip(),
            }

            for attr, raw in field_map.items():
                if not raw:
                    continue
                try:
                    new_val = int(raw)
                except ValueError:
                    await interaction.response.send_message(
                        f"Invalid value for **{attr}**: `{raw}` — must be a whole number.",
                        ephemeral=True,
                    )
                    return
                old_val = getattr(char, attr)
                if new_val != old_val:
                    changes.append((attr, old_val, new_val))
                    setattr(char, attr, new_val)

        if not changes:
            await interaction.response.send_message(
                "No changes were made.", ephemeral=True
            )
            return

        change_lines = "\n".join(
            f"• **{f}**: {o} → {n}" for f, o, n in changes
        )
        embed = discord.Embed(
            title="Character Edited",
            description=f"**{char.name}** was updated by {self.editor.display_name}.",
            color=0xF59E0B,
            timestamp=datetime.utcnow(),
        )
        embed.add_field(name="Changes", value=change_lines, inline=False)
        embed.set_footer(text="LoreForge GM Audit")

        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"Updated **{char.name}**:\n{change_lines}",
                color=0x22C55E,
            ),
            ephemeral=True,
        )
        await _post_audit_log(self.bot, interaction.guild_id, embed)


# ---------------------------------------------------------------------------
# Edit-selector view (two modals)
# ---------------------------------------------------------------------------

class EditModalSelector(discord.ui.View):
    def __init__(self, char: Character, editor: discord.Member, bot: commands.Bot):
        super().__init__(timeout=60)
        self.char = char
        self.editor = editor
        self.bot = bot

    @discord.ui.button(label="HP / Gold / STR / DEX", style=discord.ButtonStyle.primary)
    async def page1(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            SheetEditModal(self.char, self.editor, self.bot)
        )

    @discord.ui.button(label="CON / INT / WIS / CHA / Level", style=discord.ButtonStyle.secondary)
    async def page2(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            SheetEditModal2(self.char, self.editor, self.bot)
        )


# ---------------------------------------------------------------------------
# App command groups
# ---------------------------------------------------------------------------

gm_group = app_commands.Group(name="gm", description="Game Master tools")
sheet_group = app_commands.Group(
    name="sheet", description="Character sheet tools", parent=gm_group
)


# ---------------------------------------------------------------------------
# /gm add @user
# ---------------------------------------------------------------------------

@gm_group.command(name="add", description="Add a user as GM (server owner only)")
@app_commands.describe(user="The user to promote to GM")
async def gm_add(interaction: discord.Interaction, user: discord.Member):
    if not await owner_only(interaction):
        return

    async with get_db() as db:
        existing = await db.execute(
            select(GuildGM).where(
                GuildGM.guild_id == interaction.guild_id,
                GuildGM.user_id == user.id,
            )
        )
        if existing.scalar_one_or_none():
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{user.mention} is already a GM in this server.",
                    color=0xF59E0B,
                ),
                ephemeral=True,
            )
            return

        db.add(
            GuildGM(
                guild_id=interaction.guild_id,
                user_id=user.id,
                added_by=interaction.user.id,
                added_at=datetime.utcnow(),
            )
        )

    embed = discord.Embed(
        title="GM Added",
        description=f"{user.mention} has been added as a Game Master by {interaction.user.mention}.",
        color=0x22C55E,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="LoreForge")
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /gm remove @user
# ---------------------------------------------------------------------------

@gm_group.command(name="remove", description="Remove a user's GM status (server owner only)")
@app_commands.describe(user="The user to demote")
async def gm_remove(interaction: discord.Interaction, user: discord.Member):
    if not await owner_only(interaction):
        return

    async with get_db() as db:
        existing = await db.execute(
            select(GuildGM).where(
                GuildGM.guild_id == interaction.guild_id,
                GuildGM.user_id == user.id,
            )
        )
        row = existing.scalar_one_or_none()
        if not row:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{user.mention} is not a registered GM.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return
        await db.delete(row)

    embed = discord.Embed(
        title="GM Removed",
        description=f"{user.mention} has been removed as a Game Master by {interaction.user.mention}.",
        color=0xEF4444,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="LoreForge")
    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /gm list
# ---------------------------------------------------------------------------

@gm_group.command(name="list", description="List all GMs in this server (GM only)")
async def gm_list(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(GuildGM).where(GuildGM.guild_id == interaction.guild_id)
        )
        gm_rows = result.scalars().all()

    owner = interaction.guild.owner
    lines = [f"👑 {owner.mention} (Server Owner)"]
    for row in gm_rows:
        member = interaction.guild.get_member(row.user_id)
        mention = member.mention if member else f"<@{row.user_id}>"
        lines.append(f"⚔️ {mention}")

    embed = discord.Embed(
        title=f"Game Masters — {interaction.guild.name}",
        description="\n".join(lines) if lines else "No GMs registered.",
        color=0x6366F1,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="LoreForge")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gm sheet view [@user]
# ---------------------------------------------------------------------------

@sheet_group.command(name="view", description="View a player's character sheet (GM only)")
@app_commands.describe(user="The player whose sheet to view (omit = your own)")
async def sheet_view(interaction: discord.Interaction, user: discord.Member | None = None):
    if not await gm_only(interaction):
        return

    target = user or interaction.user
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.user_id == target.id,
            )
        )
        chars = result.scalars().all()

    if not chars:
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{target.mention} has no characters in this server.",
                color=0xEF4444,
            ),
            ephemeral=True,
        )
        return

    from cogs.character import build_sheet_embed

    embeds = [build_sheet_embed(c) for c in chars]
    await interaction.response.send_message(embeds=embeds[:10], ephemeral=True)


# ---------------------------------------------------------------------------
# /gm sheet edit @user
# ---------------------------------------------------------------------------

@sheet_group.command(name="edit", description="Edit a player's character stats (GM only)")
@app_commands.describe(user="The player whose character to edit")
async def sheet_edit(interaction: discord.Interaction, user: discord.Member):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.user_id == user.id,
                Character.is_active == True,
            )
        )
        char = result.scalar_one_or_none()

        if not char:
            # Fall back to most recent character
            result2 = await db.execute(
                select(Character)
                .where(
                    Character.guild_id == interaction.guild_id,
                    Character.user_id == user.id,
                )
                .order_by(Character.id.desc())
            )
            char = result2.scalar_one_or_none()

    if not char:
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"{user.mention} has no characters in this server.",
                color=0xEF4444,
            ),
            ephemeral=True,
        )
        return

    view = EditModalSelector(char, interaction.user, interaction.client)
    await interaction.response.send_message(
        embed=discord.Embed(
            description=f"Select which stats to edit for **{char.name}**:",
            color=0x6366F1,
        ),
        view=view,
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# /gm pending
# ---------------------------------------------------------------------------

@gm_group.command(name="pending", description="List all pending stat-change requests (GM only)")
async def gm_pending(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.guild_id == interaction.guild_id,
                PendingApproval.status == "pending",
            ).order_by(PendingApproval.requested_at.asc())
        )
        requests = result.scalars().all()

    if not requests:
        await interaction.response.send_message(
            embed=discord.Embed(
                description="No pending requests.",
                color=0x6B7280,
            ),
            ephemeral=True,
        )
        return

    lines: list[str] = []
    for req in requests:
        member = interaction.guild.get_member(req.user_id)
        mention = member.mention if member else f"<@{req.user_id}>"
        ts = req.requested_at.strftime("%Y-%m-%d %H:%M") if req.requested_at else "unknown"
        lines.append(
            f"**ID {req.id}** — {req.character_name} | `{req.field_name}`: "
            f"`{req.old_value}` → `{req.new_value}`\n"
            f"  Requested by {mention} at {ts}"
        )

    description = "\n\n".join(lines)
    # Truncate if too long
    if len(description) > 4000:
        description = description[:3990] + "\n…"

    embed = discord.Embed(
        title="Pending Stat Requests",
        description=description,
        color=0xF59E0B,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Use /gm approve <id> or /gm deny <id> to act")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gm approve <id>
# ---------------------------------------------------------------------------

@gm_group.command(name="approve", description="Approve a pending stat-change request (GM only)")
@app_commands.describe(request_id="The request ID from /gm pending")
async def gm_approve(interaction: discord.Interaction, request_id: int):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.id == request_id,
                PendingApproval.guild_id == interaction.guild_id,
                PendingApproval.status == "pending",
            )
        )
        req = result.scalar_one_or_none()

        if not req:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"No pending request with ID **{request_id}** found.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return

        char_result = await db.execute(
            select(Character).where(Character.id == req.character_id)
        )
        char = char_result.scalar_one_or_none()

        if not char:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description="The character for this request no longer exists.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return

        attr = MECHANICAL_FIELDS.get(req.field_name)
        if not attr:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"Unknown field `{req.field_name}`. Cannot apply.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return

        try:
            new_val = int(req.new_value)
        except ValueError:
            new_val = req.new_value  # type: ignore[assignment]

        old_val = getattr(char, attr)
        setattr(char, attr, new_val)
        req.status = "approved"

    # Notify requester
    channel = interaction.channel
    member = interaction.guild.get_member(req.user_id)
    notify_mention = member.mention if member else f"<@{req.user_id}>"
    await interaction.response.send_message(
        embed=discord.Embed(
            title="Request Approved",
            description=(
                f"{notify_mention}, your request to change **{req.character_name}**'s "
                f"`{req.field_name}` from `{old_val}` to `{new_val}` has been **approved** "
                f"by {interaction.user.mention}."
            ),
            color=0x22C55E,
            timestamp=datetime.utcnow(),
        )
    )

    # Audit log
    audit = discord.Embed(
        title="Approval Audit Log",
        description=(
            f"**{req.character_name}** — `{req.field_name}`: `{old_val}` → `{new_val}`\n"
            f"Approved by {interaction.user.mention} | Requested by {notify_mention}"
        ),
        color=0x22C55E,
        timestamp=datetime.utcnow(),
    )
    audit.set_footer(text=f"Request ID {req.id} | LoreForge")
    await _post_audit_log(interaction.client, interaction.guild_id, audit)


# ---------------------------------------------------------------------------
# /gm deny <id> [reason]
# ---------------------------------------------------------------------------

@gm_group.command(name="deny", description="Deny a pending stat-change request (GM only)")
@app_commands.describe(
    request_id="The request ID from /gm pending",
    reason="Optional reason for denial",
)
async def gm_deny(
    interaction: discord.Interaction,
    request_id: int,
    reason: str | None = None,
):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.id == request_id,
                PendingApproval.guild_id == interaction.guild_id,
                PendingApproval.status == "pending",
            )
        )
        req = result.scalar_one_or_none()

        if not req:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"No pending request with ID **{request_id}** found.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return

        req.status = "denied"

    member = interaction.guild.get_member(req.user_id)
    notify_mention = member.mention if member else f"<@{req.user_id}>"
    reason_text = f"\n**Reason:** {reason}" if reason else ""

    await interaction.response.send_message(
        embed=discord.Embed(
            title="Request Denied",
            description=(
                f"{notify_mention}, your request to change **{req.character_name}**'s "
                f"`{req.field_name}` from `{req.old_value}` to `{req.new_value}` has been "
                f"**denied** by {interaction.user.mention}.{reason_text}"
            ),
            color=0xEF4444,
            timestamp=datetime.utcnow(),
        )
    )

    # Audit log
    audit = discord.Embed(
        title="Denial Audit Log",
        description=(
            f"**{req.character_name}** — `{req.field_name}`: `{req.old_value}` → `{req.new_value}` (NOT applied)\n"
            f"Denied by {interaction.user.mention} | Requested by {notify_mention}"
            + (f"\nReason: {reason}" if reason else "")
        ),
        color=0xEF4444,
        timestamp=datetime.utcnow(),
    )
    audit.set_footer(text=f"Request ID {req.id} | LoreForge")
    await _post_audit_log(interaction.client, interaction.guild_id, audit)


# ---------------------------------------------------------------------------
# /gm xp @user <amount>
# ---------------------------------------------------------------------------

@gm_group.command(name="xp", description="Award XP to a player's active character (GM only)")
@app_commands.describe(
    user="The player to award XP to",
    amount="Amount of XP to award",
)
async def gm_xp(interaction: discord.Interaction, user: discord.Member, amount: int):
    if not await gm_only(interaction):
        return

    if amount <= 0:
        await interaction.response.send_message(
            embed=discord.Embed(
                description="XP amount must be positive.", color=0xEF4444
            ),
            ephemeral=True,
        )
        return

    leveled_up = False
    new_level = None
    hp_gained = 0
    feature_unlocked = None

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.user_id == user.id,
                Character.is_active == True,
            )
        )
        char = result.scalar_one_or_none()

        if not char:
            await interaction.response.send_message(
                embed=discord.Embed(
                    description=f"{user.mention} has no active character in this server.",
                    color=0xEF4444,
                ),
                ephemeral=True,
            )
            return

        char.xp += amount

        # Check level-up (loop in case multiple levels gained)
        while True:
            next_level = check_level_up(char.xp, char.level)
            if next_level is None:
                break
            gain = hp_gain_on_level(char.char_class, char.constitution)
            char.level = next_level
            char.hp_max += gain
            char.hp_current = min(char.hp_current + gain, char.hp_max)
            hp_gained += gain
            leveled_up = True
            new_level = char.level

        char_snapshot = {
            "name": char.name,
            "level": char.level,
            "xp": char.xp,
            "hp_max": char.hp_max,
            "char_class": char.char_class,
            "constitution": char.constitution,
        }

    bar = xp_bar(char_snapshot["xp"], char_snapshot["level"])

    embed = discord.Embed(
        title="XP Awarded",
        description=(
            f"{user.mention}'s **{char_snapshot['name']}** received **+{amount} XP**!\n\n"
            f"{bar}"
        ),
        color=0x6366F1,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="LoreForge")

    if leveled_up:
        embed.add_field(
            name="LEVEL UP!",
            value=(
                f"**{char_snapshot['name']}** is now **Level {new_level}**!\n"
                f"HP increased by **+{hp_gained}** → {char_snapshot['hp_max']} max"
            ),
            inline=False,
        )
        embed.color = 0xF59E0B
        # Offer attack unlock via DM
        char_to_unlock = None
        async with get_db() as db_check:
            r = await db_check.execute(select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.user_id == user.id,
                Character.is_active == True,
            ))
            char_to_unlock = r.scalar_one_or_none()
        if char_to_unlock:
            await _offer_attack_unlock(interaction.client, char_to_unlock, new_level)

    await interaction.response.send_message(embed=embed)


# ---------------------------------------------------------------------------
# /gm edit — GM Edit Panel (full character edit, instant, no approval)
# ---------------------------------------------------------------------------

class GMEditModal(discord.ui.Modal, title="GM Edit Character"):
    """Discord modals support max 5 fields. Two panels cover all stats."""
    level = discord.ui.TextInput(label="Level (1–20)", required=False)
    hp_max = discord.ui.TextInput(label="HP Max (leave blank = auto from level)", required=False)
    hp_current = discord.ui.TextInput(label="HP Current", required=False)
    gold = discord.ui.TextInput(label="Gold", required=False)
    armor_class = discord.ui.TextInput(label="Armor Class", required=False)

    def __init__(self, char: Character, editor: discord.Member):
        super().__init__(title=f"GM Edit — {char.name}")
        self.char_id = char.id
        self.char_name = char.name
        self._char_class = char.char_class
        self._constitution = char.constitution
        self.editor = editor
        self.level.default = str(char.level)
        self.hp_max.default = str(char.hp_max)
        self.hp_current.default = str(char.hp_current)
        self.gold.default = str(char.gold)
        self.armor_class.default = str(char.armor_class)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            changes = []
            async with get_db() as db:
                result = await db.execute(select(Character).where(Character.id == self.char_id))
                char = result.scalar_one_or_none()
                if not char:
                    await interaction.followup.send("Character not found.", ephemeral=True)
                    return

                new_level: int | None = None
                hp_max_explicitly_set = bool(self.hp_max.value.strip())

                for attr in ("level", "hp_max", "hp_current", "gold", "armor_class"):
                    raw = getattr(self, attr).value.strip()
                    if not raw:
                        continue
                    try:
                        new_val = int(raw)
                    except ValueError:
                        await interaction.followup.send(f"Invalid value for **{attr}**: `{raw}`.", ephemeral=True)
                        return
                    old_val = getattr(char, attr)
                    if old_val != new_val:
                        changes.append((attr, old_val, new_val))
                        setattr(char, attr, new_val)
                    if attr == "level":
                        new_level = new_val

                # When level changes: auto-recalculate hp_max (unless GM explicitly set it)
                # and bump XP to the minimum for that level.
                if new_level is not None:
                    from services.leveling import _HIT_DICE, XP_THRESHOLDS
                    con_mod = (char.constitution - 10) // 2
                    hit_die = _HIT_DICE.get(char.char_class.lower(), 8)
                    auto_hp = hit_die + con_mod  # level 1 = max die
                    for _ in range(new_level - 1):
                        auto_hp += max(1, (hit_die // 2 + 1) + con_mod)
                    auto_hp = max(1, auto_hp)

                    if not hp_max_explicitly_set and char.hp_max != auto_hp:
                        old_hp = char.hp_max
                        char.hp_max = auto_hp
                        char.hp_current = min(char.hp_current, auto_hp)
                        changes.append(("hp_max (auto)", old_hp, auto_hp))

                    min_xp = XP_THRESHOLDS[new_level - 1] if new_level <= 20 else XP_THRESHOLDS[-1]
                    if char.xp < min_xp:
                        old_xp = char.xp
                        char.xp = min_xp
                        changes.append(("xp (auto)", old_xp, min_xp))

        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error saving changes: `{type(e).__name__}: {e}`", ephemeral=True)
            return

        if not changes:
            await interaction.followup.send("No changes were made.", ephemeral=True)
            return

        change_lines = "\n".join(f"• **{f}**: {o} → {n}" for f, o, n in changes)
        embed = discord.Embed(
            title="✅ Character Edited",
            description=f"**{self.char_name}** was updated by GM {self.editor.display_name}.",
            color=0x22C55E,
        )
        embed.add_field(name="Changes", value=change_lines, inline=False)
        embed.set_footer(text="Use /gm edit again for ability scores and profile fields")
        await interaction.followup.send(embed=embed, ephemeral=True)

        audit = discord.Embed(
            title="GM Edit Audit Log",
            description=f"**{self.char_name}** edited by {self.editor.display_name}\n{change_lines}",
            color=0x22C55E,
        )
        await _post_audit_log(interaction.client, interaction.guild_id, audit)


class GMEditStatsModal(discord.ui.Modal, title="GM Edit — Ability Scores"):
    strength = discord.ui.TextInput(label="Strength", required=False)
    dexterity = discord.ui.TextInput(label="Dexterity", required=False)
    constitution = discord.ui.TextInput(label="Constitution", required=False)
    intelligence = discord.ui.TextInput(label="Intelligence", required=False)
    wisdom = discord.ui.TextInput(label="Wisdom", required=False)

    def __init__(self, char: Character, editor: discord.Member):
        super().__init__(title=f"GM Edit Stats — {char.name}")
        self.char_id = char.id
        self.char_name = char.name
        self.editor = editor
        self.strength.default = str(char.strength)
        self.dexterity.default = str(char.dexterity)
        self.constitution.default = str(char.constitution)
        self.intelligence.default = str(char.intelligence)
        self.wisdom.default = str(char.wisdom)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            changes = []
            async with get_db() as db:
                result = await db.execute(select(Character).where(Character.id == self.char_id))
                char = result.scalar_one_or_none()
                if not char:
                    await interaction.followup.send("Character not found.", ephemeral=True)
                    return
                for attr in ("strength", "dexterity", "constitution", "intelligence", "wisdom"):
                    raw = getattr(self, attr).value.strip()
                    if not raw:
                        continue
                    try:
                        new_val = int(raw)
                    except ValueError:
                        await interaction.followup.send(f"Invalid value for **{attr}**: `{raw}`.", ephemeral=True)
                        return
                    old_val = getattr(char, attr)
                    if old_val != new_val:
                        changes.append((attr, old_val, new_val))
                        setattr(char, attr, new_val)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error saving changes: `{type(e).__name__}: {e}`", ephemeral=True)
            return

        if not changes:
            await interaction.followup.send("No changes were made.", ephemeral=True)
            return
        change_lines = "\n".join(f"• **{f}**: {o} → {n}" for f, o, n in changes)
        embed = discord.Embed(title="✅ Stats Edited", description=f"**{self.char_name}** updated.", color=0x22C55E)
        embed.add_field(name="Changes", value=change_lines, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        audit = discord.Embed(title="GM Stat Edit", description=f"**{self.char_name}** edited by {self.editor.display_name}\n{change_lines}", color=0x22C55E)
        await _post_audit_log(interaction.client, interaction.guild_id, audit)


class GMEditProfileModal(discord.ui.Modal, title="GM Edit — Profile"):
    char_class = discord.ui.TextInput(label="Class", required=False)
    race = discord.ui.TextInput(label="Race", required=False)
    background = discord.ui.TextInput(label="Background", required=False)
    charisma = discord.ui.TextInput(label="Charisma", required=False)
    xp = discord.ui.TextInput(label="XP", required=False)

    def __init__(self, char: Character, editor: discord.Member):
        super().__init__(title=f"GM Edit Profile — {char.name}")
        self.char_id = char.id
        self.char_name = char.name
        self.editor = editor
        self.char_class.default = char.char_class
        self.race.default = char.race
        self.background.default = char.background or ""
        self.charisma.default = str(char.charisma)
        self.xp.default = str(char.xp or 0)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            changes = []
            async with get_db() as db:
                result = await db.execute(select(Character).where(Character.id == self.char_id))
                char = result.scalar_one_or_none()
                if not char:
                    await interaction.followup.send("Character not found.", ephemeral=True)
                    return
                text_fields = {
                    "char_class": self.char_class.value.strip(),
                    "race": self.race.value.strip(),
                    "background": self.background.value.strip(),
                }
                int_fields = {
                    "charisma": self.charisma.value.strip(),
                    "xp": self.xp.value.strip(),
                }
                for attr, raw in text_fields.items():
                    if not raw:
                        continue
                    old_val = getattr(char, attr)
                    if str(old_val) != raw:
                        changes.append((attr, old_val, raw))
                        setattr(char, attr, raw)
                for attr, raw in int_fields.items():
                    if not raw:
                        continue
                    try:
                        new_val = int(raw)
                    except ValueError:
                        await interaction.followup.send(f"Invalid value for **{attr}**: `{raw}`.", ephemeral=True)
                        return
                    old_val = getattr(char, attr)
                    if old_val != new_val:
                        changes.append((attr, old_val, new_val))
                        setattr(char, attr, new_val)
        except Exception as e:
            import traceback
            traceback.print_exc()
            await interaction.followup.send(f"Error saving changes: `{type(e).__name__}: {e}`", ephemeral=True)
            return

        if not changes:
            await interaction.followup.send("No changes were made.", ephemeral=True)
            return
        change_lines = "\n".join(f"• **{f}**: {o} → {n}" for f, o, n in changes)
        embed = discord.Embed(title="✅ Profile Edited", description=f"**{self.char_name}** updated.", color=0x22C55E)
        embed.add_field(name="Changes", value=change_lines, inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)
        audit = discord.Embed(title="GM Profile Edit", description=f"**{self.char_name}** edited by {self.editor.display_name}\n{change_lines}", color=0x22C55E)
        await _post_audit_log(interaction.client, interaction.guild_id, audit)


class GMEditView(discord.ui.View):
    """Three-panel edit picker — Discord modals are capped at 5 fields."""
    def __init__(self, char: Character, editor: discord.Member):
        super().__init__(timeout=120)
        self.char = char
        self.editor = editor

    @discord.ui.button(label="⚔️ Level / HP / Gold / AC", style=discord.ButtonStyle.primary)
    async def main_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GMEditModal(self.char, self.editor))

    @discord.ui.button(label="💪 Ability Scores", style=discord.ButtonStyle.secondary)
    async def stats_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GMEditStatsModal(self.char, self.editor))

    @discord.ui.button(label="📋 Class / Race / Profile", style=discord.ButtonStyle.secondary)
    async def profile_panel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(GMEditProfileModal(self.char, self.editor))


class GMEditCharSelect(discord.ui.Select):
    def __init__(self, chars: list[Character], editor: discord.Member):
        self._chars = chars
        self._editor = editor
        options = [
            discord.SelectOption(
                label=c.name,
                value=str(c.id),
                description=f"Lv{c.level} {c.race} {c.char_class}",
            )
            for c in chars
        ]
        super().__init__(placeholder="Choose a character to edit...", options=options)

    async def callback(self, interaction: discord.Interaction):
        char_id = int(self.values[0])
        char = next((c for c in self._chars if c.id == char_id), None)
        if not char:
            await interaction.response.send_message("Character not found.", ephemeral=True)
            return
        await interaction.response.send_message(
            embed=discord.Embed(title=f"✏️ Editing {char.name}", description="Choose what to edit:", color=0x6366F1),
            view=GMEditView(char, self._editor),
            ephemeral=True,
        )


class GMEditCharView(discord.ui.View):
    def __init__(self, chars: list[Character], editor: discord.Member):
        super().__init__(timeout=120)
        self.add_item(GMEditCharSelect(chars, editor))


@gm_group.command(name="edit", description="Open a full GM edit panel for a character (GM only)")
@app_commands.describe(user="The player whose character to edit (omit for char picker)")
async def gm_edit(interaction: discord.Interaction, user: discord.Member | None = None):
    if not await gm_only(interaction):
        return

    target = user or interaction.user
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.user_id == target.id,
                Character.is_dead == False,
            ).order_by(Character.is_active.desc(), Character.id)
        )
        chars = list(result.scalars().all())

    if not chars:
        await interaction.response.send_message(
            f"{target.mention} has no living characters in this server.", ephemeral=True
        )
        return

    if len(chars) == 1:
        char = chars[0]
        await interaction.response.send_message(
            embed=discord.Embed(
                title=f"✏️ Editing {char.name}",
                description=f"Lv{char.level} {char.race} {char.char_class} — choose a panel to edit:",
                color=0x6366F1,
            ),
            view=GMEditView(char, interaction.user),
            ephemeral=True,
        )
    else:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Select a Character to Edit",
                description=f"Choose which character of {target.display_name}'s to edit.",
                color=0x6366F1,
            ),
            view=GMEditCharView(chars, interaction.user),
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# /gm dashboard — World stats overview
# ---------------------------------------------------------------------------

@gm_group.command(name="dashboard", description="View world overview stats (GM only)")
async def gm_dashboard(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    from database.models import Location, NPC, Quest, Faction, WorldTime, WeatherState, CharacterLocation, Character
    from services.weather_service import get_weather
    from services.time_service import get_world_time

    async with get_db() as db:
        loc_count = (await db.execute(select(Location).where(Location.guild_id == interaction.guild_id))).scalars().all()
        locs = len(loc_count)

        npc_count = (await db.execute(select(NPC).where(NPC.guild_id == interaction.guild_id, NPC.is_dead == False))).scalars().all()
        npcs = len(npc_count)

        quest_count = (await db.execute(select(Quest).where(Quest.guild_id == interaction.guild_id, Quest.is_active == True))).scalars().all()
        quests = len(quest_count)

        faction_count = (await db.execute(select(Faction).where(Faction.guild_id == interaction.guild_id))).scalars().all()
        factions = len(faction_count)

        player_count = (await db.execute(select(Character).where(Character.guild_id == interaction.guild_id, Character.is_dead == False, Character.is_active == True))).scalars().all()
        players = len(player_count)

        active_locations = (await db.execute(select(CharacterLocation).where(CharacterLocation.guild_id == interaction.guild_id))).scalars().all()
        active_locs = len(active_locations)

    time_info = await get_world_time(interaction.guild_id)
    weather_info = await get_weather(interaction.guild_id)

    embed = discord.Embed(
        title="\U0001f5fa\ufe0f World Dashboard",
        description=f"Overview for **{interaction.guild.name}**",
        color=0x6366F1,
    )
    embed.add_field(name="\U0001f5fa\ufe0f Locations", value=str(locs), inline=True)
    embed.add_field(name="\U0001f464 NPCs", value=str(npcs), inline=True)
    embed.add_field(name="\U0001f4dc Quests", value=str(quests), inline=True)
    embed.add_field(name="\U0001f3db\ufe0f Factions", value=str(factions), inline=True)
    embed.add_field(name="\U0001f9d1\u200d\u2695\ufe0f Players", value=str(players), inline=True)
    embed.add_field(name="Active Locations", value=str(active_locs), inline=True)
    embed.add_field(name="\u23f0 Time", value=f"{time_info['emoji']} {time_info['time_of_day']} (Day {time_info['day']}, {time_info['season']})", inline=False)
    embed.add_field(name="\u2601\ufe0f Weather", value=f"{weather_info['icon']} {weather_info['weather_type'].title()} ({weather_info['temperature']})", inline=False)
    embed.set_footer(text="LoreForge World Dashboard")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gm revive <character_name>
# ---------------------------------------------------------------------------

@gm_group.command(name="revive", description="Bring a dead character back to life (GM only)")
@app_commands.describe(character_name="Exact name of the dead character to revive")
async def gm_revive(interaction: discord.Interaction, character_name: str):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.name.ilike(character_name.strip()),
                Character.is_dead == True,
            )
        )
        char = result.scalar_one_or_none()

        if not char:
            await interaction.response.send_message(
                f"No dead character named **{character_name}** found in this server.",
                ephemeral=True,
            )
            return

        char.is_dead = False
        char.is_unconscious = False
        char.hp_current = 1
        char.death_saves_success = 0
        char.death_saves_failure = 0
        char_name = char.name
        char_hp_max = char.hp_max

    embed = discord.Embed(
        title="Character Revived",
        description=f"**{char_name}** has been brought back to life by {interaction.user.display_name}.",
        color=0x22C55E,
    )
    embed.add_field(name="HP", value=f"1 / {char_hp_max}", inline=True)
    embed.add_field(name="Status", value="Alive", inline=True)
    embed.set_footer(text="LoreForge")
    await interaction.response.send_message(embed=embed)





# ---------------------------------------------------------------------------
# /gm pending-user <user>
# ---------------------------------------------------------------------------

@gm_group.command(name="pending-user", description="List pending requests for a specific user (GM only)")
@app_commands.describe(user="The user whose pending requests to view")
async def gm_pending_user(interaction: discord.Interaction, user: discord.Member):
    if not await gm_only(interaction):
        return

    async with get_db() as db:
        result = await db.execute(
            select(PendingApproval).where(
                PendingApproval.guild_id == interaction.guild_id,
                PendingApproval.user_id == user.id,
                PendingApproval.status == "pending",
            ).order_by(PendingApproval.requested_at.asc())
        )
        requests = result.scalars().all()

    if not requests:
        await interaction.response.send_message(
            embed=discord.Embed(
                description=f"No pending requests for {user.mention}.",
                color=0x6B7280,
            ),
            ephemeral=True,
        )
        return

    lines: list[str] = []
    for req in requests:
        ts = req.requested_at.strftime("%Y-%m-%d %H:%M") if req.requested_at else "unknown"
        lines.append(
            f"**ID {req.id}** — {req.character_name} | `{req.field_name}`: "
            f"`{req.old_value}` → `{req.new_value}`\n"
            f"  Requested at {ts}"
        )

    description = "\n\n".join(lines)
    if len(description) > 4000:
        description = description[:3990] + "\n…"

    embed = discord.Embed(
        title=f"Pending Requests — {user.display_name}",
        description=description,
        color=0xF59E0B,
        timestamp=datetime.utcnow(),
    )
    embed.set_footer(text="Use /gm approve <id> or /gm deny <id> to act")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gm boss subgroup
# ---------------------------------------------------------------------------

boss_group = app_commands.Group(name="boss", description="Boss encounter management (GM only)", parent=gm_group)


# ── /gm boss create ───────────────────────────────────────────────────────────

class BossCreateModal(discord.ui.Modal, title="Create Boss Template"):
    name = discord.ui.TextInput(label="Boss Name", max_length=100)
    title = discord.ui.TextInput(label="Title (optional)", required=False, max_length=100)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph)
    hp_max = discord.ui.TextInput(label="Max HP", placeholder="e.g. 150")
    armor_class = discord.ui.TextInput(label="Armor Class", placeholder="e.g. 16")
    damage_dice = discord.ui.TextInput(label="Damage Dice", placeholder="e.g. 2d8")
    xp_value = discord.ui.TextInput(label="XP Value", placeholder="e.g. 1500")

    async def on_submit(self, interaction: discord.Interaction):
        try:
            hp = int(self.hp_max.value.strip())
            ac = int(self.armor_class.value.strip())
            xp = int(self.xp_value.value.strip())
        except ValueError:
            await interaction.response.send_message("HP, AC, and XP must be whole numbers.", ephemeral=True)
            return

        async with get_db() as db:
            from database.models import BossTemplate
            template = BossTemplate(
                guild_id=interaction.guild_id,
                name=self.name.value.strip(),
                title=self.title.value.strip() or None,
                description=self.description.value.strip(),
                hp_max=hp,
                armor_class=ac,
                attack_bonus=4,
                damage_dice=self.damage_dice.value.strip(),
                damage_bonus=0,
                xp_value=xp,
                created_by=interaction.user.id,
            )
            db.add(template)
            await db.flush()
            tid = template.id

        embed = discord.Embed(
            title="🗡️ Boss Template Created",
            description=f"**{self.name.value.strip()}** is ready for battle!",
            color=0xEF4444,
        )
        embed.add_field(name="HP", value=str(hp), inline=True)
        embed.add_field(name="AC", value=str(ac), inline=True)
        embed.add_field(name="Damage", value=self.damage_dice.value.strip(), inline=True)
        embed.add_field(name="XP", value=str(xp), inline=True)
        embed.set_footer(text=f"Template ID: {tid} • Use /gm boss spawn to deploy")
        await interaction.response.send_message(embed=embed, ephemeral=True)


@boss_group.command(name="create", description="Create a new boss template (GM only)")
async def gm_boss_create(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.send_modal(BossCreateModal())


# ── /gm boss list ─────────────────────────────────────────────────────────────

@boss_group.command(name="list", description="List all boss templates (GM only)")
async def gm_boss_list(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        from database.models import BossTemplate
        result = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id
            ).order_by(BossTemplate.name)
        )
        templates = list(result.scalars().all())

    if not templates:
        await interaction.followup.send("No boss templates created yet.", ephemeral=True)
        return

    embed = discord.Embed(
        title="🗡️ Boss Templates",
        color=0xEF4444,
    )
    for t in templates[:20]:
        embed.add_field(
            name=f"{t.name} ({t.title or 'No title'})",
            value=f"❤️ {t.hp_max}  🛡️ {t.armor_class}  ⚔️ {t.damage_dice}  ✨ {t.xp_value} XP  ⚡ {t.phase_count} phase(s)",
            inline=False,
        )
    embed.set_footer(text=f"{len(templates)} template(s)  •  LoreForge")
    await interaction.followup.send(embed=embed, ephemeral=True)


# ── /gm boss spawn ────────────────────────────────────────────────────────────

async def _boss_name_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        from database.models import BossTemplate
        result = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                BossTemplate.name.ilike(f"%{current}%"),
            ).limit(25)
        )
        return [
            app_commands.Choice(name=f"{t.name} (HP:{t.hp_max} AC:{t.armor_class})", value=t.name)
            for t in result.scalars().all()
        ]


@boss_group.command(name="spawn", description="Spawn a boss in the current channel (GM only)")
@app_commands.describe(name="Boss template name", hp_override="Override HP (optional)", name_override="Custom display name (optional)")
@app_commands.autocomplete(name=_boss_name_autocomplete)
async def gm_boss_spawn(interaction: discord.Interaction, name: str, hp_override: int | None = None, name_override: str | None = None):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import BossTemplate, SpawnedBoss
        result = await db.execute(
            select(BossTemplate).where(
                BossTemplate.guild_id == interaction.guild_id,
                BossTemplate.name.ilike(name),
            )
        )
        t = result.scalar_one_or_none()
        if not t:
            await interaction.followup.send(f"Boss template **{name}** not found.", ephemeral=True)
            return

        display_name = name_override or t.name
        hp = hp_override or t.hp_max

        spawned = SpawnedBoss(
            guild_id=interaction.guild_id,
            channel_id=interaction.channel_id,
            template_id=t.id,
            display_name=display_name,
            hp_current=hp,
            hp_max=hp,
            armor_class=t.armor_class,
            attack_bonus=t.attack_bonus,
            damage_dice=t.damage_dice,
            damage_bonus=t.damage_bonus,
            xp_value=t.xp_value,
            gold_drop=t.gold_drop,
            loot_table=t.loot_table,
            current_phase=1,
            phase_thresholds=t.phase_thresholds,
            phase_abilities=t.phase_abilities,
            legendary_actions=t.legendary_actions,
            legendary_actions_remaining=t.legendary_action_count,
            legendary_action_count=t.legendary_action_count,
            minion_template_id=t.minion_template_id,
            minion_count_per_summon=t.minion_count_per_summon,
            is_lair_boss=t.is_lair_boss,
            lair_actions=t.lair_actions,
            spawned_by=interaction.user.id,
        )
        db.add(spawned)
        await db.flush()
        sid = spawned.id

    # Build intro embed
    hp_bar_filled = 10
    hp_bar = "█" * hp_bar_filled + "░" * (10 - hp_bar_filled)
    embed = discord.Embed(
        title=f"🗡️ {display_name} has appeared!",
        description=t.description[:500],
        color=0xEF4444,
    )
    embed.add_field(name="❤️ HP", value=f"`{hp_bar}` **{hp}/{hp}**", inline=True)
    embed.add_field(name="🛡️ AC", value=str(t.armor_class), inline=True)
    embed.add_field(name="⚡ Phases", value=str(t.phase_count or 1), inline=True)
    if t.image_url:
        embed.set_image(url=t.image_url)

    lair_text = "Yes" if t.is_lair_boss else "No"
    embed.add_field(name="🏰 Lair Boss", value=lair_text, inline=True)
    embed.add_field(name="⚔️ Legendary Actions", value=str(t.legendary_action_count), inline=True)
    embed.add_field(name="✨ XP Value", value=str(t.xp_value), inline=True)
    embed.set_footer(text=f"Spawned by {interaction.user.display_name}  •  ID: {sid}")
    await interaction.followup.send(embed=embed)


# ── /gm boss force-attack ─────────────────────────────────────────────────────

@boss_group.command(name="force-attack", description="Force the active boss to target a specific player (GM only)")
@app_commands.describe(user="The player for the boss to target")
async def gm_boss_force_attack(interaction: discord.Interaction, user: discord.Member):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        boss.forced_target_id = user.id

    embed = discord.Embed(
        title="🎯 Boss Target Set",
        description=f"**{boss.display_name}** is now targeting **{user.display_name}**!",
        color=0xEF4444,
    )
    await interaction.followup.send(embed=embed)


# ── /gm boss force-ability ────────────────────────────────────────────────────

async def _boss_ability_autocomplete(interaction: discord.Interaction, current: str):
    """Autocomplete from the active spawned boss's phase_abilities JSON."""
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            return []
        phase_key = f"phase_{boss.current_phase}"
        abilities = (boss.phase_abilities or {}).get(phase_key, [])
    return [
        app_commands.Choice(name=a.get("name", "Unknown"), value=a.get("name", ""))
        for a in abilities
        if current.lower() in a.get("name", "").lower()
    ][:25]


@boss_group.command(name="force-ability", description="Force the boss to use a specific phase ability (GM only)")
@app_commands.describe(ability_name="Name of the ability to use")
@app_commands.autocomplete(ability_name=_boss_ability_autocomplete)
async def gm_boss_force_ability(interaction: discord.Interaction, ability_name: str):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        phase_key = f"phase_{boss.current_phase}"
        abilities = (boss.phase_abilities or {}).get(phase_key, [])
        ability = next((a for a in abilities if a.get("name", "").lower() == ability_name.lower()), None)
        if not ability:
            await interaction.followup.send(
                f"Ability **{ability_name}** not found in current phase ({boss.current_phase}).",
                ephemeral=True,
            )
            return

    embed = discord.Embed(
        title=f"⚡ Boss Ability — {ability['name']}",
        description=ability.get("description", f"{boss.display_name} uses {ability['name']}!"),
        color=0xEF4444,
    )
    if ability.get("effect"):
        embed.add_field(name="Effect", value=ability["effect"], inline=True)
    if ability.get("condition_applied"):
        embed.add_field(name="Condition", value=ability["condition_applied"], inline=True)
    await interaction.followup.send(embed=embed)


# ── /gm boss set-phase ────────────────────────────────────────────────────────

@boss_group.command(name="set-phase", description="Manually set the boss's current phase (GM only)")
@app_commands.describe(phase="Phase number (1-4)")
async def gm_boss_set_phase(interaction: discord.Interaction, phase: int):
    if not await gm_only(interaction):
        return
    if phase < 1 or phase > 4:
        await interaction.response.send_message("Phase must be 1-4.", ephemeral=True)
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        old_phase = boss.current_phase
        boss.current_phase = phase

    phase_descriptions = {
        1: "The boss fights normally.",
        2: "The boss becomes more aggressive — new abilities unlock!",
        3: "The boss is enraged! Powerful attacks are unleashed!",
        4: "Desperate measures — the boss fights with everything it has!",
    }

    embed = discord.Embed(
        title=f"⚡ Phase Change!",
        description=f"**{boss.display_name}** shifts to **Phase {phase}**!\n\n"
                    f"*{phase_descriptions.get(phase, 'The boss transforms!')}*",
        color=0xEF4444,
    )
    embed.add_field(name="Previous Phase", value=str(old_phase), inline=True)
    embed.add_field(name="New Phase", value=str(phase), inline=True)
    await interaction.followup.send(embed=embed)


# ── /gm boss hp ───────────────────────────────────────────────────────────────

@boss_group.command(name="hp", description="Set the active boss's HP directly (GM only)")
@app_commands.describe(value="New HP value")
async def gm_boss_hp(interaction: discord.Interaction, value: int):
    if not await gm_only(interaction):
        return
    if value < 0:
        await interaction.response.send_message("HP cannot be negative.", ephemeral=True)
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        old_hp = boss.hp_current
        boss.hp_current = min(value, boss.hp_max)

        # Check phase thresholds
        if boss.phase_thresholds:
            pct = (boss.hp_current / boss.hp_max) * 100 if boss.hp_max > 0 else 0
            for i, threshold in enumerate(boss.phase_thresholds):
                if pct <= threshold:
                    new_phase = i + 2
                    if new_phase > boss.current_phase and new_phase <= (boss.phase_count or 1):
                        boss.current_phase = new_phase

    # Build HP bar
    pct = boss.hp_current / boss.hp_max if boss.hp_max > 0 else 0
    bar_filled = round(pct * 10)
    hp_bar = "█" * bar_filled + "░" * (10 - bar_filled)
    embed = discord.Embed(
        title=f"❤️ {boss.display_name} HP Updated",
        description=f"`{hp_bar}` **{boss.hp_current}/{boss.hp_max}**  (was `{old_hp}`)",
        color=0x22C55E if pct > 0.5 else (0xF97316 if pct > 0.25 else 0xEF4444),
    )
    embed.add_field(name="Phase", value=str(boss.current_phase), inline=True)
    embed.add_field(name="HP %", value=f"{round(pct * 100)}%", inline=True)
    await interaction.followup.send(embed=embed)


# ── /gm boss summon-minions ───────────────────────────────────────────────────

@boss_group.command(name="summon-minions", description="Spawn minions for the active boss (GM only)")
async def gm_boss_summon_minions(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss, BossTemplate
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        mini_template_id = boss.minion_template_id
        if not mini_template_id:
            await interaction.followup.send("This boss has no minion template configured.", ephemeral=True)
            return

        t_result = await db.execute(select(BossTemplate).where(BossTemplate.id == mini_template_id))
        mini_t = t_result.scalar_one_or_none()
        if not mini_t:
            await interaction.followup.send("Minion template not found.", ephemeral=True)
            return

        count = boss.minion_count_per_summon or 2
        for _ in range(count):
            mini = SpawnedBoss(
                guild_id=boss.guild_id,
                channel_id=boss.channel_id,
                template_id=mini_t.id,
                display_name=mini_t.name,
                hp_current=mini_t.hp_max,
                hp_max=mini_t.hp_max,
                armor_class=mini_t.armor_class,
                attack_bonus=mini_t.attack_bonus or 3,
                damage_dice=mini_t.damage_dice,
                damage_bonus=mini_t.damage_bonus or 0,
                xp_value=mini_t.xp_value or 50,
                parent_boss_id=boss.id,
                spawned_by=interaction.user.id,
            )
            db.add(mini)

    embed = discord.Embed(
        title=f"👥 Minions Arrive!",
        description=f"**{count}** **{mini_t.name}**(s) emerge to aid **{boss.display_name}**!",
        color=0xF97316,
    )
    await interaction.followup.send(embed=embed)


# ── /gm boss legendary ────────────────────────────────────────────────────────

@boss_group.command(name="legendary", description="Use a legendary action for the active boss (GM only)")
@app_commands.describe(action_name="Name of the legendary action to use")
async def gm_boss_legendary(interaction: discord.Interaction, action_name: str):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        if boss.legendary_actions_remaining <= 0:
            await interaction.followup.send(
                f"{boss.display_name} has no legendary actions remaining this round.",
                ephemeral=True,
            )
            return

        action = next(
            (a for a in (boss.legendary_actions or []) if a.get("name", "").lower() == action_name.lower()),
            None,
        )
        if not action:
            await interaction.followup.send(
                f"Legendary action **{action_name}** not found.",
                ephemeral=True,
            )
            return

        cost = action.get("cost", 1)
        if boss.legendary_actions_remaining < cost:
            await interaction.followup.send(
                f"Need {cost} legendary action(s) but only {boss.legendary_actions_remaining} remaining.",
                ephemeral=True,
            )
            return

        boss.legendary_actions_remaining -= cost

    embed = discord.Embed(
        title=f"⚡ Legendary Action — {action['name']}",
        description=action.get("description", f"{boss.display_name} unleashes a legendary power!") or f"{boss.display_name} unleashes a legendary power!",
        color=0xEF4444,
    )
    embed.add_field(name="Legendary Actions Remaining", value=f"{boss.legendary_actions_remaining}/{boss.legendary_action_count}", inline=True)
    await interaction.followup.send(embed=embed)


# ── /gm boss kill ─────────────────────────────────────────────────────────────

@boss_group.command(name="kill", description="Instantly kill the active boss and award loot/XP (GM only)")
async def gm_boss_kill(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss, Character
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        xp_value = boss.xp_value or 500
        gold_drop = boss.gold_drop or 0
        loot_table = boss.loot_table or []
        boss_name = boss.display_name

        # Get active characters for XP split
        active_chars = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        combat_participants = list(active_chars.scalars().all())
        participant_count = max(len(combat_participants), 1)
        xp_per_player = xp_value // participant_count

        for char in combat_participants:
            char.xp = (char.xp or 0) + xp_per_player
            if gold_drop > 0:
                char.gold = (char.gold or 0) + (gold_drop // participant_count)

        await db.delete(boss)

    embed = discord.Embed(
        title=f"💀 {boss_name} Defeated!",
        description=f"The mighty **{boss_name}** has fallen!",
        color=0x22C55E,
    )
    if combat_participants:
        embed.add_field(
            name="✨ XP Awarded",
            value=f"**{xp_per_player} XP** each to {participant_count} player(s)",
            inline=False,
        )
    if gold_drop > 0:
        embed.add_field(name="💰 Gold", value=f"**{gold_drop}** gold dropped!", inline=True)
    if loot_table:
        loot_lines = []
        for item in loot_table:
            qty = item.get("qty", 1)
            chance = item.get("chance", 1.0)
            qty_str = f"x{qty}" if qty > 1 else ""
            loot_lines.append(f"• {item.get('item', 'Unknown')} {qty_str} ({round(chance * 100)}% chance)")
        embed.add_field(name="🎁 Loot Table", value="\n".join(loot_lines) or "None", inline=False)
    embed.set_footer(text="Use /gm boss spawn to summon another")
    await interaction.followup.send(embed=embed)


# ── /gm boss flee ─────────────────────────────────────────────────────────────

@boss_group.command(name="flee", description="The active boss flees — awards half XP (GM only)")
async def gm_boss_flee(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return

    await interaction.response.defer()
    async with get_db() as db:
        from database.models import SpawnedBoss, Character
        result = await db.execute(
            select(SpawnedBoss).where(
                SpawnedBoss.guild_id == interaction.guild_id,
                SpawnedBoss.channel_id == interaction.channel_id,
            ).order_by(SpawnedBoss.spawned_at.desc()).limit(1)
        )
        boss = result.scalar_one_or_none()
        if not boss:
            await interaction.followup.send("No active boss in this channel.", ephemeral=True)
            return

        xp_value = boss.xp_value or 500
        xp_half = xp_value // 2
        boss_name = boss.display_name

        active_chars = await db.execute(
            select(Character).where(
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        combat_participants = list(active_chars.scalars().all())
        participant_count = max(len(combat_participants), 1)
        xp_per_player = xp_half // participant_count

        for char in combat_participants:
            char.xp = (char.xp or 0) + xp_per_player

        await db.delete(boss)

    embed = discord.Embed(
        title=f"💨 {boss_name} Flees!",
        description=f"**{boss_name}** retreats in defeat! "
                    f"The party earns **{xp_per_player} XP** each (half value) for driving it off.",
        color=0xF97316,
    )
    await interaction.followup.send(embed=embed)


# ---------------------------------------------------------------------------
# /gm title subgroup
# ---------------------------------------------------------------------------

gm_title_group = app_commands.Group(name="title", description="GM: manage character titles", parent=gm_group)


# ── /gm title create ──────────────────────────────────────────────────────────

@gm_title_group.command(name="create", description="Create a new title for this server (GM only)")
@app_commands.describe(
    name="Title name (e.g. 'The Undying')",
    tier="Rarity tier",
    description="Flavor text for the title",
    unique="Only one holder at a time?",
)
@app_commands.choices(tier=[
    app_commands.Choice(name="Common", value="common"),
    app_commands.Choice(name="Rare", value="rare"),
    app_commands.Choice(name="Epic", value="epic"),
    app_commands.Choice(name="Legendary", value="legendary"),
    app_commands.Choice(name="Mythic", value="mythic"),
])
async def gm_title_create(
    interaction: discord.Interaction,
    name: str,
    tier: app_commands.Choice[str],
    description: str | None = None,
    unique: bool = False,
):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        try:
            title = await create_title(
                db=db,
                guild_id=str(interaction.guild_id),
                name=name.strip(),
                tier=tier.value,
                description=description.strip() if description else None,
                is_unique=unique,
                created_by=str(interaction.user.id),
            )
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

    meta = TIER_META.get(title.tier, TIER_META["common"])
    embed = discord.Embed(
        title=f"{meta['icon']} Title Created",
        description=f"**{meta['icon']} {title.name}** — *{meta['label']}*",
        color=meta["color"],
    )
    if title.description:
        embed.add_field(name="Description", value=title.description, inline=False)
    embed.add_field(name="Unique", value="Yes — only one holder" if title.is_unique else "No", inline=True)
    embed.set_footer(text="Use /gm title award to give this title to a character")
    await interaction.followup.send(embed=embed)


# ── /gm title award ───────────────────────────────────────────────────────────

@gm_title_group.command(name="award", description="Give a title to a character (GM only)")
@app_commands.describe(character_name="Name of the character", title_name="Name of the title")
async def gm_title_award(interaction: discord.Interaction, character_name: str, title_name: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        char = await db.scalar(select(Character).where(
            Character.guild_id == interaction.guild_id,
            Character.name.ilike(character_name),
        ))
        if not char:
            await interaction.followup.send(
                f"No character named '{character_name}' found.", ephemeral=True
            )
            return

        title = await db.scalar(select(Title).where(
            Title.guild_id == str(interaction.guild_id),
            Title.name.ilike(title_name),
        ))
        if not title:
            await interaction.followup.send(
                f"No title named '{title_name}' found in this server.", ephemeral=True
            )
            return

        try:
            ct = await award_title(db, char.id, title.id, str(interaction.user.id))
        except ValueError as e:
            await interaction.followup.send(str(e), ephemeral=True)
            return

    meta = TIER_META.get(title.tier, TIER_META["common"])
    embed = discord.Embed(
        title="Title Awarded",
        description=f"{meta['icon']} **{title.name}** awarded to **{char.name}**!",
        color=meta["color"],
    )
    await interaction.followup.send(embed=embed)


# ── /gm title revoke ──────────────────────────────────────────────────────────

@gm_title_group.command(name="revoke", description="Remove a title from a character (GM only)")
@app_commands.describe(character_name="Name of the character", title_name="Name of the title")
async def gm_title_revoke(interaction: discord.Interaction, character_name: str, title_name: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        char = await db.scalar(select(Character).where(
            Character.guild_id == interaction.guild_id,
            Character.name.ilike(character_name),
        ))
        if not char:
            await interaction.followup.send(
                f"No character named '{character_name}' found.", ephemeral=True
            )
            return

        title = await db.scalar(select(Title).where(
            Title.guild_id == str(interaction.guild_id),
            Title.name.ilike(title_name),
        ))
        if not title:
            await interaction.followup.send(
                f"No title named '{title_name}' found in this server.", ephemeral=True
            )
            return

        removed = await revoke_title(db, char.id, title.id)
        if not removed:
            await interaction.followup.send(
                f"**{char.name}** doesn't hold the title '{title_name}'.", ephemeral=True
            )
            return

    await interaction.followup.send(
        f"❌ **{title_name}** revoked from **{char.name}**."
    )


# ── /gm title delete ──────────────────────────────────────────────────────────

@gm_title_group.command(name="delete", description="Permanently delete a title from the server (GM only)")
@app_commands.describe(title_name="Name of the title to delete")
async def gm_title_delete(interaction: discord.Interaction, title_name: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()
    async with get_db() as db:
        title = await db.scalar(select(Title).where(
            Title.guild_id == str(interaction.guild_id),
            Title.name.ilike(title_name),
        ))
        if not title:
            await interaction.followup.send(
                f"No title named '{title_name}' found.", ephemeral=True
            )
            return

        # Remove all character associations first
        await db.execute(
            delete(CharacterTitle).where(CharacterTitle.title_id == title.id)
        )
        await db.delete(title)
        await db.commit()

    await interaction.followup.send(
        f"🗑️ Title **{title_name}** and all its character associations have been deleted."
    )


# ── /gm title list ────────────────────────────────────────────────────────────

@gm_title_group.command(name="list", description="List all titles in this server with holder counts (GM only)")
async def gm_title_list(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        titles = await list_guild_titles(db, str(interaction.guild_id))

    if not titles:
        await interaction.followup.send(
            "No titles defined in this server yet. Use `/gm title create` to add one.",
            ephemeral=True,
        )
        return

    embed = discord.Embed(
        title="🏅 Titles — This Server",
        color=0xF1C40F,
    )
    for t in titles:
        meta = TIER_META.get(t.tier, TIER_META["common"])
        unique_tag = " [Unique]" if t.is_unique else ""
        embed.add_field(
            name=f"{meta['icon']} {t.name}{unique_tag}",
            value=f"*{meta['label']}*  ·  {t.description or 'No description'}",
            inline=False,
        )
    embed.set_footer(text=f"{len(titles)} title(s)  •  LoreForge")
    await interaction.followup.send(embed=embed, ephemeral=True)


# ---------------------------------------------------------------------------
# /gm generate — Procedural content generation (Tier 2)
# ---------------------------------------------------------------------------

@boss_group.command(name="generate", description="Generate a procedural encounter and save as boss template")
@app_commands.describe(difficulty="Difficulty level", location="Location context (e.g. 'the dark forest')")
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Easy", value="easy"),
    app_commands.Choice(name="Medium", value="medium"),
    app_commands.Choice(name="Hard", value="hard"),
    app_commands.Choice(name="Deadly", value="deadly"),
])
async def gm_generate_encounter(interaction: discord.Interaction, difficulty: app_commands.Choice[str], location: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()

    from services.procedural_gen import generate_encounter

    gen = await generate_encounter(difficulty.value, location)
    enemies_text = "\n".join(
        f"• **{e['name']}** — ❤️ {e['hp']} HP, ⚔️ +{e['attack']} ATK, {e['damage']} DMG"
        for e in gen.get("enemies", [])
    ) or "None"
    rewards = gen.get("rewards", {})
    rewards_text = f"✨ {rewards.get('xp', 0)} XP  ·  💰 {rewards.get('gold', 0)} Gold"

    embed = discord.Embed(
        title=f"⚔️ Generated Encounter: {gen['name']}",
        description=gen.get("description", ""),
        color=0xEF4444,
    )
    embed.add_field(name="Enemies", value=enemies_text, inline=False)
    embed.add_field(name="Rewards", value=rewards_text, inline=False)
    embed.set_footer(text=f"Difficulty: {difficulty.value}")

    class GenerateEncounterView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.gen = gen
            self.difficulty = difficulty.value
            self.location = location

        @discord.ui.button(label="💾 Save to DB", style=discord.ButtonStyle.success)
        async def save_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            async with get_db() as db:
                enemies = self.gen.get("enemies", [])
                if enemies:
                    main_enemy = enemies[0]
                    template = BossTemplate(
                        guild_id=interaction2.guild_id,
                        name=self.gen["name"],
                        description=self.gen.get("description", ""),
                        hp_max=main_enemy["hp"],
                        armor_class=14,
                        attack_bonus=main_enemy["attack"],
                        damage_dice=main_enemy["damage"],
                        damage_bonus=0,
                        xp_value=self.gen.get("rewards", {}).get("xp", 200),
                        gold_drop=self.gen.get("rewards", {}).get("gold", 50),
                        created_by=interaction2.user.id,
                    )
                    db.add(template)
                    await db.flush()
                    await interaction2.response.edit_message(
                        content=f"✅ Saved as boss template **{self.gen['name']}** (ID: {template.id})!",
                        embed=None,
                        view=None,
                    )

        @discord.ui.button(label="🔄 Regenerate", style=discord.ButtonStyle.secondary)
        async def regen_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            self.gen = await generate_encounter(self.difficulty, self.location)
            enemies_text = "\n".join(
                f"• **{e['name']}** — ❤️ {e['hp']} HP, ⚔️ +{e['attack']} ATK, {e['damage']} DMG"
                for e in self.gen.get("enemies", [])
            ) or "None"
            rewards = self.gen.get("rewards", {})
            embed2 = discord.Embed(
                title=f"⚔️ Generated Encounter: {self.gen['name']}",
                description=self.gen.get("description", ""),
                color=0xEF4444,
            )
            embed2.add_field(name="Enemies", value=enemies_text, inline=False)
            embed2.add_field(name="Rewards", value=f"✨ {rewards.get('xp', 0)} XP  ·  💰 {rewards.get('gold', 0)} Gold", inline=False)
            await interaction2.response.edit_message(embed=embed2, view=self)

        @discord.ui.button(label="🗑️ Discard", style=discord.ButtonStyle.danger)
        async def discard_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            await interaction2.response.edit_message(content="❌ Discarded.", embed=None, view=None)

    await interaction.followup.send(embed=embed, view=GenerateEncounterView())


# ── /gm generate quest ──────────────────────────────────────────────────────

generate_group = app_commands.Group(name="generate", description="Procedural content generation", parent=gm_group)


@generate_group.command(name="quest", description="Generate a procedural quest")
@app_commands.describe(difficulty="Difficulty level", location="Quest location", theme="Optional theme")
@app_commands.choices(difficulty=[
    app_commands.Choice(name="Easy", value="easy"),
    app_commands.Choice(name="Medium", value="medium"),
    app_commands.Choice(name="Hard", value="hard"),
    app_commands.Choice(name="Deadly", value="deadly"),
])
async def gm_generate_quest(interaction: discord.Interaction, difficulty: app_commands.Choice[str], location: str = "the realm", theme: str = None):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()

    from services.procedural_gen import generate_quest

    gen = await generate_quest(difficulty.value, location, theme)
    objectives_text = "\n".join(f"{i+1}. {o}" for i, o in enumerate(gen.get("objectives", [])))

    embed = discord.Embed(
        title=f"📜 Generated Quest: {gen['title']}",
        description=gen.get("description", ""),
        color=0xF59E0B,
    )
    embed.add_field(name="Objectives", value=objectives_text or "None", inline=False)
    embed.add_field(name="Rewards", value=f"✨ {gen.get('reward_xp', 0)} XP  ·  💰 {gen.get('reward_gold', 0)} Gold", inline=True)
    embed.add_field(name="NPC Giver", value=gen.get("npc_name", "Unknown"), inline=True)
    embed.set_footer(text=f"Difficulty: {difficulty.value}")

    class GenerateQuestView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.gen = gen
            self.difficulty = difficulty.value
            self.location = location
            self.theme = theme

        @discord.ui.button(label="💾 Save to DB", style=discord.ButtonStyle.success)
        async def save_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            from database.models import Quest
            async with get_db() as db:
                quest = Quest(
                    guild_id=interaction2.guild_id,
                    name=self.gen["title"],
                    description=self.gen.get("description", ""),
                    is_active=True,
                    reward_xp=self.gen.get("reward_xp", 500),
                    reward_gold=self.gen.get("reward_gold", 200),
                    quest_type="generated",
                    created_by=interaction2.user.id,
                )
                db.add(quest)
                await db.flush()
                await interaction2.response.edit_message(
                    content=f"✅ Saved as quest **{self.gen['title']}** (ID: {quest.id})!",
                    embed=None,
                    view=None,
                )

        @discord.ui.button(label="🔄 Regenerate", style=discord.ButtonStyle.secondary)
        async def regen_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            self.gen = await generate_quest(self.difficulty, self.location, self.theme)
            objectives_text = "\n".join(f"{i+1}. {o}" for i, o in enumerate(self.gen.get("objectives", [])))
            embed2 = discord.Embed(
                title=f"📜 Generated Quest: {self.gen['title']}",
                description=self.gen.get("description", ""),
                color=0xF59E0B,
            )
            embed2.add_field(name="Objectives", value=objectives_text or "None", inline=False)
            embed2.add_field(name="Rewards", value=f"✨ {self.gen.get('reward_xp', 0)} XP  ·  💰 {self.gen.get('reward_gold', 0)} Gold", inline=True)
            embed2.add_field(name="NPC Giver", value=self.gen.get("npc_name", "Unknown"), inline=True)
            await interaction2.response.edit_message(embed=embed2, view=self)

        @discord.ui.button(label="🗑️ Discard", style=discord.ButtonStyle.danger)
        async def discard_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            await interaction2.response.edit_message(content="❌ Discarded.", embed=None, view=None)

    await interaction.followup.send(embed=embed, view=GenerateQuestView())


@generate_group.command(name="npc", description="Generate a procedural NPC")
@app_commands.describe(location="Where the NPC is found", role="Their role (e.g. merchant, guard)")
async def gm_generate_npc(interaction: discord.Interaction, location: str, role: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer()

    from services.procedural_gen import generate_npc

    gen = await generate_npc(location, role)
    dialogue_text = "\n".join(f"*\"{d}\"*" for d in gen.get("dialogue", []))

    embed = discord.Embed(
        title=f"👤 Generated NPC: {gen['name']}",
        description=f"**{gen.get('title', 'No title')}**\n\n{gen.get('description', '')}",
        color=0x3B82F6,
    )
    embed.add_field(name="Personality", value=gen.get("personality", "Mysterious"), inline=True)
    embed.add_field(name="Appearance", value=gen.get("appearance", "Ordinary"), inline=True)
    embed.add_field(name="Attitude", value=gen.get("attitude", "neutral").capitalize(), inline=True)
    if dialogue_text:
        embed.add_field(name="Dialogue", value=dialogue_text[:500], inline=False)

    class GenerateNPCView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.gen = gen
            self.location = location
            self.role = role

        @discord.ui.button(label="💾 Save to DB", style=discord.ButtonStyle.success)
        async def save_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            async with get_db() as db:
                # Find a location to place them
                loc_result = await db.execute(
                    select(Location).where(
                        Location.guild_id == interaction2.guild_id,
                        Location.name.ilike(f"%{self.location}%"),
                    )
                )
                loc = loc_result.scalar_one_or_none()
                location_id = loc.id if loc else 1

                npc = NPC(
                    guild_id=interaction2.guild_id,
                    name=self.gen["name"],
                    title=self.gen.get("title", ""),
                    description=self.gen.get("description", ""),
                    location_id=location_id,
                    disposition=self.gen.get("attitude", "neutral"),
                    created_by=interaction2.user.id,
                )
                db.add(npc)
                await db.flush()
                await interaction2.response.edit_message(
                    content=f"✅ Saved as NPC **{self.gen['name']}** (ID: {npc.id})!",
                    embed=None,
                    view=None,
                )

        @discord.ui.button(label="🔄 Regenerate", style=discord.ButtonStyle.secondary)
        async def regen_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            if not await gm_only(interaction2):
                return
            self.gen = await generate_npc(self.location, self.role)
            dialogue_text = "\n".join(f"*\"{d}\"*" for d in self.gen.get("dialogue", []))
            embed2 = discord.Embed(
                title=f"👤 Generated NPC: {self.gen['name']}",
                description=f"**{self.gen.get('title', 'No title')}**\n\n{self.gen.get('description', '')}",
                color=0x3B82F6,
            )
            embed2.add_field(name="Personality", value=self.gen.get("personality", "Mysterious"), inline=True)
            embed2.add_field(name="Appearance", value=self.gen.get("appearance", "Ordinary"), inline=True)
            embed2.add_field(name="Attitude", value=self.gen.get("attitude", "neutral").capitalize(), inline=True)
            if dialogue_text:
                embed2.add_field(name="Dialogue", value=dialogue_text[:500], inline=False)
            await interaction2.response.edit_message(embed=embed2, view=self)

        @discord.ui.button(label="🗑️ Discard", style=discord.ButtonStyle.danger)
        async def discard_btn(self, interaction2: discord.Interaction, btn: discord.ui.Button):
            await interaction2.response.edit_message(content="❌ Discarded.", embed=None, view=None)

    await interaction.followup.send(embed=embed, view=GenerateNPCView())


# ── /gm world-pulse — Manually tick the living world ──────────────────────────

@gm_group.command(name="world-pulse", description="Manually trigger the living world simulation tick (GM only)")
async def gm_world_pulse(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    if hasattr(interaction.client, 'living_world') and interaction.client.living_world:
        await interaction.client.living_world._tick_all_guilds()
        await interaction.followup.send("🌍 World pulse triggered! All guilds ticked.", ephemeral=True)
    else:
        await interaction.followup.send("⚠️ Living World service is not running.", ephemeral=True)


# ── /npc letter — Send in-character letter to a player (GM only) ──────────────

@app_commands.command(name="npc-letter", description="Send an in-character letter from an NPC to a player (GM only)")
@app_commands.describe(user="Target player", content="Letter content")
async def npc_letter_cmd(interaction: discord.Interaction, user: discord.Member, content: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)

    embed = discord.Embed(
        title="📜 A Letter Has Arrived",
        description=content,
        color=0xD97706,
    )
    embed.set_footer(text="LoreForge — In-Character Mail")

    try:
        await user.send(embed=embed)
        await interaction.followup.send(f"✅ Letter sent to {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(
            f"⚠️ Could not DM {user.mention} — they may have DMs disabled.",
            ephemeral=True,
        )


# ---------------------------------------------------------------------------
# /gm vision — Send a custom vision to a player (Phase 6)
# ---------------------------------------------------------------------------

@gm_group.command(name="vision", description="Send a custom vision/dream to a player (GM only)")
@app_commands.describe(user="The player to send the vision to", text="The vision content")
async def gm_vision(interaction: discord.Interaction, user: discord.Member, text: str):
    if not await gm_only(interaction):
        return

    await interaction.response.defer(ephemeral=True)
    from database.models import Vision

    # Save to DB
    async with get_db() as db:
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        char = char_result.scalar_one_or_none()

        if char:
            db.add(Vision(
                character_id=char.id,
                guild_id=interaction.guild_id,
                vision_text=text,
                trigger="gm_custom",
            ))

    # DM the player
    embed = discord.Embed(
        title="💫 A Vision Comes to You...",
        description=text,
        color=0x9B59B6,
    )
    embed.set_footer(text="Only you can see this vision.")
    try:
        await user.send(embed=embed)
        await interaction.followup.send(f"✅ Vision sent to {user.mention}.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(f"⚠️ Could not DM {user.mention} — may have DMs disabled. Vision saved to DB.", ephemeral=True)


# ---------------------------------------------------------------------------
# /gm spawn set / clear
# ---------------------------------------------------------------------------

async def _all_locations_autocomplete(interaction: discord.Interaction, current: str):
    async with get_db() as db:
        result = await db.execute(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.name.ilike(f"%{current}%"),
            ).limit(25)
        )
        return [app_commands.Choice(name=loc.name, value=loc.name) for loc in result.scalars().all()]


@gm_group.command(name="spawn-set", description="Set the default spawn location for all new characters (GM only)")
@app_commands.describe(location="Name of the location new characters will start in")
@app_commands.autocomplete(location=_all_locations_autocomplete)
async def gm_spawn_set(interaction: discord.Interaction, location: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        loc = await db.scalar(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.name.ilike(location),
            )
        )
        if not loc:
            await interaction.followup.send(
                f"Location **{location}** not found. Use the exact name from `/location view`.",
                ephemeral=True,
            )
            return
        config = await db.scalar(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
        if config:
            config.default_spawn_location_id = loc.id
        else:
            config = GuildConfig(guild_id=interaction.guild_id, default_spawn_location_id=loc.id)
            db.add(config)
    await interaction.followup.send(
        f"✅ Default spawn point set to **{loc.name}**. All future characters will start there.",
        ephemeral=True,
    )


@gm_group.command(name="spawn-clear", description="Remove the default spawn point so characters start without a location (GM only)")
async def gm_spawn_clear(interaction: discord.Interaction):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        config = await db.scalar(select(GuildConfig).where(GuildConfig.guild_id == interaction.guild_id))
        if not config or config.default_spawn_location_id is None:
            await interaction.followup.send("No default spawn point is currently set.", ephemeral=True)
            return
        config.default_spawn_location_id = None
    await interaction.followup.send("✅ Default spawn point cleared.", ephemeral=True)


# ---------------------------------------------------------------------------
# /gm teleport
# ---------------------------------------------------------------------------

@gm_group.command(name="teleport", description="Move a player's active character to any location (GM only)")
@app_commands.describe(user="The player to teleport", location="Destination location name")
@app_commands.autocomplete(location=_all_locations_autocomplete)
async def gm_teleport(interaction: discord.Interaction, user: discord.Member, location: str):
    if not await gm_only(interaction):
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        from database.models import CharacterLocation

        loc = await db.scalar(
            select(Location).where(
                Location.guild_id == interaction.guild_id,
                Location.name.ilike(location),
            )
        )
        if not loc:
            await interaction.followup.send(
                f"Location **{location}** not found. Use the exact name from `/location view`.",
                ephemeral=True,
            )
            return

        char = await db.scalar(
            select(Character).where(
                Character.user_id == user.id,
                Character.guild_id == interaction.guild_id,
                Character.is_active == True,
            )
        )
        if not char:
            await interaction.followup.send(
                f"{user.mention} has no active character in this server.",
                ephemeral=True,
            )
            return

        existing = await db.scalar(
            select(CharacterLocation).where(
                CharacterLocation.character_id == char.id,
                CharacterLocation.guild_id == interaction.guild_id,
            )
        )
        if existing:
            existing.location_id = loc.id
        else:
            db.add(CharacterLocation(
                character_id=char.id,
                guild_id=interaction.guild_id,
                location_id=loc.id,
            ))

    await interaction.followup.send(
        f"✅ **{char.name}** has been teleported to **{loc.name}**.",
        ephemeral=True,
    )


# ---------------------------------------------------------------------------
# Cog
# ---------------------------------------------------------------------------

class GmCog(commands.Cog, name="GM"):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.tree.add_command(gm_group)
        bot.tree.add_command(npc_letter_cmd)

    async def cog_unload(self):
        self.bot.tree.remove_command("gm")
        self.bot.tree.remove_command("npc-letter")


async def setup(bot: commands.Bot):
    await bot.add_cog(GmCog(bot))
