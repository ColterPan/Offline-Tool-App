"""Image views you can draw on. Shapes are kept in normalised (0-1) image coordinates.

- ImageCanvas: shows an image scaled to fit; base class with the coordinate mapping
- ClickCanvas: reports where on the image the user clicked (watermark placement)
- BoxCanvas: drag to draw rectangles, click to select, Delete to remove (redaction)
- CornerCanvas: four draggable corners, keyboard-nudgeable (document scanning)
"""

from collections.abc import Sequence

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPalette,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import QSizePolicy, QWidget

from offline_tools.core.geometry import FULL_QUAD, Point, Quad, Rect
from offline_tools.ui.widgets.pixmaps import pil_to_pixmap

CANVAS_MARGIN = 10
MIN_CANVAS_SIZE = QSize(320, 260)
HANDLE_RADIUS = 9
HANDLE_HIT_RADIUS = 22
NUDGE_STEP = 0.004
NUDGE_STEP_LARGE = 0.02
BOX_PREVIEW_ALPHA = 200  # boxes are slightly see-through while editing; the export is solid


class ImageCanvas(QWidget):
    def __init__(self, placeholder: str = "No image yet", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._placeholder = placeholder
        self.setMinimumSize(MIN_CANVAS_SIZE)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def has_image(self) -> bool:
        return self._pixmap is not None

    def set_image(self, image: Image.Image | None) -> None:
        self._pixmap = pil_to_pixmap(image) if image is not None else None
        self.update()

    def set_placeholder(self, text: str) -> None:
        self._placeholder = text
        self.update()

    def image_rect(self) -> QRectF:
        """Where the image is drawn: centred and scaled to fit, keeping its shape."""
        area = QRectF(self.rect()).adjusted(
            CANVAS_MARGIN, CANVAS_MARGIN, -CANVAS_MARGIN, -CANVAS_MARGIN
        )
        if self._pixmap is None or self._pixmap.width() == 0:
            return area
        scale = min(area.width() / self._pixmap.width(), area.height() / self._pixmap.height())
        width, height = self._pixmap.width() * scale, self._pixmap.height() * scale
        return QRectF(
            area.x() + (area.width() - width) / 2,
            area.y() + (area.height() - height) / 2,
            width,
            height,
        )

    def to_norm(self, pos: QPointF) -> Point:
        rect = self.image_rect()
        return Point(
            (pos.x() - rect.x()) / max(rect.width(), 1),
            (pos.y() - rect.y()) / max(rect.height(), 1),
        ).clamped()

    def to_widget(self, point: Point) -> QPointF:
        rect = self.image_rect()
        return QPointF(rect.x() + point.x * rect.width(), rect.y() + point.y * rect.height())

    def accent(self) -> QColor:
        return self.palette().color(QPalette.ColorRole.Highlight)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        if self._pixmap is None:
            painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self._placeholder)
        else:
            painter.drawPixmap(self.image_rect(), self._pixmap, QRectF(self._pixmap.rect()))
            self.paint_overlay(painter)
        painter.end()

    def paint_overlay(self, painter: QPainter) -> None:
        """Subclasses draw their shapes here."""


class ClickCanvas(ImageCanvas):
    clicked = Signal(object)  # Point

    def __init__(self, placeholder: str = "No image yet", parent: QWidget | None = None) -> None:
        super().__init__(placeholder, parent)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if self.has_image and event.button() is Qt.MouseButton.LeftButton:
            self.clicked.emit(self.to_norm(event.position()))


class BoxCanvas(ImageCanvas):
    boxes_changed = Signal()

    def __init__(self, placeholder: str = "No image yet", parent: QWidget | None = None) -> None:
        super().__init__(placeholder, parent)
        self._boxes: list[Rect] = []
        self._selected: int | None = None
        self._drag_start: Point | None = None
        self._drag_now: Point | None = None
        self._fill = QColor(0, 0, 0)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setAccessibleName("Page preview: drag to draw boxes over what you want to hide")

    @property
    def boxes(self) -> tuple[Rect, ...]:
        return tuple(self._boxes)

    @property
    def selected(self) -> int | None:
        return self._selected

    def set_boxes(self, boxes: Sequence[Rect]) -> None:
        self._boxes = list(boxes)
        self._selected = None
        self.update()

    def set_fill(self, colour: QColor) -> None:
        self._fill = colour
        self.update()

    def add_box(self, box: Rect) -> None:
        if box.is_empty:
            return
        self._boxes.append(box)
        self._selected = len(self._boxes) - 1
        self._changed()

    def undo(self) -> None:
        if self._boxes:
            self._boxes.pop()
            self._selected = None
            self._changed()

    def remove_selected(self) -> None:
        if self._selected is not None:
            del self._boxes[self._selected]
            self._selected = None
            self._changed()

    def clear(self) -> None:
        if self._boxes:
            self._boxes.clear()
            self._selected = None
            self._changed()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.has_image or event.button() is not Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        point = self.to_norm(event.position())
        hits = [i for i, box in enumerate(self._boxes) if box.contains(point)]
        if hits:
            self._selected = hits[-1]  # the topmost box
            self.update()
            return
        self._selected = None
        self._drag_start = self._drag_now = point

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is not None:
            self._drag_now = self.to_norm(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_start is None:
            return
        box = Rect.from_points(self._drag_start, self.to_norm(event.position()))
        self._drag_start = self._drag_now = None
        self.add_box(box)
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.remove_selected()
        else:
            super().keyPressEvent(event)

    def paint_overlay(self, painter: QPainter) -> None:
        fill = QColor(self._fill)
        fill.setAlpha(BOX_PREVIEW_ALPHA)
        for index, box in enumerate(self._boxes):
            area = self._box_rect(box)
            painter.fillRect(area, fill)
            if index == self._selected:
                pen = QPen(self.accent(), 2, Qt.PenStyle.DashLine)
                painter.setPen(pen)
                painter.drawRect(area)
        if self._drag_start is not None and self._drag_now is not None:
            painter.setPen(QPen(self.accent(), 2))
            painter.drawRect(self._box_rect(Rect.from_points(self._drag_start, self._drag_now)))

    def _box_rect(self, box: Rect) -> QRectF:
        top_left = self.to_widget(Point(box.left, box.top))
        bottom_right = self.to_widget(Point(box.right, box.bottom))
        return QRectF(top_left, bottom_right)

    def _changed(self) -> None:
        self.update()
        self.boxes_changed.emit()


class CornerCanvas(ImageCanvas):
    corners_changed = Signal()

    def __init__(self, placeholder: str = "No image yet", parent: QWidget | None = None) -> None:
        super().__init__(placeholder, parent)
        self._corners: list[Point] = list(FULL_QUAD)
        self._dragging: int | None = None
        self.selected_corner = 0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName(
            "Photo with page corners. Drag the corners, or press 1 to 4 to pick one and use "
            "the arrow keys to move it."
        )

    @property
    def quad(self) -> Quad:
        tl, tr, br, bl = self._corners
        return (tl, tr, br, bl)

    def set_quad(self, quad: Quad) -> None:
        self._corners = list(quad)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if not self.has_image or event.button() is not Qt.MouseButton.LeftButton:
            return
        self.setFocus()
        nearest = self._nearest_corner(event.position())
        if nearest is not None:
            self._dragging = self.selected_corner = nearest
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging is not None:
            self._corners[self._dragging] = self.to_norm(event.position())
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._dragging is not None:
            self._dragging = None
            self.corners_changed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        number_keys = (Qt.Key.Key_1, Qt.Key.Key_2, Qt.Key.Key_3, Qt.Key.Key_4)
        if event.key() in number_keys:
            self.selected_corner = number_keys.index(Qt.Key(event.key()))
            self.update()
            return
        step = (
            NUDGE_STEP_LARGE
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier
            else NUDGE_STEP
        )
        moves = {
            Qt.Key.Key_Left: (-step, 0.0),
            Qt.Key.Key_Right: (step, 0.0),
            Qt.Key.Key_Up: (0.0, -step),
            Qt.Key.Key_Down: (0.0, step),
        }
        move = moves.get(Qt.Key(event.key()))
        if move is None:
            super().keyPressEvent(event)
            return
        corner = self._corners[self.selected_corner]
        self._corners[self.selected_corner] = Point(
            corner.x + move[0], corner.y + move[1]
        ).clamped()
        self.update()
        self.corners_changed.emit()

    def paint_overlay(self, painter: QPainter) -> None:
        accent = self.accent()
        points = [self.to_widget(corner) for corner in self._corners]
        outline = QPainterPath(points[0])
        for point in points[1:]:
            outline.lineTo(point)
        outline.closeSubpath()
        tint = QColor(accent)
        tint.setAlpha(40)
        painter.fillPath(outline, tint)
        painter.setPen(QPen(accent, 2))
        painter.drawPath(outline)
        for index, point in enumerate(points):
            radius = HANDLE_RADIUS + (3 if index == self.selected_corner else 0)
            painter.setPen(QPen(QColor("white"), 2))
            painter.setBrush(accent)
            painter.drawEllipse(point, radius, radius)
            painter.setPen(QColor("white"))
            label_box = QRectF(point.x() - radius, point.y() - radius, 2 * radius, 2 * radius)
            painter.drawText(label_box, Qt.AlignmentFlag.AlignCenter, str(index + 1))

    def _nearest_corner(self, pos: QPointF) -> int | None:
        distances = [
            (abs(self.to_widget(c).x() - pos.x()) + abs(self.to_widget(c).y() - pos.y()), i)
            for i, c in enumerate(self._corners)
        ]
        distance, index = min(distances)
        return index if distance <= HANDLE_HIT_RADIUS * 2 else None
