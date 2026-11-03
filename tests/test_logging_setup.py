import logging
from collections.abc import Iterator
from pathlib import Path

import pytest

from offline_tools.logging_setup import (
    LOG_DIR_ENV,
    LOG_FILE_NAME,
    configure_logging,
    default_log_dir,
)


@pytest.fixture
def restore_root_logger() -> Iterator[None]:
    root = logging.getLogger()
    saved_handlers, saved_level = list(root.handlers), root.level
    yield
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    for handler in saved_handlers:
        root.addHandler(handler)
    root.setLevel(saved_level)


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_writes_to_file(tmp_path: Path) -> None:
    log_file = configure_logging(tmp_path / "logs")

    logging.getLogger("offline_tools.test").info("hello from the test")
    for handler in logging.getLogger().handlers:
        handler.flush()

    assert log_file == tmp_path / "logs" / LOG_FILE_NAME
    assert "hello from the test" in log_file.read_text(encoding="utf-8")


def test_log_dir_can_be_overridden(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv(LOG_DIR_ENV, str(tmp_path))

    assert default_log_dir() == tmp_path


def test_log_dir_defaults_to_platform_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LOG_DIR_ENV, raising=False)

    assert "offline-tools" in str(default_log_dir())


@pytest.mark.usefixtures("restore_root_logger")
def test_configure_logging_is_idempotent(tmp_path: Path) -> None:
    configure_logging(tmp_path)
    configure_logging(tmp_path)

    file_handlers = [h for h in logging.getLogger().handlers if isinstance(h, logging.FileHandler)]
    assert len(file_handlers) == 1
