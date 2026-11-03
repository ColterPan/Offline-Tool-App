"""Every tool the app offers. To add one, see docs/adding-a-tool.md."""

from offline_tools.registry import Category, Tool
from offline_tools.ui.tools.hash_checker import HashCheckerPage

ALL_TOOLS: tuple[Tool, ...] = (
    Tool(
        id="file-hash",
        name="Check File Hash",
        summary="Get a file's SHA-256 fingerprint and confirm a download wasn't tampered with.",
        category=Category.EVERYDAY,
        page_factory=HashCheckerPage,
        keywords=("sha256", "sha-256", "checksum", "verify", "md5", "integrity", "download"),
    ),
)
