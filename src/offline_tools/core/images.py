"""Image conversion and images → PDF, using Pillow."""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps, UnidentifiedImageError

from offline_tools.core.errors import InvalidInputError, OutputError, ToolError
from offline_tools.core.paths import part_path, preferred_output_path, require_file
from offline_tools.core.progress import ProgressCallback, report

logger = logging.getLogger(__name__)

SUPPORTED_INPUT_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
)
DEFAULT_QUALITY = 90
PDF_DPI = 200
MM_PER_INCH = 25.4
WHITE = (255, 255, 255)


class ImageFormat(StrEnum):
    PNG = "png"
    JPEG = "jpeg"
    WEBP = "webp"

    @property
    def suffix(self) -> str:
        return {"png": ".png", "jpeg": ".jpg", "webp": ".webp"}[self.value]

    @property
    def uses_quality(self) -> bool:
        return self is not ImageFormat.PNG


class PageSize(StrEnum):
    FIT = "fit"  # each page is the size of its image
    A4 = "a4"
    LETTER = "letter"


PAGE_SIZES_MM = {PageSize.A4: (210.0, 297.0), PageSize.LETTER: (215.9, 279.4)}


@dataclass(frozen=True)
class BatchResult:
    outputs: tuple[Path, ...]
    failures: tuple[tuple[Path, str], ...]  # (file, user-facing reason)


def open_image(path: Path) -> Image.Image:
    """Load an image fully into memory, upright (phone photos store rotation in EXIF)."""
    source = require_file(path)
    try:
        with Image.open(source) as img:
            img.load()
            upright = ImageOps.exif_transpose(img)
            # Leaving the `with` closes img, so keep a copy if nothing was rotated.
            return upright if upright is not img else img.copy()
    except Image.DecompressionBombError as exc:
        raise InvalidInputError(f'"{source.name}" is too large to open safely.', repr(exc)) from exc
    except UnidentifiedImageError as exc:
        raise InvalidInputError(
            f'"{source.name}" isn\'t an image this app can read.', repr(exc)
        ) from exc
    except OSError as exc:
        raise InvalidInputError(
            f'"{source.name}" could not be read. It may be damaged.', repr(exc)
        ) from exc


def to_rgb(img: Image.Image) -> Image.Image:
    """Drop transparency onto white (JPEG and PDF pages can't be transparent)."""
    if img.mode == "RGB":
        return img
    if _has_alpha(img):
        rgba = img.convert("RGBA")
        background = Image.new("RGB", rgba.size, WHITE)
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background
    return img.convert("RGB")


def convert_image(
    source: Path,
    target: ImageFormat,
    *,
    out_dir: Path,
    quality: int = DEFAULT_QUALITY,
) -> Path:
    """Save `source` as `target` in out_dir. Metadata (camera, GPS location) is not copied."""
    img = open_image(source)
    prepared = to_rgb(img) if target is ImageFormat.JPEG else _rgb_or_rgba(img)
    out = preferred_output_path(source, out_dir=out_dir, new_suffix=target.suffix)
    _save_atomically(prepared, out, target.value.upper(), **_save_options(target, quality))
    return out


def convert_images(
    sources: Sequence[Path],
    target: ImageFormat,
    *,
    out_dir_for: Callable[[Path], Path],
    quality: int = DEFAULT_QUALITY,
    on_progress: ProgressCallback | None = None,
) -> BatchResult:
    """Convert each file; one bad file is reported in `failures` instead of stopping the batch."""
    if not sources:
        raise InvalidInputError("Add at least one image.")
    outputs: list[Path] = []
    failures: list[tuple[Path, str]] = []
    for index, source in enumerate(sources, start=1):
        try:
            outputs.append(
                convert_image(source, target, out_dir=out_dir_for(source), quality=quality)
            )
        except ToolError as exc:
            logger.warning("Could not convert %s: %s", source, exc.detail)
            failures.append((source, exc.user_message))
        report(on_progress, index, len(sources))
    return BatchResult(outputs=tuple(outputs), failures=tuple(failures))


def images_to_pdf(
    sources: Sequence[Path],
    out_path: Path,
    *,
    page_size: PageSize = PageSize.FIT,
    margin_mm: float = 0,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """One page per image, in order. Pages are written one at a time to keep memory low."""
    if not sources:
        raise InvalidInputError("Add at least one image.")
    tmp = part_path(out_path)
    try:
        for index, source in enumerate(sources):
            page = _pdf_page(open_image(source), page_size, margin_mm)
            page.save(tmp, "PDF", resolution=PDF_DPI, append=index > 0)
            report(on_progress, index + 1, len(sources))
        tmp.replace(out_path)
    except ToolError:
        tmp.unlink(missing_ok=True)
        raise
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(
            f'Could not save "{out_path.name}". Check the folder is writable.', repr(exc)
        ) from exc
    return out_path


def _pdf_page(img: Image.Image, page_size: PageSize, margin_mm: float) -> Image.Image:
    rgb = to_rgb(img)
    if page_size is PageSize.FIT:
        return rgb
    width_mm, height_mm = PAGE_SIZES_MM[page_size]
    if rgb.width > rgb.height:  # landscape image -> landscape page
        width_mm, height_mm = height_mm, width_mm
    page_w, page_h = _mm_to_px(width_mm), _mm_to_px(height_mm)
    margin = min(_mm_to_px(max(margin_mm, 0)), min(page_w, page_h) // 4)
    box_w, box_h = page_w - 2 * margin, page_h - 2 * margin
    scale = min(box_w / rgb.width, box_h / rgb.height)
    size = (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale)))
    page = Image.new("RGB", (page_w, page_h), WHITE)
    page.paste(
        rgb.resize(size, Image.Resampling.LANCZOS),
        ((page_w - size[0]) // 2, (page_h - size[1]) // 2),
    )
    return page


def _mm_to_px(mm: float) -> int:
    return round(mm / MM_PER_INCH * PDF_DPI)


def _has_alpha(img: Image.Image) -> bool:
    return img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)


def _rgb_or_rgba(img: Image.Image) -> Image.Image:
    wanted = "RGBA" if _has_alpha(img) else "RGB"
    return img if img.mode == wanted else img.convert(wanted)


def _save_options(target: ImageFormat, quality: int) -> dict[str, Any]:
    if target is ImageFormat.JPEG:
        return {"quality": quality, "optimize": True}
    if target is ImageFormat.WEBP:
        return {"quality": quality, "method": 4}
    return {}


def _save_atomically(img: Image.Image, out: Path, pillow_format: str, **options: Any) -> None:
    tmp = part_path(out)
    try:
        img.save(tmp, pillow_format, **options)
        tmp.replace(out)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(
            f'Could not save "{out.name}". Check the folder is writable.', repr(exc)
        ) from exc
