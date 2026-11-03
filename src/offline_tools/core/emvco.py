"""Read EMVCo merchant QR codes (the format behind SGQR and PayNow QR codes).

The payload is a list of tag-length-value fields, e.g. "5917TAN AH KOW HAWKER" is tag 59
(merchant name), length 17. The last field (tag 63) is a CRC-16 checksum of everything before
it, so an edited code (a scam sticker typed up by hand, say) usually fails the check.
"""

from dataclasses import dataclass

CRC_TAG = "63"
CRC_PREFIX_LEN = 4  # "6304"
MERCHANT_ACCOUNT_TAGS = range(26, 52)  # each payment app has its own block in this range
CURRENCIES = {"702": "SGD", "840": "USD", "458": "MYR"}
PAYNOW_PROXY_TYPES = {"0": "Mobile", "2": "UEN"}


@dataclass(frozen=True)
class PaymentInfo:
    merchant_name: str | None
    city: str | None
    amount: str | None  # None: the payer types the amount
    currency: str | None
    schemes: tuple[str, ...]  # e.g. ("SG.PAYNOW", "COM.GRAB")
    paynow_target: str | None  # "UEN 201912345K" / "Mobile +6591234567"
    reference: str | None
    checksum_valid: bool


def parse_tlv(data: str) -> list[tuple[str, str]]:
    """Split a TLV string into (tag, value) pairs. Raises ValueError if it is malformed."""
    fields: list[tuple[str, str]] = []
    index = 0
    while index < len(data):
        header = data[index : index + 4]
        if len(header) < 4 or not header.isdigit():
            raise ValueError(f"bad TLV header at {index}: {header!r}")
        tag, length = header[:2], int(header[2:])
        value = data[index + 4 : index + 4 + length]
        if len(value) != length:
            raise ValueError(f"TLV field {tag} is truncated")
        fields.append((tag, value))
        index += 4 + length
    return fields


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE (poly 0x1021, initial 0xFFFF), as EMVCo specifies."""
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return crc


def parse_payment(payload: str) -> PaymentInfo:
    """Raises ValueError if the payload isn't a well-formed EMVCo QR."""
    fields = dict(parse_tlv(payload))
    schemes: list[str] = []
    paynow_target: str | None = None
    for tag, value in parse_tlv(payload):
        if int(tag) not in MERCHANT_ACCOUNT_TAGS:
            continue
        account = dict(parse_tlv(value))
        scheme = account.get("00", "")
        if scheme:
            schemes.append(scheme)
        if scheme.upper() == "SG.PAYNOW" and "02" in account:
            kind = PAYNOW_PROXY_TYPES.get(account.get("01", ""), "ID")
            paynow_target = f"{kind} {account['02']}"
    additional = dict(parse_tlv(fields["62"])) if "62" in fields else {}
    return PaymentInfo(
        merchant_name=fields.get("59"),
        city=fields.get("60"),
        amount=fields.get("54"),
        currency=CURRENCIES.get(fields.get("53", ""), fields.get("53")),
        schemes=tuple(schemes),
        paynow_target=paynow_target,
        reference=additional.get("01") or additional.get("05"),
        checksum_valid=_checksum_valid(payload, fields),
    )


def _checksum_valid(payload: str, fields: dict[str, str]) -> bool:
    expected = fields.get(CRC_TAG)
    if expected is None or not payload.endswith(expected):
        return False
    signed_part = payload[: -len(expected)]
    if not signed_part.endswith(CRC_TAG + "04"):
        return False
    return f"{crc16_ccitt(signed_part.encode()):04X}" == expected.upper()
