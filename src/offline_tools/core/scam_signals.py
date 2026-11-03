"""Warning-sign lists used by the QR / link checker. Heuristics only: keep them up to date.

Everything here works offline. The checker can't look up live scam databases, so it looks
for the patterns scam links commonly use.
"""

# Brands scammers impersonate in Singapore, with the domains they really use.
# A link that mentions the brand but isn't on one of these domains is flagged.
OFFICIAL_DOMAINS: dict[str, tuple[str, ...]] = {
    "DBS": ("dbs.com.sg", "dbs.com"),
    "POSB": ("posb.com.sg",),
    "OCBC": ("ocbc.com",),
    "UOB": ("uob.com.sg", "uobgroup.com"),
    "SingPost": ("singpost.com",),
    "Shopee": ("shopee.sg", "shopee.com"),
    "Lazada": ("lazada.sg", "lazada.com"),
    "Carousell": ("carousell.sg", "carousell.com"),
    "Grab": ("grab.com",),
}

# Government services that only ever live on .gov.sg.
GOVERNMENT_BRANDS: dict[str, str] = {
    "singpass": "Singpass",
    "cpf": "CPF",
    "iras": "IRAS",
    "hdb": "HDB",
}

GOVERNMENT_SUFFIX = "gov.sg"

URL_SHORTENERS = frozenset(
    {
        "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd", "buff.ly", "rebrand.ly",
        "cutt.ly", "shorturl.at", "rb.gy", "tiny.cc", "s.id", "t.ly", "lnkd.in", "qrco.de",
        "shorturl.asia", "linktr.ee",
    }
)  # fmt: skip

# Top-level domains that are cheap and disproportionately used by scam sites.
RISKY_TLDS = frozenset(
    {
        "zip", "mov", "top", "xyz", "click", "country", "gq", "tk", "ml", "cf", "ga", "work",
        "rest", "cam", "icu", "sbs", "cfd", "buzz", "monster", "cyou", "lol", "quest", "support",
    }
)  # fmt: skip

# Files that install or run programs.
APP_EXTENSIONS = frozenset({"apk", "xapk", "apks", "ipa"})
PROGRAM_EXTENSIONS = frozenset(
    {
        "exe", "msi", "bat", "cmd", "scr", "pif", "js", "jse", "vbs", "vbe", "wsf", "ps1",
        "jar", "hta", "lnk", "reg", "dll", "dmg", "pkg", "appx", "msix", "iso", "img", "vhd",
    }
)  # fmt: skip
ARCHIVE_EXTENSIONS = frozenset({"zip", "rar", "7z", "gz", "tar", "tgz", "cab"})
MACRO_EXTENSIONS = frozenset({"docm", "xlsm", "pptm"})

# Schemes that run code instead of opening a page.
CODE_SCHEMES = frozenset({"javascript", "data", "vbscript", "file"})
WEB_SCHEMES = frozenset({"http", "https"})

MAX_NORMAL_LABELS = 4  # a.b.c.example.com has 5
MAX_NORMAL_HYPHENS = 3
LONG_URL_CHARS = 200
