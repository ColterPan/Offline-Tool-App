import pytest

from offline_tools.core.emvco import crc16_ccitt, parse_payment, parse_tlv


def _tlv(tag: str, value: str) -> str:
    return f"{tag}{len(value):02d}{value}"


def build_paynow_payload(name: str = "TAN AH KOW HAWKER", amount: str | None = "4.50") -> str:
    """A PayNow-style SGQR payload with a correct checksum (test helper)."""
    account = _tlv("00", "SG.PAYNOW") + _tlv("01", "2") + _tlv("02", "201912345K") + _tlv("03", "0")
    body = (
        _tlv("00", "01")
        + _tlv("01", "12")
        + _tlv("26", account)
        + _tlv("52", "0000")
        + _tlv("53", "702")
        + (_tlv("54", amount) if amount else "")
        + _tlv("58", "SG")
        + _tlv("59", name)
        + _tlv("60", "Singapore")
        + _tlv("62", _tlv("01", "INV-042"))
        + "6304"
    )
    return body + f"{crc16_ccitt(body.encode()):04X}"


def test_crc16_ccitt_false_check_value() -> None:
    assert crc16_ccitt(b"123456789") == 0x29B1


def test_parse_tlv_reads_fields_in_order() -> None:
    assert parse_tlv("0002AB0103XYZ") == [("00", "AB"), ("01", "XYZ")]


@pytest.mark.parametrize("bad", ["0005AB", "00X1A", "000"])
def test_parse_tlv_rejects_malformed_data(bad: str) -> None:
    with pytest.raises(ValueError):
        parse_tlv(bad)


def test_parse_payment_extracts_who_and_how_much() -> None:
    info = parse_payment(build_paynow_payload())

    assert info.merchant_name == "TAN AH KOW HAWKER"
    assert info.city == "Singapore"
    assert info.amount == "4.50"
    assert info.currency == "SGD"
    assert info.checksum_valid
    assert info.schemes == ("SG.PAYNOW",)
    assert info.paynow_target == "UEN 201912345K"
    assert info.reference == "INV-042"


def test_parse_payment_without_amount() -> None:
    info = parse_payment(build_paynow_payload(amount=None))

    assert info.amount is None


def test_parse_payment_detects_tampering() -> None:
    payload = build_paynow_payload().replace("TAN AH KOW", "SCAM PTE L")

    assert not parse_payment(payload).checksum_valid
