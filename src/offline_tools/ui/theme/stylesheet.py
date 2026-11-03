"""Qt stylesheet (QSS) built from the design tokens."""

from offline_tools.ui.theme.tokens import (
    FONT_SIZE_PT,
    RADIUS,
    RADIUS_SMALL,
    SIDEBAR_WIDTH,
    TITLE_SIZE_PT,
    Palette,
)


def build_stylesheet(p: Palette) -> str:
    return f"""
* {{ font-size: {FONT_SIZE_PT}pt; }}
QMainWindow, QWidget#PageRoot {{ background: {p.window}; color: {p.text}; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}

QLabel {{ color: {p.text}; background: transparent; }}
QLabel[role="title"] {{ font-size: {TITLE_SIZE_PT}pt; font-weight: 600; }}
QLabel[role="section"] {{ font-size: {FONT_SIZE_PT + 1}pt; font-weight: 600; margin-top: 8px; }}
QLabel[role="muted"] {{ color: {p.text_muted}; }}

QListWidget#Sidebar {{
    background: {p.sidebar}; border: none; border-right: 1px solid {p.border};
    padding: 12px 8px; min-width: {SIDEBAR_WIDTH}px; max-width: {SIDEBAR_WIDTH}px; outline: 0;
}}
QListWidget#Sidebar::item {{ padding: 8px 10px; border-radius: {RADIUS_SMALL}px; color: {p.text}; }}
QListWidget#Sidebar::item:disabled {{
    color: {p.text_muted}; font-weight: 600; padding-top: 14px; background: transparent;
}}
QListWidget#Sidebar::item:hover:!selected:enabled {{ background: {p.surface_alt}; }}
QListWidget#Sidebar::item:selected {{ background: {p.selection}; color: {p.text}; }}

QPushButton {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: {RADIUS_SMALL}px; padding: 7px 14px;
}}
QPushButton:hover {{ background: {p.surface_alt}; }}
QPushButton:focus {{ border: 2px solid {p.accent}; }}
QPushButton:disabled {{ color: {p.text_muted}; }}
QPushButton[variant="primary"] {{
    background: {p.accent}; color: {p.accent_text}; border: 1px solid {p.accent}; font-weight: 600;
}}
QPushButton[variant="primary"]:hover {{ background: {p.accent_hover}; }}

QPushButton#ToolCard {{
    background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px;
    padding: 14px; text-align: left;
}}
QPushButton#ToolCard:hover {{ border: 1px solid {p.accent}; background: {p.surface}; }}
QPushButton#ToolCard:focus {{ border: 2px solid {p.accent}; }}

QLineEdit, QComboBox, QPlainTextEdit {{
    background: {p.surface}; color: {p.text}; border: 1px solid {p.border};
    border-radius: {RADIUS_SMALL}px; padding: 6px 8px;
    selection-background-color: {p.accent}; selection-color: {p.accent_text};
}}
QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{ border: 2px solid {p.accent}; }}
QLineEdit[readOnly="true"] {{ background: {p.surface_alt}; }}
QComboBox QAbstractItemView {{
    background: {p.surface}; color: {p.text}; selection-background-color: {p.selection};
}}

QFrame#Card {{ background: {p.surface}; border: 1px solid {p.border}; border-radius: {RADIUS}px; }}
QFrame#DropZone {{
    background: {p.surface}; border: 2px dashed {p.border}; border-radius: {RADIUS}px;
}}
QFrame#DropZone[dragActive="true"] {{ border: 2px dashed {p.accent}; background: {p.selection}; }}

QFrame#ResultBanner {{ border-radius: {RADIUS_SMALL}px; padding: 4px; }}
QFrame#ResultBanner[state="success"] {{
    background: {p.success_bg}; border: 1px solid {p.success};
}}
QFrame#ResultBanner[state="error"] {{ background: {p.danger_bg}; border: 1px solid {p.danger}; }}
QLabel[state="success"] {{ color: {p.success}; font-weight: 600; }}
QLabel[state="error"] {{ color: {p.danger}; font-weight: 600; }}

QProgressBar {{
    background: {p.surface_alt}; border: none; border-radius: 4px; height: 8px; text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {p.accent}; border-radius: 4px; }}

QRadioButton, QCheckBox {{ color: {p.text}; background: transparent; spacing: 8px; }}
QToolTip {{ background: {p.surface}; color: {p.text}; border: 1px solid {p.border}; }}
"""
