import discord

TEMPLATES = {
    "character": {
        "fields": ["age", "occupation", "birthplace", "faction", "personality", "appearance", "backstory"],
        "color": 0x3B82F6,
        "icon": "👤",
    },
    "item": {
        "fields": ["item_type", "material", "weight", "rarity", "enchantments", "value", "lore_text"],
        "color": 0xF59E0B,
        "icon": "⚔️",
    },
    "creature": {
        "fields": ["habitat", "diet", "behavior", "danger_level", "loot", "stats_block"],
        "color": 0xEF4444,
        "icon": "🐉",
    },
    "religion": {
        "fields": ["deity_name", "domains", "holy_symbol", "tenets", "clergy_structure", "sacred_sites"],
        "color": 0x8B5CF6,
        "icon": "⛪",
    },
    "event": {
        "fields": ["date", "location", "participants", "outcome", "significance"],
        "color": 0x06B6D4,
        "icon": "📅",
    },
    "organization": {
        "fields": ["org_type", "leader", "headquarters", "members", "goals", "secrets"],
        "color": 0x10B981,
        "icon": "🏛️",
    },
    "magic": {
        "fields": ["school", "components", "effects", "limitations", "known_users"],
        "color": 0x7C3AED,
        "icon": "✨",
    },
}


def render_template_embed(
    title: str,
    template_name: str,
    field_data: dict,
    author_name: str = None,
) -> discord.Embed:
    """Render a lore entry using a structured template."""
    template = TEMPLATES.get(template_name, {})
    embed = discord.Embed(
        title=f"{template.get('icon', '📚')} {title}",
        color=template.get("color", 0x6B7280),
    )
    for field in template.get("fields", []):
        value = field_data.get(field, "*Not specified*")
        if value and value.strip():
            embed.add_field(
                name=field.replace("_", " ").title(),
                value=value[:512],
                inline=False,
            )
    if author_name:
        embed.set_footer(text=f"Template: {template_name} · Author: {author_name}")
    return embed
