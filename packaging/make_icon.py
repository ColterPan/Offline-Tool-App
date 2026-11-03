"""Generate the app icon (PNG for the window, ICO for Windows) from code.

Run from the repo root:  python packaging/make_icon.py
Replace with a designed icon later by overwriting the two output files.
"""

import logging
from pathlib import Path

from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PNG_OUT = ROOT / "src" / "offline_tools" / "assets" / "icon.png"
ICO_OUT = ROOT / "packaging" / "windows" / "icon.ico"

SIZE = 1024
ACCENT = (37, 99, 235, 255)  # matches tokens.LIGHT.accent
WHITE = (255, 255, 255, 255)
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def draw_icon(size: int = SIZE) -> Image.Image:
    """Blue rounded square, white document with a folded corner, blue tick: 'done, locally'."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 100  # draw on a 100-unit grid

    draw.rounded_rectangle((4 * s, 4 * s, 96 * s, 96 * s), radius=22 * s, fill=ACCENT)

    fold = 14 * s
    left, top, right, bottom = 27 * s, 18 * s, 73 * s, 82 * s
    draw.polygon(
        [(left, top), (right - fold, top), (right, top + fold), (right, bottom), (left, bottom)],
        fill=WHITE,
    )
    draw.polygon(
        [(right - fold, top), (right - fold, top + fold), (right, top + fold)],
        fill=(190, 208, 248, 255),
    )
    draw.line(
        [(37 * s, 52 * s), (46 * s, 62 * s), (63 * s, 42 * s)],
        fill=ACCENT,
        width=round(7 * s),
        joint="curve",
    )
    return img


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    icon = draw_icon()
    PNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    ICO_OUT.parent.mkdir(parents=True, exist_ok=True)
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(PNG_OUT)
    icon.save(ICO_OUT, sizes=ICO_SIZES)
    logger.info("Wrote %s and %s", PNG_OUT, ICO_OUT)


if __name__ == "__main__":
    main()
