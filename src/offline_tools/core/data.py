"""Excel <-> CSV conversion (openpyxl + the csv module)."""

import codecs
import csv
import datetime as dt
import io
import logging
import re
import zipfile
from collections.abc import Iterable
from enum import StrEnum
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils.exceptions import InvalidFileException
from openpyxl.workbook.workbook import Workbook as LoadedWorkbook
from openpyxl.worksheet._write_only import WriteOnlyWorksheet

from offline_tools.core.errors import InvalidInputError, OutputError, ToolError
from offline_tools.core.paths import (
    part_path,
    preferred_output_path,
    require_file,
    unique_output_path,
)
from offline_tools.core.progress import ProgressCallback, report

logger = logging.getLogger(__name__)

EXCEL_SUFFIXES = frozenset({".xlsx", ".xlsm"})
CSV_SUFFIXES = frozenset({".csv", ".tsv", ".txt"})
MAX_EXCEL_ROWS = 1_048_576
MAX_EXACT_DIGITS = 15  # Excel numbers are doubles: longer digit strings would lose digits
SNIFF_CHARS = 64 * 1024
READ_CHUNK = 1024 * 1024
CANDIDATE_DELIMITERS = ",;\t|"
FALLBACK_ENCODING = "cp1252"  # what Excel on Windows usually writes when not UTF-8
PROGRESS_EVERY_ROWS = 2000
MAX_SHEET_TITLE = 31

_UNSAFE_FILENAME_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_UNSAFE_SHEET_CHARS = re.compile(r"[\[\]:*?/\\]")
_INTEGER = re.compile(r"-?(0|[1-9]\d*)")
_DECIMAL = re.compile(r"-?(0|[1-9]\d*)\.\d+")


class CsvEncoding(StrEnum):
    UTF8_BOM = "utf-8-sig"  # Excel needs the BOM to read accents/Chinese characters correctly
    UTF8 = "utf-8"


# ---- Excel -> CSV -------------------------------------------------------------


def list_sheets(path: Path) -> tuple[str, ...]:
    workbook = _open_workbook(path)
    try:
        return tuple(workbook.sheetnames)
    finally:
        workbook.close()


def excel_to_csv(
    source: Path,
    *,
    sheet: str | None,
    out_dir: Path,
    encoding: CsvEncoding = CsvEncoding.UTF8_BOM,
    on_progress: ProgressCallback | None = None,
) -> tuple[Path, ...]:
    """Write one CSV per sheet (sheet=None means every sheet). Formulas become their values."""
    workbook = _open_workbook(source)
    try:
        if sheet is not None and sheet not in workbook.sheetnames:
            raise InvalidInputError(f'The workbook has no sheet called "{sheet}".')
        names = list(workbook.sheetnames) if sheet is None else [sheet]
        outputs: list[Path] = []
        for index, name in enumerate(names, start=1):
            label = _UNSAFE_FILENAME_CHARS.sub("_", name)
            out = unique_output_path(source, out_dir=out_dir, new_suffix=".csv", label=label)
            _write_csv(workbook[name].iter_rows(values_only=True), out, encoding)
            outputs.append(out)
            report(on_progress, index, len(names))
        return tuple(outputs)
    finally:
        workbook.close()


def _open_workbook(path: Path) -> LoadedWorkbook:
    source = require_file(path)
    if source.suffix.lower() == ".xls":
        raise InvalidInputError(
            "Old .xls files aren't supported yet. Open it in Excel and save it as .xlsx first."
        )
    try:
        return load_workbook(source, read_only=True, data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, OSError) as exc:
        raise InvalidInputError(
            f'"{source.name}" isn\'t an Excel workbook this app can read (.xlsx).', repr(exc)
        ) from exc


def _write_csv(rows: Iterable[tuple[object, ...]], out: Path, encoding: CsvEncoding) -> None:
    tmp = part_path(out)
    try:
        with tmp.open("w", encoding=encoding.value, newline="") as handle:
            writer = csv.writer(handle)
            pending_blank_rows = 0  # blank rows are only written if real data follows
            for row in rows:
                cells = [_csv_text(value) for value in row]
                if not any(cells):
                    pending_blank_rows += 1
                    continue
                writer.writerows([[]] * pending_blank_rows)
                pending_blank_rows = 0
                writer.writerow(cells)
        tmp.replace(out)
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(f'Could not save "{out.name}".', repr(exc)) from exc


def _csv_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):  # before int: bool is a subclass of int
        return "TRUE" if value else "FALSE"
    if isinstance(value, dt.datetime):
        return value.date().isoformat() if value.time() == dt.time() else value.isoformat(" ")
    if isinstance(value, dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() and abs(value) < 1e15 else f"{value:.15g}"
    return str(value)


# ---- CSV -> Excel -------------------------------------------------------------


def csv_to_excel(
    source: Path,
    *,
    out_dir: Path,
    on_progress: ProgressCallback | None = None,
) -> Path:
    """Convert a CSV to .xlsx. Numbers become numbers; IDs with leading zeros stay text."""
    src = require_file(source)
    out = preferred_output_path(src, out_dir=out_dir, new_suffix=".xlsx")
    tmp = part_path(out)
    try:
        workbook = _csv_workbook(src, on_progress)
        workbook.save(tmp)
        tmp.replace(out)
    except ToolError:
        tmp.unlink(missing_ok=True)
        raise
    except (csv.Error, UnicodeDecodeError) as exc:
        tmp.unlink(missing_ok=True)
        raise InvalidInputError(
            f'"{src.name}" isn\'t a CSV file this app can read.', repr(exc)
        ) from exc
    except OSError as exc:
        tmp.unlink(missing_ok=True)
        raise OutputError(f'Could not convert "{src.name}".', repr(exc)) from exc
    return out


def _csv_workbook(src: Path, on_progress: ProgressCallback | None) -> Workbook:
    encoding = _detect_encoding(src)
    total = src.stat().st_size
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet(_sheet_title(src.stem))
    rows = 0
    has_data = False
    try:
        with src.open("rb") as raw:
            text = io.TextIOWrapper(raw, encoding=encoding, errors="replace", newline="")
            dialect = _sniff(text.read(SNIFF_CHARS))
            text.seek(0)
            for row in csv.reader(text, dialect):
                rows += 1
                if rows > MAX_EXCEL_ROWS:
                    raise InvalidInputError(
                        f'"{src.name}" has more rows than Excel allows ({MAX_EXCEL_ROWS:,}).'
                    )
                has_data = has_data or any(cell.strip() for cell in row)
                sheet.append([_excel_cell(sheet, cell) for cell in row])
                if rows % PROGRESS_EVERY_ROWS == 0:
                    report(on_progress, raw.tell(), total)
    except BaseException:
        _discard(sheet)
        raise
    if not has_data:
        _discard(sheet)
        raise InvalidInputError(f'"{src.name}" has no data to convert.')
    report(on_progress, total, total)
    return workbook


def _discard(sheet: WriteOnlyWorksheet) -> None:
    """Finish openpyxl's temporary sheet file so an aborted conversion cleans up quietly."""
    try:
        sheet.close()
    except (OSError, ValueError) as exc:
        logger.debug("Ignoring error while discarding sheet: %r", exc)


def _detect_encoding(path: Path) -> str:
    decoder = codecs.getincrementaldecoder("utf-8-sig")()
    try:
        with path.open("rb") as handle:
            while chunk := handle.read(READ_CHUNK):
                decoder.decode(chunk)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError:
        return FALLBACK_ENCODING
    return "utf-8-sig"


def _sniff(sample: str) -> type[csv.Dialect] | csv.Dialect:
    try:
        return csv.Sniffer().sniff(sample, delimiters=CANDIDATE_DELIMITERS)
    except csv.Error:
        return csv.excel


def _excel_cell(sheet: WriteOnlyWorksheet, text: str) -> object:
    value = _excel_value(text)
    if isinstance(value, str) and value.startswith("="):
        # openpyxl would store this as a live formula; force plain text so a CSV can't
        # smuggle in formulas like =HYPERLINK(...) (CSV injection).
        cell = WriteOnlyCell(sheet, value=value)
        cell.data_type = "s"
        return cell
    return value


def _excel_value(text: str) -> int | float | str:
    stripped = text.strip()
    digit_count = len(stripped.lstrip("-").replace(".", ""))
    if digit_count <= MAX_EXACT_DIGITS:
        if _INTEGER.fullmatch(stripped):
            return int(stripped)
        if _DECIMAL.fullmatch(stripped):
            return float(stripped)
    return ILLEGAL_CHARACTERS_RE.sub("", text)


def _sheet_title(stem: str) -> str:
    title = _UNSAFE_SHEET_CHARS.sub("_", stem).strip("'")[:MAX_SHEET_TITLE]
    return title or "Sheet1"
