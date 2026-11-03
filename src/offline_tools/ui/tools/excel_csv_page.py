"""Excel ↔ CSV: the direction is picked from the file you drop."""

from enum import StrEnum
from functools import partial
from pathlib import Path

from PySide6.QtWidgets import QLabel, QPushButton, QWidget

from offline_tools.core.data import (
    CSV_SUFFIXES,
    EXCEL_SUFFIXES,
    CsvEncoding,
    csv_to_excel,
    excel_to_csv,
    list_sheets,
)
from offline_tools.ui.context import AppContext
from offline_tools.ui.widgets.card import Card
from offline_tools.ui.widgets.drop_zone import DropZone
from offline_tools.ui.widgets.forms import combo, form
from offline_tools.ui.widgets.tool_page import ToolPage

ENCODING_OPTIONS = (
    ("For Excel (UTF-8 with BOM, recommended)", CsvEncoding.UTF8_BOM),
    ("Plain UTF-8 (for code and databases)", CsvEncoding.UTF8),
)
ALL_SHEETS_LABEL = "All sheets (one CSV each)"
CSV_NOTE = (
    "Numbers become real numbers. Values with leading zeros, such as phone numbers or postal "
    "codes, stay exactly as typed. Cells starting with = stay as text and never become formulas."
)


class Direction(StrEnum):
    NONE = "none"
    TO_CSV = "to_csv"
    TO_EXCEL = "to_excel"


class ExcelCsvPage(ToolPage):
    def __init__(self, context: AppContext, parent: QWidget | None = None) -> None:
        super().__init__(
            "Excel ↔ CSV",
            "Drop an Excel workbook to turn it into CSV, or a CSV file to turn it into Excel.",
            parent,
        )
        self._context = context
        self._file: Path | None = None
        self.direction = Direction.NONE

        self.drop_zone = DropZone(
            prompt="Drop an .xlsx or .csv file here",
            extensions=EXCEL_SUFFIXES | CSV_SUFFIXES | {".xls"},
        )
        self.drop_zone.files_selected.connect(lambda paths: self.select_file(paths[0]))
        self.file_label = QLabel("No file selected yet.")
        self.file_label.setProperty("role", "muted")

        self.sheet_combo = combo((), accessible_name="Sheet")
        self.encoding_combo = combo(ENCODING_OPTIONS, accessible_name="CSV encoding")
        self.excel_options = Card("CSV options")
        self.excel_options.add(
            form(("Sheet:", self.sheet_combo), ("Encoding:", self.encoding_combo))
        )
        self.excel_options.hide()

        self.csv_note = QLabel(CSV_NOTE)
        self.csv_note.setProperty("role", "muted")
        self.csv_note.setWordWrap(True)
        self.csv_note.hide()

        self.convert_button = QPushButton("Convert")
        self.convert_button.setProperty("variant", "primary")
        self.convert_button.clicked.connect(self.convert)

        for widget in (self.drop_zone, self.file_label, self.excel_options, self.csv_note,
                       self.convert_button):  # fmt: skip
            self.add_content(widget)
        self._busy_widgets = [self.drop_zone, self.excel_options, self.convert_button]
        self.refresh_state()

    def select_file(self, path: Path) -> None:
        self._file = path
        self.file_label.setText(f"File: {path.name}")
        self.direction = Direction.NONE
        self.excel_options.hide()
        self.csv_note.hide()
        if path.suffix.lower() in CSV_SUFFIXES:
            self.direction = Direction.TO_EXCEL
            self.csv_note.show()
            self.banner.clear()
            self.refresh_state()
            return
        # Reading sheet names opens the workbook, which can be slow for big files.
        self.run_task(
            self._context.runner,
            partial(list_sheets, path),
            self._on_sheets,
            disable=self._busy_widgets,
        )

    def convert(self) -> None:
        if self._file is None or self.direction is Direction.NONE:
            return
        out_dir = self._context.settings.output_dir_for(self._file)
        if self.direction is Direction.TO_EXCEL:
            job = partial(csv_to_excel, self._file, out_dir=out_dir)
            self.run_task(self._context.runner, job, self._on_done, disable=self._busy_widgets)
            return
        sheet = self.sheet_combo.currentData()
        job = partial(
            excel_to_csv,
            self._file,
            sheet=str(sheet) if sheet else None,
            out_dir=out_dir,
            encoding=CsvEncoding(self.encoding_combo.currentData()),
        )
        self.run_task(self._context.runner, job, self._on_done, disable=self._busy_widgets)

    def refresh_state(self) -> None:
        if self.is_running:
            return
        self.convert_button.setEnabled(self.direction is not Direction.NONE)
        self.convert_button.setText(
            "Convert to Excel" if self.direction is Direction.TO_EXCEL else "Convert to CSV"
        )

    def _on_sheets(self, sheets: tuple[str, ...]) -> None:
        self.sheet_combo.clear()
        if len(sheets) > 1:
            self.sheet_combo.addItem(ALL_SHEETS_LABEL, "")
        for name in sheets:
            self.sheet_combo.addItem(name, name)
        self.direction = Direction.TO_CSV
        self.excel_options.show()
        self.refresh_state()

    def _on_done(self, result: Path | tuple[Path, ...]) -> None:
        outputs = result if isinstance(result, tuple) else (result,)
        names = ", ".join(f'"{p.name}"' for p in outputs)
        self.banner.show_success(f"Saved {names}", folder=outputs[0].parent)
