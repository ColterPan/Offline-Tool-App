"""Rounded panel used to group related controls."""

from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QWidget


class Card(QFrame):
    def __init__(self, title: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(18, 16, 18, 16)
        self.layout_.setSpacing(10)
        if title:
            heading = QLabel(title)
            heading.setProperty("role", "section")
            self.layout_.addWidget(heading)

    def add(self, widget: QWidget) -> None:
        self.layout_.addWidget(widget)
