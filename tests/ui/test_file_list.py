from pathlib import Path

from pytestqt.qtbot import QtBot

from offline_tools.ui.widgets.file_list import FileList


def _files(tmp_path: Path, *names: str) -> list[Path]:
    paths = [tmp_path / name for name in names]
    for path in paths:
        path.write_bytes(b"x")
    return paths


def test_add_paths_skips_duplicates(qtbot: QtBot, tmp_path: Path) -> None:
    widget = FileList()
    qtbot.addWidget(widget)
    a, b = _files(tmp_path, "a.png", "b.png")

    widget.add_paths([a, b])
    widget.add_paths([a])

    assert widget.paths() == [a, b]
    assert widget.count_label.text() == "2 file(s)"


def test_move_remove_and_clear(qtbot: QtBot, tmp_path: Path) -> None:
    widget = FileList()
    qtbot.addWidget(widget)
    a, b, c = _files(tmp_path, "a.png", "b.png", "c.png")
    widget.add_paths([a, b, c])

    widget.list.setCurrentRow(2)
    widget.move_current(-1)
    assert widget.paths() == [a, c, b]

    widget.move_current(-5)  # out of range: ignored
    assert widget.paths() == [a, c, b]

    widget.remove_current()
    assert len(widget.paths()) == 2

    widget.clear()
    assert widget.paths() == []
    assert not widget.clear_button.isEnabled()


def test_buttons_follow_selection(qtbot: QtBot, tmp_path: Path) -> None:
    widget = FileList()
    qtbot.addWidget(widget)
    widget.add_paths(_files(tmp_path, "a.png", "b.png"))

    widget.list.setCurrentRow(0)

    assert not widget.up_button.isEnabled()
    assert widget.down_button.isEnabled()
    assert widget.remove_button.isEnabled()
