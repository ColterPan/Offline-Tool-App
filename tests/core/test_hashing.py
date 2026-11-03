import hashlib
from pathlib import Path

import pytest

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.hashing import ALGORITHMS, hash_file, hashes_match, normalize_hash


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    path = tmp_path / "sample.bin"
    path.write_bytes(b"offline tools " * 100_000)  # ~1.4 MB, spans several chunks
    return path


@pytest.mark.parametrize("algorithm", ALGORITHMS)
def test_hash_file_matches_hashlib(sample_file: Path, algorithm: str) -> None:
    expected = hashlib.new(algorithm, sample_file.read_bytes()).hexdigest()

    assert hash_file(sample_file, algorithm) == expected


def test_hash_file_reports_progress_up_to_file_size(sample_file: Path) -> None:
    calls: list[tuple[int, int]] = []

    hash_file(sample_file, on_progress=lambda done, total: calls.append((done, total)))

    size = sample_file.stat().st_size
    assert len(calls) > 1
    assert calls[-1] == (size, size)
    assert [done for done, _ in calls] == sorted(done for done, _ in calls)


def test_hash_file_rejects_unknown_algorithm(sample_file: Path) -> None:
    with pytest.raises(InvalidInputError, match="not supported"):
        hash_file(sample_file, "crc32")


def test_hash_file_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(InvalidInputError):
        hash_file(tmp_path / "nope.bin")


def test_normalize_hash_strips_spaces_and_case() -> None:
    assert normalize_hash("  AB cd\nEF  ") == "abcdef"


def test_normalize_hash_accepts_sha256sum_output_format() -> None:
    line = "ABCDEF0123  OfflineTools-Setup.exe"

    assert normalize_hash(line) == "abcdef0123"


@pytest.mark.parametrize(
    ("expected", "actual", "result"),
    [
        ("ABC123", "abc123", True),
        (" abc 123 ", "abc123", True),
        ("abc124", "abc123", False),
        ("", "abc123", False),
    ],
)
def test_hashes_match(expected: str, actual: str, result: bool) -> None:
    assert hashes_match(expected, actual) is result
