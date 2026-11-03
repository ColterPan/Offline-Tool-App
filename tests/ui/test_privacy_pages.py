from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw
from PySide6.QtGui import QGuiApplication, QImage
from pytestqt.qtbot import QtBot

from offline_tools.core.geometry import FULL_QUAD, Point, Rect
from offline_tools.core.images import images_to_pdf
from offline_tools.core.pdf_render import page_count
from offline_tools.core.qr import make_qr
from offline_tools.core.qr_check import Verdict
from offline_tools.ui.camera import CAMERA_ERROR, CameraScanner
from offline_tools.ui.context import AppContext
from offline_tools.ui.tools.qr_check_page import QrCheckPage, ReportCard
from offline_tools.ui.tools.redact_page import RedactPage
from offline_tools.ui.tools.scan_page import ScanPage
from offline_tools.ui.tools.watermark_page import WatermarkPage

WAIT_MS = 8000


def _wait_done(qtbot: QtBot, page: Any) -> str:
    qtbot.waitUntil(lambda: page.banner.state in ("success", "error"), timeout=WAIT_MS)
    qtbot.waitUntil(lambda: not page.is_running, timeout=WAIT_MS)
    return str(page.banner.state)


# ---- Redact ---------------------------------------------------------------------


def test_redact_photo(qtbot: QtBot, app_context: AppContext, tmp_path: Path) -> None:
    page = RedactPage(app_context)
    qtbot.addWidget(page)
    source = tmp_path / "ic.png"
    Image.new("RGB", (300, 200), "white").save(source)
    assert not page.save_button.isEnabled()

    page.select_file(source)
    qtbot.waitUntil(lambda: page.canvas.has_image and not page.is_running, timeout=WAIT_MS)
    page.canvas.add_box(Rect(0.1, 0.1, 0.5, 0.5))
    assert page.save_button.isEnabled()
    assert "1 box(es) on this page" in page.count_label.text()
    page.save()

    assert _wait_done(qtbot, page) == "success"
    with Image.open(tmp_path / "ic (redacted).png") as out:
        assert out.getpixel((60, 40)) == (0, 0, 0)


def test_redact_pdf_pages_keep_their_own_boxes(
    qtbot: QtBot, app_context: AppContext, tmp_path: Path
) -> None:
    pages = []
    for name in ("1.png", "2.png"):
        Image.new("RGB", (120, 160), "white").save(tmp_path / name)
        pages.append(tmp_path / name)
    source = images_to_pdf(pages, tmp_path / "payslip.pdf")
    page = RedactPage(app_context)
    qtbot.addWidget(page)

    page.select_file(source)
    qtbot.waitUntil(lambda: page.canvas.has_image and not page.is_running, timeout=WAIT_MS)
    assert page.page_label.text() == "Page 1 of 2"
    assert not page.prev_button.isEnabled()
    page.show_page(1)
    page.canvas.add_box(Rect(0, 0, 1, 0.3))
    page.show_page(0)
    assert page.canvas.boxes == ()
    assert page.total_boxes == 1

    page.save()

    assert _wait_done(qtbot, page) == "success"
    assert page_count(tmp_path / "payslip (redacted).pdf") == 2


# ---- Watermark ------------------------------------------------------------------


@pytest.fixture
def watermark_page(qtbot: QtBot, app_context: AppContext) -> WatermarkPage:
    page = WatermarkPage(app_context)
    qtbot.addWidget(page)
    return page


def test_watermark_preview_explains_missing_text(watermark_page: WatermarkPage) -> None:
    watermark_page.refresh_preview()

    assert "Type the watermark text" in watermark_page.preview_status.text()
    assert not watermark_page.apply_button.isEnabled()


def test_watermark_applies_to_photos(
    qtbot: QtBot, watermark_page: WatermarkPage, tmp_path: Path
) -> None:
    photo = tmp_path / "shop.jpg"
    Image.new("RGB", (400, 300), (90, 90, 90)).save(photo)
    watermark_page.file_list.add_paths([photo])
    watermark_page.text_edit.setPlainText("SAMPLE")
    watermark_page.refresh_preview()
    assert "selected photo" in watermark_page.preview_status.text()
    assert watermark_page.apply_button.text() == "Watermark 1 photo(s)"

    watermark_page.apply()

    assert _wait_done(qtbot, watermark_page) == "success"
    assert (tmp_path / "shop (watermarked).jpg").exists()


def test_id_template_and_click_to_place(watermark_page: WatermarkPage) -> None:
    watermark_page.use_id_template()

    style = watermark_page.watermark_style()
    assert style.tiled
    assert "COPY FOR" in style.text
    assert watermark_page.text_edit.textCursor().selectedText() == "__________"

    watermark_page._on_preview_clicked(Point(0.2, 0.8))
    style = watermark_page.watermark_style()
    assert not style.tiled
    assert style.position == Point(0.2, 0.8)
    assert watermark_page.position_group.checkedButton() is None


def test_logo_watermark_mode(watermark_page: WatermarkPage, tmp_path: Path) -> None:
    logo = tmp_path / "logo.png"
    Image.new("RGBA", (40, 40), (0, 0, 255, 255)).save(logo)

    watermark_page.logo_radio.setChecked(True)
    watermark_page.set_logo(logo)
    watermark_page.refresh_preview()

    assert watermark_page.watermark_style().logo_path == logo
    assert "Logo: logo.png" in watermark_page.logo_label.text()
    assert watermark_page.text_edit.isHidden()


# ---- QR check -------------------------------------------------------------------


class FakeCamera:
    """Stands in for a webcam: yields the given RGB frames as BGR, like OpenCV does."""

    def __init__(self, frames: list[np.ndarray[Any, Any]], opened: bool = True) -> None:
        self._frames = [cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) for frame in frames]
        self._opened = opened
        self.released = False

    def isOpened(self) -> bool:
        return self._opened

    def read(self) -> tuple[bool, Any]:
        frame = self._frames[0] if self._frames else None
        if len(self._frames) > 1:
            self._frames.pop(0)
        return frame is not None, frame

    def release(self) -> None:
        self.released = True


@pytest.fixture
def qr_page(qtbot: QtBot, app_context: AppContext) -> QrCheckPage:
    page = QrCheckPage(app_context)
    qtbot.addWidget(page)
    return page


def _cards(page: QrCheckPage) -> list[ReportCard]:
    return page.results.findChildren(ReportCard)


def test_qr_check_from_image_file(qtbot: QtBot, qr_page: QrCheckPage, tmp_path: Path) -> None:
    path = tmp_path / "poster.png"
    make_qr("https://dbs-sg-login.com/verify", size_px=300).save(path)

    qr_page.check_image_file(path)

    qtbot.waitUntil(lambda: bool(qr_page.reports), timeout=WAIT_MS)
    assert qr_page.reports[0].verdict is Verdict.DANGER
    qtbot.waitUntil(lambda: len(_cards(qr_page)) == 1, timeout=WAIT_MS)


def test_qr_check_image_without_code(qtbot: QtBot, qr_page: QrCheckPage, tmp_path: Path) -> None:
    path = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), "white").save(path)

    qr_page.check_image_file(path)

    assert _wait_done(qtbot, qr_page) == "error"
    assert "No QR code" in qr_page.banner.message.text()


def test_qr_check_pasted_link(qr_page: QrCheckPage) -> None:
    qr_page.link_edit.setText("https://www.gov.sg/")

    qr_page.check_link()

    assert qr_page.reports[0].verdict is Verdict.OK


def test_qr_check_paste_screenshot(qtbot: QtBot, qr_page: QrCheckPage, tmp_path: Path) -> None:
    path = tmp_path / "shot.png"
    make_qr("hello", size_px=250).save(path)
    QGuiApplication.clipboard().setImage(QImage(str(path)))

    qr_page.paste_from_clipboard()

    qtbot.waitUntil(lambda: bool(qr_page.reports), timeout=WAIT_MS)
    assert qr_page.reports[0].payload == "hello"


def test_qr_check_webcam_finds_code(qtbot: QtBot, qr_page: QrCheckPage) -> None:
    blank = np.full((240, 320, 3), 255, np.uint8)
    code = np.asarray(make_qr("https://example.com", size_px=240))
    camera = FakeCamera([blank, blank, code])

    qr_page.start_camera(CameraScanner(open_source=lambda: camera, parent=qr_page))

    qtbot.waitUntil(lambda: bool(qr_page.reports), timeout=WAIT_MS)
    assert qr_page.reports[0].payload == "https://example.com"
    qtbot.waitUntil(lambda: qr_page.camera_view.isHidden(), timeout=WAIT_MS)
    assert camera.released


def test_qr_check_webcam_unavailable(qtbot: QtBot, qr_page: QrCheckPage) -> None:
    camera = FakeCamera([], opened=False)

    qr_page.start_camera(CameraScanner(open_source=lambda: camera, parent=qr_page))

    qtbot.waitUntil(lambda: qr_page.banner.state == "error", timeout=WAIT_MS)
    assert qr_page.banner.message.text().endswith(CAMERA_ERROR)
    qtbot.waitUntil(lambda: qr_page.camera_button.text() == "Scan with webcam", timeout=WAIT_MS)


def test_qr_check_stop_camera(qtbot: QtBot, qr_page: QrCheckPage) -> None:
    blank = np.full((120, 160, 3), 255, np.uint8)
    qr_page.start_camera(CameraScanner(open_source=lambda: FakeCamera([blank]), parent=qr_page))
    assert qr_page.camera_button.text() == "Stop webcam"

    qr_page.stop_camera()

    assert qr_page.camera_button.text() == "Scan with webcam"


# ---- Scan -----------------------------------------------------------------------


def _document_photo(path: Path) -> Path:
    photo = Image.new("RGB", (900, 1200), (60, 55, 50))
    draw = ImageDraw.Draw(photo)
    draw.polygon([(170, 140), (720, 190), (760, 1060), (120, 1010)], fill=(235, 232, 225))
    for row in range(8):
        draw.rectangle((250, 300 + row * 80, 600, 318 + row * 80), fill=(30, 30, 30))
    photo.save(path)
    return path


def test_scan_page_detects_corners_and_saves_pdf(
    qtbot: QtBot, app_context: AppContext, tmp_path: Path
) -> None:
    page = ScanPage(app_context)
    qtbot.addWidget(page)
    assert not page.save_button.isEnabled()

    page.select_file(_document_photo(tmp_path / "receipt.jpg"))
    qtbot.waitUntil(lambda: page.save_button.isEnabled(), timeout=WAIT_MS)
    assert page.corners.quad != FULL_QUAD
    assert page.result.has_image

    page.save()

    assert _wait_done(qtbot, page) == "success"
    assert page_count(tmp_path / "receipt (scan).pdf") == 1


def test_scan_page_use_whole_photo(qtbot: QtBot, app_context: AppContext, tmp_path: Path) -> None:
    page = ScanPage(app_context)
    qtbot.addWidget(page)
    page.select_file(_document_photo(tmp_path / "doc.png"))
    qtbot.waitUntil(lambda: page.save_button.isEnabled(), timeout=WAIT_MS)

    page.whole_button.click()
    assert page.corners.quad == FULL_QUAD

    page.reset_to_detected()
    assert page.corners.quad != FULL_QUAD
