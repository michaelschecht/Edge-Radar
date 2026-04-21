"""Generate favicon.ico + favicon.png with a radar scope design.

Run from repo root:
  .venv/Scripts/python.exe scripts/make_favicon.py
Outputs favicon.ico and favicon.png in the current directory.
"""
from PIL import Image, ImageDraw


def make_radar(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 100.0
    cx = cy = size / 2
    cyan = (0, 212, 170)

    r = 48 * s
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(10, 14, 23, 255))

    for radius, alpha in [(38, 102), (25, 153), (12, 204)]:
        r = radius * s
        w = max(1, round(3 * s))
        draw.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=cyan + (alpha,),
            width=w,
        )

    draw.line(
        [cx, cy, 85 * s, 25 * s],
        fill=cyan + (255,),
        width=max(1, round(3 * s)),
    )

    for (x, y, radius) in [(50, 50, 3), (72, 30, 4)]:
        px, py = x * s, y * s
        r = radius * s
        draw.ellipse([px - r, py - r, px + r, py + r], fill=cyan + (255,))

    return img


if __name__ == "__main__":
    master = make_radar(48)
    master.save("favicon.ico", format="ICO", sizes=[(16, 16), (32, 32), (48, 48)])
    make_radar(32).save("favicon.png", format="PNG")
    print("Wrote favicon.ico and favicon.png")
