import io
import aiohttp
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter


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


async def render_profile_card(member, profile):

    username = member.display_name
    user_id = member.id

    level = profile["level"]
    rep = profile["rep"]
    balance = profile["balance"]
    xp = profile["xp"]
    xp_needed = profile["xp_needed"]

    avatar_url = member.display_avatar.url

    base = Image.new("RGBA", (WIDTH, HEIGHT), (9, 12, 25))
    draw = ImageDraw.Draw(base)

    # gradient background
    gradient = Image.new("RGBA", (WIDTH, HEIGHT))
    gdraw = ImageDraw.Draw(gradient)

    for y in range(HEIGHT):
        r = 9
        g = 12 + int(y * 0.02)
        b = 25 + int(y * 0.05)
        gdraw.line((0, y, WIDTH, y), fill=(r, g, b))

    base = Image.alpha_composite(base, gradient)

    # main card
    card = Image.new("RGBA", (WIDTH, HEIGHT))
    cdraw = ImageDraw.Draw(card)

    cdraw.rounded_rectangle(
        (60, 80, WIDTH - 60, HEIGHT - 80),
        radius=30,
        fill=(15, 20, 40, 220),
        outline=(80, 100, 255, 80),
        width=2,
    )

    glow = card.filter(ImageFilter.GaussianBlur(12))
    base.alpha_composite(glow)
    base.alpha_composite(card)

    # avatar
    avatar = await fetch_avatar(avatar_url)
    avatar = circle_crop(avatar)

    base.paste(avatar, (110, 150), avatar)

    # avatar ring
    ring = Image.new("RGBA", base.size)
    rdraw = ImageDraw.Draw(ring)

    rdraw.ellipse((100, 140, 320, 360), outline=(70, 120, 255), width=10)

    glow = ring.filter(ImageFilter.GaussianBlur(10))
    base.alpha_composite(glow)
    base.alpha_composite(ring)

    # fonts
    name_font = load_font(50)
    small_font = load_font(24)
    stat_font = load_font(24)

    # username
    draw = ImageDraw.Draw(base)

    draw.text((380, 140), username, font=name_font, fill=(240, 245, 255))

    draw.text(
        (380, 205),
        f"ID: {user_id}",
        font=small_font,
        fill=(140, 150, 200),
    )

    # stat boxes
    def stat_box(x, label, value):

        draw.rounded_rectangle(
            (x, 260, x + 260, 340),
            radius=16,
            fill=(20, 30, 60),
            outline=(120, 140, 255, 80),
        )

        draw.text((x + 20, 272), label, font=small_font, fill=(160, 170, 220))

        draw.text((x + 20, 300), str(value), font=stat_font, fill=(255, 255, 255))

    stat_box(380, "LEVEL", level)
    stat_box(660, "REP", rep)
    stat_box(940, "BALANCE", f"{balance} ")

    # progress bar
    progress = xp / xp_needed if xp_needed > 0 else 0

    bar_x = 450
    bar_y = 390
    bar_w = 600
    bar_h = 24

    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h),
        radius=12,
        fill=(10, 15, 30),
    )

    fill = int(bar_w * progress)

    draw.rounded_rectangle(
        (bar_x, bar_y, bar_x + fill, bar_y + bar_h),
        radius=12,
        fill=(60, 180, 255),
    )

    draw.text(
        (bar_x - 60, bar_y - 4),
        "XP",
        font=small_font,
        fill=(120, 180, 255),
    )

    draw.text(
        (bar_x + bar_w + 20, bar_y - 4),
        f"{xp}/{xp_needed} XP",
        font=small_font,
        fill=(230, 235, 255),
    )

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)

    return buffer