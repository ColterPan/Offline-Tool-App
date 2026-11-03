"""Settings: theme, where results are saved, and the log folder."""

import logging
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QRadioButton,
    QWidget,
)

from offline_tools.settings import OutputMode, ThemeMode
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.tool_page import ToolPage

logger = logging.getLogger(__name__)

THEME_LABELS = {
    ThemeMode.SYSTEM: "Match system",
    ThemeMode.LIGHT: "Light",
    ThemeMode.DARK: "Dark",
}


class SettingsPage(ToolPage):
    theme_changed = Signal(object)  # ThemeMode

    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__("Settings", "Preferences are saved on this computer only.", parent)
        self._settings = context.settings
        self._log_dir = context.log_dir
        self.add_content(self._build_appearance())
        self.add_content(self._build_output())
        self.add_content(self._build_logs())

    def _build_appearance(self) -> Card:
        card = Card("Appearance")
        self.theme_combo = QComboBox()
        self.theme_combo.setAccessibleName("Theme")
        for mode, label in THEME_LABELS.items():
            self.theme_combo.addItem(label, mode)
        self.theme_combo.setCurrentIndex(list(THEME_LABELS).index(self._settings.theme))
        self.theme_combo.currentIndexChanged.connect(self._on_theme_selected)
        card.add(self.theme_combo)
        return card

    def _build_output(self) -> Card:
        card = Card("Save results")
        self.next_to_input_radio = QRadioButton("Next to the original file")
        self.folder_radio = QRadioButton("Always in this folder:")
        self.folder_edit = QLineEdit()
        self.folder_edit.setReadOnly(True)
        self.folder_edit.setPlaceholderText("No folder chosen")
        self.folder_edit.setAccessibleName("Output folder")
        folder = self._settings.output_folder
        self.folder_edit.setText(str(folder) if folder else "")
        choose = QPushButton("Choose…")
        choose.clicked.connect(self._choose_folder)

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(24, 0, 0, 0)
        row_layout.addWidget(self.folder_edit, stretch=1)
        row_layout.addWidget(choose)

        is_folder_mode = self._settings.output_mode is OutputMode.FOLDER
        self.folder_radio.setChecked(is_folder_mode)
        self.next_to_input_radio.setChecked(not is_folder_mode)
        self.folder_radio.toggled.connect(self._on_output_mode_toggled)

        note = QLabel("Your original files are never changed or overwritten.")
        note.setProperty("role", "muted")
        for widget in (self.next_to_input_radio, self.folder_radio, row, note):
            card.add(widget)
        return card

    def _build_logs(self) -> Card:
        card = Card("Troubleshooting")
        path = QLabel(f"Log files: {self._log_dir}")
        path.setProperty("role", "muted")
        path.setWordWrap(True)
        open_logs = QPushButton("Open log folder")
        open_logs.clicked.connect(
            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._log_dir)))
        )
        card.add(path)
        card.add(open_logs)
        return card

    def _on_theme_selected(self, index: int) -> None:
        # Qt stores the enum as a plain string, so convert it back.
        raw = self.theme_combo.itemData(index)
        try:
            mode = ThemeMode(raw)
        except ValueError:
            logger.warning("Unknown theme option %r", raw)
            return
        self.theme_changed.emit(mode)

    def _on_output_mode_toggled(self, folder_mode: bool) -> None:
        if folder_mode and self._settings.output_folder is None and not self._choose_folder():
            self.next_to_input_radio.setChecked(True)
            return
        self._settings.set_output_mode(
            OutputMode.FOLDER if folder_mode else OutputMode.NEXT_TO_INPUT
        )

    def _choose_folder(self) -> bool:
        chosen = QFileDialog.getExistingDirectory(self, "Choose where to save results")
        if not chosen:
            return False
        self.set_output_folder(Path(chosen))
        return True

    def set_output_folder(self, folder: Path) -> None:
        self._settings.set_output_folder(folder)
        self.folder_edit.setText(str(folder))
        self.folder_radio.setChecked(True)
