"""File checksums, used to confirm a download has not been tampered with."""

import hashlib
from collections.abc import Callable
from pathlib import Path

from offline_tools.core.errors import InvalidInputError
from offline_tools.core.paths import require_file

ALGORITHMS = ("sha256", "sha1", "md5")
CHUNK_SIZE = 1024 * 1024

ProgressCallback = Callable[[int, int], None]


def hash_file(
    path: Path,
    algorithm: str = "sha256",
    on_progress: ProgressCallback | None = None,
) -> str:
    """Return the file's lowercase hex digest. Reads in chunks so big files use little memory."""
    if algorithm not in ALGORITHMS:
        raise InvalidInputError(
            f'"{algorithm}" is not supported. Choose one of: {", ".join(ALGORITHMS)}.'
        )

    source = require_file(path)
    total = source.stat().st_size
    digest = hashlib.new(algorithm)
    done = 0

    try:
        with source.open("rb") as handle:
            while chunk := handle.read(CHUNK_SIZE):
                digest.update(chunk)
                done += len(chunk)
                if on_progress is not None:
                    on_progress(done, total)
    except OSError as exc:
        raise InvalidInputError(f'"{source.name}" could not be read.', repr(exc)) from exc

    return digest.hexdigest()


def normalize_hash(text: str) -> str:
    """Lowercase and strip whitespace. Accepts 'HASH  filename' lines from sha256sum files."""
    first_token = text.strip().split("  ", 1)[0]
    return "".join(first_token.split()).lower()


def hashes_match(expected: str, actual: str) -> bool:
    expected_clean = normalize_hash(expected)
    return bool(expected_clean) and expected_clean == normalize_hash(actual)
