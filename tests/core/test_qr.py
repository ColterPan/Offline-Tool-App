from pathlib import Path

import pytest

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.qr import (
    ContactDetails,
    ErrorCorrection,
    WifiDetails,
    WifiSecurity,
    make_qr,
    make_qr_svg,
    save_png,
    vcard_payload,
    wifi_payload,
)


def test_wifi_payload_wpa() -> None:
    details = WifiDetails(ssid="Home Net", password="pa55word")

    assert wifi_payload(details) == "WIFI:T:WPA;S:Home Net;P:pa55word;;"


def test_wifi_payload_escapes_special_characters() -> None:
    details = WifiDetails(ssid='a;b,c"d:e\\f', password="p;w")

    assert wifi_payload(details) == 'WIFI:T:WPA;S:a\\;b\\,c\\"d\\:e\\\\f;P:p\\;w;;'


def test_wifi_payload_open_network_and_hidden() -> None:
    details = WifiDetails(ssid="Cafe", security=WifiSecurity.NONE, hidden=True)

    assert wifi_payload(details) == "WIFI:T:nopass;S:Cafe;H:true;;"


@pytest.mark.parametrize(
    ("details", "message"),
    [
        (WifiDetails(ssid="  ", password="x"), "network name"),
        (WifiDetails(ssid="Home", password=""), "password"),
    ],
)
def test_wifi_payload_validation(details: WifiDetails, message: str) -> None:
    with pytest.raises(InvalidInputError, match=message):
        wifi_payload(details)


def test_vcard_payload_includes_filled_fields_only() -> None:
    contact = ContactDetails(name="Tan Ah Kow", phone="+65 9123 4567", email="ak@example.com")

    payload = vcard_payload(contact)

    assert payload.startswith("BEGIN:VCARD\r\nVERSION:3.0\r\n")
    assert "FN:Tan Ah Kow\r\n" in payload
    assert "TEL;TYPE=CELL:+65 9123 4567\r\n" in payload
    assert "EMAIL:ak@example.com\r\n" in payload
    assert "ORG:" not in payload
    assert payload.endswith("END:VCARD\r\n")


def test_vcard_payload_escapes_values() -> None:
    contact = ContactDetails(name="Lim, Mei; Ling", organisation="A\nB")

    payload = vcard_payload(contact)

    assert "FN:Lim\\, Mei\\; Ling\r\n" in payload
    assert "ORG:A\\nB\r\n" in payload


def test_vcard_payload_requires_name() -> None:
    with pytest.raises(InvalidInputError, match="name"):
        vcard_payload(ContactDetails(name=""))


def test_make_qr_returns_rgb_image_near_requested_size() -> None:
    image = make_qr("https://pantechautomation.com", size_px=600)

    assert image.mode == "RGB"
    assert image.width == image.height
    assert 450 <= image.width <= 750


def test_make_qr_higher_error_correction_needs_more_modules() -> None:
    # size_px=1 gives one pixel per module, so width equals the module count.
    low = make_qr("hello world " * 5, size_px=1, error_correction=ErrorCorrection.LOW)
    high = make_qr("hello world " * 5, size_px=1, error_correction=ErrorCorrection.HIGH)

    assert high.width > low.width


def test_make_qr_rejects_empty_text() -> None:
    with pytest.raises(InvalidInputError, match="Type some text"):
        make_qr("   ")


def test_make_qr_rejects_too_much_data() -> None:
    with pytest.raises(InvalidInputError, match="too much"):
        make_qr("x" * 5000)


def test_make_qr_svg_returns_svg_markup() -> None:
    svg = make_qr_svg("hello")

    assert b"<svg" in svg


def test_save_png_writes_file(tmp_path: Path) -> None:
    out = tmp_path / "qr.png"

    save_png(make_qr("hi"), out)

    assert out.read_bytes().startswith(b"\x89PNG")
