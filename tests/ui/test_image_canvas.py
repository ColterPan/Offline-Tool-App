import pytest
from PIL import Image
from PySide6.QtCore import QPoint, Qt
from pytestqt.qtbot import QtBot

from offline_tools.core.geometry import FULL_QUAD, Point, Rect
from offline_tools.ui.widgets.image_canvas import BoxCanvas, ClickCanvas, CornerCanvas

CANVAS_SIZE = (420, 320)


def _show(qtbot: QtBot, canvas: BoxCanvas | ClickCanvas | CornerCanvas) -> None:
    canvas.set_image(Image.new("RGB", (400, 300), "white"))
    canvas.resize(*CANVAS_SIZE)
    canvas.show()
    qtbot.addWidget(canvas)
    qtbot.waitExposed(canvas)


def _box_count(canvas: BoxCanvas) -> int:
    # A function call stops mypy treating `canvas.boxes` as permanently narrowed.
    return len(canvas.boxes)


def _at(canvas: BoxCanvas | ClickCanvas | CornerCanvas, x: float, y: float) -> QPoint:
    return canvas.to_widget(Point(x, y)).toPoint()


def test_mapping_round_trip(qtbot: QtBot) -> None:
    canvas = BoxCanvas()
    _show(qtbot, canvas)

    back = canvas.to_norm(canvas.to_widget(Point(0.25, 0.75)))

    assert back.x == pytest.approx(0.25, abs=0.01)
    assert back.y == pytest.approx(0.75, abs=0.01)


def test_drag_draws_a_box_then_delete_removes_it(qtbot: QtBot) -> None:
    canvas = BoxCanvas()
    _show(qtbot, canvas)
    changes: list[int] = []
    canvas.boxes_changed.connect(lambda: changes.append(len(canvas.boxes)))

    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.1, 0.1))
    qtbot.mouseMove(canvas, _at(canvas, 0.5, 0.4))
    qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.5, 0.4))

    (box,) = canvas.boxes
    assert box.left == pytest.approx(0.1, abs=0.01)
    assert box.bottom == pytest.approx(0.4, abs=0.01)
    assert canvas.selected == 0

    qtbot.keyClick(canvas, Qt.Key.Key_Delete)
    assert canvas.boxes == ()
    assert changes == [1, 0]


def test_click_selects_existing_box_instead_of_drawing(qtbot: QtBot) -> None:
    canvas = BoxCanvas()
    _show(qtbot, canvas)
    canvas.set_boxes([Rect(0.2, 0.2, 0.6, 0.6)])

    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.4, 0.4))

    assert canvas.selected == 0
    assert len(canvas.boxes) == 1


def test_tiny_drag_is_ignored_and_undo_clear(qtbot: QtBot) -> None:
    canvas = BoxCanvas()
    _show(qtbot, canvas)

    qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.9, 0.9))
    assert _box_count(canvas) == 0

    canvas.add_box(Rect(0, 0, 0.3, 0.3))
    canvas.add_box(Rect(0.5, 0.5, 0.8, 0.8))
    canvas.undo()
    assert _box_count(canvas) == 1
    canvas.clear()
    assert _box_count(canvas) == 0


def test_click_canvas_reports_position(qtbot: QtBot) -> None:
    canvas = ClickCanvas()
    _show(qtbot, canvas)

    with qtbot.waitSignal(canvas.clicked) as blocker:
        qtbot.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.8, 0.2))

    point = blocker.args[0]
    assert point.x == pytest.approx(0.8, abs=0.01)
    assert point.y == pytest.approx(0.2, abs=0.01)


def test_corner_canvas_drag_and_keyboard_nudge(qtbot: QtBot) -> None:
    canvas = CornerCanvas()
    _show(qtbot, canvas)
    canvas.set_quad(FULL_QUAD)

    qtbot.mousePress(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.0, 0.0))
    qtbot.mouseMove(canvas, _at(canvas, 0.2, 0.1))
    with qtbot.waitSignal(canvas.corners_changed):
        qtbot.mouseRelease(canvas, Qt.MouseButton.LeftButton, pos=_at(canvas, 0.2, 0.1))
    assert canvas.quad[0].x == pytest.approx(0.2, abs=0.01)

    qtbot.keyClick(canvas, Qt.Key.Key_3)  # bottom-right corner
    qtbot.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert canvas.selected_corner == 2
    assert canvas.quad[2].x == pytest.approx(0.98, abs=0.001)
