"""QR codes for links/text, Wi-Fi logins and contact cards."""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import qrcode
import qrcode.image.svg
from PIL import Image
from qrcode.constants import ERROR_CORRECT_H, ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q
from qrcode.exceptions import DataOverflowError

from offline_tools.core.errors import InvalidInputError, OutputError

DEFAULT_SIZE_PX = 600
QUIET_ZONE_MODULES = 4  # white border scanners need around the code
SVG_BOX_SIZE = 10


class ErrorCorrection(StrEnum):
    """How much of the code can be damaged or covered and still scan."""

    LOW = "L"  # ~7%
    MEDIUM = "M"  # ~15%
    QUARTILE = "Q"  # ~25%
    HIGH = "H"  # ~30%


_LEVELS = {
    ErrorCorrection.LOW: ERROR_CORRECT_L,
    ErrorCorrection.MEDIUM: ERROR_CORRECT_M,
    ErrorCorrection.QUARTILE: ERROR_CORRECT_Q,
    ErrorCorrection.HIGH: ERROR_CORRECT_H,
}


class WifiSecurity(StrEnum):
    WPA = "WPA"  # WPA/WPA2/WPA3: what almost every home router uses
    WEP = "WEP"
    NONE = "nopass"


@dataclass(frozen=True)
class WifiDetails:
    ssid: str
    password: str = ""
    security: WifiSecurity = WifiSecurity.WPA
    hidden: bool = False


@dataclass(frozen=True)
class ContactDetails:
    name: str
    phone: str = ""
    email: str = ""
    organisation: str = ""
    website: str = ""


_WIFI_SPECIAL_CHARS = '\\;,":'


def wifi_payload(details: WifiDetails) -> str:
    """Text for the de-facto standard 'WIFI:' QR format that phone cameras understand."""
    if not details.ssid.strip():
        raise InvalidInputError("Enter the Wi-Fi network name.")
    fields = [f"T:{details.security.value}", f"S:{_escape_wifi(details.ssid)}"]
    if details.security is not WifiSecurity.NONE:
        if not details.password:
            raise InvalidInputError("Enter the Wi-Fi password, or choose 'No password'.")
        fields.append(f"P:{_escape_wifi(details.password)}")
    if details.hidden:
        fields.append("H:true")
    return "WIFI:" + ";".join(fields) + ";;"


def vcard_payload(contact: ContactDetails) -> str:
    """A vCard 3.0 contact. Phones offer to save it to the address book when scanned."""
    if not contact.name.strip():
        raise InvalidInputError("Enter the contact's name.")
    name = _escape_vcard(contact.name.strip())
    lines = ["BEGIN:VCARD", "VERSION:3.0", f"N:{name};;;;", f"FN:{name}"]
    optional = (
        ("ORG", contact.organisation),
        ("TEL;TYPE=CELL", contact.phone),
        ("EMAIL", contact.email),
        ("URL", contact.website),
    )
    lines += [f"{key}:{_escape_vcard(value.strip())}" for key, value in optional if value.strip()]
    lines.append("END:VCARD")
    return "\r\n".join(lines) + "\r\n"


def make_qr(
    data: str,
    *,
    size_px: int = DEFAULT_SIZE_PX,
    error_correction: ErrorCorrection = ErrorCorrection.MEDIUM,
) -> Image.Image:
    """Black-on-white RGB QR image, about size_px wide (whole pixels per module keep it sharp)."""
    qr = _build(data, error_correction)
    modules = qr.modules_count + 2 * QUIET_ZONE_MODULES
    qr.box_size = max(1, round(size_px / modules))
    image: Image.Image = qr.make_image().get_image()
    return image.convert("RGB")


def make_qr_svg(data: str, *, error_correction: ErrorCorrection = ErrorCorrection.MEDIUM) -> bytes:
    """Scalable QR code with a white background, for print and design tools."""
    qr = _build(data, error_correction)
    qr.box_size = SVG_BOX_SIZE
    svg = qr.make_image(image_factory=qrcode.image.svg.SvgPathFillImage)
    markup: bytes = svg.to_string()
    return markup


def save_png(image: Image.Image, path: Path) -> None:
    try:
        image.save(path, "PNG")
    except OSError as exc:
        raise OutputError(
            f'Could not save "{path.name}". Check the folder is writable.', repr(exc)
        ) from exc


def save_svg(markup: bytes, path: Path) -> None:
    try:
        path.write_bytes(markup)
    except OSError as exc:
        raise OutputError(
            f'Could not save "{path.name}". Check the folder is writable.', repr(exc)
        ) from exc


def _build(data: str, error_correction: ErrorCorrection) -> qrcode.QRCode:  # type: ignore[type-arg]
    if not data.strip():
        raise InvalidInputError("Type some text or a link first.")
    qr = qrcode.QRCode(
        error_correction=_LEVELS[error_correction], box_size=1, border=QUIET_ZONE_MODULES
    )
    qr.add_data(data)
    try:
        qr.make(fit=True)
    except (DataOverflowError, ValueError) as exc:
        raise InvalidInputError(
            "That's too much text for one QR code. Try a shorter link or message.", repr(exc)
        ) from exc
    return qr


def _escape_wifi(value: str) -> str:
    return "".join(f"\\{char}" if char in _WIFI_SPECIAL_CHARS else char for char in value)


def _escape_vcard(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace(";", "\\;")
        .replace("\r\n", "\\n")
        .replace("\n", "\\n")
    )
