"""Progress reporting shared by core functions: on_progress(done, total)."""

from collections.abc import Callable

type ProgressCallback = Callable[[int, int], None]


def report(on_progress: ProgressCallback | None, done: int, total: int) -> None:
    if on_progress is not None:
        on_progress(done, total)
