"""Input validation and safe output naming. Tools never overwrite the user's files."""

from pathlib import Path

from offline_tools.core.errors import InvalidInputError, OutputError

MAX_NAME_ATTEMPTS = 1000


def require_file(path: Path) -> Path:
    """Return the resolved path, or raise InvalidInputError unless it is a non-empty file."""
    resolved = path.expanduser().resolve()
    if not resolved.exists():
        raise InvalidInputError(f'"{path.name}" could not be found.', f"missing: {resolved}")
    if resolved.is_dir():
        raise InvalidInputError(f'"{path.name}" is a folder, not a file.', f"is dir: {resolved}")
    if resolved.stat().st_size == 0:
        raise InvalidInputError(f'"{path.name}" is empty.', f"zero bytes: {resolved}")
    return resolved


def unique_output_path(
    source: Path,
    *,
    out_dir: Path | None = None,
    new_suffix: str | None = None,
    label: str = "converted",
) -> Path:
    """Build an output path like 'photo (converted).png' that does not exist yet.

    If the name is taken, ' 2', ' 3', ... is appended inside the brackets.
    """
    _check_suffix(new_suffix)
    folder = out_dir if out_dir is not None else source.parent
    suffix = new_suffix if new_suffix is not None else source.suffix

    for attempt in range(1, MAX_NAME_ATTEMPTS + 1):
        candidate = folder / f"{source.stem}{_bracket(label, attempt)}{suffix}"
        if not candidate.exists():
            return candidate

    raise OutputError(
        f'Could not find a free file name for "{source.name}". Try a different output folder.',
        f"{MAX_NAME_ATTEMPTS} names taken in {folder}",
    )


def preferred_output_path(
    source: Path,
    *,
    out_dir: Path | None = None,
    new_suffix: str | None = None,
    label: str = "converted",
) -> Path:
    """Use the plain name ('photo.jpg') when it is free, otherwise fall back to a labelled one."""
    _check_suffix(new_suffix)
    folder = out_dir if out_dir is not None else source.parent
    plain = folder / f"{source.stem}{new_suffix if new_suffix is not None else source.suffix}"
    if not plain.exists() and plain != source:
        return plain
    return unique_output_path(source, out_dir=out_dir, new_suffix=new_suffix, label=label)


def part_path(final: Path) -> Path:
    """Temporary name used while writing, so a crash never leaves a half-written result."""
    return final.with_name(f"{final.name}.part")


def _check_suffix(new_suffix: str | None) -> None:
    if new_suffix is not None and not new_suffix.startswith("."):
        raise ValueError(f"new_suffix must start with '.', got {new_suffix!r}")


def _bracket(label: str, attempt: int) -> str:
    parts = [part for part in (label, str(attempt) if attempt > 1 else "") if part]
    return f" ({' '.join(parts)})" if parts else ""
