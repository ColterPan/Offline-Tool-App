"""Explain what a QR code (or pasted link) does and flag common scam warning signs.

Runs fully offline, so it can't consult live scam lists. It reports warning signs, never a
guarantee of safety, and the UI says so.
"""

import ipaddress
import re
from dataclasses import dataclass
from enum import IntEnum, StrEnum
from urllib.parse import parse_qsl, unquote, urlsplit

from offline_tools.core import scam_signals as signals
from offline_tools.core.emvco import parse_payment

_URL_IN_TEXT = re.compile(r"https?://\S+", re.IGNORECASE)
_BARE_DOMAIN = re.compile(r"^(www\.)?[a-z0-9-]+(\.[a-z0-9-]+)+(/\S*)?$", re.IGNORECASE)
_HOST_TOKENS = re.compile(r"[.\-_]")


class Severity(IntEnum):
    INFO = 0
    CAUTION = 1
    DANGER = 2


class Verdict(StrEnum):
    OK = "No warning signs found"
    CAUTION = "Be careful"
    DANGER = "Likely dangerous"


class QrKind(StrEnum):
    LINK = "Website link"
    WIFI = "Wi-Fi login"
    PAYMENT = "Payment (SGQR / PayNow)"
    CONTACT = "Contact card"
    PHONE = "Phone call"
    SMS = "Text message"
    EMAIL = "Email"
    APP_LINK = "Opens an app"
    TEXT = "Plain text"


@dataclass(frozen=True)
class Finding:
    severity: Severity
    message: str


@dataclass(frozen=True)
class QrReport:
    payload: str
    kind: QrKind
    summary: str
    details: tuple[tuple[str, str], ...]
    findings: tuple[Finding, ...]  # most severe first

    @property
    def verdict(self) -> Verdict:
        worst = max((f.severity for f in self.findings), default=Severity.INFO)
        return {
            Severity.INFO: Verdict.OK,
            Severity.CAUTION: Verdict.CAUTION,
            Severity.DANGER: Verdict.DANGER,
        }[worst]


def analyse(payload: str) -> QrReport:
    text = payload.strip()
    lower = text.lower()
    if lower.startswith("wifi:"):
        return _wifi(text)
    if text.startswith("000201"):
        return _payment(text)
    if lower.startswith("begin:vcard"):
        return _contact(text)
    if lower.startswith("tel:"):
        number = text[4:]
        return _report(text, QrKind.PHONE, f"Calls {number}", [("Number", number)], [])
    if lower.startswith(("smsto:", "sms:")):
        return _sms(text)
    if lower.startswith("mailto:"):
        address = unquote(text[7:].split("?", 1)[0])
        return _report(text, QrKind.EMAIL, f"Writes an email to {address}", [("To", address)], [])
    scheme = urlsplit(text).scheme.lower()
    if scheme in signals.WEB_SCHEMES or scheme in signals.CODE_SCHEMES:
        return _link(text, text)
    if _BARE_DOMAIN.match(text):
        return _link(text, f"https://{text}")
    if scheme and re.fullmatch(r"[a-z][a-z0-9+.-]*", scheme) and ":" in text and " " not in text:
        return _app_link(text, scheme)
    embedded = _URL_IN_TEXT.search(text)
    if embedded:
        return _link(text, embedded.group(0))
    return _report(
        text,
        QrKind.TEXT,
        "Just text. Scanning it won't open anything.",
        [("Text", text)],
        [],
    )


# ---- links -------------------------------------------------------------------------


def _link(payload: str, url: str) -> QrReport:
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme in signals.CODE_SCHEMES:
        return _report(
            payload,
            QrKind.LINK,
            "Tries to run code on your device",
            [("Content", url[:120])],
            [
                _danger(
                    "This code tries to run code on your device instead of "
                    "opening a website. Don't open it.",
                )
            ],
        )
    host = (parts.hostname or "").rstrip(".")
    if not host:
        return _report(
            payload,
            QrKind.LINK,
            "A broken link",
            [("Link", url)],
            [_caution("This link has no website address.")],
        )
    findings = [
        *_host_findings(host, parts.netloc),
        *_scheme_findings(scheme),
        *_download_findings(parts.path, parts.query),
    ]
    if len(url) > signals.LONG_URL_CHARS:
        findings.append(_info("The link is unusually long, which can hide where it really goes."))
    details = [("Website", host), ("Full link", url), ("Encrypted", _yes_no(scheme == "https"))]
    return _report(payload, QrKind.LINK, f"Opens a website: {host}", details, findings)


def _host_findings(host: str, netloc: str) -> list[Finding]:
    findings: list[Finding] = []
    if "@" in netloc:
        findings.append(
            _danger(
                f"The real website is {host}. The text before "
                "'@' is there to make it look like another site."
            )
        )
    if _is_ip(host):
        findings.append(
            _danger(
                "It points to a bare IP address instead of a "
                "named website. Real businesses rarely do this."
            )
        )
        return findings
    if any(label.startswith("xn--") for label in host.split(".")):
        findings.append(
            _danger(
                f"The address uses look-alike characters "
                f"({_decode_idn(host)}) to imitate a real site."
            )
        )
    if _on_domain(host, signals.GOVERNMENT_SUFFIX):
        findings.append(_info("✓ This is a Singapore Government website (.gov.sg)."))
        return findings
    findings += _impersonation_findings(host)
    if host in signals.URL_SHORTENERS:
        findings.append(
            _caution(
                f"This is a short link ({host}). It hides where "
                "it really goes, and this app can't follow it "
                "without going online."
            )
        )
    tld = host.rsplit(".", 1)[-1]
    if tld in signals.RISKY_TLDS:
        findings.append(_caution(f"The address ends in .{tld}, which is often used by scam sites."))
    if (
        host.count(".") + 1 > signals.MAX_NORMAL_LABELS
        or host.count("-") > signals.MAX_NORMAL_HYPHENS
    ):
        findings.append(_caution("The website address is unusually long or complicated."))
    return findings


def _impersonation_findings(host: str) -> list[Finding]:
    tokens = set(_HOST_TOKENS.split(host))
    for brand, domains in signals.OFFICIAL_DOMAINS.items():
        if any(_on_domain(host, domain) for domain in domains):
            return [_info(f"✓ This is the official {brand} website.")]
        if brand.lower() in tokens or (len(brand) > 4 and brand.lower() in host):
            return [
                _danger(
                    f"It mentions {brand} but is NOT {brand}'s website "
                    f"(that's {domains[0]}). A classic scam trick."
                )
            ]
    for keyword, name in signals.GOVERNMENT_BRANDS.items():
        if keyword in tokens or (len(keyword) > 4 and keyword in host):
            return [
                _danger(
                    f"It mentions {name}, but real {name} websites always "
                    "end in .gov.sg. This one doesn't."
                )
            ]
    if {"gov", "sg"} <= tokens or "govsg" in tokens:
        return [
            _danger(
                "It pretends to be a Singapore government website, but "
                "real ones always end in .gov.sg."
            )
        ]
    return []


def _scheme_findings(scheme: str) -> list[Finding]:
    if scheme == "http":
        return [
            _caution(
                "The connection is not encrypted (http). Never enter "
                "passwords or card details on it."
            )
        ]
    return []


def _download_findings(path: str, query: str) -> list[Finding]:
    candidates = [unquote(path)] + [unquote(value) for _, value in parse_qsl(query)]
    for candidate in candidates:
        name = candidate.rstrip("/").rsplit("/", 1)[-1]
        if "." not in name:
            continue
        ext = name.rsplit(".", 1)[-1].lower()
        if ext in signals.APP_EXTENSIONS:
            return [
                _danger(
                    f"It downloads a phone app (.{ext}) from outside the "
                    "app store. Many banking scams start this way. Only "
                    "install apps from Google Play or the App Store."
                )
            ]
        if ext in signals.PROGRAM_EXTENSIONS:
            return [
                _danger(
                    f"It downloads a program (.{ext}). Programs from QR "
                    "codes or messages can take over your device."
                )
            ]
        if ext in signals.ARCHIVE_EXTENSIONS:
            return [
                _caution(
                    f"It downloads a compressed file (.{ext}). Scammers "
                    "hide harmful programs inside these."
                )
            ]
        if ext in signals.MACRO_EXTENSIONS:
            return [
                _caution(
                    f"It downloads an Office file with macros (.{ext}), "
                    "which can run code when opened."
                )
            ]
    return []


def _app_link(payload: str, scheme: str) -> QrReport:
    finding = _caution(
        f"It opens an app on your phone ({scheme}:) instead of a "
        "website. Only continue if you expected that."
    )
    return _report(
        payload, QrKind.APP_LINK, f"Opens an app ({scheme})", [("Link", payload)], [finding]
    )


# ---- other kinds -----------------------------------------------------------------


def _wifi(payload: str) -> QrReport:
    fields = _wifi_fields(payload[5:])
    network = fields.get("S", "")
    security = fields.get("T", "nopass") or "nopass"
    details = [("Network", network), ("Security", "None" if security == "nopass" else security)]
    if fields.get("P"):
        details.append(("Password", "•" * len(fields["P"])))
    findings = [
        _info(
            "Joins a Wi-Fi network. Only scan these in places you "
            "trust, such as your café or hotel."
        )
    ]
    if security == "nopass":
        findings.append(
            _caution(
                "This network has no password, so others on it "
                "may see what you do. Avoid banking on it."
            )
        )
    return _report(payload, QrKind.WIFI, f"Joins the Wi-Fi network “{network}”", details, findings)


def _wifi_fields(body: str) -> dict[str, str]:
    """Split 'T:WPA;S:name;P:pass;;' honouring backslash escapes."""
    fields: dict[str, str] = {}
    current, escaped = "", False
    for char in body:
        if escaped:
            current += char
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == ";":
            if ":" in current:
                key, value = current.split(":", 1)
                fields[key.upper()] = value
            current = ""
        else:
            current += char
    return fields


def _payment(payload: str) -> QrReport:
    try:
        info = parse_payment(payload)
    except ValueError:
        finding = _caution(
            "This looks like a payment code but it's damaged or not in the standard format."
        )
        return _report(payload, QrKind.PAYMENT, "An unreadable payment code", [], [finding])
    details = [("Pays to", info.merchant_name or "(no name in the code)")]
    if info.city:
        details.append(("City", info.city))
    amount = f"{info.currency or ''} {info.amount}".strip() if info.amount else "You type it in"
    details.append(("Amount", amount))
    if info.paynow_target:
        details.append(("PayNow", info.paynow_target))
    if info.schemes:
        details.append(("Payment apps", ", ".join(info.schemes)))
    if info.reference:
        details.append(("Reference", info.reference))
    findings = [
        _caution(
            "Before paying, check that the name above matches who "
            "you mean to pay. Scammers stick fake codes over real "
            "ones."
        )
    ]
    if not info.checksum_valid:
        findings.insert(
            0,
            _danger("The code's built-in checksum is wrong. It has probably been edited or faked."),
        )
    summary = f"Pays {info.merchant_name or 'an unnamed account'}"
    return _report(payload, QrKind.PAYMENT, summary, details, findings)


def _contact(payload: str) -> QrReport:
    wanted = {"FN": "Name", "TEL": "Phone", "EMAIL": "Email", "ORG": "Company", "URL": "Website"}
    details: list[tuple[str, str]] = []
    for line in payload.replace("\r\n", "\n").split("\n"):
        key, _, value = line.partition(":")
        label = wanted.get(key.split(";", 1)[0].upper())
        if label and value:
            details.append((label, value.replace("\\,", ",").replace("\\;", ";")))
    name = next((value for label, value in details if label == "Name"), "a contact")
    return _report(payload, QrKind.CONTACT, f"Saves {name} to your contacts", details, [])


def _sms(payload: str) -> QrReport:
    body = payload.split(":", 1)[1]
    number, _, message = (
        body.partition(":") if not body.startswith("+") or ":" in body else (body, "", "")
    )
    if "?" in number:  # sms:+65...?body=...
        number, _, query = number.partition("?")
        message = dict(parse_qsl(query)).get("body", message)
    details = [("To", number)] + ([("Message", message)] if message else [])
    finding = _caution(
        "Sends a text message. Check the number and message "
        "first. Some numbers charge you to text them."
    )
    return _report(payload, QrKind.SMS, f"Texts {number}", details, [finding])


# ---- helpers ---------------------------------------------------------------------


def _danger(message: str) -> Finding:
    return Finding(Severity.DANGER, message)


def _caution(message: str) -> Finding:
    return Finding(Severity.CAUTION, message)


def _info(message: str) -> Finding:
    return Finding(Severity.INFO, message)


def _report(
    payload: str,
    kind: QrKind,
    summary: str,
    details: list[tuple[str, str]],
    findings: list[Finding],
) -> QrReport:
    ordered = sorted(findings, key=lambda f: f.severity, reverse=True)
    return QrReport(payload, kind, summary, tuple(details), tuple(ordered))


def _on_domain(host: str, domain: str) -> bool:
    return host == domain or host.endswith("." + domain)


def _is_ip(host: str) -> bool:
    try:
        ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        return False
    return True


def _decode_idn(host: str) -> str:
    try:
        return host.encode("ascii").decode("idna")
    except UnicodeError:
        return host


def _yes_no(value: bool) -> str:
    return "Yes (https)" if value else "No"
