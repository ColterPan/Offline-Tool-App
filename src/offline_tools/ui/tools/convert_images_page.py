"""Convert Images: batch PNG / JPG / WEBP conversion that also strips photo metadata."""

from functools import partial

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QPushButton, QSlider, QWidget

from offline_tools.core.images import (
    DEFAULT_QUALITY,
    SUPPORTED_INPUT_SUFFIXES,
    BatchResult,
    ImageFormat,
    convert_images,
)
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.file_list import FileList
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.tool_page import ToolPage

FORMAT_OPTIONS = (
    ("JPG: photos, small files", ImageFormat.JPEG),
    ("PNG: sharp graphics, keeps transparency", ImageFormat.PNG),
    ("WEBP: modern format for websites", ImageFormat.WEBP),
)
MIN_QUALITY = 40
MAX_QUALITY = 100
MAX_FAILURES_SHOWN = 3


class ConvertImagesPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Convert Images",
            "Change images between JPG, PNG and WEBP, one or many at a time.",
            parent,
        )
        self._context = context

        self.drop_zone = DropZone(
            prompt="Drop images here", extensions=SUPPORTED_INPUT_SUFFIXES, multiple=True
        )
        self.file_list = FileList(reorderable=False)
        self.drop_zone.files_selected.connect(self.file_list.add_paths)
        self.file_list.changed.connect(self.refresh_state)
        files_card = Card("Images")
        files_card.add(self.file_list)

        self.format_combo = combo(FORMAT_OPTIONS, accessible_name="Convert to")
        self.format_combo.currentIndexChanged.connect(lambda _i: self.refresh_state())
        self.quality_slider = QSlider(Qt.Orientation.Horizontal)
        self.quality_slider.setRange(MIN_QUALITY, MAX_QUALITY)
        self.quality_slider.setValue(DEFAULT_QUALITY)
        self.quality_label = QLabel()
        self.quality_slider.valueChanged.connect(self._update_quality_label)
        self._update_quality_label(DEFAULT_QUALITY)
        privacy = QLabel(
            "Camera details and location data are not copied into the converted images. "
            "Your originals are not changed."
        )
        privacy.setProperty("role", "muted")
        privacy.setWordWrap(True)
        options_card = Card("Convert to")
        options_card.add(form(("Format:", self.format_combo), ("Quality:", self.quality_slider)))
        options_card.add(self.quality_label)
        options_card.add(privacy)

        self.convert_button = QPushButton("Convert")
        self.convert_button.setProperty("variant", "primary")
        self.convert_button.clicked.connect(self.convert)

        for widget in (self.drop_zone, files_card, options_card, self.convert_button):
            self.add_content(widget)
        self._busy_widgets = [self.drop_zone, files_card, options_card, self.convert_button]
        self.refresh_state()

    @property
    def target(self) -> ImageFormat:
        return ImageFormat(self.format_combo.currentData())

    def convert(self) -> None:
        sources = self.file_list.paths()
        if not sources:
            return
        job = partial(
            convert_images,
            sources,
            self.target,
            out_dir_for=self._context.settings.output_dir_for,
            quality=self.quality_slider.value(),
        )
        self.run_task(self._context.runner, job, self._on_done, disable=self._busy_widgets)

    def refresh_state(self) -> None:
        if self.is_running:
            return
        self.convert_button.setEnabled(bool(self.file_list.paths()))
        uses_quality = self.target.uses_quality
        self.quality_slider.setEnabled(uses_quality)
        self.quality_label.setVisible(uses_quality)

    def _on_done(self, result: BatchResult) -> None:
        total = len(result.outputs) + len(result.failures)
        if not result.outputs:
            self.banner.show_error(f"No images were converted. {result.failures[0][1]}")
            return
        folder = result.outputs[0].parent
        if not result.failures:
            self.banner.show_success(f"Converted {total} image(s).", folder=folder)
            return
        reasons = " ".join(reason for _, reason in result.failures[:MAX_FAILURES_SHOWN])
        self.banner.show_success(
            f"Converted {len(result.outputs)} of {total}. Skipped: {reasons}", folder=folder
        )

    def _update_quality_label(self, value: int) -> None:
        hint = "best" if value >= 95 else "smaller files" if value < 75 else "good balance"
        self.quality_label.setText(f"Quality {value} ({hint})")
        self.quality_label.setProperty("role", "muted")
