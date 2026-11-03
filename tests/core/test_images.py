import re
from pathlib import Path

import pytest
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.images import (
    ImageFormat,
    PageSize,
    convert_image,
    convert_images,
    images_to_pdf,
    open_image,
)

EXIF_ORIENTATION = 0x0112
EXIF_GPS_IFD = 0x8825
ROTATE_90_CW = 6


def _png(path: Path, size: tuple[int, int] = (40, 20), colour: str = "red") -> Path:
    Image.new("RGB", size, colour).save(path)
    return path


def _jpeg_with_exif(path: Path) -> Path:
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = ROTATE_90_CW
    exif[0x010F] = "PhoneMaker"  # camera make
    Image.new("RGB", (40, 20), "green").save(path, "JPEG", exif=exif.tobytes())
    return path


def _pdf_page_count(path: Path) -> int:
    counts = re.findall(rb"/Count (\d+)", path.read_bytes())
    return int(counts[-1])


def _pdf_media_boxes(path: Path) -> list[tuple[float, float]]:
    boxes = re.findall(rb"/MediaBox \[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", path.read_bytes())
    return [(float(w), float(h)) for w, h in boxes]


# ---- open_image -------------------------------------------------------------


def test_open_image_applies_exif_rotation(tmp_path: Path) -> None:
    image = open_image(_jpeg_with_exif(tmp_path / "photo.jpg"))

    assert image.size == (20, 40)


def test_open_image_rejects_non_image(tmp_path: Path) -> None:
    fake = tmp_path / "notes.png"
    fake.write_text("not really a picture", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="isn't an image"):
        open_image(fake)


def test_open_image_rejects_decompression_bombs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 100)
    source = _png(tmp_path / "huge.png", size=(100, 100))

    with pytest.raises(InvalidInputError, match="too large"):
        open_image(source)


# ---- convert ------------------------------------------------------------------


def test_convert_png_with_transparency_to_jpeg_uses_white_background(tmp_path: Path) -> None:
    source = tmp_path / "logo.png"
    Image.new("RGBA", (10, 10), (0, 0, 0, 0)).save(source)

    result = convert_image(source, ImageFormat.JPEG, out_dir=tmp_path)

    assert result == tmp_path / "logo.jpg"
    with Image.open(result) as converted:
        assert converted.format == "JPEG"
        assert converted.getpixel((5, 5)) == (255, 255, 255)


def test_convert_strips_metadata_but_keeps_orientation(tmp_path: Path) -> None:
    source = _jpeg_with_exif(tmp_path / "photo.jpg")

    result = convert_image(source, ImageFormat.WEBP, out_dir=tmp_path)

    with Image.open(result) as converted:
        assert converted.size == (20, 40)
        assert dict(converted.getexif()) == {}


def test_convert_never_overwrites_existing_files(tmp_path: Path) -> None:
    source = _png(tmp_path / "pic.png")
    (tmp_path / "pic.jpg").touch()

    result = convert_image(source, ImageFormat.JPEG, out_dir=tmp_path)

    assert result == tmp_path / "pic (converted).jpg"


def test_convert_to_same_format_does_not_touch_original(tmp_path: Path) -> None:
    source = _png(tmp_path / "pic.png")
    original = source.read_bytes()

    result = convert_image(source, ImageFormat.PNG, out_dir=tmp_path)

    assert result != source
    assert source.read_bytes() == original


def test_convert_images_reports_failures_without_stopping(tmp_path: Path) -> None:
    good = _png(tmp_path / "good.png")
    bad = tmp_path / "bad.png"
    bad.write_text("nope", encoding="utf-8")
    progress: list[tuple[int, int]] = []

    result = convert_images(
        [good, bad],
        ImageFormat.JPEG,
        out_dir_for=lambda source: source.parent,
        on_progress=lambda done, total: progress.append((done, total)),
    )

    assert result.outputs == (tmp_path / "good.jpg",)
    assert [path for path, _ in result.failures] == [bad]
    assert progress[-1] == (2, 2)


def test_convert_images_requires_at_least_one_file() -> None:
    with pytest.raises(InvalidInputError, match="Add at least one"):
        convert_images([], ImageFormat.PNG, out_dir_for=lambda p: p.parent)


# ---- images -> PDF ------------------------------------------------------------


def test_images_to_pdf_one_page_per_image(tmp_path: Path) -> None:
    sources = [_png(tmp_path / f"{i}.png", colour=c) for i, c in enumerate(["red", "blue", "lime"])]
    out = tmp_path / "out.pdf"

    result = images_to_pdf(sources, out)

    assert result == out
    assert out.read_bytes().startswith(b"%PDF")
    assert _pdf_page_count(out) == 3


def test_images_to_pdf_a4_pages_have_a4_size(tmp_path: Path) -> None:
    sources = [_png(tmp_path / "wide.png", size=(300, 100))]
    out = tmp_path / "a4.pdf"

    images_to_pdf(sources, out, page_size=PageSize.A4, margin_mm=10)

    width, height = _pdf_media_boxes(out)[-1]
    # A wide image gets a landscape A4 page (842 x 595 points), within rounding.
    assert width == pytest.approx(842, abs=2)
    assert height == pytest.approx(595, abs=2)


def test_images_to_pdf_leaves_no_partial_file_on_failure(tmp_path: Path) -> None:
    good = _png(tmp_path / "good.png")
    bad = tmp_path / "bad.png"
    bad.write_text("nope", encoding="utf-8")
    out = tmp_path / "out.pdf"

    with pytest.raises(InvalidInputError):
        images_to_pdf([good, bad], out)

    assert list(tmp_path.glob("*.pdf")) == []


def test_images_to_pdf_requires_images(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="Add at least one"):
        images_to_pdf([], tmp_path / "x.pdf")
