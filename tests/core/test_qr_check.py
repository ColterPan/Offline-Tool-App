import pytest

from offline_tools.core.qr_check import QrKind, Severity, Verdict, analyse
from tests.core.test_emvco import build_paynow_payload


@pytest.mark.parametrize(
    ("url", "verdict", "hint"),
    [
        ("https://www.gov.sg/", Verdict.OK, "Singapore Government"),
        ("https://go.gov.sg/abc", Verdict.OK, "Singapore Government"),
        ("https://www.singpass.gov.sg/main", Verdict.OK, "Singapore Government"),
        ("https://www.dbs.com.sg/personal", Verdict.OK, "official DBS"),
        ("https://example.com/menu", Verdict.OK, ""),
        ("http://example.com", Verdict.CAUTION, "not encrypted"),
        ("https://bit.ly/3xYz", Verdict.CAUTION, "short link"),
        ("https://secure-update.top/", Verdict.CAUTION, ".top"),
        ("https://example.com/files/photos.zip", Verdict.CAUTION, "compressed file"),
        ("https://dbs-sg-secure-login.com/", Verdict.DANGER, "DBS"),
        ("https://singpass-verify.com/login", Verdict.DANGER, "Singpass"),
        ("https://gov.sg.claim-refund.net/", Verdict.DANGER, "government"),
        ("https://192.168.1.10/login", Verdict.DANGER, "IP address"),
        ("https://www.dbs.com.sg@evil.example/", Verdict.DANGER, "evil.example"),
        ("https://xn--dbs-4na.com/", Verdict.DANGER, "look-alike"),
        ("https://example.com/app/update.apk", Verdict.DANGER, "app"),
        ("https://example.com/dl.php?file=setup.exe", Verdict.DANGER, ".exe"),
        ("javascript:alert(1)", Verdict.DANGER, "run code"),
    ],
)
def test_link_checks(url: str, verdict: Verdict, hint: str) -> None:
    report = analyse(url)

    assert report.kind is QrKind.LINK
    assert report.verdict is verdict, [f.message for f in report.findings]
    assert hint.lower() in " ".join(f.message for f in report.findings).lower()


def test_link_without_scheme_is_treated_as_website() -> None:
    report = analyse("www.example.com/promo")

    assert report.kind is QrKind.LINK
    assert ("Website", "www.example.com") in report.details


def test_dangerous_findings_come_first() -> None:
    report = analyse("http://dbs-login.top/x.apk")

    severities = [f.severity for f in report.findings]
    assert severities == sorted(severities, reverse=True)
    assert severities[0] is Severity.DANGER


def test_wifi_code() -> None:
    report = analyse("WIFI:T:WPA;S:Cafe\\;Guest;P:secret;;")

    assert report.kind is QrKind.WIFI
    assert ("Network", "Cafe;Guest") in report.details
    assert report.verdict is Verdict.OK


def test_open_wifi_is_caution() -> None:
    assert analyse("WIFI:T:nopass;S:Free;;").verdict is Verdict.CAUTION


def test_payment_code_shows_who_you_pay() -> None:
    report = analyse(build_paynow_payload())

    assert report.kind is QrKind.PAYMENT
    assert ("Pays to", "TAN AH KOW HAWKER") in report.details
    assert ("Amount", "SGD 4.50") in report.details
    assert report.verdict is Verdict.CAUTION  # always: check the name before paying


def test_tampered_payment_code_is_dangerous() -> None:
    payload = build_paynow_payload().replace("TAN AH KOW", "SCAM PTE L")

    assert analyse(payload).verdict is Verdict.DANGER


@pytest.mark.parametrize(
    ("payload", "kind"),
    [
        ("tel:+6591234567", QrKind.PHONE),
        ("SMSTO:+6591234567:hello", QrKind.SMS),
        ("mailto:hello@example.com", QrKind.EMAIL),
        ("BEGIN:VCARD\r\nVERSION:3.0\r\nFN:Ali\r\nEND:VCARD", QrKind.CONTACT),
        ("Table 12", QrKind.TEXT),
    ],
)
def test_other_kinds(payload: str, kind: QrKind) -> None:
    assert analyse(payload).kind is kind


def test_plain_text_is_ok() -> None:
    assert analyse("Table 12").verdict is Verdict.OK


def test_text_containing_a_link_checks_the_link() -> None:
    report = analyse("Claim your refund now: https://singpass-refund.com/x")

    assert report.kind is QrKind.LINK
    assert report.verdict is Verdict.DANGER
