"""User preferences, stored in an .ini file in the user's config folder."""

import logging
from enum import StrEnum
from pathlib import Path

from PySide6.QtCore import QSettings

from offline_tools import APP_ID

logger = logging.getLogger(__name__)


class ThemeMode(StrEnum):
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class OutputMode(StrEnum):
    NEXT_TO_INPUT = "next_to_input"
    FOLDER = "folder"


_THEME_KEY = "appearance/theme"
_OUTPUT_MODE_KEY = "output/mode"
_OUTPUT_FOLDER_KEY = "output/folder"


def default_store() -> QSettings:
    return QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, APP_ID, APP_ID)


class AppSettings:
    """Typed access to QSettings. Values read from disk are validated, never trusted."""

    def __init__(self, store: QSettings) -> None:
        self._store = store

    @property
    def theme(self) -> ThemeMode:
        return self._read_enum(_THEME_KEY, ThemeMode, ThemeMode.SYSTEM)

    def set_theme(self, mode: ThemeMode) -> None:
        self._write(_THEME_KEY, mode.value)

    @property
    def output_mode(self) -> OutputMode:
        return self._read_enum(_OUTPUT_MODE_KEY, OutputMode, OutputMode.NEXT_TO_INPUT)

    def set_output_mode(self, mode: OutputMode) -> None:
        self._write(_OUTPUT_MODE_KEY, mode.value)

    @property
    def output_folder(self) -> Path | None:
        raw = self._store.value(_OUTPUT_FOLDER_KEY, "")
        return Path(raw) if isinstance(raw, str) and raw else None

    def set_output_folder(self, folder: Path) -> None:
        self._write(_OUTPUT_FOLDER_KEY, str(folder))

    def output_dir_for(self, source: Path) -> Path:
        """Where results for `source` should be saved. Falls back to the source folder."""
        folder = self.output_folder
        if self.output_mode is OutputMode.FOLDER and folder is not None:
            if folder.is_dir():
                return folder
            logger.warning("Output folder %s no longer exists; saving next to input", folder)
        return source.parent

    def _read_enum[E: StrEnum](self, key: str, enum_type: type[E], default: E) -> E:
        raw = self._store.value(key, default.value)
        try:
            return enum_type(str(raw))
        except ValueError:
            logger.warning("Ignoring invalid setting %s=%r", key, raw)
            return default

    def _write(self, key: str, value: str) -> None:
        self._store.setValue(key, value)
        self._store.sync()
        if self._store.status() is not QSettings.Status.NoError:
            logger.error("Could not save setting %s (status %s)", key, self._store.status())
