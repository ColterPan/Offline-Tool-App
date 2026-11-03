"""Application start-up: logging, settings, theme, main window."""

import logging
import sys
from types import TracebackType

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from offline_tools import APP_ID, APP_NAME, __version__
from offline_tools.logging_setup import configure_logging, default_log_dir
from offline_tools.registry import ToolRegistry
from offline_tools.resources import asset_path
from offline_tools.settings import AppSettings, ThemeMode, default_store
from offline_tools.ui.context import AppContext
from offline_tools.ui.main_window import MainWindow
from offline_tools.ui.theme import apply_theme
from offline_tools.ui.tools import ALL_TOOLS
from offline_tools.ui.worker import UNEXPECTED_ERROR_MESSAGE, TaskRunner

logger = logging.getLogger(__name__)

SHUTDOWN_WAIT_MS = 3000
SMOKE_TEST_FLAG = "--smoke-test"
SMOKE_TEST_QUIT_MS = 500


def main(argv: list[str] | None = None) -> int:
    log_dir = default_log_dir()
    log_file = configure_logging(log_dir)
    logger.info("Starting %s %s (log file: %s)", APP_NAME, __version__, log_file)

    args = argv if argv is not None else sys.argv
    app = QApplication(args)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(asset_path("icon.png"))))
    _install_excepthook()

    context = AppContext(
        settings=AppSettings(default_store()), runner=TaskRunner(), log_dir=log_dir
    )
    window = create_main_window(app, context)
    window.show()
    if SMOKE_TEST_FLAG in args:
        # Used by CI to prove the packaged app starts: open the window, then quit.
        logger.info("Smoke test: quitting after start-up")
        QTimer.singleShot(SMOKE_TEST_QUIT_MS, app.quit)

    exit_code = app.exec()
    context.runner.wait_for_done(SHUTDOWN_WAIT_MS)
    logger.info("Exiting with code %s", exit_code)
    return exit_code


def create_main_window(app: QApplication, context: AppContext) -> MainWindow:
    settings = context.settings

    def change_theme(mode: ThemeMode) -> None:
        settings.set_theme(mode)
        apply_theme(app, mode)

    def follow_system_theme(_scheme: Qt.ColorScheme) -> None:
        if settings.theme is ThemeMode.SYSTEM:
            apply_theme(app, ThemeMode.SYSTEM)

    apply_theme(app, settings.theme)
    app.styleHints().colorSchemeChanged.connect(follow_system_theme)
    return MainWindow(context, ToolRegistry(ALL_TOOLS), on_theme_change=change_theme)


def _install_excepthook() -> None:
    """Log crashes in Qt callbacks and tell the user, instead of failing silently."""
    showing_dialog = False

    def hook(exc_type: type[BaseException], exc: BaseException, tb: TracebackType | None) -> None:
        nonlocal showing_dialog
        logger.critical("Unhandled exception", exc_info=(exc_type, exc, tb))
        if showing_dialog or QApplication.instance() is None:
            return
        showing_dialog = True
        try:
            QMessageBox.critical(None, APP_NAME, UNEXPECTED_ERROR_MESSAGE)
        finally:
            showing_dialog = False

    sys.excepthook = hook
