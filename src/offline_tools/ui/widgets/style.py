"""Helpers for property-driven QSS styling."""

from PySide6.QtWidgets import QWidget


def set_style_property(widget: QWidget, name: str, value: str | bool) -> None:
    """Set a property and re-polish, so QSS selectors like [state="error"] take effect."""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
