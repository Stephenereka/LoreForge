import discord
import random
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from database.session import get_db
from database.models import Language, Character, GuildGM
from services.utils import is_gm


language_group = app_commands.Group(
    name="language", description="Language system"
)


async def _autocomplete_languages(
    interaction: discord.Interaction, current: str
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        return []
    async with get_db() as db:
        result = await db.execute(
            select(Language).where(
                Language.guild_id == interaction.guild_id,
                Language.name.ilike(f"%{current}%"),
            )
        )
        langs = result.scalars().all()
    return [app_commands.Choice(name=l.name[:80], value=l.name) for l in langs[:25]]


def _scramble_text(text: str) -> str:
    """Generate a cryptic-looking scrambled version of text."""
    char_map = {
        "a": "ᚨ", "b": "ᛒ", "c": "ᚲ", "d": "ᛞ", "e": "ᛖ", "f": "ᚠ", "g": "ᚷ",
        "h": "ᚺ", "i": "ᛁ", "j": "ᛃ", "k": "ᚴ", "l": "ᛚ", "m": "ᛗ", "n": "ᚾ",
        "o": "ᛟ", "p": "ᛈ", "q": "ᛩ", "r": "ᚱ", "s": "ᛋ", "t": "ᛏ", "u": "ᚢ",
        "v": "ᚡ", "w": "ᚹ", "x": "ᛪ", "y": "ᚤ", "z": "ᛉ",
    }
    result = []
    for ch in text.lower():
        if ch in char_map:
            result.append(char_map[ch])
        elif ch == " ":
            result.append("᛫")
        elif ch in ".,!?":
            result.append("⸬")
        else:
            result.append(ch)
    return "".join(result)


@language_group.command(name="create", description="GM only: Create a new language")
@app_commands.describe(name="Language name", script_type="Script type (e.g. runic, elvish)")
async def language_create(interaction: discord.Interaction, name: str, script_type: str = None):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can create languages.", ephemeral=True)
        return
    async with get_db() as db:
        existing = await db.execute(
            select(Language).where(
                Language.guild_id == interaction.guild_id,
                Language.name.ilike(name),
            )
        )
        if existing.scalar_one_or_none():
            await interaction.followup.send(f"Language '{name}' already exists.", ephemeral=True)
            return
        lang = Language(
            guild_id=interaction.guild_id,
            name=name,
            script_type=script_type,
        )
        db.add(lang)
        await db.commit()
    await interaction.followup.send(f"📜 Created language: **{name}**" + (f" (Script: {script_type})" if script_type else ""), ephemeral=True)


@language_group.command(name="learn", description="Learn a language (costs 500 Spirit Stones)")
@app_commands.describe(name="Language to learn")
async def language_learn(interaction: discord.Interaction, name: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    async with get_db() as db:
        # Check character
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need a character first!", ephemeral=True)
            return

        # Check language exists
        lang_result = await db.execute(
            select(Language).where(
                Language.guild_id == interaction.guild_id,
                Language.name.ilike(name),
            )
        )
        lang = lang_result.scalar_one_or_none()
        if not lang:
            await interaction.followup.send(f"Language '{name}' doesn't exist in this world.", ephemeral=True)
            return

        # Check if already known
        if lang.name in char.languages:
            await interaction.followup.send(f"You already know **{lang.name}**!", ephemeral=True)
            return

        # Check cost
        cost = 500
        if char.balance < cost:
            await interaction.followup.send(f"Learning a language costs **{cost} Spirit Stones**. You only have **{char.balance}**.", ephemeral=True)
            return

        char.balance -= cost
        char.languages = char.languages + [lang.name]
        flag_modified(char, "languages")
        await db.commit()

    await interaction.followup.send(f"📚 You learned **{lang.name}**! **{cost} Spirit Stones** deducted.", ephemeral=True)


@language_group.command(name="list", description="List languages in this world")
async def language_list(interaction: discord.Interaction):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer()
    async with get_db() as db:
        result = await db.execute(
            select(Language).where(Language.guild_id == interaction.guild_id).order_by(Language.name)
        )
        langs = list(result.scalars().all())

        # Get all characters to show who speaks what
        chars_result = await db.execute(
            select(Character).where(Character.guild_id == interaction.guild_id).order_by(Character.name)
        )
        chars = list(chars_result.scalars().all())

    if not langs:
        await interaction.followup.send("No languages have been created in this world yet.")
        return

    embed = discord.Embed(title="📜 Languages of the World", color=0x6366F1)
    for lang in langs:
        speakers = [c.name for c in chars if lang.name in c.languages]
        speaker_text = ", ".join(speakers[:10]) if speakers else "*None*"
        if len(speakers) > 10:
            speaker_text += f" *+{len(speakers) - 10} more*"
        embed.add_field(
            name=lang.name + (f" ({lang.script_type})" if lang.script_type else ""),
            value=f"Speakers: {speaker_text}",
            inline=False,
        )
    await interaction.followup.send(embed=embed)


@language_group.command(name="speak", description="Speak in a language")
@app_commands.describe(language_name="Language name", message="What you say")
async def language_speak(interaction: discord.Interaction, language_name: str, message: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=False)
    async with get_db() as db:
        # Check character
        char_result = await db.execute(
            select(Character).where(
                Character.user_id == interaction.user.id,
                Character.guild_id == interaction.guild_id,
            )
        )
        char = char_result.scalar_one_or_none()
        if not char:
            await interaction.followup.send("You need a character first!", ephemeral=True)
            return

        # Check language exists
        lang_result = await db.execute(
            select(Language).where(
                Language.guild_id == interaction.guild_id,
                Language.name.ilike(language_name),
            )
        )
        lang = lang_result.scalar_one_or_none()
        if not lang:
            await interaction.followup.send(f"Language '{language_name}' doesn't exist.", ephemeral=True)
            return

    # Check if character knows the language
    knows_lang = lang.name in char.languages

    if knows_lang:
        # Translate common phrases if available
        translated_parts = []
        for word in message.split():
            if lang.common_phrases and word.lower() in lang.common_phrases:
                translated_parts.append(lang.common_phrases[word.lower()])
            else:
                translated_parts.append(word)
        output = " ".join(translated_parts)
        embed = discord.Embed(
            title=f"[Speaking in {lang.name}]",
            description=output,
            color=0x6366F1,
        )
        embed.set_footer(text=f"{char.name} — You understand this language")
    else:
        scrambled = _scramble_text(message)
        embed = discord.Embed(
            title="🗣️ ...",
            description=scrambled,
            color=0x6B7280,
        )
        embed.set_footer(text=f"You hear {char.name} speak in a tongue you don't understand.")

    await interaction.followup.send(embed=embed)


@language_group.command(name="add-phrase", description="GM only: Add a phrase to a language's vocabulary")
@app_commands.describe(language_name="Language name", common_word="Word in common tongue", translation="Translation in this language")
async def language_add_phrase(interaction: discord.Interaction, language_name: str, common_word: str, translation: str):
    if not interaction.guild_id:
        await interaction.response.send_message("LoreForge only works in a server.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    if not await is_gm(interaction):
        await interaction.followup.send("Only GMs can add phrases.", ephemeral=True)
        return
    async with get_db() as db:
        result = await db.execute(
            select(Language).where(
                Language.guild_id == interaction.guild_id,
                Language.name.ilike(language_name),
            )
        )
        lang = result.scalar_one_or_none()
        if not lang:
            await interaction.followup.send(f"Language '{language_name}' not found.", ephemeral=True)
            return
        phrases = dict(lang.common_phrases or {})
        phrases[common_word.lower()] = translation
        lang.common_phrases = phrases
        flag_modified(lang, "common_phrases")
        await db.commit()
    await interaction.followup.send(f"📖 Added **{common_word}** → **{translation}** to **{lang.name}**.", ephemeral=True)


class LanguageCog(commands.Cog, name="Language"):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.add_command(language_group)

    async def cog_unload(self):
        self.bot.tree.remove_command("language")


async def setup(bot):
    await bot.add_cog(LanguageCog(bot))
