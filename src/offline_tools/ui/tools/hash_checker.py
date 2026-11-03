"""Check File Hash: compute a checksum and compare it with a published one."""

from functools import partial
from pathlib import Path

from PySide6.QtGui import QFontDatabase, QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QWidget,
)

from offline_tools.core.hashing import hash_file, hashes_match
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.style import set_style_property
from offline_tools.ui.widgets.tool_page import ToolPage

ALGORITHM_LABELS = {
    "sha256": "SHA-256 (recommended)",
    "sha1": "SHA-1",
    "md5": "MD5",
}
PROGRESS_STEPS = 1000
MATCH_TEXT = "✓  Match. This file is exactly what the publisher released."
MISMATCH_TEXT = "✗  No match. The file may be corrupted or tampered with. Don't open it."


class HashCheckerPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Check File Hash",
            "Get a file's fingerprint (checksum) and compare it with the one published by the "
            "site you downloaded it from. If they match, the file hasn't been changed.",
            parent,
        )
        self._runner = context.runner
        self._file: Path | None = None

        self.drop_zone = DropZone(prompt="Drop any file here")
        self.drop_zone.files_selected.connect(lambda paths: self.select_file(paths[0]))
        self.add_content(self.drop_zone)
        self.add_content(self._build_result_card())

    @property
    def is_busy(self) -> bool:
        return not self.drop_zone.isEnabled()

    def select_file(self, path: Path) -> None:
        self._file = path
        self.file_label.setText(f"File: {path.name}")
        self._start()

    def _build_result_card(self) -> Card:
        card = Card("Result")
        self.file_label = QLabel("No file selected yet.")
        self.file_label.setProperty("role", "muted")

        self.algorithm_combo = QComboBox()
        self.algorithm_combo.setAccessibleName("Hash type")
        for algorithm, label in ALGORITHM_LABELS.items():
            self.algorithm_combo.addItem(label, algorithm)
        self.algorithm_combo.currentIndexChanged.connect(lambda _index: self._start())

        self.progress = QProgressBar()
        self.progress.setRange(0, PROGRESS_STEPS)
        self.progress.hide()

        mono = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.result_edit = QLineEdit()
        self.result_edit.setReadOnly(True)
        self.result_edit.setFont(mono)
        self.result_edit.setPlaceholderText("The hash will appear here")
        self.result_edit.setAccessibleName("Calculated hash")
        self.copy_button = QPushButton("Copy")
        self.copy_button.setEnabled(False)
        self.copy_button.clicked.connect(
            lambda: QGuiApplication.clipboard().setText(self.result_edit.text())
        )
        result_row = QWidget()
        row_layout = QHBoxLayout(result_row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.addWidget(self.result_edit, stretch=1)
        row_layout.addWidget(self.copy_button)

        self.expected_edit = QLineEdit()
        self.expected_edit.setFont(mono)
        self.expected_edit.setPlaceholderText("Paste the expected hash to compare (optional)")
        self.expected_edit.setAccessibleName("Expected hash")
        self.expected_edit.textChanged.connect(lambda _text: self._update_match())
        self.match_label = QLabel()
        self.match_label.setWordWrap(True)
        self.match_label.hide()

        for widget in (
            self.file_label,
            self.algorithm_combo,
            self.progress,
            result_row,
            self.expected_edit,
            self.match_label,
        ):
            card.add(widget)
        return card

    def _start(self) -> None:
        if self._file is None or self.is_busy:
            return
        algorithm = str(self.algorithm_combo.currentData())
        self.banner.clear()
        self.result_edit.clear()
        self._set_busy(True)
        self._runner.submit(
            partial(hash_file, self._file, algorithm),
            on_success=self._on_done,
            on_error=self._on_error,
            on_progress=self._on_progress,
        )

    def _on_progress(self, done: int, total: int) -> None:
        if total:
            self.progress.setValue(done * PROGRESS_STEPS // total)

    def _on_done(self, digest: object) -> None:
        self._set_busy(False)
        self.result_edit.setText(str(digest))
        self.copy_button.setEnabled(True)
        self._update_match()

    def _on_error(self, message: str, _detail: str) -> None:
        self._set_busy(False)
        self.banner.show_error(message)
        self._update_match()

    def _set_busy(self, busy: bool) -> None:
        self.drop_zone.setEnabled(not busy)
        self.algorithm_combo.setEnabled(not busy)
        self.copy_button.setEnabled(False)
        self.progress.setValue(0)
        self.progress.setVisible(busy)

    def _update_match(self) -> None:
        expected, actual = self.expected_edit.text(), self.result_edit.text()
        if not expected.strip() or not actual:
            self.match_label.hide()
            return
        matched = hashes_match(expected, actual)
        self.match_label.setText(MATCH_TEXT if matched else MISMATCH_TEXT)
        set_style_property(self.match_label, "state", "success" if matched else "error")
        self.match_label.show()
