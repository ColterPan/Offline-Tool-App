"""Logging to a rotating file in the user's log folder (there is no console in the packaged app)."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import platformdirs

from offline_tools import APP_ID

LOG_FILE_NAME = f"{APP_ID}.log"
MAX_LOG_BYTES = 1_000_000
LOG_BACKUP_COUNT = 3
LOG_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def default_log_dir() -> Path:
    return Path(platformdirs.user_log_dir(APP_ID, appauthor=False))


def configure_logging(log_dir: Path, level: int = logging.INFO) -> Path:
    """Send log records to `log_dir`/offline-tools.log (and stderr when one exists). Returns the file path."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / LOG_FILE_NAME
    formatter = logging.Formatter(LOG_FORMAT)

    file_handler = RotatingFileHandler(
        log_file, maxBytes=MAX_LOG_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.addHandler(file_handler)

    # Windowed PyInstaller builds have no stderr, and writing to None would crash.
    if sys.stderr is not None:
        stream_handler = logging.StreamHandler(sys.stderr)
        stream_handler.setFormatter(formatter)
        root.addHandler(stream_handler)

    return log_file
