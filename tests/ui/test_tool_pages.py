import re
from pathlib import Path

import openpyxl
import pytest
from PIL import Image
from pytestqt.qtbot import QtBot

from offline_tools.core.images import ImageFormat, PageSize
from offline_tools.ui.context import AppContext
from offline_tools.ui.tools.convert_images_page import ConvertImagesPage
from offline_tools.ui.tools.excel_csv_page import ALL_SHEETS_LABEL, Direction, ExcelCsvPage
from offline_tools.ui.tools.images_to_pdf_page import ImagesToPdfPage
from offline_tools.ui.tools.qr_page import QrContent, QrPage

WAIT_MS = 5000


def _png(path: Path, colour: str = "red") -> Path:
    Image.new("RGB", (30, 20), colour).save(path)
    return path


def _wait_for_banner(qtbot: QtBot, page: object) -> str:
    banner = page.banner  # type: ignore[attr-defined]
    qtbot.waitUntil(lambda: banner.state in ("success", "error"), timeout=WAIT_MS)
    qtbot.waitUntil(lambda: not page.is_running, timeout=WAIT_MS)  # type: ignore[attr-defined]
    return str(banner.state)


# ---- QR -----------------------------------------------------------------------


@pytest.fixture
def qr_page(qtbot: QtBot, app_context: AppContext) -> QrPage:
    page = QrPage(app_context)
    qtbot.addWidget(page)
    return page


def test_qr_page_starts_with_prompt_and_disabled_buttons(qr_page: QrPage) -> None:
    assert qr_page.image is None
    assert "Type some text" in qr_page.status_label.text()
    assert not qr_page.save_png_button.isEnabled()


def test_qr_page_previews_and_saves_png_and_svg(qr_page: QrPage, tmp_path: Path) -> None:
    qr_page.text_edit.setPlainText("https://pantechautomation.com")
    qr_page.refresh_preview()

    assert qr_page.image is not None
    assert qr_page.save_png_button.isEnabled()

    qr_page.save_to(tmp_path / "code.png")
    qr_page.save_to(tmp_path / "code.svg")
    assert (tmp_path / "code.png").read_bytes().startswith(b"\x89PNG")
    assert b"<svg" in (tmp_path / "code.svg").read_bytes()
    assert qr_page.banner.state == "success"


def test_qr_page_wifi_needs_password(qr_page: QrPage) -> None:
    qr_page.content_combo.setCurrentIndex(qr_page.content_combo.findData(QrContent.WIFI))
    qr_page.ssid_edit.setText("Home")
    qr_page.refresh_preview()

    assert qr_page.image is None
    assert "password" in qr_page.status_label.text()

    qr_page.password_edit.setText("secret123")
    qr_page.refresh_preview()
    assert qr_page.payload() == "WIFI:T:WPA;S:Home;P:secret123;;"
    assert qr_page.image is not None


def test_qr_page_contact_card(qr_page: QrPage) -> None:
    qr_page.content_combo.setCurrentIndex(qr_page.content_combo.findData(QrContent.CONTACT))
    qr_page.name_edit.setText("Tan Ah Kow")
    qr_page.refresh_preview()

    assert "FN:Tan Ah Kow" in qr_page.payload()
    assert qr_page._suggested_name() == "contact-Tan-Ah-Kow"


def test_qr_page_copy_to_clipboard(qr_page: QrPage) -> None:
    qr_page.text_edit.setPlainText("hello")
    qr_page.refresh_preview()

    qr_page.copy_to_clipboard()

    assert qr_page.banner.state == "success"


# ---- Images -> PDF --------------------------------------------------------------


def test_images_to_pdf_page_creates_pdf_next_to_first_image(
    qtbot: QtBot, app_context: AppContext, tmp_path: Path
) -> None:
    page = ImagesToPdfPage(app_context)
    qtbot.addWidget(page)
    assert not page.create_button.isEnabled()

    page.file_list.add_paths([_png(tmp_path / "scan1.png"), _png(tmp_path / "scan2.png", "blue")])
    page.page_combo.setCurrentIndex(page.page_combo.findData(PageSize.A4))
    assert page.create_button.isEnabled()
    assert page.margin_combo.isEnabled()

    page.create_pdf()

    assert _wait_for_banner(qtbot, page) == "success"
    pdf = tmp_path / "scan1.pdf"
    assert int(re.findall(rb"/Count (\d+)", pdf.read_bytes())[-1]) == 2
    assert "2 page(s)" in page.banner.message.text()
    assert page.create_button.isEnabled()


# ---- Convert images -------------------------------------------------------------


def test_convert_images_page_reports_partial_failures(
    qtbot: QtBot, app_context: AppContext, tmp_path: Path
) -> None:
    page = ConvertImagesPage(app_context)
    qtbot.addWidget(page)
    bad = tmp_path / "broken.png"
    bad.write_text("nope", encoding="utf-8")
    page.file_list.add_paths([_png(tmp_path / "ok.png"), bad])
    page.format_combo.setCurrentIndex(page.format_combo.findData(ImageFormat.WEBP))

    page.convert()

    assert _wait_for_banner(qtbot, page) == "success"
    assert (tmp_path / "ok.webp").exists()
    assert "Converted 1 of 2" in page.banner.message.text()


def test_convert_images_page_png_disables_quality(qtbot: QtBot, app_context: AppContext) -> None:
    page = ConvertImagesPage(app_context)
    qtbot.addWidget(page)

    page.format_combo.setCurrentIndex(page.format_combo.findData(ImageFormat.PNG))

    assert not page.quality_slider.isEnabled()


def test_convert_images_page_all_failed_shows_error(
    qtbot: QtBot, app_context: AppContext, tmp_path: Path
) -> None:
    page = ConvertImagesPage(app_context)
    qtbot.addWidget(page)
    bad = tmp_path / "broken.png"
    bad.write_text("nope", encoding="utf-8")
    page.file_list.add_paths([bad])

    page.convert()

    assert _wait_for_banner(qtbot, page) == "error"


# ---- Excel <-> CSV --------------------------------------------------------------


@pytest.fixture
def excel_page(qtbot: QtBot, app_context: AppContext) -> ExcelCsvPage:
    page = ExcelCsvPage(app_context)
    qtbot.addWidget(page)
    return page


def test_excel_page_converts_workbook_to_csv(
    qtbot: QtBot, excel_page: ExcelCsvPage, tmp_path: Path
) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Data"
    ws.append(["a", 1])
    wb.create_sheet("Other").append(["b", 2])
    source = tmp_path / "book.xlsx"
    wb.save(source)

    excel_page.select_file(source)
    qtbot.waitUntil(lambda: excel_page.direction is Direction.TO_CSV, timeout=WAIT_MS)
    assert excel_page.sheet_combo.itemText(0) == ALL_SHEETS_LABEL
    assert excel_page.convert_button.text() == "Convert to CSV"

    excel_page.sheet_combo.setCurrentIndex(excel_page.sheet_combo.findData("Data"))
    excel_page.convert()

    assert _wait_for_banner(qtbot, excel_page) == "success"
    assert (tmp_path / "book (Data).csv").read_text(encoding="utf-8-sig").strip() == "a,1"


def test_excel_page_converts_csv_to_workbook(
    qtbot: QtBot, excel_page: ExcelCsvPage, tmp_path: Path
) -> None:
    source = tmp_path / "list.csv"
    source.write_text("name,qty\npen,3\n", encoding="utf-8")

    excel_page.select_file(source)
    assert excel_page.direction is Direction.TO_EXCEL
    assert excel_page.convert_button.text() == "Convert to Excel"
    excel_page.convert()

    assert _wait_for_banner(qtbot, excel_page) == "success"
    assert (tmp_path / "list.xlsx").exists()


def test_excel_page_reports_unreadable_workbook(
    qtbot: QtBot, excel_page: ExcelCsvPage, tmp_path: Path
) -> None:
    fake = tmp_path / "fake.xlsx"
    fake.write_text("hello", encoding="utf-8")

    excel_page.select_file(fake)

    assert _wait_for_banner(qtbot, excel_page) == "error"
    assert excel_page.direction is Direction.NONE
    assert not excel_page.convert_button.isEnabled()
