import datetime as dt
from pathlib import Path

import openpyxl
import pytest

from offline_tools.core.data import (
    MAX_EXCEL_ROWS,
    CsvEncoding,
    csv_to_excel,
    excel_to_csv,
    list_sheets,
)
from offline_tools.core.errors import InvalidInputError


@pytest.fixture
def workbook(tmp_path: Path) -> Path:
    wb = openpyxl.Workbook()
    sales = wb.active
    assert sales is not None
    sales.title = "Sales"
    sales.append(["Name", "Date", "Amount", "Paid"])
    sales.append(["Ali", dt.datetime(2026, 11, 3), 12.5, True])
    sales.append(["Mei, Ling", dt.datetime(2026, 11, 4, 9, 30), 7, False])
    staff = wb.create_sheet("Staff|2026")  # allowed in Excel, not in file names
    staff.append(["ID", "Name"])
    staff.append(["0042", "Ravi"])
    path = tmp_path / "report.xlsx"
    wb.save(path)
    return path


# ---- Excel -> CSV -------------------------------------------------------------


def test_list_sheets(workbook: Path) -> None:
    assert list_sheets(workbook) == ("Sales", "Staff|2026")


def test_excel_to_csv_single_sheet(workbook: Path, tmp_path: Path) -> None:
    outputs = excel_to_csv(workbook, sheet="Sales", out_dir=tmp_path)

    assert outputs == (tmp_path / "report (Sales).csv",)
    text = outputs[0].read_text(encoding="utf-8-sig")
    assert text.splitlines() == [
        "Name,Date,Amount,Paid",
        "Ali,2026-11-03,12.5,TRUE",
        '"Mei, Ling",2026-11-04 09:30:00,7,FALSE',
    ]


def test_excel_to_csv_writes_bom_only_for_excel_encoding(workbook: Path, tmp_path: Path) -> None:
    plain_dir = tmp_path / "plain"
    plain_dir.mkdir()
    (with_bom,) = excel_to_csv(workbook, sheet="Sales", out_dir=tmp_path)
    (plain,) = excel_to_csv(workbook, sheet="Sales", out_dir=plain_dir, encoding=CsvEncoding.UTF8)

    assert with_bom.read_bytes().startswith(b"\xef\xbb\xbf")
    assert not plain.read_bytes().startswith(b"\xef\xbb\xbf")


def test_excel_to_csv_all_sheets_with_safe_file_names(workbook: Path, tmp_path: Path) -> None:
    outputs = excel_to_csv(workbook, sheet=None, out_dir=tmp_path)

    assert [p.name for p in outputs] == ["report (Sales).csv", "report (Staff_2026).csv"]
    assert "0042,Ravi" in outputs[1].read_text(encoding="utf-8-sig")


def test_excel_to_csv_unknown_sheet(workbook: Path, tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="no sheet"):
        excel_to_csv(workbook, sheet="Nope", out_dir=tmp_path)


def test_excel_to_csv_rejects_files_that_are_not_workbooks(tmp_path: Path) -> None:
    fake = tmp_path / "fake.xlsx"
    fake.write_text("hello", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="isn't an Excel"):
        excel_to_csv(fake, sheet=None, out_dir=tmp_path)


# ---- CSV -> Excel -------------------------------------------------------------


def _read_cells(path: Path) -> list[list[tuple[object, str]]]:
    wb = openpyxl.load_workbook(path)
    ws = wb.worksheets[0]
    return [[(c.value, c.data_type) for c in row] for row in ws.iter_rows()]


def test_csv_to_excel_converts_numbers_but_keeps_ids_as_text(tmp_path: Path) -> None:
    source = tmp_path / "contacts.csv"
    source.write_text(
        "Name,Phone,Postal,Amount,Card\nAli,91234567,018956,12.50,4111111111111111111\n",
        encoding="utf-8",
    )

    result = csv_to_excel(source, out_dir=tmp_path)

    assert result == tmp_path / "contacts.xlsx"
    rows = _read_cells(result)
    assert [value for value, _ in rows[1]] == [
        "Ali",
        91234567,
        "018956",
        12.5,
        "4111111111111111111",
    ]


def test_csv_to_excel_never_creates_formulas(tmp_path: Path) -> None:
    source = tmp_path / "evil.csv"
    source.write_text('Name,Note\nBob,"=HYPERLINK(""http://x"",""click"")"\n', encoding="utf-8")

    rows = _read_cells(csv_to_excel(source, out_dir=tmp_path))

    value, data_type = rows[1][1]
    assert value == '=HYPERLINK("http://x","click")'
    assert data_type == "s"


def test_csv_to_excel_detects_semicolons_and_windows_encoding(tmp_path: Path) -> None:
    source = tmp_path / "export.csv"
    source.write_bytes("Café;Prix\nCrème;3\n".encode("cp1252"))

    rows = _read_cells(csv_to_excel(source, out_dir=tmp_path))

    assert [v for v, _ in rows[0]] == ["Café", "Prix"]
    assert [v for v, _ in rows[1]] == ["Crème", 3]


def test_csv_to_excel_rejects_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.csv"
    source.write_text("\n\n", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="no data"):
        csv_to_excel(source, out_dir=tmp_path)


def test_csv_to_excel_rejects_more_rows_than_excel_allows(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("offline_tools.core.data.MAX_EXCEL_ROWS", 2)
    source = tmp_path / "big.csv"
    source.write_text("a\n1\n2\n3\n", encoding="utf-8")

    with pytest.raises(InvalidInputError, match="rows"):
        csv_to_excel(source, out_dir=tmp_path)
    assert list(tmp_path.glob("*.xlsx")) == []
    assert MAX_EXCEL_ROWS == 1_048_576
