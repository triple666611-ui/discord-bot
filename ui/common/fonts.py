from pathlib import Path
from PIL import ImageFont


BASE_DIR = Path(__file__).resolve().parents[2]

FONT_CANDIDATES = [
    BASE_DIR / "assets" / "fonts" / "Inter-Bold.otf",
    BASE_DIR / "assets" / "fonts" / "Inter-Bold.ttf",
    BASE_DIR / "assets" / "fonts" / "Inter-Regular.otf",
    BASE_DIR / "assets" / "fonts" / "Inter-Regular.ttf",
]

LINUX_FALLBACKS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
]


def load_font(size: int):
    for font_path in FONT_CANDIDATES:
        if font_path.exists():
            return ImageFont.truetype(str(font_path), size)

    for fallback in LINUX_FALLBACKS:
        path = Path(fallback)
        if path.exists():
            return ImageFont.truetype(str(path), size)

    return ImageFont.load_default()


def get_font_pack() -> dict[str, int]:
    return {
        "hero": 72,
        "title": 56,
        "subtitle": 34,
        "body": 26,
        "small": 22,
        "label": 24,
        "stat": 36,
        "name": 50,
        "xp": 24,
    }