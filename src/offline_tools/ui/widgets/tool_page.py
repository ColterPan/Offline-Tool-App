"""Common layout for every tool: title, one-line summary, body, result banner."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from offline_tools.ui.widgets.result_banner import ResultBanner

PAGE_MARGIN = 32
MAX_CONTENT_WIDTH = 820


class ToolPage(QWidget):
    def __init__(self, title: str, summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageRoot")

        content = QWidget()
        content.setMaximumWidth(MAX_CONTENT_WIDTH)
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self.body.setSpacing(14)

        heading = QLabel(title)
        heading.setProperty("role", "title")
        heading.setAccessibleName(title)
        description = QLabel(summary)
        description.setProperty("role", "muted")
        description.setWordWrap(True)
        self.banner = ResultBanner()

        self.body.addWidget(heading)
        self.body.addWidget(description)
        self.body.addSpacing(6)
        self._insert_at = self.body.count()
        self.body.addWidget(self.banner)
        self.body.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    def add_content(self, widget: QWidget) -> None:
        """Add a widget above the result banner."""
        self.body.insertWidget(self._insert_at, widget)
        self._insert_at += 1
