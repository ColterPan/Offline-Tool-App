import pytest
from PySide6.QtWidgets import QApplication
from pytestqt.qtbot import QtBot

from offline_tools.app import create_main_window
from offline_tools.settings import ThemeMode
from offline_tools.ui.context import AppContext
from offline_tools.ui.main_window import ABOUT_KEY, HOME_KEY, SETTINGS_KEY, MainWindow, tool_key
from offline_tools.ui.theme import DARK, LIGHT, Palette
from offline_tools.ui.tools.hash_checker import HashCheckerPage


@pytest.fixture
def window(qtbot: QtBot, qapp: QApplication, app_context: AppContext) -> MainWindow:
    win = create_main_window(qapp, app_context)
    qtbot.addWidget(win)
    return win


def test_starts_on_home_page(window: MainWindow) -> None:
    assert window.current_key == HOME_KEY
    assert window.windowTitle() == "Offline Tools"


def test_tool_pages_are_created_on_first_open(window: MainWindow) -> None:
    window.open_tool("file-hash")

    assert window.current_key == tool_key("file-hash")
    assert isinstance(window.stack.currentWidget(), HashCheckerPage)


def test_clicking_a_home_card_opens_the_tool(window: MainWindow, qtbot: QtBot) -> None:
    window.home_page.tool_requested.emit("file-hash")

    assert window.current_key == tool_key("file-hash")


@pytest.mark.parametrize("key", [SETTINGS_KEY, ABOUT_KEY, HOME_KEY])
def test_sidebar_selection_switches_page(window: MainWindow, key: str) -> None:
    item = window._sidebar_item(key)
    assert item is not None

    window.sidebar.setCurrentItem(item)

    assert window.current_key == key


def test_unknown_page_key_raises(window: MainWindow) -> None:
    with pytest.raises(KeyError):
        window.show_page("nope")


def test_home_search_filters_cards(window: MainWindow) -> None:
    home = window.home_page

    home.search.setText("sha256")
    assert home.visible_tool_ids() == ["file-hash"]
    assert home.empty_label.isHidden()

    home.search.setText("definitely-not-a-tool")
    assert home.visible_tool_ids() == []
    assert not home.empty_label.isHidden()


@pytest.mark.parametrize(("mode", "palette"), [(ThemeMode.DARK, DARK), (ThemeMode.LIGHT, LIGHT)])
def test_changing_theme_in_settings_applies_and_saves_it(
    window: MainWindow,
    qapp: QApplication,
    app_context: AppContext,
    mode: ThemeMode,
    palette: Palette,
) -> None:
    combo = window.settings_page.theme_combo

    combo.setCurrentIndex(combo.findData(mode))

    assert app_context.settings.theme is mode
    assert palette.window in qapp.styleSheet()
