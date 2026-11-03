"""Read QR codes from photos and screenshots (zxing-cpp)."""

from pathlib import Path

import zxingcpp
from PIL import Image

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.images import open_image

NO_CODE_MESSAGE = "No QR code found. Try a sharper, closer or better-lit picture."


def find_qr_codes(img: Image.Image) -> tuple[str, ...]:
    """Every distinct QR code text in the image, in reading order; empty if none."""
    # Built per call: a module-level zxing object triggers leak warnings at interpreter exit.
    formats = zxingcpp.BarcodeFormats(
        (zxingcpp.BarcodeFormat.QRCode, zxingcpp.BarcodeFormat.MicroQRCode)
    )
    results = zxingcpp.read_barcodes(img.convert("RGB"), formats=formats)
    texts = [result.text for result in results if result.valid and result.text]
    return tuple(dict.fromkeys(texts))  # de-duplicate, keep order


def decode_qr_codes(img: Image.Image) -> tuple[str, ...]:
    texts = find_qr_codes(img)
    if not texts:
        raise InvalidInputError(NO_CODE_MESSAGE)
    return texts


def decode_qr_file(path: Path) -> tuple[str, ...]:
    return decode_qr_codes(open_image(path))
