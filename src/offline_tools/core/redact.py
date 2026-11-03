"""Black (or white) out parts of images and PDFs, safely.

PDF pages are flattened into images. Drawing a box over text is not enough: the text stays in
the file and can be copied out. Flattening means only the pixels you can see are saved.
"""

from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path

from PIL import Image, ImageDraw

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.geometry import Rect
from offline_tools.core.images import (
    PDF_DPI,
    format_for_suffix,
    open_image,
    save_image,
    to_rgb,
    write_pdf,
)
from offline_tools.core.paths import unique_output_path
from offline_tools.core.pdf_render import iter_pages, page_count
from offline_tools.core.progress import ProgressCallback

REDACTED_IMAGE_QUALITY = 95
NO_BOXES_MESSAGE = "Draw at least one box over the part you want to hide."


class FillColour(StrEnum):
    BLACK = "black"
    WHITE = "white"

    @property
    def rgb(self) -> tuple[int, int, int]:
        return (0, 0, 0) if self is FillColour.BLACK else (255, 255, 255)


def redact_image(img: Image.Image, boxes: Sequence[Rect], colour: FillColour) -> Image.Image:
    """A copy of `img` with every box filled solid. The input is not modified."""
    result = to_rgb(img).copy()
    draw = ImageDraw.Draw(result)
    for box in boxes:
        if box.is_empty:
            continue
        left, top, right, bottom = box.to_pixels(result.width, result.height)
        # ImageDraw rectangles include their end pixel, so subtract one.
        draw.rectangle((left, top, right - 1, bottom - 1), fill=colour.rgb)
    return result


def redact_image_file(
    source: Path, boxes: Sequence[Rect], colour: FillColour, *, out_dir: Path
) -> Path:
    if not _has_boxes(boxes):
        raise InvalidInputError(NO_BOXES_MESSAGE)
    target = format_for_suffix(source.suffix)
    out = unique_output_path(source, out_dir=out_dir, new_suffix=target.suffix, label="redacted")
    redacted = redact_image(open_image(source), boxes, colour)
    return save_image(redacted, out, target, quality=REDACTED_IMAGE_QUALITY)


def redact_pdf(
    source: Path,
    boxes_by_page: Mapping[int, Sequence[Rect]],
    colour: FillColour,
    *,
    out_dir: Path,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Flatten every page to an image (so no hidden text survives) and fill the boxes."""
    if not any(_has_boxes(boxes) for boxes in boxes_by_page.values()):
        raise InvalidInputError(NO_BOXES_MESSAGE)
    total = page_count(source)
    missing = sorted(index for index in boxes_by_page if not 0 <= index < total)
    if missing:
        raise InvalidInputError(f"This PDF has no page {missing[0] + 1}.")
    out = unique_output_path(source, out_dir=out_dir, new_suffix=".pdf", label="redacted")
    pages = (
        redact_image(page, boxes_by_page.get(index, ()), colour)
        for index, page in enumerate(iter_pages(source, dpi=PDF_DPI))
    )
    return write_pdf(pages, out, total=total, resolution=PDF_DPI, on_progress=on_progress)


def _has_boxes(boxes: Sequence[Rect]) -> bool:
    return any(not box.is_empty for box in boxes)
