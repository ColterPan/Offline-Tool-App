"""Helpers for property-driven QSS styling."""

from PySide6.QtWidgets import QWidget


def set_style_property(widget: QWidget, name: str, value: str | bool) -> None:
    """Set a dynamic property and re-apply the stylesheet so selectors like [state="error"] update."""
    widget.setProperty(name, value)
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
