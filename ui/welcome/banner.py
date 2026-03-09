import random
from io import BytesIO

from PIL import Image, ImageDraw, ImageFilter

from config import Config
from ui.common.canvas import (
    add_blurred_shadow,
    clamp_text,
    create_rgba_canvas,
    make_vertical_gradient,
    rounded_box,
)
from ui.common.fonts import get_font_pack, load_font
from ui.common.style import (
    ACCENT,
    ACCENT_SOFT,
    BG_BOTTOM,
    BG_TOP,
    CARD_FILL,
    CARD_OUTLINE,
    CARD_SHADOW,
    TEXT,
    TEXT_MUTED,
    TEXT_SOFT,
)
from utils.images import fetch_image_bytes, fit_cover, image_to_png_bytes, minimal_bg


WIDTH = 1400
HEIGHT = 420


async def _build_background(width: int, height: int) -> Image.Image:
    bg_url = Config.WELCOME_PANEL_BG_URL or ""
    bg_bytes = await fetch_image_bytes(bg_url) if bg_url else None

    if bg_bytes:
        try:
            bg_img = Image.open(BytesIO(bg_bytes)).convert("RGBA")
            bg = fit_cover(bg_img, width, height).filter(ImageFilter.GaussianBlur(8))
            overlay = Image.new("RGBA", (width, height), (0, 0, 0, 120))
            bg = Image.alpha_composite(bg, overlay)
        except Exception:
            bg = minimal_bg(width, height)
    else:
        bg = make_vertical_gradient(width, height, BG_TOP, BG_BOTTOM)

    if bg.mode != "RGBA":
        bg = bg.convert("RGBA")

    blobs, bdraw = create_rgba_canvas(width, height, (0, 0, 0, 0))
    for _ in range(3):
        cx = random.randint(0, width)
        cy = random.randint(0, height)
        rr = random.randint(260, 420)
        bdraw.ellipse(
            (cx - rr, cy - rr, cx + rr, cy + rr),
            fill=random.choice([ACCENT_SOFT, (88, 101, 242, 55)]),
        )

    blobs = blobs.filter(ImageFilter.GaussianBlur(90))
    return Image.alpha_composite(bg, blobs)


async def build_minimal_welcome_banner(guild_name: str) -> bytes:
    base = await _build_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(base)

    fonts = get_font_pack()
    title_font = load_font(fonts["hero"])
    subtitle_font = load_font(fonts["subtitle"])
    body_font = load_font(fonts["body"])
    small_font = load_font(fonts["small"])

    card_x1, card_y1 = 90, 85
    card_x2, card_y2 = WIDTH - 90, HEIGHT - 85

    base = add_blurred_shadow(
        base,
        (card_x1, card_y1, card_x2, card_y2),
        radius=32,
        fill=CARD_SHADOW,
        blur=18,
        offset=(8, 10),
    )

    glass = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glass)
    rounded_box(
        gdraw,
        (card_x1, card_y1, card_x2, card_y2),
        radius=32,
        fill=CARD_FILL,
        outline=CARD_OUTLINE,
        width=2,
    )
    base = Image.alpha_composite(base, glass)
    draw = ImageDraw.Draw(base)

    rounded_box(
        draw,
        (card_x1 + 22, card_y1 + 22, card_x1 + 28, card_y2 - 22),
        radius=6,
        fill=ACCENT,
    )

    safe_guild = clamp_text(guild_name, 26)

    draw.text(
        (card_x1 + 60, card_y1 + 42),
        "WELCOME",
        font=title_font,
        fill=TEXT,
    )

    draw.text(
        (card_x1 + 60, card_y1 + 145),
        safe_guild,
        font=subtitle_font,
        fill=TEXT_SOFT,
    )

    draw.text(
        (card_x1 + 60, card_y2 - 52),
        "Роли можно изменить в любой момент через панель ниже.",
        font=small_font,
        fill=TEXT_SOFT,
    )

    return image_to_png_bytes(base)