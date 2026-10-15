"""Generate assets/nibba.ico (multi-size Windows icon, no fonts needed).

Mark: orange rounded square (dashboard accent #E8932B) with a white
package glyph drawn from rectangles - crisp at 16px through 256px.
Run:  venv\\Scripts\\python.exe assets\\gen_icon.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
BG = (232, 147, 43, 255)      # dashboard accent
INK = (255, 255, 255, 255)    # glyph white
SIZE = 256


def rounded_square(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def draw_package(draw, s):
    # White open-box glyph, all coordinates relative to canvas size s.
    u = s / 256
    # Box body.
    draw.rectangle([88 * u, 118 * u, 168 * u, 186 * u],
                   outline=INK, width=int(15 * u))
    # Lid flaps.
    draw.line([88 * u, 118 * u, 128 * u, 88 * u], fill=INK,
              width=int(15 * u), joint="curve")
    draw.line([168 * u, 118 * u, 128 * u, 88 * u], fill=INK,
              width=int(15 * u), joint="curve")
    # Tape seam.
    draw.line([128 * u, 88 * u, 128 * u, 186 * u], fill=INK,
              width=int(9 * u))


def main():
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    rounded_square(draw, [8, 8, SIZE - 8, SIZE - 8], 58, BG)
    draw_package(draw, SIZE)
    out = HERE / "nibba.ico"
    out.unlink(missing_ok=True)
    img.save(out, sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                         (64, 64), (128, 128), (256, 256)])
    print(f"ICON OK: {out} ({out.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
