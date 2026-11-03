import pytest
from pytestqt.qtbot import QtBot

from offline_tools.core.errors import ToolError
from offline_tools.ui.worker import UNEXPECTED_ERROR_MESSAGE, ProgressFn, TaskRunner, _Task

WAIT_MS = 5000


def _collect(qtbot: QtBot, runner: TaskRunner, job: object) -> dict[str, object]:
    results: dict[str, object] = {}
    runner.submit(
        job,  # type: ignore[arg-type]
        on_success=lambda value: results.update(value=value),
        on_error=lambda msg, detail: results.update(error=(msg, detail)),
        on_progress=lambda done, total: results.setdefault("progress", []).append((done, total)),  # type: ignore[attr-defined]
    )
    qtbot.waitUntil(lambda: "value" in results or "error" in results, timeout=WAIT_MS)
    qtbot.waitUntil(lambda: runner.active_count == 0, timeout=WAIT_MS)
    return results


def test_success_delivers_result_and_progress(qtbot: QtBot) -> None:
    def job(*, on_progress: ProgressFn) -> int:
        on_progress(1, 2)
        on_progress(2, 2)
        return 42

    results = _collect(qtbot, TaskRunner(), job)

    assert results["value"] == 42
    qtbot.waitUntil(lambda: results.get("progress") == [(1, 2), (2, 2)], timeout=WAIT_MS)


def test_tool_error_is_reported_with_user_message(qtbot: QtBot) -> None:
    def job(*, on_progress: ProgressFn) -> None:
        raise ToolError("That file is not a PDF.", "bad header")

    results = _collect(qtbot, TaskRunner(), job)

    assert results["error"] == ("That file is not a PDF.", "bad header")


@pytest.mark.parametrize(
    ("job_result", "signal_name"),
    [("ok", "succeeded"), (ToolError("bad"), "failed"), (ValueError("bug"), "failed")],
)
def test_task_run_emits_matching_signal(qtbot: QtBot, job_result: object, signal_name: str) -> None:
    # Runs on the main thread so coverage can trace the body of _Task.run.
    def job(*, on_progress: ProgressFn) -> object:
        if isinstance(job_result, Exception):
            raise job_result
        return job_result

    task = _Task(job)

    with qtbot.waitSignal(getattr(task.signals, signal_name), timeout=WAIT_MS):
        task.run()


def test_unexpected_error_gets_generic_message(qtbot: QtBot) -> None:
    def job(*, on_progress: ProgressFn) -> None:
        raise RuntimeError("boom")

    results = _collect(qtbot, TaskRunner(), job)

    error = results["error"]
    assert isinstance(error, tuple)
    message, detail = error
    assert message == UNEXPECTED_ERROR_MESSAGE
    assert "boom" in detail
