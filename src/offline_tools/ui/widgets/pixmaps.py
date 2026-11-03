"""Convert between Pillow images and Qt images (previews, clipboard)."""

import io

from PIL import Image
from PySide6.QtGui import QImage, QPixmap

PREVIEW_MAX_SIDE = 1400


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


def qimage_to_pil(image: QImage) -> Image.Image:
    """Copy the pixels straight across (no PNG round trip). Handles Qt's row padding."""
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    size = (rgba.width(), rgba.height())
    pixels = bytes(rgba.constBits())
    return Image.frombuffer("RGBA", size, pixels, "raw", "RGBA", rgba.bytesPerLine(), 1).copy()


def preview_copy(image: Image.Image, max_side: int = PREVIEW_MAX_SIDE) -> Image.Image:
    """A smaller copy for on-screen previews (shapes are normalised, so they still line up)."""
    copy = image.copy()
    copy.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    return copy
