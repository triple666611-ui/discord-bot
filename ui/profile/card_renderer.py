import io
from pathlib import Path

import aiohttp
from PIL import Image, ImageDraw, ImageFilter, ImageFont


WIDTH = 1400
HEIGHT = 500

BASE_DIR = Path(__file__).resolve().parents[2]
FONT_PATH = BASE_DIR / "assets" / "fonts" / "Inter-Bold.otf"
WINDOWS_FALLBACK_FONT = Path("C:/Windows/Fonts/arial.ttf")


def load_font(size: int):
    for path in (FONT_PATH, WINDOWS_FALLBACK_FONT):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


async def fetch_avatar(url: str):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            data = await resp.read()

    avatar = Image.open(io.BytesIO(data)).convert("RGBA")
    avatar = avatar.resize((200, 200))
    return avatar


def circle_crop(img):
    size = img.size[0]

    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0, size, size), fill=255)

    out = Image.new("RGBA", (size, size))
    out.paste(img, (0, 0), mask)
    return out


def normalize_theme(theme):
    if theme in {"color", "color_profile"}:
        return "color_profile"
    if theme in {"custom_bg", "custom"}:
        return "custom_bg"
    return None


def normalize_frame(frame):
    if frame in {"vip", "vip_frame"}:
        return "vip_frame"
    if frame in {"shadow", "shadow_frame"}:
        return "shadow"
    return None


async def render_profile_card(member, profile):
    username = member.display_name
    user_id = member.id

    level = profile["level"]
    rep = profile["rep"]
    balance = profile["balance"]
    xp = profile["xp"]
    xp_needed = profile["xp_needed"]

    theme = normalize_theme(profile.get("theme"))
    frame = normalize_frame(profile.get("frame"))

    avatar_url = member.display_avatar.url

    bg_color = (9, 12, 25)
    if theme == "color_profile":
        bg_color = (20, 18, 48)
    elif theme == "custom_bg":
        bg_color = (14, 32, 36)

    base = Image.new("RGBA", (WIDTH, HEIGHT), bg_color)
    draw = ImageDraw.Draw(base)

    gradient = Image.new("RGBA", (WIDTH, HEIGHT))
    gdraw = ImageDraw.Draw(gradient)

    for y in range(HEIGHT):
        if theme == "color_profile":
            r = 40 + int(y * 0.05)
            g = 18 + int(y * 0.03)
            b = 70 + int(y * 0.04)
        elif theme == "custom_bg":
            r = 6 + int(y * 0.01)
            g = 35 + int(y * 0.05)
            b = 40 + int(y * 0.03)
        else:
            r = 9
            g = 12 + int(y * 0.02)
            b = 25 + int(y * 0.05)

        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        gdraw.line((0, y, WIDTH, y), fill=(r, g, b))

    base = Image.alpha_composite(base, gradient)

    card = Image.new("RGBA", (WIDTH, HEIGHT))
    cdraw = ImageDraw.Draw(card)

    outline_color = (80, 100, 255, 80)
    ring_color = (70, 120, 255)
    card_fill = (15, 20, 40, 220)

    if frame == "vip_frame":
        outline_color = (255, 210, 90, 180)
        ring_color = (255, 210, 90)
    elif frame == "shadow":
        outline_color = (140, 110, 255, 180)
        ring_color = (140, 110, 255)

    if theme == "custom_bg":
        card_fill = (10, 24, 28, 220)
    elif theme == "color_profile":
        card_fill = (24, 20, 48, 220)

    cdraw.rounded_rectangle(
        (60, 80, WIDTH - 60, HEIGHT - 80),
        radius=30,
        fill=card_fill,
        outline=outline_color,
        width=3,
    )

    glow = card.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(glow)
    base.alpha_composite(card)

    avatar = await fetch_avatar(avatar_url)
    avatar = circle_crop(avatar)
    base.paste(avatar, (110, 150), avatar)

    ring = Image.new("RGBA", base.size)
    rdraw = ImageDraw.Draw(ring)
    rdraw.ellipse((100, 140, 320, 360), outline=ring_color, width=10)

    glow = ring.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(glow)
    base.alpha_composite(ring)

    name_font = load_font(50)
    small_font = load_font(24)
    stat_font = load_font(24)

    draw = ImageDraw.Draw(base)

    draw.text((380, 140), username, font=name_font, fill=(240, 245, 255))
    draw.text((380, 205), f"ID: {user_id}", font=small_font, fill=(140, 150, 200))

    def stat_box(x, label, value):
        box_fill = (20, 30, 60)
        box_outline = (120, 140, 255, 80)

        if theme == "color_profile":
            box_fill = (35, 28, 72)
            box_outline = (180, 120, 255, 120)
        elif theme == "custom_bg":
            box_fill = (16, 42, 46)
            box_outline = (90, 200, 180, 120)

        draw.rounded_rectangle(
            (x, 260, x + 260, 340),
            radius=16,
            fill=box_fill,
            outline=box_outline,
        )

        draw.text((x + 20, 272), label, font=small_font, fill=(160, 170, 220))
        draw.text((x + 20, 300), str(value), font=stat_font, fill=(255, 255, 255))

    stat_box(380, "LEVEL", level)
    stat_box(660, "REP", rep)
    stat_box(940, "BALANCE", f"{balance}")

    progress = xp / xp_needed if xp_needed > 0 else 0
    progress = max(0, min(1, progress))

    bar_x = 450
    bar_y = 390
    bar_w = 600
    bar_h = 24

    bar_bg = (10, 15, 30)
    bar_fill = (60, 180, 255)
    xp_text_color = (120, 180, 255)

    if theme == "color_profile":
        bar_bg = (24, 18, 40)
        bar_fill = (180, 90, 255)
        xp_text_color = (200, 140, 255)
    elif theme == "custom_bg":
        bar_bg = (8, 22, 24)
        bar_fill = (60, 220, 170)
        xp_text_color = (120, 230, 190)

    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=12,
        fill=bar_bg,
    )

    fill = int(bar_w * progress)
    if fill > 0:
        draw.rounded_rectangle(
            (bar_x, bar_y, bar_x + fill, bar_y + bar_h),
            radius=12,
            fill=bar_fill,
        )

    draw.text((bar_x - 60, bar_y - 4), "XP", font=small_font, fill=xp_text_color)
    draw.text(
        (bar_x + bar_w + 20, bar_y - 4),
        f"{xp}/{xp_needed} XP",
        font=small_font,
        fill=(230, 235, 255),
    )

    if frame == "vip_frame":
        badge_text = "VIP FRAME"
        badge_fill = (255, 210, 90)
        badge_text_fill = (30, 20, 0)

        badge_bbox = draw.textbbox((0, 0), badge_text, font=small_font)
        badge_w = badge_bbox[2] - badge_bbox[0]
        badge_h = badge_bbox[3] - badge_bbox[1]

        bx = WIDTH - 240
        by = 110
        draw.rounded_rectangle(
            (bx, by, bx + badge_w + 32, by + badge_h + 18),
            radius=16,
            fill=badge_fill,
        )
        draw.text((bx + 16, by + 8), badge_text, font=small_font, fill=badge_text_fill)

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer