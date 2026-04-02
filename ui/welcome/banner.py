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
from utils.images import fetch_image_bytes, fit_cover, image_to_png_bytes, minimal_bg


WIDTH = 1400
HEIGHT = 420
BG_TOP = (10, 18, 20, 255)
BG_BOTTOM = (14, 52, 51, 255)
ACCENT = (82, 218, 180, 255)
ACCENT_SOFT = (82, 218, 180, 45)
CARD_FILL = (10, 22, 24, 220)
CARD_OUTLINE = (82, 218, 180, 95)
CARD_SHADOW = (0, 0, 0, 165)
TEXT = (238, 255, 250, 245)
TEXT_SOFT = (173, 240, 223, 235)
TEXT_MUTED = (122, 188, 175, 220)
GLOW_ALT = (120, 255, 220, 35)
BODY_TEXT = "Выберите роли ниже и начните знакомство с сервером."
FOOTER_TEXT = "Роли можно изменить в любой момент через панель ниже."


async def _build_background(width: int, height: int) -> Image.Image:
    bg_url = Config.WELCOME_PANEL_BG_URL or ""
    bg_bytes = await fetch_image_bytes(bg_url) if bg_url else None

    if bg_bytes:
        try:
            bg_img = Image.open(BytesIO(bg_bytes)).convert("RGBA")
            bg = fit_cover(bg_img, width, height).filter(ImageFilter.GaussianBlur(8))
            overlay = Image.new("RGBA", (width, height), (5, 14, 16, 170))
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
        rr = random.randint(250, 410)
        bdraw.ellipse(
            (cx - rr, cy - rr, cx + rr, cy + rr),
            fill=random.choice([ACCENT_SOFT, GLOW_ALT]),
        )

    blobs = blobs.filter(ImageFilter.GaussianBlur(90))
    return Image.alpha_composite(bg, blobs)


def text_height(draw: ImageDraw.ImageDraw, text: str, font) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def draw_multiline(draw: ImageDraw.ImageDraw, x: int, y: int, lines: list[str], font, fill, line_gap: int) -> int:
    cursor_y = y
    for line in lines:
        draw.text((x, cursor_y), line, font=font, fill=fill)
        cursor_y += text_height(draw, line, font) + line_gap
    return cursor_y - line_gap if lines else y


async def build_minimal_welcome_banner(guild_name: str) -> bytes:
    base = await _build_background(WIDTH, HEIGHT)
    draw = ImageDraw.Draw(base)

    fonts = get_font_pack()
    title_font = load_font(64)
    subtitle_font = load_font(fonts["subtitle"])
    body_font = load_font(24)
    small_font = load_font(20)

    card_x1, card_y1 = 90, 85
    card_x2, card_y2 = WIDTH - 90, HEIGHT - 85
    inner_pad_x = 58
    inner_pad_y = 32
    accent_width = 8
    accent_gap = 28
    accent_x1 = card_x1 + inner_pad_x - accent_gap - accent_width
    accent_x2 = accent_x1 + accent_width
    accent_y1 = card_y1 + inner_pad_y
    accent_y2 = card_y2 - inner_pad_y
    content_x = card_x1 + inner_pad_x
    content_w = card_x2 - content_x - 70

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
        (accent_x1, accent_y1, accent_x2, accent_y2),
        radius=6,
        fill=ACCENT,
    )

    safe_guild = clamp_text(guild_name, 26)
    body_lines = wrap_text(draw, BODY_TEXT, body_font, content_w)
    footer_lines = wrap_text(draw, FOOTER_TEXT, small_font, content_w)

    y = card_y1 + 34
    draw.text((content_x, y), "WELCOME", font=title_font, fill=TEXT)
    y += text_height(draw, "WELCOME", title_font) + 28

    draw.text((content_x, y), safe_guild, font=subtitle_font, fill=TEXT_SOFT)
    y += text_height(draw, safe_guild, subtitle_font) + 22

    y = draw_multiline(draw, content_x, y, body_lines, body_font, TEXT, 8)
    y += 16
    draw_multiline(draw, content_x, y, footer_lines, small_font, TEXT_MUTED, 6)

    return image_to_png_bytes(base)
