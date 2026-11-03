"""Drag-and-drop area with a Browse button. Emits the chosen file paths."""

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QFileDialog, QFrame, QLabel, QPushButton, QVBoxLayout, QWidget

from offline_tools.ui.widgets.style import set_style_property

MIN_HEIGHT = 170


class DropZone(QFrame):
    files_selected = Signal(list)  # list[Path]

    def __init__(
        self,
        *,
        prompt: str = "Drop a file here",
        extensions: Iterable[str] = (),
        multiple: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setMinimumHeight(MIN_HEIGHT)
        self._extensions = frozenset(ext.lower() for ext in extensions)
        self._multiple = multiple

        title = QLabel(prompt)
        title.setProperty("role", "section")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        hint = QLabel(self._hint_text())
        hint.setProperty("role", "muted")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.browse_button = QPushButton("Browse files…" if multiple else "Browse…")
        self.browse_button.setProperty("variant", "primary")
        self.browse_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.browse_button.clicked.connect(self._browse)

        layout = QVBoxLayout(self)
        layout.addStretch()
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addSpacing(8)
        layout.addWidget(self.browse_button, alignment=Qt.AlignmentFlag.AlignCenter)
        layout.addStretch()

    def accepted_paths(self, mime: QMimeData) -> list[Path]:
        """Local files from a drag that match the allowed extensions (folders are skipped)."""
        if not mime.hasUrls():
            return []
        paths = [Path(url.toLocalFile()) for url in mime.urls() if url.isLocalFile()]
        valid = [p for p in paths if p.is_file() and self._extension_ok(p)]
        return valid if self._multiple else valid[:1]

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.isEnabled() and self.accepted_paths(event.mimeData()):
            event.acceptProposedAction()
            set_style_property(self, "dragActive", True)
        else:
            event.ignore()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        set_style_property(self, "dragActive", False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        set_style_property(self, "dragActive", False)
        paths = self.accepted_paths(event.mimeData())
        if paths:
            event.acceptProposedAction()
            self.files_selected.emit(paths)

    def _browse(self) -> None:
        name_filter = self._dialog_filter()
        if self._multiple:
            names, _ = QFileDialog.getOpenFileNames(self, "Choose files", "", name_filter)
        else:
            name, _ = QFileDialog.getOpenFileName(self, "Choose a file", "", name_filter)
            names = [name] if name else []
        if names:
            self.files_selected.emit([Path(n) for n in names])

    def _extension_ok(self, path: Path) -> bool:
        return not self._extensions or path.suffix.lower() in self._extensions

    def _hint_text(self) -> str:
        if not self._extensions:
            return "Any file type · or click Browse"
        return f"{', '.join(sorted(self._extensions))} · or click Browse"

    def _dialog_filter(self) -> str:
        if not self._extensions:
            return "All files (*)"
        patterns = " ".join(f"*{ext}" for ext in sorted(self._extensions))
        return f"Supported files ({patterns})"
