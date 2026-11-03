from pathlib import Path

import pypdfium2 as pdfium
import pytest
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.geometry import Rect
from offline_tools.core.images import images_to_pdf
from offline_tools.core.pdf_render import page_count, render_page
from offline_tools.core.redact import FillColour, redact_image, redact_image_file, redact_pdf

LEFT_HALF = Rect(0.0, 0.0, 0.5, 1.0)


def _text_pdf(path: Path, text: str) -> Path:
    """A real PDF with selectable text (hand-written; PDFium repairs the xref offsets)."""
    stream = f"BT /F1 24 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    body = b"%PDF-1.4\n"
    for number, obj in enumerate(objects, start=1):
        body += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    body += b"trailer\n<< /Root 1 0 R /Size 6 >>\n%%EOF\n"
    path.write_bytes(body)
    return path


def _pdf_text(path: Path) -> str:
    document = pdfium.PdfDocument(str(path))
    try:
        page = document[0]
        text = page.get_textpage().get_text_range()
        page.close()
        return str(text)
    finally:
        document.close()


def test_redact_image_fills_boxes_only() -> None:
    img = Image.new("RGB", (100, 50), "white")

    result = redact_image(img, [LEFT_HALF], FillColour.BLACK)

    assert result.getpixel((10, 25)) == (0, 0, 0)
    assert result.getpixel((49, 0)) == (0, 0, 0)
    assert result.getpixel((80, 25)) == (255, 255, 255)
    assert img.getpixel((10, 25)) == (255, 255, 255)  # original untouched


def test_redact_image_white_fill() -> None:
    img = Image.new("RGB", (20, 20), "black")

    result = redact_image(img, [Rect(0, 0, 1, 1)], FillColour.WHITE)

    assert result.getpixel((10, 10)) == (255, 255, 255)


def test_redact_image_file_keeps_format_and_labels_output(tmp_path: Path) -> None:
    source = tmp_path / "nric.jpg"
    Image.new("RGB", (60, 40), "white").save(source)

    out = redact_image_file(source, [LEFT_HALF], FillColour.BLACK, out_dir=tmp_path)

    assert out == tmp_path / "nric (redacted).jpg"
    with Image.open(out) as result:
        assert result.format == "JPEG"
        pixel = result.convert("RGB").getpixel((5, 20))
        assert isinstance(pixel, tuple)
        assert max(pixel) < 20


def test_redact_requires_a_box(tmp_path: Path) -> None:
    source = tmp_path / "a.png"
    Image.new("RGB", (10, 10)).save(source)

    with pytest.raises(InvalidInputError, match="Draw at least one box"):
        redact_image_file(source, [], FillColour.BLACK, out_dir=tmp_path)


def test_redact_pdf_removes_text_and_keeps_page_count(tmp_path: Path) -> None:
    source = _text_pdf(tmp_path / "payslip.pdf", "NRIC S1234567D")
    assert "S1234567D" in _pdf_text(source)

    out = redact_pdf(source, {0: [Rect(0.0, 0.0, 1.0, 0.2)]}, FillColour.BLACK, out_dir=tmp_path)

    assert out == tmp_path / "payslip (redacted).pdf"
    assert page_count(out) == 1
    assert "S1234567D" not in _pdf_text(out)  # flattened: no text left to copy
    page = render_page(out, 0, dpi=50)
    assert page.getpixel((page.width // 2, 5)) == (0, 0, 0)


def test_redact_pdf_only_boxes_listed_pages(tmp_path: Path) -> None:
    pages = []
    for name in ("p1.png", "p2.png"):
        Image.new("RGB", (100, 140), "white").save(tmp_path / name)
        pages.append(tmp_path / name)
    source = images_to_pdf(pages, tmp_path / "doc.pdf")
    progress: list[tuple[int, int]] = []

    out = redact_pdf(
        source,
        {1: [LEFT_HALF]},
        FillColour.BLACK,
        out_dir=tmp_path,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    first, second = render_page(out, 0, dpi=40), render_page(out, 1, dpi=40)
    assert first.getpixel((5, 5)) == (255, 255, 255)
    assert second.getpixel((5, 5)) == (0, 0, 0)
    assert progress[-1] == (2, 2)


def test_redact_pdf_rejects_boxes_on_missing_pages(tmp_path: Path) -> None:
    source = _text_pdf(tmp_path / "a.pdf", "x")

    with pytest.raises(InvalidInputError, match="page 5"):
        redact_pdf(source, {4: [LEFT_HALF]}, FillColour.BLACK, out_dir=tmp_path)


def test_redact_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    fake = tmp_path / "fake.pdf"
    fake.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="isn't a PDF"):
        redact_pdf(fake, {0: [LEFT_HALF]}, FillColour.BLACK, out_dir=tmp_path)
