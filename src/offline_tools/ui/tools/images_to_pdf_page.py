"""Images → PDF: combine photos or scans into one PDF, in the order shown."""

from functools import partial
from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from offline_tools.core.images import SUPPORTED_INPUT_SUFFIXES, PageSize, images_to_pdf
from offline_tools.core.paths import preferred_output_path
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.file_list import FileList
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.tool_page import ToolPage

PAGE_OPTIONS = (
    ("Same size as each image", PageSize.FIT),
    ("A4", PageSize.A4),
    ("US Letter", PageSize.LETTER),
)
MARGIN_OPTIONS = (("No margin", 0.0), ("Small (10 mm)", 10.0), ("Normal (20 mm)", 20.0))


class ImagesToPdfPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Images → PDF",
            "Combine photos or scanned pages into a single PDF, for example a scanned NRIC or "
            "certificates for a job application.",
            parent,
        )
        self._context = context

        self.drop_zone = DropZone(
            prompt="Drop photos or scans here", extensions=SUPPORTED_INPUT_SUFFIXES, multiple=True
        )
        self.file_list = FileList(reorderable=True)
        self.drop_zone.files_selected.connect(self.file_list.add_paths)
        self.file_list.changed.connect(self.refresh_state)
        hint = QLabel("Pages are created in this order. Drag or use Move up/down to reorder.")
        hint.setProperty("role", "muted")

        files_card = Card("Pages")
        files_card.add(self.file_list)
        files_card.add(hint)

        self.page_combo = combo(PAGE_OPTIONS, accessible_name="Page size")
        self.margin_combo = combo(MARGIN_OPTIONS, accessible_name="Margin")
        self.page_combo.currentIndexChanged.connect(lambda _i: self.refresh_state())
        options_card = Card("Page layout")
        options_card.add(form(("Page size:", self.page_combo), ("Margin:", self.margin_combo)))

        self.create_button = QPushButton("Create PDF")
        self.create_button.setProperty("variant", "primary")
        self.create_button.clicked.connect(self.create_pdf)

        for widget in (self.drop_zone, files_card, options_card, self.create_button):
            self.add_content(widget)
        self._busy_widgets = [self.drop_zone, files_card, options_card, self.create_button]
        self.refresh_state()

    def create_pdf(self) -> None:
        sources = self.file_list.paths()
        if not sources:
            return
        first = sources[0]
        out = preferred_output_path(
            first,
            out_dir=self._context.settings.output_dir_for(first),
            new_suffix=".pdf",
            label="pdf",
        )
        job = partial(
            images_to_pdf,
            sources,
            out,
            page_size=PageSize(self.page_combo.currentData()),
            margin_mm=float(self.margin_combo.currentData()),
        )
        self.run_task(
            self._context.runner,
            job,
            lambda path: self._on_done(path, len(sources)),
            disable=self._busy_widgets,
        )

    def refresh_state(self) -> None:
        if self.is_running:
            return
        self.create_button.setEnabled(bool(self.file_list.paths()))
        self.margin_combo.setEnabled(PageSize(self.page_combo.currentData()) is not PageSize.FIT)

    def _on_done(self, path: Path, pages: int) -> None:
        self.banner.show_success(f'Saved "{path.name}" ({pages} page(s))', folder=path.parent)
