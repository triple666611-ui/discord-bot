import json
import random
from io import BytesIO
from pathlib import Path

import aiohttp
import discord
from discord.ext.commands import Bot, Cog
from discord.ui import Select, View
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from config import Config
from utils.images import fetch_image_bytes, fit_cover, image_to_png_bytes, load_font, minimal_bg, rounded_rect


PANEL_STATE_FILE = Path("panel_messages.json")


def load_panel_state() -> dict:
    if not PANEL_STATE_FILE.exists():
        return {}

    try:
        return json.loads(PANEL_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_panel_state(data: dict) -> None:
    try:
        PANEL_STATE_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


async def build_minimal_welcome_banner(guild_name: str) -> bytes:
    w, h = 1400, 420
    bg_url = Config.WELCOME_PANEL_BG_URL or ""
    bg_bytes = await fetch_image_bytes(bg_url) if bg_url else None

    if bg_bytes:
        try:
            bg_img = Image.open(BytesIO(bg_bytes))
            bg = fit_cover(bg_img, w, h).filter(ImageFilter.GaussianBlur(8))
            bg = Image.alpha_composite(bg, Image.new("RGBA", (w, h), (0, 0, 0, 120)))
        except Exception:
            bg = minimal_bg(w, h)
    else:
        bg = minimal_bg(w, h)

    blobs = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    bd = ImageDraw.Draw(blobs)
    for _ in range(3):
        cx = random.randint(0, w)
        cy = random.randint(0, h)
        rr = random.randint(260, 420)
        bd.ellipse(
            (cx - rr, cy - rr, cx + rr, cy + rr),
            fill=random.choice([(88, 101, 242, 55), (60, 200, 255, 35)])
        )
    blobs = blobs.filter(ImageFilter.GaussianBlur(90))
    bg = Image.alpha_composite(bg.convert("RGBA"), blobs)
    draw = ImageDraw.Draw(bg)

    card_x1, card_y1 = 90, 85
    card_x2, card_y2 = w - 90, h - 85

    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    rounded_rect(
        sd,
        (card_x1 + 8, card_y1 + 10, card_x2 + 8, card_y2 + 10),
        32,
        fill=(0, 0, 0, 160)
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    bg = Image.alpha_composite(bg, shadow)

    glass = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glass)
    rounded_rect(
        gd,
        (card_x1, card_y1, card_x2, card_y2),
        32,
        fill=(20, 22, 28, 165),
        outline=(255, 255, 255, 35),
        width=2
    )
    bg = Image.alpha_composite(bg, glass)
    draw = ImageDraw.Draw(bg)

    rounded_rect(
        draw,
        (card_x1 + 22, card_y1 + 22, card_x1 + 28, card_y2 - 22),
        6,
        fill=(88, 101, 242, 255)
    )

    title_font = load_font(66, bold=True)
    sub_font = load_font(34, bold=True)
    text_font = load_font(26, bold=False)

    safe_guild = guild_name.strip()[:26]
    if len(guild_name.strip()) > 26:
        safe_guild = safe_guild[:25] + "…"

    draw.text((card_x1 + 60, card_y1 + 55), "WELCOME", font=title_font, fill=(245, 246, 250, 245))
    draw.text((card_x1 + 60, card_y1 + 145), safe_guild, font=sub_font, fill=(230, 232, 240, 235))
    draw.text(
        (card_x1 + 60, card_y1 + 200),
        "Выбери роли и обязательно ознакомься с правилами сервера.",
        font=text_font,
        fill=(200, 202, 212, 225)
    )

    return image_to_png_bytes(bg)


