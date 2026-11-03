"""Watermark Photos: text or logo, placed anywhere or tiled, with live preview."""

import datetime as dt
from functools import partial
from pathlib import Path

from PIL import Image, ImageDraw
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QColorDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from offline_tools.core.errors import ToolError
from offline_tools.core.geometry import Point
from offline_tools.core.images import SUPPORTED_INPUT_SUFFIXES, BatchResult, open_image
from offline_tools.core.watermark import (
    WatermarkKind,
    WatermarkStyle,
    watermark_files,
    watermark_image,
)
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.file_list import FileList
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.image_canvas import ClickCanvas
from offline_tools.ui.widgets.pixmaps import preview_copy
from offline_tools.ui.widgets.tool_page import ToolPage

PREVIEW_MAX_SIDE = 900
PREVIEW_DELAY_MS = 120
PREVIEW_HEIGHT = 440
POSITION_BUTTON_SIZE = (44, 36)
TEXT_BOX_HEIGHT = 64
MAX_FAILURES_SHOWN = 3
SAMPLE_SIZE = (900, 600)
ID_TEMPLATE_BLANK = "__________"

COLOUR_OPTIONS = (
    ("White", (255, 255, 255)),
    ("Black", (0, 0, 0)),
    ("Grey", (128, 128, 128)),
    ("Red", (220, 38, 38)),
    ("Blue", (37, 99, 235)),
    ("Yellow", (250, 204, 21)),
)
# 3x3 grid of placement buttons: (label, accessible name, position)
POSITIONS = (
    ("↖", "Top left", Point(0, 0)),
    ("↑", "Top centre", Point(0.5, 0)),
    ("↗", "Top right", Point(1, 0)),
    ("←", "Middle left", Point(0, 0.5)),
    ("•", "Centre", Point(0.5, 0.5)),
    ("→", "Middle right", Point(1, 0.5)),
    ("↙", "Bottom left", Point(0, 1)),
    ("↓", "Bottom centre", Point(0.5, 1)),
    ("↘", "Bottom right", Point(1, 1)),
)
CENTRE_INDEX = 4


class WatermarkPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Watermark Photos",
            "Add text or your logo on top of photos. Choose where it goes, how big, and how "
            "faint or strong. Great for marking ID copies with what they're for.",
            parent,
        )
        self._context = context
        self._colour: tuple[int, int, int] = COLOUR_OPTIONS[0][1]
        self._position = Point(0.5, 0.5)
        self._logo_path: Path | None = None
        self._logo_preview: Image.Image | None = None
        self._preview_base = _sample_photo()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(PREVIEW_DELAY_MS)
        self._timer.timeout.connect(self.refresh_preview)

        self.drop_zone = DropZone(
            prompt="Drop photos here", extensions=SUPPORTED_INPUT_SUFFIXES, multiple=True
        )
        self.file_list = FileList(reorderable=False)
        self.drop_zone.files_selected.connect(self.file_list.add_paths)
        self.file_list.changed.connect(self._on_files_changed)
        self.file_list.list.currentRowChanged.connect(lambda _row: self._load_preview_base())
        files = Card("Photos")
        files.add(self.file_list)
        self.add_content(self.drop_zone)
        self.add_content(files)

        columns = QWidget()
        row = QHBoxLayout(columns)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(14)
        options = QVBoxLayout()
        for card in (
            self._build_content_card(),
            self._build_look_card(),
            self._build_position_card(),
        ):
            options.addWidget(card)
        options.addStretch()
        row.addLayout(options, stretch=1)
        row.addWidget(self._build_preview_card(), stretch=1, alignment=Qt.AlignmentFlag.AlignTop)
        self.add_content(columns)

        self.apply_button = QPushButton("Watermark photos")
        self.apply_button.setProperty("variant", "primary")
        self.apply_button.clicked.connect(self.apply)
        self.add_content(self.apply_button)
        self._busy_widgets = [self.drop_zone, files, columns, self.apply_button]
        self._on_kind_changed()
        self.refresh_state()

    # ---- building -----------------------------------------------------------------

    def _build_content_card(self) -> Card:
        card = Card("Watermark")
        self.text_radio = QRadioButton("Text")
        self.logo_radio = QRadioButton("Logo or image")
        self.text_radio.setChecked(True)
        self.text_radio.toggled.connect(lambda _on: self._on_kind_changed())
        kinds = QWidget()
        kinds_row = QHBoxLayout(kinds)
        kinds_row.setContentsMargins(0, 0, 0, 0)
        kinds_row.addWidget(self.text_radio)
        kinds_row.addWidget(self.logo_radio)
        kinds_row.addStretch()

        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlaceholderText("e.g. © Pan Photography, or SAMPLE")
        self.text_edit.setFixedHeight(TEXT_BOX_HEIGHT)
        self.text_edit.setAccessibleName("Watermark text")
        self.text_edit.textChanged.connect(self._schedule_preview)
        self.template_button = QPushButton("Use ID-copy template")
        self.template_button.setToolTip(
            "Marks a copy of your NRIC or passport with who it's for and today's date, so a "
            "leaked copy can't be reused elsewhere."
        )
        self.template_button.clicked.connect(self.use_id_template)

        self.logo_button = QPushButton("Choose logo…")
        self.logo_button.clicked.connect(self._choose_logo)
        self.logo_label = QLabel("No logo chosen. A PNG with a transparent background works best.")
        self.logo_label.setProperty("role", "muted")
        self.logo_label.setWordWrap(True)

        for widget in (
            kinds,
            self.text_edit,
            self.template_button,
            self.logo_button,
            self.logo_label,
        ):
            card.add(widget)
        return card

    def _build_look_card(self) -> Card:
        card = Card("Look")
        self.colour_combo = combo(COLOUR_OPTIONS, accessible_name="Colour")
        self.colour_combo.currentIndexChanged.connect(self._on_colour_preset)
        custom = QPushButton("Custom colour…")
        custom.clicked.connect(self._choose_custom_colour)
        colour_row = QWidget()
        colour_layout = QHBoxLayout(colour_row)
        colour_layout.setContentsMargins(0, 0, 0, 0)
        colour_layout.addWidget(self.colour_combo, stretch=1)
        colour_layout.addWidget(custom)

        self.opacity_slider = _slider(5, 100, 40, "Opacity")
        self.size_slider = _slider(2, 60, 8, "Size")
        self.rotation_slider = _slider(-90, 90, 0, "Angle")
        self.value_label = QLabel()
        self.value_label.setProperty("role", "muted")
        for slider in (self.opacity_slider, self.size_slider, self.rotation_slider):
            slider.valueChanged.connect(self._schedule_preview)
        self.outline_check = QCheckBox("Outline (stands out on busy photos)")
        self.outline_check.setChecked(True)
        self.outline_check.toggled.connect(self._schedule_preview)

        card.add(
            form(
                ("Colour:", colour_row),
                ("Opacity:", self.opacity_slider),
                ("Size:", self.size_slider),
                ("Angle:", self.rotation_slider),
            )
        )
        card.add(self.value_label)
        card.add(self.outline_check)
        return card

    def _build_position_card(self) -> Card:
        card = Card("Position")
        grid_widget = QWidget()
        grid = QGridLayout(grid_widget)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(6)
        grid.setColumnStretch(3, 1)  # keep the 3x3 buttons together on the left
        self.position_group = QButtonGroup(self)
        for index, (label, name, point) in enumerate(POSITIONS):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setAccessibleName(name)
            button.setToolTip(name)
            button.setFixedSize(*POSITION_BUTTON_SIZE)
            button.clicked.connect(partial(self.set_position, point))
            self.position_group.addButton(button, index)
            grid.addWidget(button, index // 3, index % 3)
        self.position_group.button(CENTRE_INDEX).setChecked(True)
        self.tile_check = QCheckBox("Repeat across the whole photo")
        self.tile_check.toggled.connect(self._schedule_preview)
        hint = QLabel("Or click anywhere on the preview to place it exactly.")
        hint.setProperty("role", "muted")
        hint.setWordWrap(True)
        card.add(grid_widget)
        card.add(self.tile_check)
        card.add(hint)
        return card

    def _build_preview_card(self) -> Card:
        card = Card("Preview")
        self.preview = ClickCanvas("Preview")
        self.preview.setFixedHeight(PREVIEW_HEIGHT)
        self.preview.setAccessibleName("Watermark preview. Click to place the watermark.")
        self.preview.clicked.connect(self._on_preview_clicked)
        self.preview_status = QLabel()
        self.preview_status.setProperty("role", "muted")
        self.preview_status.setWordWrap(True)
        card.add(self.preview)
        card.add(self.preview_status)
        return card

    # ---- behaviour ------------------------------------------------------------------

    def watermark_style(self) -> WatermarkStyle:
        return WatermarkStyle(
            kind=WatermarkKind.TEXT if self.text_radio.isChecked() else WatermarkKind.LOGO,
            text=self.text_edit.toPlainText(),
            logo_path=self._logo_path,
            colour=self._colour,
            opacity=self.opacity_slider.value() / 100,
            size=self.size_slider.value() / 100,
            rotation=float(self.rotation_slider.value()),
            position=self._position,
            tiled=self.tile_check.isChecked(),
            outline=self.outline_check.isChecked(),
        )

    def set_position(self, point: Point) -> None:
        self._position = point
        self.tile_check.setChecked(False)
        self._schedule_preview()

    def use_id_template(self) -> None:
        today = dt.date.today().strftime("%d %b %Y")
        self.text_radio.setChecked(True)
        self.text_edit.setPlainText(f"COPY FOR {ID_TEMPLATE_BLANK} ONLY\n{today}")
        self.colour_combo.setCurrentIndex(2)  # grey
        self.opacity_slider.setValue(35)
        self.size_slider.setValue(4)
        self.rotation_slider.setValue(30)
        self.tile_check.setChecked(True)
        # Select the blank so the user can type the purpose straight away.
        cursor = self.text_edit.textCursor()
        start = self.text_edit.toPlainText().index(ID_TEMPLATE_BLANK)
        cursor.setPosition(start)
        cursor.setPosition(start + len(ID_TEMPLATE_BLANK), QTextCursor.MoveMode.KeepAnchor)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.setFocus()

    def refresh_preview(self) -> None:
        style = self.watermark_style()
        self.value_label.setText(
            f"Opacity {self.opacity_slider.value()}% · Size {self.size_slider.value()}% · "
            f"Angle {self.rotation_slider.value()}°"
        )
        try:
            marked = watermark_image(self._preview_base, style, logo=self._logo_preview)
        except ToolError as exc:
            self.preview.set_image(self._preview_base)
            self.preview_status.setText(exc.user_message)
            return
        self.preview.set_image(marked)
        self.preview_status.setText(
            "Showing a sample. Add photos to preview them."
            if not self.file_list.paths()
            else "Preview of the selected photo."
        )

    def apply(self) -> None:
        sources = self.file_list.paths()
        if not sources:
            return
        job = partial(
            watermark_files,
            sources,
            self.watermark_style(),
            out_dir_for=self._context.settings.output_dir_for,
        )
        self.run_task(self._context.runner, job, self._on_done, disable=self._busy_widgets)

    def refresh_state(self) -> None:
        if self.is_running:
            return
        count = len(self.file_list.paths())
        self.apply_button.setEnabled(count > 0)
        self.apply_button.setText(f"Watermark {count} photo(s)" if count else "Watermark photos")

    def _on_done(self, result: BatchResult) -> None:
        if not result.outputs:
            self.banner.show_error(f"No photos were watermarked. {result.failures[0][1]}")
            return
        folder = result.outputs[0].parent
        if result.failures:
            reasons = " ".join(reason for _, reason in result.failures[:MAX_FAILURES_SHOWN])
            self.banner.show_success(
                f"Watermarked {len(result.outputs)} photo(s). Skipped: {reasons}", folder=folder
            )
        else:
            self.banner.show_success(f"Watermarked {len(result.outputs)} photo(s).", folder=folder)

    def _on_files_changed(self) -> None:
        if self.file_list.list.currentRow() < 0 and self.file_list.paths():
            self.file_list.list.setCurrentRow(0)
        self._load_preview_base()
        self.refresh_state()

    def _load_preview_base(self) -> None:
        paths = self.file_list.paths()
        row = self.file_list.list.currentRow()
        if not paths:
            self._preview_base = _sample_photo()
        else:
            try:
                self._preview_base = preview_copy(open_image(paths[max(row, 0)]), PREVIEW_MAX_SIDE)
            except ToolError as exc:
                self.banner.show_error(exc.user_message)
                self._preview_base = _sample_photo()
        self._schedule_preview()

    def _on_kind_changed(self) -> None:
        is_text = self.text_radio.isChecked()
        self.text_edit.setVisible(is_text)
        self.template_button.setVisible(is_text)
        self.logo_button.setVisible(not is_text)
        self.logo_label.setVisible(not is_text)
        self.outline_check.setEnabled(is_text)
        self.colour_combo.setEnabled(is_text)
        self._schedule_preview()

    def _on_preview_clicked(self, point: Point) -> None:
        self.position_group.setExclusive(False)
        for button in self.position_group.buttons():
            button.setChecked(False)
        self.position_group.setExclusive(True)
        self.set_position(point)

    def _on_colour_preset(self, index: int) -> None:
        self._colour = (
            COLOUR_OPTIONS[index][1] if 0 <= index < len(COLOUR_OPTIONS) else self._colour
        )
        self._schedule_preview()

    def _choose_custom_colour(self) -> None:
        chosen = QColorDialog.getColor(QColor(*self._colour), self, "Watermark colour")
        if chosen.isValid():
            self._colour = (chosen.red(), chosen.green(), chosen.blue())
            self._schedule_preview()

    def _choose_logo(self) -> None:
        patterns = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_INPUT_SUFFIXES))
        chosen, _ = QFileDialog.getOpenFileName(self, "Choose a logo", "", f"Images ({patterns})")
        if chosen:
            self.set_logo(Path(chosen))

    def set_logo(self, path: Path) -> None:
        try:
            self._logo_preview = open_image(path)
        except ToolError as exc:
            self.banner.show_error(exc.user_message)
            return
        self._logo_path = path
        self.logo_label.setText(f"Logo: {path.name}")
        self._schedule_preview()

    def _schedule_preview(self) -> None:
        self._timer.start()


def _slider(minimum: int, maximum: int, value: int, name: str) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(minimum, maximum)
    slider.setValue(value)
    slider.setAccessibleName(name)
    return slider


def _sample_photo() -> Image.Image:
    """A stand-in 'photo' so the settings can be previewed before any photo is added."""
    sample = Image.new("RGB", SAMPLE_SIZE, (120, 140, 160))
    draw = ImageDraw.Draw(sample)
    width, height = SAMPLE_SIZE
    for band in range(0, height, 6):  # a simple sky-to-ground gradient
        shade = round(200 - band / height * 120)
        draw.rectangle((0, band, width, band + 6), fill=(shade - 40, shade - 20, shade))
    return sample
