from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.geometry import FULL_QUAD, Point, Quad
from offline_tools.core.pdf_render import page_count
from offline_tools.core.scanner import (
    ScanMode,
    detect_page,
    enhance,
    save_scan,
    scan_document,
    straighten,
)

PHOTO_SIZE = (900, 1200)
# A slightly tilted page, as if photographed on a desk: TL, TR, BR, BL in pixels.
PAGE_CORNERS = [(170, 140), (720, 190), (760, 1060), (120, 1010)]
CORNER_TOLERANCE = 0.03


def _photo_of_page() -> Image.Image:
    photo = Image.new("RGB", PHOTO_SIZE, (60, 55, 50))  # dark desk
    draw = ImageDraw.Draw(photo)
    draw.polygon(PAGE_CORNERS, fill=(235, 232, 225))  # slightly grey paper
    for row in range(8):  # "text" lines
        y = 300 + row * 80
        draw.rectangle((250, y, 600, y + 18), fill=(30, 30, 30))
    return photo


def _expected_quad() -> Quad:
    w, h = PHOTO_SIZE
    tl, tr, br, bl = (Point(x / w, y / h) for x, y in PAGE_CORNERS)
    return (tl, tr, br, bl)


def test_detect_page_finds_the_corners_in_order() -> None:
    found = detect_page(_photo_of_page())

    assert found is not None
    for got, expected in zip(found, _expected_quad(), strict=True):
        assert abs(got.x - expected.x) < CORNER_TOLERANCE
        assert abs(got.y - expected.y) < CORNER_TOLERANCE


def test_detect_page_returns_none_without_a_page() -> None:
    assert detect_page(Image.new("RGB", (400, 400), (90, 90, 90))) is None


def test_straighten_produces_upright_page_with_matching_shape() -> None:
    flat = straighten(_photo_of_page(), _expected_quad())

    assert flat.height > flat.width
    assert 1.25 < flat.height / flat.width < 1.5
    # The paper fills the result: corners are paper-coloured, not desk-coloured.
    corner = flat.getpixel((5, 5))
    assert isinstance(corner, tuple)
    assert sum(corner) > 600


def test_straighten_rejects_collapsed_corners() -> None:
    collapsed: Quad = (Point(0.5, 0.5), Point(0.5, 0.5), Point(0.51, 0.51), Point(0.5, 0.51))

    with pytest.raises(InvalidInputError, match="corners"):
        straighten(_photo_of_page(), collapsed)


def test_black_and_white_mode_is_pure_black_and_white() -> None:
    flat = straighten(_photo_of_page(), _expected_quad())

    bw = enhance(flat, ScanMode.BLACK_WHITE)

    assert bw.mode == "L"
    assert set(np.unique(np.asarray(bw)).tolist()) <= {0, 255}
    assert bw.getpixel((bw.width // 2, bw.height - 20)) == 255  # paper becomes white


@pytest.mark.parametrize(
    ("mode", "image_mode"),
    [(ScanMode.GREYSCALE, "L"), (ScanMode.COLOUR, "RGB"), (ScanMode.ORIGINAL, "RGB")],
)
def test_other_modes(mode: ScanMode, image_mode: str) -> None:
    flat = straighten(_photo_of_page(), FULL_QUAD)

    assert enhance(flat, mode).mode == image_mode


def test_scan_document_in_one_step(tmp_path: Path) -> None:
    out = scan_document(_photo_of_page(), _expected_quad(), ScanMode.GREYSCALE, tmp_path / "s.png")

    with Image.open(out) as saved:
        assert saved.mode == "L"
        assert saved.height > saved.width


@pytest.mark.parametrize("suffix", [".pdf", ".png", ".jpg"])
def test_save_scan(tmp_path: Path, suffix: str) -> None:
    scan = enhance(straighten(_photo_of_page(), _expected_quad()), ScanMode.BLACK_WHITE)

    out = save_scan(scan, tmp_path / f"scan{suffix}")

    assert out.exists()
    if suffix == ".pdf":
        assert page_count(out) == 1
