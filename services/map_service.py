import io
import base64
import random
import math
import urllib.request
import urllib.parse

try:
    from PIL import Image, ImageDraw, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

_MAP_CACHE: dict[int, bytes] = {}  # guild_id → cached base map bytes


def fetch_world_map(world_name: str, guild_id: int, force: bool = False) -> bytes | None:
    """Fetch a fantasy world map image from Pollinations.AI and cache it per guild."""
    if not force and guild_id in _MAP_CACHE:
        return _MAP_CACHE[guild_id]
    prompt = (
        f"fantasy world map, top-down view, parchment style, hand-drawn, "
        f"continents with kingdoms and territories labeled, mountains forests rivers, "
        f"compass rose, aged paper texture, {world_name}, no text overlays, clean"
    )
    url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1200&height=800&nologo=true&seed={guild_id}"
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            data = r.read()
        _MAP_CACHE[guild_id] = data
        return data
    except Exception:
        return None


async def fetch_world_map_async(
    world_name: str, guild_id: int, db,
    force: bool = False,
) -> bytes | None:
    """Async version — checks GuildMapCache first, fetches from Pollinations if needed,
    caches to DB so the map survives bot restarts."""
    from database.models import GuildMapCache
    from sqlalchemy import select

    if not force:
        result = await db.execute(
            select(GuildMapCache).where(GuildMapCache.guild_id == guild_id)
        )
        cached = result.scalar_one_or_none()
        if cached and cached.map_bytes_b64:
            try:
                return base64.b64decode(cached.map_bytes_b64)
            except Exception:
                pass

    # Fetch from Pollinations (in executor since it's sync I/O)
    import asyncio
    data = await asyncio.get_running_loop().run_in_executor(
        None, lambda: fetch_world_map(world_name, guild_id, force=force)
    )
    if data:
        # Save to DB cache
        result = await db.execute(
            select(GuildMapCache).where(GuildMapCache.guild_id == guild_id)
        )
        cached = result.scalar_one_or_none()
        if not cached:
            cached = GuildMapCache(guild_id=guild_id)
            db.add(cached)
        prompt = (
            f"fantasy world map, top-down view, parchment style, hand-drawn, "
            f"continents with kingdoms and territories labeled, mountains forests rivers, "
            f"compass rose, aged paper texture, {world_name}, no text overlays, clean"
        )
        cached.map_url = f"https://image.pollinations.ai/prompt/{urllib.parse.quote(prompt)}?width=1200&height=800&nologo=true&seed={guild_id}"
        cached.map_bytes_b64 = base64.b64encode(data).decode("ascii")
    return data


def generate_world_map_overlay(
    base_image_bytes: bytes | None,
    locations: list[dict],
    player_location_id: int | None = None,
    show_hidden: bool = False,
    annotations: list[dict] | None = None,
) -> io.BytesIO:
    """
    Draw location markers on a base map image.
    Optionally draw annotations (road_block, danger_zone, icon, label).
    Returns BytesIO PNG.
    """
    if not HAS_PIL:
        return _fallback_map_bytes()

    try:
        if base_image_bytes:
            base = Image.open(io.BytesIO(base_image_bytes)).convert("RGBA")
        else:
            base = Image.new("RGBA", (800, 600), (53, 40, 30, 255))
    except Exception:
        base = Image.new("RGBA", (800, 600), (53, 40, 30, 255))

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    width, height = base.size

    # Draw location markers
    for loc in locations:
        if loc.get("is_hidden") and not show_hidden:
            continue

        lx = int(((loc.get("map_x") or 50) / 100) * width)
        ly = int(((loc.get("map_y") or 50) / 100) * height)

        loc_type = loc.get("location_type", "wilderness")
        is_player = loc.get("id") == player_location_id

        if is_player:
            # Player position: star
            _draw_star(draw, lx, ly, 12, (255, 215, 0, 255))
        elif loc_type == "city":
            draw.ellipse([lx - 6, ly - 6, lx + 6, ly + 6], fill=(255, 255, 255, 220))
        elif loc_type == "dungeon":
            _draw_skull(draw, lx, ly, 8, (255, 50, 50, 220))
        elif loc_type == "tavern":
            draw.ellipse([lx - 5, ly - 5, lx + 5, ly + 5], fill=(59, 130, 246, 200))
        else:
            draw.point((lx, ly), fill=(100, 100, 100, 180))

        # Label
        name = loc.get("name", "?")
        try:
            font = ImageFont.load_default()
            draw.text((lx + 10, ly - 5), name, fill=(255, 255, 200, 255), font=font)
        except Exception:
            pass

    # ── Draw overlay annotations ──────────────────────────────────────
    if annotations:
        for ann in annotations:
            ax = int((ann.get("x", 50) / 100) * width)
            ay = int((ann.get("y", 50) / 100) * height)
            ann_type = ann.get("annotation_type", "icon")
            ann_color_str = ann.get("color", "#EF4444")
            # Parse hex color to RGBA
            try:
                h = ann_color_str.lstrip("#")
                ar, ag, ab = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
            except Exception:
                ar, ag, ab = 239, 68, 68

            if ann_type == "road_block":
                # Red X shape
                arm_len = 14
                draw.line([(ax - arm_len, ay - arm_len), (ax + arm_len, ay + arm_len)], fill=(ar, ag, ab, 220), width=5)
                draw.line([(ax + arm_len, ay - arm_len), (ax - arm_len, ay + arm_len)], fill=(ar, ag, ab, 220), width=5)
            elif ann_type == "danger_zone":
                # Semi-transparent red circle radius 20px
                draw.ellipse([ax - 20, ay - 20, ax + 20, ay + 20], fill=(ar, ag, ab, 80), outline=(ar, ag, ab, 200), width=3)
                # Exclamation mark
                draw.text((ax - 3, ay - 8), "!", fill=(255, 255, 255, 220))
            elif ann_type == "icon":
                # Colored filled circle 8px
                draw.ellipse([ax - 8, ay - 8, ax + 8, ay + 8], fill=(ar, ag, ab, 220))
            elif ann_type == "label":
                # Text only
                label_text = ann.get("label", "")
                if label_text:
                    try:
                        font = ImageFont.load_default()
                        draw.text((ax + 6, ay - 5), label_text, fill=(ar, ag, ab, 255), font=font)
                    except Exception:
                        pass

    result = Image.alpha_composite(base, overlay)
    buf = io.BytesIO()
    result.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _draw_star(draw, cx, cy, size, color):
    points = []
    for i in range(10):
        angle = math.radians(i * 36 - 90)
        r = size if i % 2 == 0 else size // 2
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, fill=color)


def _draw_skull(draw, cx, cy, size, color):
    draw.ellipse([cx - size, cy - size, cx + size, cy + size], fill=color)
    draw.ellipse([cx - size // 3, cy - size // 3, cx + size // 3, cy + size // 3], fill=(0, 0, 0, 128))


def _fallback_map_bytes() -> io.BytesIO:
    """Return a simple colored square if PIL isn't available."""
    buf = io.BytesIO()
    buf.write(b"")
    buf.seek(0)
    return buf


def generate_dungeon_map(seed: int = 0, room_count: int = 8) -> io.BytesIO:
    """Generate a BSP dungeon map. Returns BytesIO PNG."""
    if not HAS_PIL:
        return _fallback_map_bytes()

    if seed:
        random.seed(seed)

    tile_size = 16
    grid_w, grid_h = 40, 40
    img_w, img_h = grid_w * tile_size, grid_h * tile_size

    img = Image.new("RGB", (img_w, img_h), (26, 26, 26))
    draw = ImageDraw.Draw(img)

    # BSP: split space
    rooms = []
    _bsp_split(0, 0, grid_w - 1, grid_h - 1, room_count, rooms)

    # Draw rooms
    for room in rooms:
        x1, y1, x2, y2 = room["x1"], room["y1"], room["x2"], room["y2"]
        draw.rectangle(
            [x1 * tile_size, y1 * tile_size, x2 * tile_size, y2 * tile_size],
            fill=(42, 42, 42),
        )
        draw.rectangle(
            [x1 * tile_size, y1 * tile_size, x2 * tile_size, y1 * tile_size + 2],
            fill=(26, 26, 26),
        )
        draw.rectangle(
            [x1 * tile_size, y1 * tile_size, x1 * tile_size + 2, y2 * tile_size],
            fill=(26, 26, 26),
        )
        draw.rectangle(
            [x2 * tile_size, y1 * tile_size, x2 * tile_size + 2, y2 * tile_size],
            fill=(26, 26, 26),
        )
        draw.rectangle(
            [x1 * tile_size, y2 * tile_size, x2 * tile_size + 2, y2 * tile_size + 2],
            fill=(26, 26, 26),
        )

    # Connect rooms with corridors
    for i in range(1, len(rooms)):
        prev = rooms[i - 1]
        curr = rooms[i]
        cx1 = (prev["x1"] + prev["x2"]) // 2
        cy1 = (prev["y1"] + prev["y2"]) // 2
        cx2 = (curr["x1"] + curr["x2"]) // 2
        cy2 = (curr["y1"] + curr["y2"]) // 2
        draw.line(
            [cx1 * tile_size, cy1 * tile_size, cx2 * tile_size, cy2 * tile_size],
            fill=(60, 60, 60),
            width=4,
        )

    ROOM_LABELS = ["Entrance", "Guard Post", "Storage", "Trap Room", "Treasure", "Boss Room", "Shrine", "Prison"]
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for i, room in enumerate(rooms[:len(ROOM_LABELS)]):
        label = ROOM_LABELS[i]
        cx = ((room["x1"] + room["x2"]) // 2) * tile_size
        cy = ((room["y1"] + room["y2"]) // 2) * tile_size
        if font:
            draw.text((cx - 20, cy - 4), label, fill=(200, 200, 200), font=font)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _bsp_split(x1, y1, x2, y2, target_rooms, rooms):
    """BSP recursion to split space into rooms."""
    w = x2 - x1
    h = y2 - y1

    if len(rooms) >= target_rooms or (w < 6 and h < 6):
        rooms.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2})
        return

    if w > h:
        split = random.randint(w // 3, 2 * w // 3)
        _bsp_split(x1, y1, x1 + split, y2, target_rooms, rooms)
        _bsp_split(x1 + split, y1, x2, y2, target_rooms, rooms)
    else:
        split = random.randint(h // 3, 2 * h // 3)
        _bsp_split(x1, y1, x2, y1 + split, target_rooms, rooms)
        _bsp_split(x1, y1 + split, x2, y2, target_rooms, rooms)


def generate_city_map_prompt(location_name: str, location_description: str) -> str:
    """Generate a Pollinations.AI prompt for a city map."""
    return (
        f"Medieval fantasy city map, top-down view, hand-drawn parchment style, "
        f"labeled districts, city walls with gates, main road, river, docks, compass rose, "
        f"fantasy {location_name}, {location_description[:100]}"
    )
