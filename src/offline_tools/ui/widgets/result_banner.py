"""Inline success/error message with an optional 'Open folder' button."""

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget

from offline_tools.ui.widgets.style import set_style_property


class ResultBanner(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ResultBanner")
        self._folder: Path | None = None

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.open_folder_button = QPushButton("Open folder")
        self.open_folder_button.clicked.connect(self._open_folder)

        layout = QHBoxLayout(self)
        layout.addWidget(self.message, stretch=1)
        layout.addWidget(self.open_folder_button)
        self.clear()

    @property
    def state(self) -> str:
        return str(self.property("state") or "")

    def show_success(self, text: str, folder: Path | None = None) -> None:
        self._show("success", f"✓  {text}", folder)

    def show_error(self, text: str) -> None:
        self._show("error", f"⚠  {text}", None)

    def clear(self) -> None:
        self._folder = None
        set_style_property(self, "state", "")
        self.hide()

    def _show(self, state: str, text: str, folder: Path | None) -> None:
        self._folder = folder
        self.message.setText(text)
        set_style_property(self, "state", state)
        set_style_property(self.message, "state", state)
        self.open_folder_button.setVisible(folder is not None)
        self.show()

    def _open_folder(self) -> None:
        if self._folder is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._folder)))
