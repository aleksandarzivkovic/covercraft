"""One-off generator for CoverCraft's "Crop Marks" app icon -> assets/icon.ico.

Draws the same geometry as concept 01 in the icon proof (100x100 viewBox:
72px rounded square at rx 9, 46px disc, corner registration ticks) on a solid
white plate, supersampled 4x per target size then downsampled for clean
antialiasing. The plate is what makes the icon hold up in Windows 11 dark
mode - a transparent-background black-stroke glyph nearly disappears against
a dark taskbar/Start Menu, since there's nothing behind the lines to contrast
with. Ticks are dropped below 32px, matching the design rationale (favicon
quietly falls back to the plain CoverCast-family square+disc).
"""

from pathlib import Path
from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]
SUPERSAMPLE = 4
INK = (22, 24, 27, 255)  # matches --ink from the icon proof page
PLATE_FILL = (255, 255, 255, 255)
PLATE_BORDER = (211, 213, 209, 255)  # matches --chip-light-line from the icon proof


def draw_icon(size_px: int, draw_ticks: bool) -> Image.Image:
    ss = size_px * SUPERSAMPLE
    scale = ss / 100.0
    img = Image.new("RGBA", (ss, ss), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def s(v):
        return v * scale

    # Solid plate behind the glyph, so the icon stays legible against a dark
    # taskbar/Start Menu, not just a light one.
    plate_border_w = max(1, round(s(1.6)))
    draw.rounded_rectangle(
        [s(1), s(1), s(99), s(99)], radius=s(14),
        fill=PLATE_FILL, outline=PLATE_BORDER, width=plate_border_w,
    )

    # Outer rounded square
    sq_stroke = max(1, round(s(6)))
    draw.rounded_rectangle(
        [s(14), s(14), s(86), s(86)], radius=s(9), outline=INK, width=sq_stroke
    )

    # Disc ring
    disc_stroke = max(1, round(s(6)))
    draw.ellipse([s(27), s(27), s(73), s(73)], outline=INK, width=disc_stroke)

    # Center dot
    r = s(4.2)
    draw.ellipse([s(50) - r, s(50) - r, s(50) + r, s(50) + r], fill=INK)

    if draw_ticks:
        tick_stroke = max(1, round(s(3.4)))
        ticks = [
            ((s(2), s(14)), (s(10), s(14))), ((s(14), s(2)), (s(14), s(10))),
            ((s(98), s(14)), (s(90), s(14))), ((s(86), s(2)), (s(86), s(10))),
            ((s(2), s(86)), (s(10), s(86))), ((s(14), s(90)), (s(14), s(98))),
            ((s(98), s(86)), (s(90), s(86))), ((s(86), s(90)), (s(86), s(98))),
        ]
        for p1, p2 in ticks:
            draw.line([p1, p2], fill=INK, width=tick_stroke)

    return img.resize((size_px, size_px), Image.LANCZOS)


def main():
    out_dir = Path(__file__).resolve().parent
    images = [draw_icon(size, draw_ticks=size >= 32) for size in SIZES]
    ico_path = out_dir / "icon.ico"
    images[0].save(
        ico_path,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[1:],
    )
    print(f"Wrote {ico_path}")

    png_path = out_dir / "icon-256.png"
    draw_icon(256, draw_ticks=True).save(png_path)
    print(f"Wrote {png_path}")


if __name__ == "__main__":
    main()
