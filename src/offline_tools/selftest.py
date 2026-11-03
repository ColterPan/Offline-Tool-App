"""`--self-test`: exercise every bundled native library, then exit (0 = all good).

The smoke test only proves the window opens. Packaged builds usually break because a DLL or
plugin wasn't bundled (PDFium, OpenCV, zxing, Qt's SVG plugin), so this actually uses each one.
CI runs it against the installed app on Windows and the .app on macOS.
"""

import logging
from collections.abc import Callable
from pathlib import Path

import openpyxl
from PIL import Image, ImageDraw
from PySide6.QtGui import QGuiApplication, QImage

from offline_tools.core.data import csv_to_excel, excel_to_csv
from offline_tools.core.geometry import Rect
from offline_tools.core.images import images_to_pdf
from offline_tools.core.pdf_render import page_count, render_page
from offline_tools.core.qr import make_qr
from offline_tools.core.qr_check import Verdict, analyse
from offline_tools.core.qr_decode import decode_qr_codes
from offline_tools.core.redact import FillColour, redact_pdf
from offline_tools.core.scanner import ScanMode, detect_page, enhance, straighten
from offline_tools.core.watermark import WatermarkStyle, watermark_image
from offline_tools.resources import asset_path

logger = logging.getLogger(__name__)

type Check = Callable[[Path], None]


def run_self_test(work_dir: Path) -> list[str]:
    """Run every check in `work_dir`; return a description of each failure (empty = pass)."""
    failures: list[str] = []
    for name, check in CHECKS:
        try:
            check(work_dir)
        except Exception as exc:
            # Diagnostic boundary: report every failing check, not just the first.
            logger.exception("Self-test failed: %s", name)
            failures.append(f"{name}: {exc!r}")
        else:
            logger.info("Self-test passed: %s", name)
    return failures


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _qr_round_trip(_work: Path) -> None:
    _expect(decode_qr_codes(make_qr("self-test", size_px=200)) == ("self-test",), "QR mismatch")


def _pdf_render_and_redact(work: Path) -> None:
    page = work / "page.png"
    Image.new("RGB", (100, 140), "white").save(page)
    pdf = images_to_pdf([page], work / "doc.pdf")
    _expect(page_count(pdf) == 1, "wrong page count")
    out = redact_pdf(pdf, {0: [Rect(0, 0, 1, 0.5)]}, FillColour.BLACK, out_dir=work)
    _expect(render_page(out, 0, dpi=40).getpixel((5, 5)) == (0, 0, 0), "redaction not applied")


def _watermark(_work: Path) -> None:
    photo = Image.new("RGB", (200, 100), "grey")
    marked = watermark_image(photo, WatermarkStyle(text="TEST", opacity=1, size=0.3))
    _expect(marked.tobytes() != photo.tobytes(), "watermark not drawn")


def _document_scan(_work: Path) -> None:
    photo = Image.new("RGB", (400, 500), (50, 50, 50))
    ImageDraw.Draw(photo).polygon([(60, 50), (340, 70), (350, 450), (50, 430)], fill="white")
    quad = detect_page(photo)
    _expect(quad is not None, "page not detected")
    assert quad is not None
    enhance(straighten(photo, quad), ScanMode.BLACK_WHITE)


def _excel_csv(work: Path) -> None:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    sheet.append(["a", 1])
    book.save(work / "book.xlsx")
    (csv_file,) = excel_to_csv(work / "book.xlsx", sheet=None, out_dir=work)
    csv_to_excel(csv_file, out_dir=work)


def _link_check(_work: Path) -> None:
    _expect(analyse("https://dbs-login.top/x.apk").verdict is Verdict.DANGER, "scam not flagged")


def _qt_svg_plugin(_work: Path) -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    _expect(app is not None, "no Qt application")
    image = QImage(str(asset_path("check-light.svg")))
    _expect(not image.isNull(), "Qt SVG image plugin missing (checkbox icons won't show)")


CHECKS: tuple[tuple[str, Check], ...] = (
    ("QR create + read (qrcode, zxing-cpp)", _qr_round_trip),
    ("PDF write, render, redact (Pillow, PDFium)", _pdf_render_and_redact),
    ("Watermark (Pillow, fonts)", _watermark),
    ("Document scan (OpenCV)", _document_scan),
    ("Excel <-> CSV (openpyxl)", _excel_csv),
    ("Link check", _link_check),
    ("Qt SVG plugin", _qt_svg_plugin),
)
