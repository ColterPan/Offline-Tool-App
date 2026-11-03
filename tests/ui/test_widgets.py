from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl
from pytestqt.qtbot import QtBot

from offline_tools.ui.theme.stylesheet import build_stylesheet
from offline_tools.ui.theme.tokens import DARK, LIGHT
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
