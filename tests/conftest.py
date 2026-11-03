import os
from pathlib import Path

import pytest

# Run Qt without a visible window (also needed on CI machines with no display).
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings

from offline_tools.settings import AppSettings
from offline_tools.ui.context import AppContext
from offline_tools.ui.worker import TaskRunner


@pytest.fixture
def settings(tmp_path: Path) -> AppSettings:
    return AppSettings(QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat))


@pytest.fixture
def app_context(qapp: object, settings: AppSettings, tmp_path: Path) -> AppContext:
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    return AppContext(settings=settings, runner=TaskRunner(), log_dir=log_dir)
