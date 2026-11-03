"""Common layout for every page: title, summary, body, progress bar and result banner."""

from collections.abc import Callable, Sequence
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QProgressBar, QScrollArea, QVBoxLayout, QWidget

from offline_tools.ui.widgets.result_banner import ResultBanner
from offline_tools.ui.worker import Job, TaskRunner

PAGE_MARGIN = 32
MAX_CONTENT_WIDTH = 820
PROGRESS_STEPS = 1000


class ToolPage(QWidget):
    def __init__(self, title: str, summary: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("PageRoot")
        self._running = False

        content = QWidget()
        content.setMaximumWidth(MAX_CONTENT_WIDTH)
        self.body = QVBoxLayout(content)
        self.body.setContentsMargins(PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN, PAGE_MARGIN)
        self.body.setSpacing(14)

        heading = QLabel(title)
        heading.setProperty("role", "title")
        heading.setAccessibleName(title)
        description = QLabel(summary)
        description.setProperty("role", "muted")
        description.setWordWrap(True)
        self.progress = QProgressBar()
        self.progress.setRange(0, PROGRESS_STEPS)
        self.progress.setAccessibleName("Progress")
        self.progress.hide()
        self.banner = ResultBanner()

        self.body.addWidget(heading)
        self.body.addWidget(description)
        self.body.addSpacing(6)
        self._insert_at = self.body.count()
        self.body.addWidget(self.progress)
        self.body.addWidget(self.banner)
        self.body.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

    @property
    def is_running(self) -> bool:
        return self._running

    def add_content(self, widget: QWidget) -> None:
        """Add a widget above the progress bar and result banner."""
        self.body.insertWidget(self._insert_at, widget)
        self._insert_at += 1

    def run_task(
        self,
        runner: TaskRunner,
        job: Job,
        on_success: Callable[[Any], None],
        *,
        disable: Sequence[QWidget] = (),
    ) -> None:
        """Run `job` in the background, disabling `disable` and showing progress meanwhile."""
        self.banner.clear()
        self._set_running(True, disable)

        def succeeded(result: Any) -> None:
            self._set_running(False, disable)
            on_success(result)

        def failed(message: str, _detail: str) -> None:
            self._set_running(False, disable)
            self.banner.show_error(message)

        runner.submit(job, on_success=succeeded, on_error=failed, on_progress=self._show_progress)

    def refresh_state(self) -> None:
        """Re-evaluate which controls are enabled. Pages override this; called after each task."""

    def _set_running(self, running: bool, widgets: Sequence[QWidget]) -> None:
        self._running = running
        for widget in widgets:
            widget.setEnabled(not running)
        self.progress.setValue(0)
        self.progress.setVisible(running)
        if not running:
            self.refresh_state()

    def _show_progress(self, done: int, total: int) -> None:
        if total:
            self.progress.setValue(done * PROGRESS_STEPS // total)
