"""Scan Document: phone photo → straight, clean scan (PDF, JPG or PNG)."""

from functools import partial
from pathlib import Path

from PIL import Image
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from offline_tools.core.errors import ToolError
from offline_tools.core.geometry import FULL_QUAD, Quad
from offline_tools.core.images import SUPPORTED_INPUT_SUFFIXES, open_image
from offline_tools.core.paths import unique_output_path
from offline_tools.core.scanner import ScanMode, detect_page, enhance, scan_document, straighten
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.image_canvas import CornerCanvas, ImageCanvas
from offline_tools.ui.widgets.pixmaps import preview_copy
from offline_tools.ui.widgets.tool_page import ToolPage

PREVIEW_DELAY_MS = 250
EDIT_PREVIEW_MAX_SIDE = 1400
RESULT_PREVIEW_MAX_SIDE = 1000
CANVAS_MIN_HEIGHT = 460
MODE_OPTIONS = (
    ("Black & white (crisp text)", ScanMode.BLACK_WHITE),
    ("Greyscale", ScanMode.GREYSCALE),
    ("Colour (whiter paper)", ScanMode.COLOUR),
    ("Original colours", ScanMode.ORIGINAL),
)
FORMAT_OPTIONS = (("PDF", ".pdf"), ("JPG image", ".jpg"), ("PNG image", ".png"))
NOT_FOUND_HINT = (
    "Couldn't find the page edges automatically. Drag the four corners onto the page's corners."
)
FOUND_HINT = "Check the corners sit on the page's corners. Drag them, or press 1-4 then arrow keys."


class ScanPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Scan Document",
            "Turn a phone photo of a document into a clean, straight scan: the background is "
            "cropped away, shadows are removed and text becomes crisp.",
            parent,
        )
        self._context = context
        self._source: Path | None = None
        self._photo: Image.Image | None = None
        self._edit_preview: Image.Image | None = None
        self._detected: Quad = FULL_QUAD
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self.refresh_result)

        self.drop_zone = DropZone(
            prompt="Drop a photo of a document", extensions=SUPPORTED_INPUT_SUFFIXES
        )
        self.drop_zone.files_selected.connect(lambda paths: self.select_file(paths[0]))
        self.add_content(self.drop_zone)

        columns = QWidget()
        row = QHBoxLayout(columns)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        row.addWidget(self._build_corners_card(), stretch=1)
        row.addWidget(self._build_result_card(), stretch=1)
        self.add_content(columns)

        self.mode_combo = combo(MODE_OPTIONS, accessible_name="Scan style")
        self.format_combo = combo(FORMAT_OPTIONS, accessible_name="Save as")
        self.mode_combo.currentIndexChanged.connect(lambda _i: self._timer.start())
        options = Card("Options")
        options.add(form(("Style:", self.mode_combo), ("Save as:", self.format_combo)))
        self.add_content(options)

        self.save_button = QPushButton("Save scan")
        self.save_button.setProperty("variant", "primary")
        self.save_button.clicked.connect(self.save)
        self.add_content(self.save_button)
        self._busy_widgets = [self.drop_zone, columns, options, self.save_button]
        self.refresh_state()

    def _build_corners_card(self) -> Card:
        card = Card("1. Page corners")
        self.corners = CornerCanvas("Your photo will appear here")
        self.corners.setMinimumHeight(CANVAS_MIN_HEIGHT)
        self.corners.corners_changed.connect(self._timer.start)
        self.corner_hint = QLabel()
        self.corner_hint.setProperty("role", "muted")
        self.corner_hint.setWordWrap(True)
        self.detect_button = QPushButton("Find edges again")
        self.whole_button = QPushButton("Use whole photo")
        self.detect_button.clicked.connect(self.reset_to_detected)
        self.whole_button.clicked.connect(lambda: self._set_quad(FULL_QUAD))
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.detect_button)
        row.addWidget(self.whole_button)
        row.addStretch()
        for widget in (self.corners, self.corner_hint, buttons):
            card.add(widget)
        return card

    def _build_result_card(self) -> Card:
        card = Card("2. Result")
        self.result = ImageCanvas("The cleaned-up scan appears here")
        self.result.setMinimumHeight(CANVAS_MIN_HEIGHT)
        self.result.setAccessibleName("Scan result preview")
        layout = card.layout_
        assert isinstance(layout, QVBoxLayout)
        layout.addWidget(self.result, stretch=1)
        return card

    def select_file(self, path: Path) -> None:
        self._source = path
        self.run_task(self._context.runner, partial(_load_and_detect, path), self._on_loaded,
                      disable=self._busy_widgets)  # fmt: skip

    def _on_loaded(self, result: tuple[Image.Image, Quad | None]) -> None:
        photo, quad = result
        self._photo = photo
        self._edit_preview = preview_copy(photo, EDIT_PREVIEW_MAX_SIDE)
        self._detected = quad or FULL_QUAD
        self.corner_hint.setText(FOUND_HINT if quad else NOT_FOUND_HINT)
        self.corners.set_image(self._edit_preview)
        self._set_quad(self._detected)
        self.refresh_state()

    def reset_to_detected(self) -> None:
        self._set_quad(self._detected)

    def refresh_result(self) -> None:
        """Quick preview from the downscaled photo; the saved scan uses full resolution."""
        if self._edit_preview is None:
            return
        try:
            flat = straighten(self._edit_preview, self.corners.quad)
            flat.thumbnail((RESULT_PREVIEW_MAX_SIDE, RESULT_PREVIEW_MAX_SIDE))
            self.result.set_image(enhance(flat, ScanMode(self.mode_combo.currentData())))
        except ToolError as exc:
            self.result.set_image(None)
            self.result.set_placeholder(exc.user_message)

    def save(self) -> None:
        if self._photo is None or self._source is None:
            return
        suffix = str(self.format_combo.currentData())
        out = unique_output_path(
            self._source,
            out_dir=self._context.settings.output_dir_for(self._source),
            new_suffix=suffix,
            label="scan",
        )
        job = partial(
            _scan_job, self._photo, self.corners.quad, ScanMode(self.mode_combo.currentData()), out
        )
        self.run_task(self._context.runner, job, self._on_saved, disable=self._busy_widgets)

    def refresh_state(self) -> None:
        if self.is_running:
            return
        loaded = self._photo is not None
        self.save_button.setEnabled(loaded)
        self.detect_button.setEnabled(loaded)
        self.whole_button.setEnabled(loaded)

    def _set_quad(self, quad: Quad) -> None:
        self.corners.set_quad(quad)
        self.refresh_result()

    def _on_saved(self, path: Path) -> None:
        self.banner.show_success(f'Saved "{path.name}"', folder=path.parent)


def _load_and_detect(path: Path, *, on_progress: object = None) -> tuple[Image.Image, Quad | None]:
    photo = open_image(path)
    return photo, detect_page(photo)


def _scan_job(
    photo: Image.Image, quad: Quad, mode: ScanMode, out: Path, *, on_progress: object = None
) -> Path:
    return scan_document(photo, quad, mode, out)
