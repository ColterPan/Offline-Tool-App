from pathlib import Path

import pytest

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.paths import require_file, unique_output_path


def test_require_file_returns_resolved_path(tmp_path: Path) -> None:
    source = tmp_path / "doc.txt"
    source.write_text("hello", encoding="utf-8")

    assert require_file(source) == source.resolve()


def test_require_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="could not be found"):
        require_file(tmp_path / "missing.pdf")


def test_require_file_rejects_folder(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError, match="is a folder"):
        require_file(tmp_path)


def test_require_file_rejects_empty_file(tmp_path: Path) -> None:
    source = tmp_path / "empty.png"
    source.touch()

    with pytest.raises(InvalidInputError, match="is empty"):
        require_file(source)


def test_unique_output_path_adds_label_next_to_source(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"

    assert unique_output_path(source) == tmp_path / "photo (converted).png"


def test_unique_output_path_changes_suffix_and_folder(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    out_dir = tmp_path / "out"

    result = unique_output_path(source, out_dir=out_dir, new_suffix=".pdf", label="pdf")

    assert result == out_dir / "photo (pdf).pdf"


def test_unique_output_path_never_returns_existing_file(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    (tmp_path / "photo (converted).png").touch()
    (tmp_path / "photo (converted 2).png").touch()

    assert unique_output_path(source) == tmp_path / "photo (converted 3).png"


def test_unique_output_path_never_returns_the_source_itself(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    source.touch()

    result = unique_output_path(source, label="")

    assert result != source
    assert not result.exists()


def test_unique_output_path_rejects_suffix_without_dot(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="must start with"):
        unique_output_path(tmp_path / "a.png", new_suffix="pdf")
