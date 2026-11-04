"""Generate the app icon (PNG for the window and macOS, ICO for Windows) from code.

Run from the repo root:  python packaging/make_icon.py
Replace with a designed icon later by overwriting the output files.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PNG_OUT = ROOT / "src" / "offline_tools" / "assets" / "icon.png"
ICO_OUT = ROOT / "packaging" / "windows" / "icon.ico"

SIZE = 1024
SUPERSAMPLE = 4  # draw large, then scale down: Pillow's shapes have no anti-aliasing
PNG_SIZE = 1024  # macOS needs 1024 px for the Retina .icns
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]

BLUE_TOP = (59, 130, 246, 255)
BLUE_BOTTOM = (29, 78, 216, 255)  # tokens.LIGHT.accent sits between these two
NAVY = (23, 37, 84, 255)
WHITE = (255, 255, 255, 255)
LID = (219, 234, 254, 255)
AMBER = (245, 158, 11, 255)
AMBER_DARK = (180, 83, 9, 255)
STEEL = (203, 213, 225, 255)
SHADOW = (15, 23, 42, 70)
CLEAR = (0, 0, 0, 0)


def draw_icon(size: int = SIZE) -> Image.Image:
    """Blue rounded square with a white toolbox, an amber latch and two tools peeking out."""
    big = size * SUPERSAMPLE
    s = big / 100  # draw on a 100-unit grid

    def box(left: float, top: float, right: float, bottom: float) -> tuple[float, ...]:
        return (left * s, top * s, right * s, bottom * s)

    icon = Image.new("RGBA", (big, big), CLEAR)
    icon.paste(_gradient(big), mask=_rounded_mask(big, box(4, 4, 96, 96), 22 * s))

    art = Image.new("RGBA", (big, big), CLEAR)
    draw = ImageDraw.Draw(art)

    # Tools behind the lid: a screwdriver (left) and an open-ended wrench (right).
    draw.rounded_rectangle(box(27, 30, 30, 40), radius=1 * s, fill=STEEL)
    draw.rounded_rectangle(box(24, 15, 33, 33), radius=3 * s, fill=AMBER)
    draw.rounded_rectangle(box(24, 27, 33, 30), radius=0, fill=AMBER_DARK)
    draw.rounded_rectangle(box(68, 22, 74, 40), radius=2 * s, fill=STEEL)
    draw.ellipse(box(63, 11, 79, 27), fill=STEEL)
    draw.rectangle(box(68.5, 9, 73.5, 18), fill=CLEAR)  # the wrench's open jaw

    # Handle, then the lid over its lower half.
    draw.rounded_rectangle(box(38, 24, 62, 40), radius=6 * s, outline=WHITE, width=round(5 * s))

    bottom_only = (False, False, True, True)  # square top so the body meets the lid flush
    draw.rounded_rectangle(box(17, 51, 85, 82), radius=7 * s, fill=SHADOW, corners=bottom_only)
    draw.rounded_rectangle(box(16, 48, 84, 79), radius=7 * s, fill=WHITE, corners=bottom_only)
    draw.rounded_rectangle(box(19, 35, 81, 49), radius=5 * s, fill=LID)
    draw.rectangle(box(16, 48, 84, 51), fill=BLUE_BOTTOM)  # seam between lid and body
    draw.rounded_rectangle(box(44, 43, 56, 57), radius=2.5 * s, fill=AMBER)  # latch
    draw.rounded_rectangle(box(47.5, 47, 52.5, 53), radius=1.2 * s, fill=NAVY)

    icon = Image.alpha_composite(icon, art)
    return icon.resize((size, size), Image.Resampling.LANCZOS)


def _gradient(size: int) -> Image.Image:
    column = Image.new("RGBA", (1, 256))
    for y in range(256):
        t = y / 255
        column.putpixel(
            (0, y),
            tuple(round(a + (b - a) * t) for a, b in zip(BLUE_TOP, BLUE_BOTTOM, strict=True)),
        )
    return column.resize((size, size), Image.Resampling.BILINEAR)


def _rounded_mask(size: int, bounds: tuple[float, ...], radius: float) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(bounds, radius=radius, fill=255)
    return mask


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    icon = draw_icon()
    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    ICO_OUT.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((PNG_SIZE, PNG_SIZE), Image.Resampling.LANCZOS).save(PNG_OUT, optimize=True)
    icon.save(ICO_OUT, sizes=ICO_SIZES)
    logger.info("Wrote %s and %s", PNG_OUT, ICO_OUT)


if __name__ == "__main__":
    main()
