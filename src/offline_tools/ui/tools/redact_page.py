"""Redact Documents: draw boxes over what to hide in a PDF or photo, then save a safe copy."""

from functools import partial
from pathlib import Path

from PIL import Image
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from offline_tools.core.errors import ToolError
from offline_tools.core.geometry import Rect
from offline_tools.core.images import SUPPORTED_INPUT_SUFFIXES, open_image
from offline_tools.core.pdf_render import page_count, render_page
from offline_tools.core.redact import FillColour, redact_image_file, redact_pdf
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.forms import combo
from offline_tools.ui.widgets.image_canvas import BoxCanvas
from offline_tools.ui.widgets.pixmaps import preview_copy
from offline_tools.ui.widgets.tool_page import ToolPage
from offline_tools.ui.worker import Job

PREVIEW_DPI = 110
CANVAS_MIN_HEIGHT = 520
COLOUR_OPTIONS = (("Black boxes", FillColour.BLACK), ("White boxes", FillColour.WHITE))
SAFETY_NOTE = (
    "The saved copy is flattened into images, so the hidden text is really gone and can't be "
    "copied out. Your original file is not changed."
)


class RedactPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Redact Documents",
            "Black out NRIC numbers, addresses, salaries or anything else before you send a "
            "document. Works with PDFs and photos.",
            parent,
        )
        self._context = context
        self._source: Path | None = None
        self._is_pdf = False
        self._page = 0
        self._pages = 0
        self._boxes: dict[int, list[Rect]] = {}

        self.drop_zone = DropZone(
            prompt="Drop a PDF or photo here", extensions=SUPPORTED_INPUT_SUFFIXES | {".pdf"}
        )
        self.drop_zone.files_selected.connect(lambda paths: self.select_file(paths[0]))
        self.add_content(self.drop_zone)
        self.add_content(self._build_editor())

        note = QLabel(SAFETY_NOTE)
        note.setProperty("role", "muted")
        note.setWordWrap(True)
        self.save_button = QPushButton("Save redacted copy")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save)
        self.add_content(note)
        self.add_content(self.save_button)

        QShortcut(QKeySequence.StandardKey.Undo, self, self.canvas.undo)
        self._busy_widgets = [self.drop_zone, self.editor_card, self.save_button]
        self.refresh_state()

    def _build_editor(self) -> Card:
        self.editor_card = Card("Draw boxes over anything you want to hide")
        hint = QLabel(
            "Drag on the page to draw a box. Click a box and press Delete to remove it. "
            "Ctrl+Z undoes the last box."
        )
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)

        self.prev_button = QPushButton("◀ Previous page")
        self.next_button = QPushButton("Next page ▶")
        self.page_label = QLabel()
        self.prev_button.clicked.connect(lambda: self.show_page(self._page - 1))
        self.next_button.clicked.connect(lambda: self.show_page(self._page + 1))
        self.undo_button = QPushButton("Undo last box")
        self.clear_button = QPushButton("Clear this page")
        self.colour_combo = combo(COLOUR_OPTIONS, accessible_name="Box colour")
        self.colour_combo.currentIndexChanged.connect(lambda _i: self._apply_colour())

        toolbar = QWidget()
        row = QHBoxLayout(toolbar)
        row.setContentsMargins(0, 0, 0, 0)
        nav: tuple[QWidget, ...] = (self.prev_button, self.page_label, self.next_button)
        tools: tuple[QWidget, ...] = (self.undo_button, self.clear_button, self.colour_combo)
        for widget in nav:
            row.addWidget(widget)
        row.addStretch()
        for widget in tools:
            row.addWidget(widget)

        self.canvas = BoxCanvas("Your document will appear here")
        self.canvas.setMinimumHeight(CANVAS_MIN_HEIGHT)
        self.canvas.boxes_changed.connect(self._on_boxes_changed)
        self.undo_button.clicked.connect(self.canvas.undo)
        self.clear_button.clicked.connect(self.canvas.clear)
        self.count_label = QLabel()
        self.count_label.setProperty("role", "muted")

        parts: tuple[QWidget, ...] = (hint, toolbar, self.canvas, self.count_label)
        for part in parts:
            self.editor_card.add(part)
        return self.editor_card

    # ---- loading ----------------------------------------------------------------

    def select_file(self, path: Path) -> None:
        self._source = path
        self._is_pdf = path.suffix.lower() == ".pdf"
        self._boxes = {}
        self._page = 0
        self.canvas.set_image(None)
        self.canvas.set_boxes([])
        job: Job = (
            partial(_count_pages, path) if self._is_pdf else partial(_load_image_preview, path)
        )
        self.run_task(self._context.runner, job, self._on_loaded, disable=self._busy_widgets)

    def _on_loaded(self, result: int | Image.Image) -> None:
        if isinstance(result, int):
            self._pages = result
            self.show_page(0)
        else:
            self._pages = 1
            self.canvas.set_image(result)
        self.refresh_state()

    def show_page(self, index: int) -> None:
        if self._source is None or not 0 <= index < self._pages:
            return
        self._page = index
        if self._is_pdf:
            try:
                # Fast enough for the UI thread at screen resolution.
                self.canvas.set_image(render_page(self._source, index, dpi=PREVIEW_DPI))
            except ToolError as exc:
                self.banner.show_error(exc.user_message)
                return
        self.canvas.set_boxes(self._boxes.get(index, []))
        self.refresh_state()

    # ---- saving -----------------------------------------------------------------

    def save(self) -> None:
        if self._source is None or not self.total_boxes:
            return
        colour = FillColour(self.colour_combo.currentData())
        out_dir = self._context.settings.output_dir_for(self._source)
        boxes = {page: list(rects) for page, rects in self._boxes.items() if rects}
        job: Job
        if self._is_pdf:
            job = partial(redact_pdf, self._source, boxes, colour, out_dir=out_dir)
        else:
            job = partial(_redact_image_job, self._source, boxes.get(0, []), colour, out_dir)
        self.run_task(self._context.runner, job, self._on_saved, disable=self._busy_widgets)

    def _on_saved(self, path: Path) -> None:
        self.banner.show_success(
            f'Saved "{path.name}". Open it and check everything is covered before sending.',
            folder=path.parent,
        )

    # ---- state ------------------------------------------------------------------

    @property
    def total_boxes(self) -> int:
        return sum(len(rects) for rects in self._boxes.values())

    def refresh_state(self) -> None:
        if self.is_running:
            return
        loaded = self.canvas.has_image
        self.prev_button.setVisible(self._is_pdf)
        self.next_button.setVisible(self._is_pdf)
        self.page_label.setVisible(self._is_pdf)
        self.prev_button.setEnabled(self._page > 0)
        self.next_button.setEnabled(self._page < self._pages - 1)
        self.page_label.setText(f"Page {self._page + 1} of {self._pages}")
        on_page = len(self._boxes.get(self._page, []))
        self.count_label.setText(
            f"{on_page} box(es) on this page, {self.total_boxes} in total." if loaded else ""
        )
        self.undo_button.setEnabled(on_page > 0)
        self.clear_button.setEnabled(on_page > 0)
        self.save_button.setEnabled(self.total_boxes > 0)

    def _on_boxes_changed(self) -> None:
        self._boxes[self._page] = list(self.canvas.boxes)
        self.refresh_state()

    def _apply_colour(self) -> None:
        colour = FillColour(self.colour_combo.currentData())
        self.canvas.set_fill(QColor(*colour.rgb))


def _count_pages(path: Path, *, on_progress: object = None) -> int:
    return page_count(path)


def _load_image_preview(path: Path, *, on_progress: object = None) -> Image.Image:
    return preview_copy(open_image(path))


def _redact_image_job(
    path: Path, boxes: list[Rect], colour: FillColour, out_dir: Path, *, on_progress: object = None
) -> Path:
    return redact_image_file(path, boxes, colour, out_dir=out_dir)
