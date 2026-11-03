"""Small helpers for building option rows consistently."""

from collections.abc import Iterable
from typing import Any

from PySide6.QtWidgets import QComboBox, QFormLayout, QWidget


def combo(options: Iterable[tuple[str, Any]], *, accessible_name: str) -> QComboBox:
    """A combo box of (label, value) pairs; read the value with currentData()."""
    box = QComboBox()
    box.setAccessibleName(accessible_name)
    for label, value in options:
        box.addItem(label, value)
    return box


def form(*rows: tuple[str, QWidget]) -> QWidget:
    """Label/field rows in a two-column layout."""
    container = QWidget()
    layout = QFormLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setVerticalSpacing(10)
    for label, field in rows:
        if label:  # unlabelled rows (checkboxes) keep their own text as the accessible name
            field.setAccessibleName(label.rstrip(":"))
        layout.addRow(label, field)
    return container
