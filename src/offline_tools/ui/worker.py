"""Run slow core functions on a background thread so the window never freezes."""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal

from offline_tools.core.errors import ToolError

logger = logging.getLogger(__name__)

UNEXPECTED_ERROR_MESSAGE = (
    "Something went wrong. The details were saved to the log file (Settings → Open log folder)."
)

type ProgressFn = Callable[[int, int], None]
# A job is called as job(on_progress=...). Core functions all take a keyword `on_progress`,
# so functools.partial(core_function, args...) is a valid job.
type Job = Callable[..., Any]


class _TaskSignals(QObject):
    # Created on the UI thread, so emits from the worker are delivered back on the UI thread.
    progress = Signal(int, int)
    succeeded = Signal(object)
    failed = Signal(str, str)  # user_message, detail


class _Task(QRunnable):
    def __init__(self, job: Job) -> None:
        super().__init__()
        self.setAutoDelete(False)  # Python owns the task; TaskRunner drops it when done
        self.signals = _TaskSignals()
        self._job = job

    def run(self) -> None:
        try:
            result = self._job(on_progress=self.signals.progress.emit)
        except ToolError as exc:
            logger.warning("Tool failed: %s", exc.detail)
            self.signals.failed.emit(exc.user_message, exc.detail)
        except Exception as exc:
            # Thread boundary: anything that isn't a ToolError is a bug, so log the traceback.
            logger.exception("Unexpected error in background task")
            self.signals.failed.emit(UNEXPECTED_ERROR_MESSAGE, repr(exc))
        else:
            self.signals.succeeded.emit(result)


class TaskRunner:
    def __init__(self, pool: QThreadPool | None = None) -> None:
        self._pool = pool or QThreadPool()
        self._active: set[_Task] = set()

    @property
    def active_count(self) -> int:
        return len(self._active)

    def submit(
        self,
        job: Job,
        *,
        on_success: Callable[[Any], None],
        on_error: Callable[[str, str], None],
        on_progress: ProgressFn | None = None,
    ) -> None:
        """Run `job(on_progress=...)` in the pool. Callbacks run on the UI thread."""
        task = _Task(job)
        self._active.add(task)
        if on_progress is not None:
            task.signals.progress.connect(on_progress)
        task.signals.succeeded.connect(on_success)
        task.signals.failed.connect(on_error)
        task.signals.succeeded.connect(lambda _result: self._active.discard(task))
        task.signals.failed.connect(lambda _msg, _detail: self._active.discard(task))
        self._pool.start(task)

    def wait_for_done(self, timeout_ms: int = -1) -> bool:
        return self._pool.waitForDone(timeout_ms)
