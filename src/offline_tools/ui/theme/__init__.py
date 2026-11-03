"""Light/dark theming. 'System' follows the OS setting, including live changes."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

from offline_tools.settings import ThemeMode
from offline_tools.ui.theme.stylesheet import build_stylesheet
from offline_tools.ui.theme.tokens import DARK, LIGHT, Palette

__all__ = ["DARK", "LIGHT", "Palette", "apply_theme", "resolve_palette"]


def resolve_palette(mode: ThemeMode, app: QGuiApplication) -> Palette:
    if mode is ThemeMode.LIGHT:
        return LIGHT
    if mode is ThemeMode.DARK:
        return DARK
    return DARK if app.styleHints().colorScheme() is Qt.ColorScheme.Dark else LIGHT


def apply_theme(app: QApplication, mode: ThemeMode) -> Palette:
    palette = resolve_palette(mode, app)
    app.setStyle("Fusion")  # same look on Windows and macOS; QSS styles on top of it
    app.setPalette(_to_qpalette(palette))
    app.setStyleSheet(build_stylesheet(palette))
    return palette


def _to_qpalette(p: Palette) -> QPalette:
    """Native dialogs (file pickers, message boxes) use QPalette rather than QSS."""
    qp = QPalette()
    roles = {
        QPalette.ColorRole.Window: p.window,
        QPalette.ColorRole.WindowText: p.text,
        QPalette.ColorRole.Base: p.surface,
        QPalette.ColorRole.AlternateBase: p.surface_alt,
        QPalette.ColorRole.Text: p.text,
        QPalette.ColorRole.Button: p.surface,
        QPalette.ColorRole.ButtonText: p.text,
        QPalette.ColorRole.Highlight: p.accent,
        QPalette.ColorRole.HighlightedText: p.accent_text,
        QPalette.ColorRole.ToolTipBase: p.surface,
        QPalette.ColorRole.ToolTipText: p.text,
        QPalette.ColorRole.PlaceholderText: p.text_muted,
        QPalette.ColorRole.Link: p.accent,
    }
    for role, colour in roles.items():
        qp.setColor(role, QColor(colour))
    qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(p.text_muted))
    qp.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(p.text_muted))
    return qp
