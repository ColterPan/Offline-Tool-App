"""About and privacy promises. Keep these statements true: they are the product."""

from PySide6.QtWidgets import QLabel, QWidget

from offline_tools import APP_NAME, SOURCE_URL, __version__
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.tool_page import ToolPage

PRIVACY_POINTS = (
    "Every tool runs on this computer. Your files are never uploaded.",
    "No account, no ads, no tracking or analytics.",
    "The app does not connect to the internet. Any optional download added in future "
    "(such as the background-removal model) will always ask you first.",
)


class AboutPage(ToolPage):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(APP_NAME, f"Version {__version__}", parent)

        privacy = Card("Your privacy")
        for point in PRIVACY_POINTS:
            label = QLabel(f"•  {point}")
            label.setWordWrap(True)
            privacy.add(label)
        self.add_content(privacy)

        source = Card("Free and open source")
        text = QLabel(
            "Released under the GNU GPL v3. Anyone can read the code to check these promises: "
            f'<a href="{SOURCE_URL}">{SOURCE_URL}</a>'
        )
        text.setWordWrap(True)
        text.setOpenExternalLinks(True)
        source.add(text)
        self.add_content(source)
