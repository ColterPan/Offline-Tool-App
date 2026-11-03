"""List of chosen files with reorder / remove buttons (drag to reorder works too)."""

from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

LIST_MIN_HEIGHT = 150
PATH_ROLE = Qt.ItemDataRole.UserRole


class FileList(QWidget):
    changed = Signal()

    def __init__(self, *, reorderable: bool = True, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._reorderable = reorderable
        self.list = QListWidget()
        self.list.setAccessibleName("Chosen files")
        self.list.setMinimumHeight(LIST_MIN_HEIGHT)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        if reorderable:
            self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
            self.list.model().rowsMoved.connect(lambda *_: self.changed.emit())
        self.list.currentRowChanged.connect(lambda _row: self._update_buttons())

        self.count_label = QLabel()
        self.count_label.setProperty("role", "muted")
        self.up_button = QPushButton("Move up")
        self.down_button = QPushButton("Move down")
        self.remove_button = QPushButton("Remove")
        self.clear_button = QPushButton("Clear all")
        self.up_button.clicked.connect(lambda: self.move_current(-1))
        self.down_button.clicked.connect(lambda: self.move_current(1))
        self.remove_button.clicked.connect(self.remove_current)
        self.clear_button.clicked.connect(self.clear)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.addWidget(self.count_label, stretch=1)
        if reorderable:
            buttons.addWidget(self.up_button)
            buttons.addWidget(self.down_button)
        buttons.addWidget(self.remove_button)
        buttons.addWidget(self.clear_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.list)
        layout.addLayout(buttons)
        self.changed.connect(self._update_buttons)
        self._update_buttons()

    def paths(self) -> list[Path]:
        return [Path(str(self.list.item(row).data(PATH_ROLE))) for row in range(self.list.count())]

    def add_paths(self, paths: Iterable[Path]) -> None:
        """Append files, skipping ones already in the list."""
        existing = {p.resolve() for p in self.paths()}
        for path in paths:
            if path.resolve() in existing:
                continue
            existing.add(path.resolve())
            item = QListWidgetItem(path.name)
            item.setToolTip(str(path))
            item.setData(PATH_ROLE, str(path))
            self.list.addItem(item)
        self.changed.emit()

    def move_current(self, offset: int) -> None:
        row = self.list.currentRow()
        target = row + offset
        if row < 0 or not 0 <= target < self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self.changed.emit()

    def remove_current(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self.list.takeItem(row)
            self.changed.emit()

    def clear(self) -> None:
        self.list.clear()
        self.changed.emit()

    def _update_buttons(self) -> None:
        count = self.list.count()
        row = self.list.currentRow()
        self.count_label.setText("No files added yet." if count == 0 else f"{count} file(s)")
        self.up_button.setEnabled(row > 0)
        self.down_button.setEnabled(0 <= row < count - 1)
        self.remove_button.setEnabled(row >= 0)
        self.clear_button.setEnabled(count > 0)
