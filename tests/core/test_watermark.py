from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageChops

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.geometry import Point
from offline_tools.core.watermark import (
    WatermarkKind,
    WatermarkStyle,
    watermark_files,
    watermark_image,
)

GREY = (128, 128, 128)
TEXT_STYLE = WatermarkStyle(text="SAMPLE", colour=(255, 0, 0), opacity=0.8, size=0.15)


def _photo(size: tuple[int, int] = (400, 300)) -> Image.Image:
    return Image.new("RGB", size, GREY)


def _changed_box(before: Image.Image, after: Image.Image) -> tuple[int, int, int, int] | None:
    return ImageChops.difference(before.convert("RGB"), after.convert("RGB")).getbbox()


def _change_strength(before: Image.Image, after: Image.Image) -> int:
    diff = ImageChops.difference(before.convert("RGB"), after.convert("RGB")).convert("L")
    return int(np.asarray(diff, dtype=np.int64).sum())


def test_text_watermark_is_drawn_around_position() -> None:
    photo = _photo()

    result = watermark_image(photo, replace(TEXT_STYLE, position=Point(0.5, 0.5)))

    box = _changed_box(photo, result)
    assert box is not None
    left, top, right, bottom = box
    assert left < 200 < right
    assert top < 150 < bottom


def test_higher_opacity_is_darker() -> None:
    photo = _photo()

    faint = watermark_image(photo, replace(TEXT_STYLE, opacity=0.2))
    strong = watermark_image(photo, replace(TEXT_STYLE, opacity=0.9))

    assert _change_strength(photo, strong) > 2 * _change_strength(photo, faint)


def test_corner_position_stays_inside_the_photo() -> None:
    photo = _photo()

    result = watermark_image(photo, replace(TEXT_STYLE, position=Point(0, 0)))

    box = _changed_box(photo, result)
    assert box is not None
    assert box[0] >= 0 and box[1] >= 0
    assert box[2] < 250 and box[3] < 150  # stays in the top-left area


def test_tiled_watermark_covers_every_quarter() -> None:
    photo = _photo()

    result = watermark_image(photo, replace(TEXT_STYLE, tiled=True, size=0.08, rotation=-30))

    for quarter in ((0, 0, 200, 150), (200, 0, 400, 150), (0, 150, 200, 300), (200, 150, 400, 300)):
        assert _changed_box(photo.crop(quarter), result.crop(quarter)) is not None


def test_logo_watermark(tmp_path: Path) -> None:
    logo = Image.new("RGBA", (50, 50), (0, 0, 255, 255))
    photo = _photo()

    result = watermark_image(
        photo, WatermarkStyle(kind=WatermarkKind.LOGO, opacity=1.0, size=0.3), logo=logo
    )

    assert result.getpixel((200, 150)) == (0, 0, 255)


def test_transparent_png_keeps_alpha() -> None:
    photo = Image.new("RGBA", (100, 100), (0, 0, 0, 0))

    result = watermark_image(photo, TEXT_STYLE)

    assert result.mode == "RGBA"


@pytest.mark.parametrize(
    ("style", "logo", "message"),
    [
        (WatermarkStyle(text="   "), None, "Type the watermark text"),
        (WatermarkStyle(kind=WatermarkKind.LOGO), None, "Choose a logo"),
    ],
)
def test_watermark_validation(
    style: WatermarkStyle, logo: Image.Image | None, message: str
) -> None:
    with pytest.raises(InvalidInputError, match=message):
        watermark_image(_photo(), style, logo=logo)


def test_watermark_files_batch(tmp_path: Path) -> None:
    jpg, png = tmp_path / "a.jpg", tmp_path / "b.png"
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"
    _photo().save(jpg, exif=exif.tobytes())
    _photo().save(png)
    bad = tmp_path / "c.png"
    bad.write_text("nope", encoding="utf-8")

    result = watermark_files([jpg, png, bad], TEXT_STYLE, out_dir_for=lambda p: p.parent)

    assert [p.name for p in result.outputs] == ["a (watermarked).jpg", "b (watermarked).png"]
    assert [p.name for p, _ in result.failures] == ["c.png"]
    with Image.open(result.outputs[0]) as out:
        assert dict(out.getexif()) == {}


def test_watermark_files_loads_logo_once(tmp_path: Path) -> None:
    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (20, 20), (255, 255, 255, 255)).save(logo_path)
    photo = tmp_path / "p.png"
    _photo().save(photo)

    result = watermark_files(
        [photo],
        WatermarkStyle(kind=WatermarkKind.LOGO, logo_path=logo_path),
        out_dir_for=lambda p: p.parent,
    )

    assert len(result.outputs) == 1
