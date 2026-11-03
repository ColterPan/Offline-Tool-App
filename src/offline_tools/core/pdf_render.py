"""Read PDF pages as images with PDFium (the PDF engine inside Chrome)."""

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.paths import require_file

POINTS_PER_INCH = 72
DEFAULT_DPI = 200

# PDFium is not thread-safe: the UI renders previews while a background job may be
# rendering pages for export, so every PDFium call goes through this lock.
_PDFIUM_LOCK = threading.RLock()


@contextmanager
def open_pdf(path: Path) -> Iterator[pdfium.PdfDocument]:
    source = require_file(path)
    with _PDFIUM_LOCK:
        try:
            document = pdfium.PdfDocument(str(source))
        except pdfium.PdfiumError as exc:
            if "password" in str(exc).lower():
                raise InvalidInputError(
                    f'"{source.name}" is password-protected. Open it, remove the password, '
                    "and try again.",
                    repr(exc),
                ) from exc
            raise InvalidInputError(
                f'"{source.name}" isn\'t a PDF this app can read. It may be damaged.', repr(exc)
            ) from exc
    try:
        yield document
    finally:
        with _PDFIUM_LOCK:
            document.close()


def page_count(path: Path) -> int:
    with open_pdf(path) as document, _PDFIUM_LOCK:
        return len(document)


def render_page(path: Path, index: int, dpi: float = DEFAULT_DPI) -> Image.Image:
    with open_pdf(path) as document:
        return _render(document, index, dpi)


def iter_pages(path: Path, dpi: float = DEFAULT_DPI) -> Iterator[Image.Image]:
    """Render every page in order, one at a time (keeps memory low for long PDFs)."""
    with open_pdf(path) as document:
        with _PDFIUM_LOCK:
            total = len(document)
        for index in range(total):
            yield _render(document, index, dpi)


def _render(document: pdfium.PdfDocument, index: int, dpi: float) -> Image.Image:
    with _PDFIUM_LOCK:
        if not 0 <= index < len(document):
            raise InvalidInputError(f"Page {index + 1} doesn't exist in this PDF.")
        page = document[index]
        try:
            image: Image.Image = page.render(scale=dpi / POINTS_PER_INCH).to_pil()
        finally:
            page.close()
    return image.convert("RGB")
