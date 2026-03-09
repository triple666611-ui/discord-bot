from PIL import Image, ImageDraw, ImageFilter


def create_rgba_canvas(width: int, height: int, color=(0, 0, 0, 0)):
    image = Image.new("RGBA", (width, height), color)
    draw = ImageDraw.Draw(image)
    return image, draw


def rounded_box(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(
        xy,
        radius=radius,
        fill=fill,
        outline=outline,
        width=width,
    )


def make_vertical_gradient(width: int, height: int, top_color, bottom_color):
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)

    for y in range(height):
        t = y / max(1, height - 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * t)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * t)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * t)
        a = int(top_color[3] + (bottom_color[3] - top_color[3]) * t)
        draw.line((0, y, width, y), fill=(r, g, b, a))

    return image


def add_blurred_shadow(base, xy, radius, fill, blur=18, offset=(8, 10)):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(shadow)

    x1, y1, x2, y2 = xy
    ox, oy = offset

    draw.rounded_rectangle(
        (x1 + ox, y1 + oy, x2 + ox, y2 + oy),
        radius=radius,
        fill=fill,
    )

    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    return Image.alpha_composite(base, shadow)


def clamp_text(text: str, max_len: int) -> str:
    value = text.strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 1] + "…"