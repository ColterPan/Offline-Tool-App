"""Convert Pillow images to Qt pixmaps for previews and the clipboard."""

import io

from PIL import Image
from PySide6.QtGui import QPixmap


def pil_to_pixmap(image: Image.Image) -> QPixmap:
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap
