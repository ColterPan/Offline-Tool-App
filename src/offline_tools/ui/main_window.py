"""Main window: sidebar navigation on the left, the current page on the right."""

import logging
from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from offline_tools import APP_NAME
from offline_tools.registry import ToolRegistry
from offline_tools.settings import ThemeMode
from offline_tools.ui.context import AppContext
from offline_tools.ui.pages.about_page import AboutPage
from offline_tools.ui.pages.home_page import HomePage
from offline_tools.ui.pages.settings_page import SettingsPage

logger = logging.getLogger(__name__)

HOME_KEY = "home"
SETTINGS_KEY = "settings"
ABOUT_KEY = "about"
TOOL_PREFIX = "tool:"
DEFAULT_SIZE = (1120, 740)
MIN_SIZE = (900, 600)


def tool_key(tool_id: str) -> str:
    return f"{TOOL_PREFIX}{tool_id}"


class MainWindow(QMainWindow):
    def __init__(
        self,
        context: AppContext,
        registry: ToolRegistry,
        on_theme_change: Callable[[ThemeMode], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._context = context
        self._registry = registry
        self._pages: dict[str, QWidget] = {}
        self.setWindowTitle(APP_NAME)
        self.resize(*DEFAULT_SIZE)
        self.setMinimumSize(*MIN_SIZE)

        self.sidebar = QListWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setAccessibleName("Navigation")
        self.stack = QStackedWidget()

        self.home_page = HomePage(registry)
        self.home_page.tool_requested.connect(self.open_tool)
        self.settings_page = SettingsPage(context)
        self.settings_page.theme_changed.connect(on_theme_change)
        self._add_page(HOME_KEY, self.home_page)
        self._add_page(SETTINGS_KEY, self.settings_page)
        self._add_page(ABOUT_KEY, AboutPage())
        self._build_sidebar()
        self.sidebar.currentItemChanged.connect(self._on_sidebar_changed)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.sidebar)
        layout.addWidget(self.stack, stretch=1)
        self.setCentralWidget(central)
        self.show_page(HOME_KEY)

    @property
    def current_key(self) -> str:
        current = self.stack.currentWidget()
        return next(key for key, page in self._pages.items() if page is current)

    def open_tool(self, tool_id: str) -> None:
        self.show_page(tool_key(tool_id))

    def show_page(self, key: str) -> None:
        self.stack.setCurrentWidget(self._page_for(key))
        item = self._sidebar_item(key)
        if item is not None and self.sidebar.currentItem() is not item:
            self.sidebar.blockSignals(True)
            self.sidebar.setCurrentItem(item)
            self.sidebar.blockSignals(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._context.runner.active_count == 0:
            event.accept()
            return
        answer = QMessageBox.question(
            self,
            APP_NAME,
            "A task is still running. Quit anyway? The unfinished result will not be saved.",
        )
        if answer is QMessageBox.StandardButton.Yes:
            event.accept()
        else:
            event.ignore()

    def _page_for(self, key: str) -> QWidget:
        """Tool pages are created on first visit to keep start-up fast."""
        if key not in self._pages:
            if not key.startswith(TOOL_PREFIX):
                raise KeyError(key)
            tool = self._registry.get(key.removeprefix(TOOL_PREFIX))
            logger.info("Opening tool %s", tool.id)
            self._add_page(key, tool.page_factory(self._context))
        return self._pages[key]

    def _add_page(self, key: str, page: QWidget) -> None:
        self._pages[key] = page
        self.stack.addWidget(page)

    def _build_sidebar(self) -> None:
        self._add_nav_item("Home", HOME_KEY)
        for category, tools in self._registry.by_category().items():
            self._add_header(category.value.upper())
            for tool in tools:
                self._add_nav_item(tool.name, tool_key(tool.id))
        self._add_header("")
        self._add_nav_item("Settings", SETTINGS_KEY)
        self._add_nav_item("About & privacy", ABOUT_KEY)

    def _add_nav_item(self, label: str, key: str) -> None:
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, key)
        self.sidebar.addItem(item)

    def _add_header(self, label: str) -> None:
        item = QListWidgetItem(label)
        item.setFlags(Qt.ItemFlag.NoItemFlags)
        self.sidebar.addItem(item)

    def _sidebar_item(self, key: str) -> QListWidgetItem | None:
        for row in range(self.sidebar.count()):
            item = self.sidebar.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                return item
        return None

    def _on_sidebar_changed(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        key = current.data(Qt.ItemDataRole.UserRole) if current is not None else None
        if isinstance(key, str):
            self.show_page(key)
