from pathlib import Path

import pytest
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.qr import make_qr
from offline_tools.core.qr_decode import decode_qr_codes, decode_qr_file


def test_decodes_a_single_code() -> None:
    assert decode_qr_codes(make_qr("https://example.com", size_px=300)) == ("https://example.com",)


def test_decodes_several_codes_and_removes_duplicates() -> None:
    a, b = make_qr("first", size_px=200), make_qr("second", size_px=200)
    canvas = Image.new("RGB", (660, 220), "white")
    canvas.paste(a, (0, 0))
    canvas.paste(b, (220, 0))
    canvas.paste(a, (440, 0))

    assert sorted(decode_qr_codes(canvas)) == ["first", "second"]


def test_no_code_found() -> None:
    with pytest.raises(InvalidInputError, match="No QR code"):
        decode_qr_codes(Image.new("RGB", (200, 200), "white"))


def test_decode_qr_file(tmp_path: Path) -> None:
    path = tmp_path / "screenshot.png"
    make_qr("hello", size_px=250).save(path)

    assert decode_qr_file(path) == ("hello",)
