"""Design tokens. Change colours, radius and spacing here; the stylesheet is generated from them."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Palette:
    name: str
    is_dark: bool
    window: str
    surface: str
    surface_alt: str
    sidebar: str
    border: str  # decorative: card outlines, dividers
    control_border: str  # inputs, checkboxes: at least 3:1 against surface (WCAG 1.4.11)
    text: str
    text_muted: str
    accent: str
    accent_hover: str
    accent_text: str
    selection: str
    success: str
    success_bg: str
    warning: str
    warning_bg: str
    danger: str
    danger_bg: str


LIGHT = Palette(
    name="light",
    is_dark=False,
    window="#F6F7F9",
    surface="#FFFFFF",
    surface_alt="#EEF1F5",
    sidebar="#ECEFF3",
    border="#D9DEE5",
    control_border="#7D8796",
    text="#1B1F24",
    text_muted="#5B6573",
    accent="#2563EB",
    accent_hover="#1D4ED8",
    accent_text="#FFFFFF",
    selection="#DBE6FD",
    success="#166534",
    success_bg="#E7F6EC",
    warning="#8A4B00",
    warning_bg="#FFF4E0",
    danger="#B91C1C",
    danger_bg="#FDECEC",
)

DARK = Palette(
    name="dark",
    is_dark=True,
    window="#16181C",
    surface="#1F2227",
    surface_alt="#272B31",
    sidebar="#1B1D21",
    border="#353A42",
    control_border="#7A8491",
    text="#E6E8EB",
    text_muted="#9AA3AE",
    accent="#60A5FA",
    accent_hover="#93C5FD",
    accent_text="#0B1220",
    selection="#1E3A5F",
    success="#4ADE80",
    success_bg="#15291D",
    warning="#FBBF24",
    warning_bg="#33270F",
    danger="#F87171",
    danger_bg="#3A1C1C",
)

RADIUS = 10
RADIUS_SMALL = 6
FONT_SIZE_PT = 10
TITLE_SIZE_PT = 18
SIDEBAR_WIDTH = 230
