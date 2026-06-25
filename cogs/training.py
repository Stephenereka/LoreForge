import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from database.session import get_db
from database.models import Character, TrainingSession
from services.combat_engine import (
    roll, modifier, Combatant, player_attack, apply_condition,
    tick_conditions, CONDITIONS,
)
from services.training_service import generate_dummy_action, DIFFICULTY_CONFIGS
from services.leveling import check_level_up
import datetime

active_training = {}

_DUMMY_AVATAR = "https://i.imgur.com/8ZQ1Z2B.png"  # fallback; webhook still works without avatar

_DIFFICULTY_LABEL = {
    "easy": "Training Dummy 🟢",
    "medium": "Training Dummy 🟡",
    "hard": "Training Dummy 🟠",
    "impossible": "Training Dummy 💀",
}


class TrainingDummy:
    def __init__(self, difficulty: str):
        config = DIFFICULTY_CONFIGS[difficulty]
        self.name = f"Training Dummy ({difficulty.title()})"
        self.difficulty = difficulty
        self.hp_max = config["hp"]
        self.hp_current = config["hp"]
        self.ac = config["ac"]
        self.attack_bonus = config["attack_bonus"]
        self.damage_dice = config["damage_dice"]  # fixed: was config["damage"]
        self.damage_bonus = config["damage_bonus"]
        self.conditions = []
        self.is_alive = True
        self.is_dead = False
        self.is_unconscious = False

    def take_damage(self, amount: int):
        self.hp_current = max(0, self.hp_current - amount)
        if self.hp_current <= 0:
            self.is_alive = False
            self.is_dead = True

    def attack(self):
        atk_roll = roll(20) + self.attack_bonus
        dmg = self._roll_damage()
        return {"attack_roll": atk_roll, "damage": dmg, "is_miss": atk_roll == 1}

    def _roll_damage(self):
        import re
        match = re.match(r"(\d+)d(\d+)(?:\+(\d+))?", self.damage_dice)
        if match:
            count, sides = int(match.group(1)), int(match.group(2))
            bonus = int(match.group(3)) if match.group(3) else 0
            return sum(roll(sides) for _ in range(count)) + bonus
        return 2


class TrainingSessionData:
    def __init__(self, channel_id, user_id, guild_id, character_id, difficulty, player, dummy, mode: str = "dnd"):
        self.channel_id = channel_id
        self.user_id = user_id
        self.guild_id = guild_id
        self.character_id = character_id
        self.difficulty = difficulty
        self.mode = mode  # "dnd" or "rp"
        self.player = player
        self.dummy = dummy
        self.round = 1
        self.log: list[str] = []
        self.state = "active"
        self.damage_dealt = 0
        self.damage_taken = 0
        self.last_player_action = ""
        self.webhook: discord.Webhook | None = None

    def add_log(self, line: str):
        self.log.append(line)

    def arena_embed(self) -> discord.Embed:
        if self.mode == "rp":
            embed = discord.Embed(
                title=f"📖 RP Sparring — {self.difficulty.title()}",
                color=0x8B5CF6,
            )
            embed.add_field(name="Round", value=f"**{self.round}**", inline=True)
            embed.add_field(name="Fighters", value=f"{self.player.name} vs Training Dummy", inline=True)
            if self.log:
                embed.add_field(name="📜 Narration", value="\n".join(self.log[-5:]), inline=False)
            embed.set_footer(text="Type your action • 'surrender' or /training stop to end")
            return embed

        player_pct = max(0, self.player.hp_current / self.player.hp_max) if self.player.hp_max > 0 else 0
        dummy_pct = max(0, self.dummy.hp_current / self.dummy.hp_max) if self.dummy.hp_max > 0 else 0
        player_bar = "█" * round(player_pct * 10) + "░" * (10 - round(player_pct * 10))
        dummy_bar = "█" * round(dummy_pct * 10) + "░" * (10 - round(dummy_pct * 10))

        embed = discord.Embed(
            title=f"⚔️ Training Arena — {self.difficulty.title()}",
            color=0xF59E0B,
        )
        embed.add_field(
            name=f"🎯 {self.player.name} (Lv{self.player.level} {self.player.char_class})",
            value=f"❤️ {self.player.hp_current}/{self.player.hp_max} {player_bar}\n🛡️ AC {self.player.armor_class}",
            inline=True,
        )
        embed.add_field(
            name="🎯 Training Dummy",
            value=f"❤️ {self.dummy.hp_current}/{self.dummy.hp_max} {dummy_bar}\n🛡️ AC {self.dummy.ac}",
            inline=True,
        )
        embed.add_field(name="Round", value=f"**{self.round}**", inline=True)
        if self.log:
            embed.add_field(name="📜 Recent Actions", value="\n".join(self.log[-5:]), inline=False)
        return embed


async def _dummy_send(session: TrainingSessionData, channel: discord.TextChannel, content: str = "", embed: discord.Embed | None = None):
    """Send a message as the training dummy via webhook if available, else plain channel send."""
    label = _DIFFICULTY_LABEL.get(session.difficulty, "Training Dummy")
    if session.webhook:
        try:
            await session.webhook.send(
                content=content or None,
                embed=embed,
                username=label,
                wait=False,
            )
            return
        except Exception:
            pass
    # Fallback to plain channel message
    await channel.send(content=content or "", embed=embed)


async def _cleanup_webhook(session: TrainingSessionData):
    if session.webhook:
        try:
            await session.webhook.delete(reason="Training session ended")
        except Exception:
            pass
        session.webhook = None


class TrainingModeView(discord.ui.View):
    """First step: choose DnD combat or pure RP sparring."""
    def __init__(self, bot):
        super().__init__(timeout=300)
        self.bot = bot

    @discord.ui.button(label="⚔️ DnD Combat", style=discord.ButtonStyle.primary, row=0)
    async def dnd_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="⚔️ DnD Combat — Choose Difficulty",
            description=(
                "**Easy 🟢** — Slow dummy, great for beginners.\n"
                "**Medium 🟡** — Basic tactics, competent fighter.\n"
                "**Hard 🟠** — Aggressive, uses conditions.\n"
                "**Impossible 💀** — Near-perfect counter-play."
            ),
            color=0xF59E0B,
        )
        await interaction.response.edit_message(embed=embed, view=TrainingDifficultyView(self.bot, mode="dnd"))

    @discord.ui.button(label="📖 RP Sparring", style=discord.ButtonStyle.secondary, row=0)
    async def rp_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="📖 RP Sparring — Choose Difficulty",
            description=(
                "No dice rolls or HP tracking — pure narrative sparring.\n"
                "Type your actions in chat and the dummy responds.\n\n"
                "**Easy 🟢** — Clumsy, makes mistakes.\n"
                "**Medium 🟡** — Trained fighter.\n"
                "**Hard 🟠** — Relentless and tactical.\n"
                "**Impossible 💀** — Perfect counter, taunts every move."
            ),
            color=0x8B5CF6,
        )
        await interaction.response.edit_message(embed=embed, view=TrainingDifficultyView(self.bot, mode="rp"))


class TrainingDifficultyView(discord.ui.View):
    def __init__(self, bot, mode: str = "dnd"):
        super().__init__(timeout=300)
        self.bot = bot
        self.mode = mode

    async def on_error(self, interaction: discord.Interaction, error: Exception, item) -> None:
        import traceback
        traceback.print_exc()
        print(f"[Training] View error on {item}: {type(error).__name__}: {error}")
        try:
            msg = f"Training error: `{type(error).__name__}: {error}`"
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    @discord.ui.button(label="Easy 😊", style=discord.ButtonStyle.success, emoji="🟢")
    async def easy_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_training(interaction, "easy")

    @discord.ui.button(label="Medium 🤔", style=discord.ButtonStyle.primary, emoji="🟡")
    async def medium_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_training(interaction, "medium")

    @discord.ui.button(label="Hard 😤", style=discord.ButtonStyle.danger, emoji="🟠")
    async def hard_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_training(interaction, "hard")

    @discord.ui.button(label="Impossible 💀", style=discord.ButtonStyle.danger, emoji="🔴")
    async def impossible_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._start_training(interaction, "impossible")

    async def _start_training(self, interaction: discord.Interaction, difficulty: str):
        import traceback
        try:
            if interaction.channel_id in active_training:
                await interaction.response.send_message("Training is already active in this channel.", ephemeral=True)
                return

            # Acknowledge the button click immediately
            await interaction.response.defer(ephemeral=True)

            char = await get_active_char(interaction.user.id, interaction.guild_id)
            if not char:
                await interaction.followup.send("You need an active living character to train.", ephemeral=True)
                return

            dummy = TrainingDummy(difficulty)

            player_combatant = Combatant(
                id=str(interaction.user.id),
                name=char.name,
                is_player=True,
                level=char.level,
                char_class=char.char_class,
                hp_max=char.hp_max,
                hp_current=char.hp_current,
                hp_temp=char.hp_temp,
                strength=char.strength, dexterity=char.dexterity,
                constitution=char.constitution, intelligence=char.intelligence,
                wisdom=char.wisdom, charisma=char.charisma,
                armor_class=char.armor_class,
                is_dead=False, is_unconscious=False,
                death_saves_success=0, death_saves_failure=0,
                conditions=[],
                class_resources=dict(char.class_resources or {}),
                weapon="unarmed",
            )

            session = TrainingSessionData(
                channel_id=interaction.channel_id,
                user_id=interaction.user.id,
                guild_id=interaction.guild_id,
                character_id=char.id,
                difficulty=difficulty,
                player=player_combatant,
                dummy=dummy,
                mode=self.mode,
            )

            # Create webhook so dummy speaks with its own identity
            try:
                session.webhook = await interaction.channel.create_webhook(
                    name=_DIFFICULTY_LABEL.get(difficulty, "Training Dummy"),
                    reason="LoreForge training dummy",
                )
            except Exception as e:
                print(f"[Training] Webhook creation failed: {e}")

            active_training[interaction.channel_id] = session

            embed = session.arena_embed()
            if self.mode == "rp":
                start_content = f"📖 **RP Sparring: {difficulty.title()}** — Write your actions in chat! Type `surrender` to end."
            else:
                start_content = f"⚔️ **Training: {difficulty.title()}** — Type your actions in chat!"

            # Send the arena as a fresh channel message (avoids edit_original_response issues)
            await interaction.channel.send(content=start_content, embed=embed)
            # Dismiss the ephemeral defer silently
            await interaction.delete_original_response()

        except Exception as e:
            traceback.print_exc()
            print(f"[Training] _start_training error: {type(e).__name__}: {e}")
            try:
                if interaction.response.is_done():
                    await interaction.followup.send(f"Failed to start training: `{type(e).__name__}: {e}`", ephemeral=True)
                else:
                    await interaction.response.send_message(f"Failed to start training: `{type(e).__name__}: {e}`", ephemeral=True)
            except Exception:
                pass


async def get_active_char(user_id: int, guild_id: int):
    async with get_db() as db:
        result = await db.execute(
            select(Character).where(
                Character.user_id == user_id,
                Character.guild_id == guild_id,
                Character.is_active == True,
                Character.is_dead == False,
            )
        )
        return result.scalar_one_or_none()


# ── Commands ──────────────────────────────────────────────────────────────────

training_group = app_commands.Group(name="training", description="Training dummy commands")


@training_group.command(name="start", description="Start training against an AI dummy")
async def training_start(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🎯 Training Dummy — Choose Mode",
        description=(
            "**⚔️ DnD Combat** — Full dice mechanics: attack rolls, AC, HP tracking, conditions, and XP rewards.\n\n"
            "**📖 RP Sparring** — Pure narrative mode. Type your actions freely; the training dummy responds with vivid descriptions powered by DeepSeek AI. No dice, just immersive roleplay."
        ),
        color=0x8B5CF6,
    )
    await interaction.response.send_message(embed=embed, view=TrainingModeView(interaction.client))


@training_group.command(name="stop", description="End your training session early")
async def training_stop(interaction: discord.Interaction):
    session = active_training.get(interaction.channel_id)
    if not session or session.user_id != interaction.user.id:
        await interaction.response.send_message("No active training session for you here.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)
    await _end_training(interaction, session, "forfeit")


# ── RP Mode Handler ───────────────────────────────────────────────────────────

async def _handle_rp_training(message: discord.Message, session: TrainingSessionData):
    """Pure narrative sparring — no dice, DeepSeek responds to every player action."""
    import aiohttp, os
    content = message.content.strip()
    content_lower = content.lower()

    # End keywords
    if any(kw in content_lower for kw in ("surrender", "stop", "quit", "flee", "run", "escape")):
        try:
            await message.delete()
        except Exception:
            pass
        await _end_training_via_msg(message.channel, session, "fled")
        return

    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    config = DIFFICULTY_CONFIGS.get(session.difficulty, DIFFICULTY_CONFIGS["medium"])

    dummy_reply = f"*{config['flavor_prefix']} as you act.*"
    if DEEPSEEK_API_KEY:
        try:
            history_text = "\n".join(session.log[-6:]) if session.log else "The sparring just began."
            system_prompt = (
                f"You are a sentient training dummy in a dark fantasy martial arts world. "
                f"Difficulty: {session.difficulty}. Personality: {config['personality']}. "
                f"Respond to the player's sparring action with 2-3 vivid sentences of combat narration. "
                f"Stay in character as a dummy that can speak and react. No game stats or dice. "
                f"Keep it immersive and exciting."
            )
            user_prompt = (
                f"Round {session.round}. Recent exchange:\n{history_text}\n\n"
                f"Player's action: {content[:300]}"
            )
            async with aiohttp.ClientSession() as http:
                resp = await http.post(
                    "https://api.deepseek.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {DEEPSEEK_API_KEY}", "Content-Type": "application/json"},
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_tokens": 120,
                        "temperature": 0.9,
                    },
                    timeout=aiohttp.ClientTimeout(total=6),
                )
                data = await resp.json()
                dummy_reply = data["choices"][0]["message"]["content"].strip()
        except Exception:
            pass

    session.add_log(f"*{session.player.name}:* {content[:80]}")
    session.round += 1
    embed = session.arena_embed()

    try:
        await message.delete()
    except Exception:
        pass

    await _dummy_send(session, message.channel, content=dummy_reply)
    await message.channel.send(f"**Round {session.round}**", embed=embed)


# ── DnD Message Handler ───────────────────────────────────────────────────────

async def _handle_training_message(bot, message: discord.Message, actual_user_id: int):
    session = active_training.get(message.channel.id)
    if not session or session.state != "active":
        return
    if actual_user_id != session.user_id:
        return
    if message.content.startswith("/"):
        return

    # Branch to RP mode
    if session.mode == "rp":
        await _handle_rp_training(message, session)
        return

    content_lower = message.content.lower()
    attack_keywords = ["attack", "strike", "hit", "slash", "punch", "kick", "swing", "cut"]
    defend_keywords = ["defend", "block", "guard", "shield", "brace"]
    flee_keywords = ["flee", "run", "escape", "retreat"]
    item_keywords = ["potion", "drink", "heal", "item", "use"]

    is_attack = any(kw in content_lower for kw in attack_keywords)
    is_defend = any(kw in content_lower for kw in defend_keywords)
    is_flee = any(kw in content_lower for kw in flee_keywords)
    is_item = any(kw in content_lower for kw in item_keywords)

    player = session.player
    dummy = session.dummy

    if is_attack:
        result = player_attack(player, weapon=player.weapon)
        if result["attack_roll"] >= dummy.ac and not result["is_miss"]:
            if result["is_crit"]:
                dummy.take_damage(result["damage"] * 2)
                session.add_log(f"⚔️ **CRIT!** You deal {result['damage'] * 2} damage!")
                session.damage_dealt += result["damage"] * 2
            else:
                dummy.take_damage(result["damage"])
                session.add_log(f"⚔️ You hit the dummy for {result['damage']} damage.")
                session.damage_dealt += result["damage"]
        else:
            session.add_log(f"🛡️ Your attack misses (rolled {result['attack_roll']} vs AC {dummy.ac}).")
        session.last_player_action = "attack"

        if not dummy.is_alive:
            await _end_training_via_msg(message.channel, session, "win")
            return

    elif is_defend:
        player.hp_temp = max(player.hp_temp, 5)
        session.add_log("🛡️ You brace for impact — gaining 5 temp HP!")
        session.last_player_action = "defend"

    elif is_item:
        healed = player.heal(roll(4) + 2)
        session.add_log(f"🧪 You drink a potion — healed **{healed} HP**!")
        session.last_player_action = "item"

    elif is_flee:
        session.last_player_action = "flee"
        if roll(20) + modifier(player.dexterity) >= 12:
            await _end_training_via_msg(message.channel, session, "fled")
            return
        else:
            session.add_log("💨 You try to flee but fail — the dummy presses its advantage!")

    else:
        session.add_log(f"📜 {message.content[:80]}")
        result = player_attack(player)
        if result["attack_roll"] >= dummy.ac and not result["is_miss"]:
            dummy.take_damage(result["damage"])
            session.damage_dealt += result["damage"]
            session.add_log(f"⚔️ Your action deals {result['damage']} damage.")
        session.last_player_action = "attack"

    # Dummy's turn
    dummy_state = {
        "hp_current": dummy.hp_current,
        "hp_max": dummy.hp_max,
        "ac": dummy.ac,
        "conditions": [c.get("name", "") for c in dummy.conditions],
    }
    player_state = {
        "hp_current": player.hp_current,
        "hp_max": player.hp_max,
        "name": player.name,
        "ac": player.armor_class,
        "conditions": [c.get("name", "") for c in (player.conditions or [])],
        "last_action": session.last_player_action,
    }

    deepseek_result = {}
    try:
        deepseek_result = await generate_dummy_action(
            session.difficulty, dummy_state, player_state, session.round
        )
        dummy_attack_desc = deepseek_result.get("flavor", "The training dummy lunges at you!")
    except Exception:
        dummy_attack_desc = "The training dummy swings at you!"

    dummy_roll = dummy.attack()
    if dummy_roll["attack_roll"] >= player.armor_class:
        player.take_damage(dummy_roll["damage"])
        session.damage_taken += dummy_roll["damage"]
        dummy_msg = f"{dummy_attack_desc} — **{dummy_roll['damage']} damage**!"
    else:
        dummy_msg = f"{dummy_attack_desc} — *It misses!*"

    # Conditions
    if deepseek_result.get("condition_apply"):
        apply_condition(player, deepseek_result["condition_apply"], 2)
        icon = CONDITIONS.get(deepseek_result["condition_apply"], {}).get("icon", "⚡")
        session.add_log(f"{icon} You're now **{deepseek_result['condition_apply']}**!")

    for line in tick_conditions(player):
        session.add_log(line)

    if player.hp_current <= 0:
        player.is_unconscious = True
        # Post dummy's final blow via webhook before ending
        await _dummy_send(session, message.channel, content=dummy_msg)
        await _end_training_via_msg(message.channel, session, "lose")
        return

    session.round += 1
    embed = session.arena_embed()

    try:
        await message.delete()
    except Exception:
        pass

    # Dummy speaks via webhook, then post the arena embed
    await _dummy_send(session, message.channel, content=dummy_msg)
    await message.channel.send(f"**Round {session.round}**", embed=embed)


async def _end_training_via_msg(channel: discord.TextChannel, session: TrainingSessionData, result: str):
    session.state = "over"
    active_training.pop(session.channel_id, None)

    embed = discord.Embed(title="🏁 Training Complete!", color=0x8B5CF6)
    if result == "win":
        config = DIFFICULTY_CONFIGS[session.difficulty]
        xp_reward = int(100 * config["xp_mult"])
        embed.description = f"🎉 **You defeated the {session.difficulty.title()} dummy!**"
        embed.add_field(name="Rounds", value=str(session.round), inline=True)
        embed.add_field(name="Damage Dealt", value=str(session.damage_dealt), inline=True)
        embed.add_field(name="Damage Taken", value=str(session.damage_taken), inline=True)
        embed.add_field(name="XP Earned", value=f"**{xp_reward}** ✨", inline=False)

        async with get_db() as db:
            db.add(TrainingSession(
                user_id=session.user_id,
                guild_id=session.guild_id,
                character_id=session.character_id,
                difficulty=session.difficulty,
                rounds_survived=session.round,
                damage_dealt=session.damage_dealt,
                damage_taken=session.damage_taken,
                result="win",
                end_time=datetime.datetime.utcnow(),
            ))
            char = await db.execute(select(Character).where(Character.id == session.character_id))
            char_obj = char.scalar_one_or_none()
            if char_obj:
                char_obj.xp = (char_obj.xp or 0) + xp_reward
                new_level = check_level_up(char_obj.xp, char_obj.level)
                if new_level:
                    char_obj.level = new_level
                    embed.add_field(name="🎉 Level Up!", value=f"Reached **Level {new_level}**!", inline=False)

    elif result == "lose":
        embed.description = "💀 **The training dummy defeats you.**"
        embed.add_field(name="Rounds", value=str(session.round), inline=True)
        embed.add_field(name="Damage Dealt", value=str(session.damage_dealt), inline=True)
        async with get_db() as db:
            db.add(TrainingSession(
                user_id=session.user_id,
                guild_id=session.guild_id,
                character_id=session.character_id,
                difficulty=session.difficulty,
                rounds_survived=session.round,
                damage_dealt=session.damage_dealt,
                damage_taken=session.damage_taken,
                result="lose",
                end_time=datetime.datetime.utcnow(),
            ))
    else:
        if session.mode == "rp" and session.round > 1:
            rp_xp = session.round * 5
            embed.description = f"📖 **RP Sparring ended** after {session.round} rounds.\n✨ **{rp_xp} XP** earned for the narrative session."
            async with get_db() as db:
                db.add(TrainingSession(
                    user_id=session.user_id,
                    guild_id=session.guild_id,
                    character_id=session.character_id,
                    difficulty=session.difficulty,
                    rounds_survived=session.round,
                    damage_dealt=0,
                    damage_taken=0,
                    result="rp_complete",
                    end_time=datetime.datetime.utcnow(),
                ))
                char = await db.execute(select(Character).where(Character.id == session.character_id))
                char_obj = char.scalar_one_or_none()
                if char_obj:
                    char_obj.xp = (char_obj.xp or 0) + rp_xp
        else:
            embed.description = f"🏳️ Training ended (Round {session.round})."
            async with get_db() as db:
                db.add(TrainingSession(
                    user_id=session.user_id,
                    guild_id=session.guild_id,
                    character_id=session.character_id,
                    difficulty=session.difficulty,
                    rounds_survived=session.round,
                    damage_dealt=session.damage_dealt,
                    damage_taken=session.damage_taken,
                    result=result,
                    end_time=datetime.datetime.utcnow(),
                ))

    await channel.send(embed=embed)
    await _cleanup_webhook(session)


async def _end_training(interaction: discord.Interaction, session: TrainingSessionData, result: str):
    session.state = "over"
    active_training.pop(session.channel_id, None)
    embed = discord.Embed(title="🏁 Training Ended", color=0xF59E0B)
    embed.add_field(name="Rounds", value=str(session.round), inline=True)
    embed.add_field(name="Damage Dealt/Taken", value=f"{session.damage_dealt}/{session.damage_taken}", inline=True)
    await interaction.followup.send(embed=embed, ephemeral=True)
    await _cleanup_webhook(session)


class TrainingCog(commands.Cog, name="Training"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(training_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("training")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.guild:
            return
        # Only process messages sent through the proxy system (LoreForge Proxy webhook).
        # Direct user messages are ignored — users must speak through their character proxy.
        if not message.author.bot or not message.webhook_id:
            return
        from cogs.proxy import _proxy_msg_authors
        original_user_id = _proxy_msg_authors.get(message.id)
        if original_user_id is None:
            return  # Not a tracked proxy message (e.g. training dummy webhook, other bots)
        await _handle_training_message(self.bot, message, original_user_id)


async def setup(bot):
    await bot.add_cog(TrainingCog(bot))
