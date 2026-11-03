"""Shared services handed to every tool page."""

from dataclasses import dataclass
from pathlib import Path

from offline_tools.settings import AppSettings
from offline_tools.ui.worker import TaskRunner


@dataclass(frozen=True)
class AppContext:
    settings: AppSettings
    runner: TaskRunner
    log_dir: Path
