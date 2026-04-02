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
    return avatar.resize((180, 180))


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


def mix_color(start, end, factor: float):
    factor = max(0.0, min(1.0, factor))
    return tuple(int(start[i] * (1 - factor) + end[i] * factor) for i in range(3))


def draw_vertical_gradient(base, top_color, bottom_color):
    gradient = Image.new("RGBA", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(gradient)
    for y in range(HEIGHT):
        mix = y / max(HEIGHT - 1, 1)
        color = mix_color(top_color, bottom_color, mix)
        draw.line((0, y, WIDTH, y), fill=(*color, 255))
    base.alpha_composite(gradient)


def draw_glow(base, box, color, blur_radius: int, alpha: int):
    glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    draw.ellipse(box, fill=(*color, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(blur_radius))
    base.alpha_composite(glow)


def rounded_panel(draw, box, radius: int, fill, outline=None, width: int = 1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def format_theme_name(theme):
    mapping = {
        None: "Standard",
        "color_profile": "Neon",
        "custom_bg": "Emerald",
    }
    return mapping.get(theme, str(theme))


def format_frame_name(frame):
    mapping = {
        None: "Standard",
        "vip_frame": "VIP",
        "shadow": "Shadow",
    }
    return mapping.get(frame, str(frame))


def format_staff_badge(staff_badge):
    mapping = {
        None: None,
        "admin": "admin",
        "moder": "moder",
    }
    return mapping.get(staff_badge, str(staff_badge))


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
    staff_badge = format_staff_badge(profile.get("staff_badge"))
    avatar_url = member.display_avatar.url

    theme_palette = {
        None: {
            "bg_top": (10, 18, 20),
            "bg_bottom": (14, 52, 51),
            "accent": (82, 220, 180),
            "panel": (10, 22, 24, 220),
            "panel_fill": (20, 50, 48, 255),
            "panel_stroke": (82, 220, 180, 90),
            "primary_text": (238, 255, 250),
            "secondary_text": (145, 212, 195),
            "muted_text": (116, 170, 158),
            "progress_bg": (19, 46, 45, 255),
            "progress_fill": (82, 220, 180, 255),
        },
        "color_profile": {
            "bg_top": (14, 14, 36),
            "bg_bottom": (53, 28, 92),
            "accent": (168, 113, 255),
            "panel": (19, 12, 42, 220),
            "panel_fill": (40, 24, 72, 255),
            "panel_stroke": (180, 130, 255, 100),
            "primary_text": (248, 243, 255),
            "secondary_text": (207, 173, 255),
            "muted_text": (170, 145, 205),
            "progress_bg": (37, 20, 66, 255),
            "progress_fill": (186, 108, 255, 255),
        },
        "custom_bg": {
            "bg_top": (7, 28, 31),
            "bg_bottom": (12, 69, 64),
            "accent": (107, 227, 197),
            "panel": (8, 23, 24, 220),
            "panel_fill": (19, 54, 50, 255),
            "panel_stroke": (107, 227, 197, 100),
            "primary_text": (238, 255, 250),
            "secondary_text": (173, 240, 223),
            "muted_text": (122, 188, 175),
            "progress_bg": (15, 41, 40, 255),
            "progress_fill": (107, 227, 197, 255),
        },
    }
    palette = theme_palette[theme]

    if frame == "vip_frame":
        palette = {
            **palette,
            "accent": (246, 201, 117),
            "panel_stroke": (246, 201, 117, 120),
            "progress_fill": (246, 201, 117, 255),
        }
    elif frame == "shadow":
        palette = {
            **palette,
            "accent": (140, 110, 255),
            "panel_stroke": (140, 110, 255, 110),
            "progress_fill": (140, 110, 255, 255),
        }

    if staff_badge == "admin":
        palette = {
            **palette,
            "accent": (255, 99, 132),
            "panel_stroke": (255, 99, 132, 130),
            "progress_fill": (255, 99, 132, 255),
        }
    elif staff_badge == "moder":
        palette = {
            **palette,
            "accent": (74, 163, 255),
            "panel_stroke": (74, 163, 255, 130),
            "progress_fill": (74, 163, 255, 255),
        }

    base = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw_vertical_gradient(base, palette["bg_top"], palette["bg_bottom"])
    draw_glow(base, (-120, -80, 470, 370), palette["accent"], 34, 70)
    draw_glow(base, (980, 40, 1480, 420), palette["accent"], 36, 52)

    panels = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    pdraw = ImageDraw.Draw(panels)
    rounded_panel(pdraw, (40, 40, 420, HEIGHT - 40), 32, palette["panel"], palette["panel_stroke"], 2)
    rounded_panel(pdraw, (460, 40, WIDTH - 40, 220), 28, palette["panel"], palette["panel_stroke"], 2)
    rounded_panel(pdraw, (460, 250, 900, HEIGHT - 40), 28, palette["panel"], palette["panel_stroke"], 2)
    rounded_panel(pdraw, (930, 250, WIDTH - 40, HEIGHT - 40), 28, palette["panel"], palette["panel_stroke"], 2)
    base.alpha_composite(panels.filter(ImageFilter.GaussianBlur(10)))
    base.alpha_composite(panels)

    avatar = circle_crop(await fetch_avatar(avatar_url))
    base.paste(avatar, (140, 78), avatar)

    ring = Image.new("RGBA", base.size, (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(ring)
    rdraw.ellipse((132, 70, 328, 266), outline=palette["accent"], width=8)
    base.alpha_composite(ring.filter(ImageFilter.GaussianBlur(12)))
    base.alpha_composite(ring)

    draw = ImageDraw.Draw(base)
    title_font = load_font(48)
    label_font = load_font(22)
    stat_font = load_font(34)
    small_font = load_font(19)

    safe_name = username if len(username) <= 18 else f"{username[:15]}..."
    draw.text((104, 292), safe_name, font=title_font, fill=palette["primary_text"])

    subtitle = "Server player"
    if frame == "vip_frame":
        subtitle = "Server player, collector, VIP"
    if staff_badge == "admin":
        subtitle = "Server admin"
    elif staff_badge == "moder":
        subtitle = "Server moderator"
    draw.text((107, 350), subtitle, font=label_font, fill=palette["secondary_text"])
    draw.text((107, 388), f"ID {user_id}", font=small_font, fill=palette["muted_text"])

    draw.text((500, 78), "Profile summary", font=label_font, fill=palette["secondary_text"])
    summary_stats = [
        ("BALANCE", str(balance)),
        ("LEVEL", str(level)),
        ("REPUTATION", str(rep)),
    ]
    for index, (label, value) in enumerate(summary_stats):
        x = 500 + index * 210
        draw.text((x, 130), label, font=small_font, fill=palette["muted_text"])
        draw.text((x, 156), value, font=stat_font, fill=palette["primary_text"])

    draw.text((500, 290), "XP progress", font=label_font, fill=palette["secondary_text"])
    progress = xp / xp_needed if xp_needed > 0 else 0
    progress = max(0, min(1, progress))
    bar_x = 500
    bar_y = 336
    bar_w = 340
    bar_h = 24
    rounded_panel(draw, (bar_x, bar_y, bar_x + bar_w, bar_y + bar_h), 12, palette["progress_bg"])
    fill_w = int(bar_w * progress)
    if fill_w > 0:
        rounded_panel(draw, (bar_x, bar_y, bar_x + fill_w, bar_y + bar_h), 12, palette["progress_fill"])
    draw.text((500, 374), f"{xp} / {xp_needed} XP", font=small_font, fill=palette["primary_text"])
    remaining_xp = max(xp_needed - xp, 0)
    draw.text((500, 408), f"{remaining_xp} XP left to next level", font=small_font, fill=palette["muted_text"])

    draw.text((970, 290), "Status", font=label_font, fill=palette["secondary_text"])
    status_items = [
        f"Theme: {format_theme_name(theme)}",
        f"Frame: {format_frame_name(frame)}",
    ]
    if staff_badge is not None:
        status_items.append(f"Role: {staff_badge}")
    for index, text in enumerate(status_items):
        top = 334 + index * 66
        rounded_panel(draw, (970, top, 1220, top + 54), 16, palette["panel_fill"])
        draw.text((994, top + 13), text, font=small_font, fill=palette["primary_text"])

    if frame == "vip_frame":
        badge_x = 240
        badge_y = 102
        rounded_panel(draw, (badge_x, badge_y, badge_x + 150, badge_y + 42), 16, palette["progress_fill"])
        draw.text((badge_x + 24, badge_y + 11), "VIP", font=small_font, fill=(35, 24, 8))

    if staff_badge is not None:
        badge_x = 106
        badge_y = 430
        rounded_panel(draw, (badge_x, badge_y, badge_x + 140, badge_y + 42), 16, palette["progress_fill"])
        draw.text((badge_x + 22, badge_y + 11), staff_badge.upper(), font=small_font, fill=palette["panel"][:3])

    buffer = io.BytesIO()
    base.save(buffer, "PNG")
    buffer.seek(0)
    return buffer
