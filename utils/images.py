from io import BytesIO

import aiohttp
from PIL import Image, ImageDraw, ImageFont


def load_font(size: int, bold: bool = False):
    candidates = []
    if bold:
        candidates += ['/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 'Arial.ttf', 'arial.ttf']
    else:
        candidates += ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf', 'Arial.ttf', 'arial.ttf']
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except Exception:
            continue
    return ImageFont.load_default()


def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius: int, fill=None, outline=None, width: int = 1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def minimal_bg(w: int, h: int) -> Image.Image:
    base = Image.new('RGBA', (w, h), (12, 14, 18, 255))
    draw = ImageDraw.Draw(base)
    top = (12, 14, 18)
    bottom = (18, 20, 26)
    for y in range(h):
        t = y / max(1, h - 1)
        r = int(top[0] + (bottom[0] - top[0]) * t)
        g = int(top[1] + (bottom[1] - top[1]) * t)
        b = int(top[2] + (bottom[2] - top[2]) * t)
        draw.line([(0, y), (w, y)], fill=(r, g, b, 255))
    return base


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    img = img.convert('RGB')
    iw, ih = img.size
    scale = max(w / iw, h / ih)
    nw, nh = int(iw * scale), int(ih * scale)
    img = img.resize((nw, nh))
    left = (nw - w) // 2
    top = (nh - h) // 2
    return img.crop((left, top, left + w, top + h)).convert('RGBA')


async def fetch_image_bytes(url: str) -> bytes | None:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=12) as response:
                if response.status != 200:
                    return None
                return await response.read()
    except Exception:
        return None


def circle_avatar(avatar_img: Image.Image, size: int) -> Image.Image:
    avatar_img = avatar_img.convert('RGBA').resize((size, size))
    mask = Image.new('L', (size, size), 0)
    md = ImageDraw.Draw(mask)
    md.ellipse((0, 0, size, size), fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(avatar_img, (0, 0), mask)
    return out


def image_to_png_bytes(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format='PNG')
    return out.getvalue()
