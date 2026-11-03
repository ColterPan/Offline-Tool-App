import logging
import os
import subprocess
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QMessageBox

from offline_tools import app as app_module
from offline_tools.app import SMOKE_TEST_FLAG
from offline_tools.logging_setup import LOG_DIR_ENV, LOG_FILE_NAME
from offline_tools.ui.worker import UNEXPECTED_ERROR_MESSAGE

SMOKE_TIMEOUT_S = 60


def test_app_starts_and_quits_in_smoke_test_mode(tmp_path: Path) -> None:
    # A separate process, like CI's packaged-app check: running the Qt event loop to
    # completion inside pytest would leave the shared QApplication in a "quitting" state.
    env = {**os.environ, "QT_QPA_PLATFORM": "offscreen", LOG_DIR_ENV: str(tmp_path)}

    result = subprocess.run(
        [sys.executable, "-m", "offline_tools", SMOKE_TEST_FLAG],
        env=env,
        capture_output=True,
        text=True,
        timeout=SMOKE_TIMEOUT_S,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    log_text = (tmp_path / LOG_FILE_NAME).read_text(encoding="utf-8")
    assert "Starting Offline Tools" in log_text
    assert "Smoke test" in log_text


def test_excepthook_logs_and_tells_the_user(
    qapp: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)  # restored after the test
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "critical", lambda _parent, _title, text: shown.append(text))
    app_module._install_excepthook()

    try:
        raise RuntimeError("kaboom")
    except RuntimeError as exc:
        with caplog.at_level(logging.CRITICAL):
            sys.excepthook(type(exc), exc, exc.__traceback__)

    assert "Unhandled exception" in caplog.text
    assert shown == [UNEXPECTED_ERROR_MESSAGE]
