"""Text or logo watermarks: placed anywhere, tiled, rotated, with adjustable opacity.

Sizes and positions are relative to the photo, so the preview and the full-size output match.
"""

import logging
import math
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from offline_tools.core.errors import InvalidInputError, ToolError
from offline_tools.core.geometry import Point
from offline_tools.core.images import (
    BatchResult,
    format_for_suffix,
    has_alpha,
    open_image,
    save_image,
)
from offline_tools.core.paths import unique_output_path
from offline_tools.core.progress import ProgressCallback, report

logger = logging.getLogger(__name__)

MARGIN_FRACTION = 0.03  # keep placed watermarks this far from the edges
TILE_GAP = 0.35  # space between tiles, as a fraction of the watermark's shorter side
MIN_FONT_PX = 8
OUTLINE_DIVISOR = 22  # outline width = font size / this
WATERMARKED_QUALITY = 95
LIGHT_COLOUR_THRESHOLD = 150
CENTRE = Point(0.5, 0.5)

_FONT_CANDIDATES = {
    "win32": ("arialbd.ttf", "segoeuib.ttf", "arial.ttf"),
    "darwin": (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ),
}


class WatermarkKind(StrEnum):
    TEXT = "text"
    LOGO = "logo"


@dataclass(frozen=True)
class WatermarkStyle:
    kind: WatermarkKind = WatermarkKind.TEXT
    text: str = ""
    logo_path: Path | None = None
    colour: tuple[int, int, int] = (255, 255, 255)
    opacity: float = 0.4  # 0 = invisible, 1 = solid
    size: float = 0.08  # text line height / logo's longer side, as a fraction of the shorter side
    rotation: float = 0.0  # degrees, anticlockwise
    position: Point = CENTRE  # centre of the watermark
    tiled: bool = False  # repeat across the whole photo (position is then ignored)
    outline: bool = True  # thin contrasting edge so text shows on busy photos


def watermark_image(
    img: Image.Image, style: WatermarkStyle, *, logo: Image.Image | None = None
) -> Image.Image:
    """A watermarked copy of `img`. Pass `logo` for LOGO watermarks."""
    base = img.convert("RGBA")
    stamp = _make_stamp(style, base.size, logo)
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    if style.tiled:
        _tile(layer, stamp)
    else:
        layer.paste(stamp, _placement(style.position, stamp.size, base.size))
    result = Image.alpha_composite(base, layer)
    return result if has_alpha(img) else result.convert("RGB")


def watermark_files(
    sources: Sequence[Path],
    style: WatermarkStyle,
    *,
    out_dir_for: Callable[[Path], Path],
    on_progress: ProgressCallback | None = None,
) -> BatchResult:
    """Watermark each photo. Metadata is not copied; one bad file doesn't stop the batch."""
    if not sources:
        raise InvalidInputError("Add at least one photo.")
    logo = _load_logo(style)
    outputs: list[Path] = []
    failures: list[tuple[Path, str]] = []
    for index, source in enumerate(sources, start=1):
        try:
            target = format_for_suffix(source.suffix)
            out = unique_output_path(
                source, out_dir=out_dir_for(source), new_suffix=target.suffix, label="watermarked"
            )
            marked = watermark_image(open_image(source), style, logo=logo)
            outputs.append(save_image(marked, out, target, quality=WATERMARKED_QUALITY))
        except ToolError as exc:
            logger.warning("Could not watermark %s: %s", source, exc.detail)
            failures.append((source, exc.user_message))
        report(on_progress, index, len(sources))
    return BatchResult(outputs=tuple(outputs), failures=tuple(failures))


def _load_logo(style: WatermarkStyle) -> Image.Image | None:
    if style.kind is not WatermarkKind.LOGO:
        return None
    if style.logo_path is None:
        raise InvalidInputError("Choose a logo image first.")
    return open_image(style.logo_path)


def _make_stamp(
    style: WatermarkStyle, image_size: tuple[int, int], logo: Image.Image | None
) -> Image.Image:
    shorter_side = min(image_size)
    size = min(max(style.size, 0.01), 1.0)
    if style.kind is WatermarkKind.LOGO:
        if logo is None:
            raise InvalidInputError("Choose a logo image first.")
        stamp = _logo_stamp(logo, max(1, round(size * shorter_side)))
    else:
        if not style.text.strip():
            raise InvalidInputError("Type the watermark text first.")
        font_px = max(MIN_FONT_PX, round(size * shorter_side))
        stamp = _text_stamp(style.text.strip(), font_px, style.colour, style.outline)
    if style.rotation:
        stamp = stamp.rotate(style.rotation, expand=True, resample=Image.Resampling.BICUBIC)
    opacity = min(max(style.opacity, 0.0), 1.0)
    stamp.putalpha(stamp.getchannel("A").point(lambda alpha: round(alpha * opacity)))
    return stamp


def _text_stamp(
    text: str, font_px: int, colour: tuple[int, int, int], outline: bool
) -> Image.Image:
    font = _font(font_px)
    stroke = max(1, font_px // OUTLINE_DIVISOR) if outline else 0
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.multiline_textbbox(
        (0, 0), text, font=font, stroke_width=stroke, align="center"
    )
    pad = stroke + 2
    size = (math.ceil(right - left) + 2 * pad, math.ceil(bottom - top) + 2 * pad)
    stamp = Image.new("RGBA", size, (0, 0, 0, 0))
    is_light = sum(colour) / 3 > LIGHT_COLOUR_THRESHOLD
    ImageDraw.Draw(stamp).multiline_text(
        (pad - left, pad - top),
        text,
        font=font,
        fill=(*colour, 255),
        align="center",
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255) if is_light else (255, 255, 255, 255),
    )
    return stamp


def _logo_stamp(logo: Image.Image, longer_side_px: int) -> Image.Image:
    rgba = logo.convert("RGBA")
    scale = longer_side_px / max(rgba.size)
    size = (max(1, round(rgba.width * scale)), max(1, round(rgba.height * scale)))
    return rgba.resize(size, Image.Resampling.LANCZOS)


def _placement(
    position: Point, stamp_size: tuple[int, int], image_size: tuple[int, int]
) -> tuple[int, int]:
    """Top-left corner for the stamp so its centre is at `position`, kept inside the margins."""
    margin = round(MARGIN_FRACTION * min(image_size))
    coords = []
    for centre, stamp_len, image_len in zip(
        position.clamped().to_pixels(*image_size), stamp_size, image_size, strict=True
    ):
        low = margin + stamp_len / 2
        high = image_len - margin - stamp_len / 2
        clamped = image_len / 2 if low > high else min(max(centre, low), high)
        coords.append(round(clamped - stamp_len / 2))
    return coords[0], coords[1]


def _tile(layer: Image.Image, stamp: Image.Image) -> None:
    # The gap follows the stamp's shorter side, so long text still repeats often enough.
    gap = round(TILE_GAP * min(stamp.size))
    step_x = max(1, stamp.width + gap)
    step_y = max(1, stamp.height + gap)
    for row, y in enumerate(range(-stamp.height // 2, layer.height, step_y)):
        offset = (step_x // 2) if row % 2 else 0  # brick pattern looks less mechanical
        for x in range(-stamp.width + offset, layer.width, step_x):
            # Tiles never overlap, so a plain paste (which copies alpha) is correct.
            layer.paste(stamp, (x, y))


@lru_cache(maxsize=32)
def _font(size_px: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in _FONT_CANDIDATES.get(sys.platform, ("DejaVuSans-Bold.ttf",)):
        try:
            return ImageFont.truetype(candidate, size_px)
        except OSError:
            continue
    return ImageFont.load_default(size=size_px)  # Pillow's built-in scalable font
