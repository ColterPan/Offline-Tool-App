import re
from pathlib import Path

import pytest
from PySide6.QtCore import QMimeData, QUrl
from pytestqt.qtbot import QtBot

from offline_tools.ui.theme.stylesheet import build_stylesheet
from offline_tools.ui.theme.tokens import DARK, LIGHT, Palette
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.result_banner import ResultBanner


def _mime(*paths: Path) -> QMimeData:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    return mime


def test_drop_zone_filters_by_extension_and_skips_folders(qtbot: QtBot, tmp_path: Path) -> None:
    png, txt = tmp_path / "a.PNG", tmp_path / "b.txt"
    png.write_bytes(b"x")
    txt.write_bytes(b"x")
    zone = DropZone(extensions={".png"}, multiple=True)
    qtbot.addWidget(zone)

    assert zone.accepted_paths(_mime(png, txt, tmp_path)) == [png]


def test_drop_zone_single_mode_keeps_first_file(qtbot: QtBot, tmp_path: Path) -> None:
    first, second = tmp_path / "1.bin", tmp_path / "2.bin"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    zone = DropZone()
    qtbot.addWidget(zone)

    assert zone.accepted_paths(_mime(first, second)) == [first]


def test_drop_zone_ignores_non_url_drags(qtbot: QtBot) -> None:
    mime = QMimeData()
    mime.setText("just text")
    zone = DropZone()
    qtbot.addWidget(zone)

    assert zone.accepted_paths(mime) == []


def test_result_banner_states(qtbot: QtBot, tmp_path: Path) -> None:
    banner = ResultBanner()
    qtbot.addWidget(banner)
    assert banner.isHidden()

    banner.show_success("Saved", folder=tmp_path)
    assert banner.state == "success"
    assert not banner.open_folder_button.isHidden()

    banner.show_error("Nope")
    assert banner.state == "error"
    assert banner.open_folder_button.isHidden()

    banner.clear()
    assert banner.isHidden()


def test_stylesheets_use_their_palette() -> None:
    light, dark = build_stylesheet(LIGHT), build_stylesheet(DARK)

    assert LIGHT.accent in light
    assert DARK.accent in dark
    assert light != dark


def test_stylesheet_icons_exist_for_both_themes() -> None:
    for palette in (LIGHT, DARK):
        sheet = build_stylesheet(palette)
        icons = re.findall(r'url\("([^"]+)"\)', sheet)
        assert len(icons) == 2
        assert all(Path(icon).is_file() for icon in icons)


def _relative_luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    high, low = sorted((_relative_luminance(a), _relative_luminance(b)), reverse=True)
    return (high + 0.05) / (low + 0.05)


@pytest.mark.parametrize("palette", [LIGHT, DARK], ids=["light", "dark"])
def test_palette_meets_wcag_contrast(palette: Palette) -> None:
    # WCAG 2.2 AA: 4.5:1 for normal text, 3:1 for control outlines.
    assert _contrast(palette.text, palette.surface) >= 4.5
    assert _contrast(palette.text_muted, palette.surface) >= 4.5
    assert _contrast(palette.text_muted, palette.window) >= 4.5
    assert _contrast(palette.accent_text, palette.accent) >= 4.5
    assert _contrast(palette.success, palette.success_bg) >= 4.5
    assert _contrast(palette.danger, palette.danger_bg) >= 4.5
    assert _contrast(palette.control_border, palette.surface) >= 3
    assert _contrast(palette.accent, palette.surface) >= 3
