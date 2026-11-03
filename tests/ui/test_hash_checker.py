import hashlib
from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from offline_tools.ui.context import AppContext
from offline_tools.ui.tools.hash_checker import MATCH_TEXT, MISMATCH_TEXT, HashCheckerPage

WAIT_MS = 5000


@pytest.fixture
def page(qtbot: QtBot, app_context: AppContext) -> HashCheckerPage:
    widget = HashCheckerPage(app_context)
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def sample(tmp_path: Path) -> Path:
    path = tmp_path / "installer.exe"
    path.write_bytes(b"pretend installer bytes")
    return path


def _wait_for_hash(qtbot: QtBot, page: HashCheckerPage) -> str:
    qtbot.waitUntil(lambda: bool(page.result_edit.text()) and not page.is_busy, timeout=WAIT_MS)
    return page.result_edit.text()


def test_selecting_a_file_shows_its_sha256(
    qtbot: QtBot, page: HashCheckerPage, sample: Path
) -> None:
    page.select_file(sample)

    assert _wait_for_hash(qtbot, page) == hashlib.sha256(sample.read_bytes()).hexdigest()
    assert page.copy_button.isEnabled()


def test_switching_algorithm_recomputes(qtbot: QtBot, page: HashCheckerPage, sample: Path) -> None:
    page.select_file(sample)
    _wait_for_hash(qtbot, page)

    page.algorithm_combo.setCurrentIndex(page.algorithm_combo.findData("md5"))

    qtbot.waitUntil(
        lambda: page.result_edit.text() == hashlib.md5(sample.read_bytes()).hexdigest(),
        timeout=WAIT_MS,
    )


def test_expected_hash_comparison(qtbot: QtBot, page: HashCheckerPage, sample: Path) -> None:
    page.select_file(sample)
    digest = _wait_for_hash(qtbot, page)

    page.expected_edit.setText(digest.upper())
    assert page.match_label.text() == MATCH_TEXT

    page.expected_edit.setText("0" * 64)
    assert page.match_label.text() == MISMATCH_TEXT

    page.expected_edit.clear()
    assert page.match_label.isHidden()


def test_missing_file_shows_error_banner(
    qtbot: QtBot, page: HashCheckerPage, tmp_path: Path
) -> None:
    page.select_file(tmp_path / "gone.exe")

    qtbot.waitUntil(lambda: page.banner.state == "error", timeout=WAIT_MS)
    assert "could not be found" in page.banner.message.text()
    assert not page.is_busy
