"""The dialog the automatic check raises, and the answers it accepts.

The point of the dialog over the old banner is that "no" sticks. These check
that each way of saying no is recorded, and that the next automatic check
honours it.
"""
import time

import pytest

pytest.importorskip("PySide6")

from src.core import app_update
from src.core.app_update import Release
from src.ui import update_prompt as up
from src.ui.update_prompt import UpdateNotifier, UpdatePrompt
from tests.test_update_button import _run_worker_inline

RELEASE = Release("2.0.0", "https://example.invalid/releases/v2.0.0")


@pytest.fixture
def prompt(qtbot, state_file):
    dialog = UpdatePrompt(RELEASE)
    qtbot.addWidget(dialog)
    return dialog


# -------------------------------------------------------------------- saying it

def test_it_names_the_release_and_the_running_build(prompt):
    from src import __version__

    texts = [label.text() for label in prompt.findChildren(up.QLabel)]

    assert any("2.0.0" in text for text in texts)
    assert any(__version__ in text for text in texts)


def test_it_summarises_rather_than_reciting_the_commit_log(prompt):
    """GitHub's notes are commit messages, written for whoever reads the diff -
    not for somebody deciding whether to install this."""
    texts = [label.text() for label in prompt.findChildren(up.QLabel)]

    assert up.SUMMARY in texts


# ------------------------------------------------------------------- answering

def test_download_opens_the_release_page(prompt, monkeypatch):
    opened = []
    monkeypatch.setattr(up, "open_link", lambda url, parent=None: opened.append(url) or True)

    prompt.btn_download.click()

    assert opened == ["https://example.invalid/releases/v2.0.0"]
    assert prompt.result() == UpdatePrompt.DialogCode.Accepted


def test_a_browser_that_never_opened_leaves_the_dialog_up(prompt, monkeypatch):
    """Closing on a link that went nowhere would take the release away with
    it - which is exactly what happened inside the AppImage."""
    monkeypatch.setattr(up, "open_link", lambda url, parent=None: False)

    prompt.btn_download.click()

    assert prompt.isVisible() or not prompt.result(), "it must not have accepted"
    assert prompt.result() != UpdatePrompt.DialogCode.Accepted


def test_skipping_retires_that_version(prompt, state_file):
    prompt.btn_skip.click()

    assert app_update.is_muted("2.0.0")


def test_a_skipped_version_does_not_block_a_later_one(prompt):
    prompt.btn_skip.click()

    assert not app_update.is_muted("2.1.0"), "a newer release is a new question"


def test_a_week_of_quiet_covers_everything(prompt, state_file):
    prompt.btn_later.click()

    assert app_update.is_muted("2.0.0")
    assert app_update.is_muted("9.9.9"), "snoozing is about time, not a version"


def test_the_quiet_runs_out(prompt, state_file, monkeypatch):
    prompt.btn_later.click()
    later = time.time() + app_update.SNOOZE_DURATION + 1
    monkeypatch.setattr(app_update.time, "time", lambda: later)

    assert not app_update.is_muted("9.9.9")


def test_closing_it_answers_nothing(prompt, state_file):
    """Not now is not never: the next run asks again."""
    prompt.reject()

    assert not app_update.is_muted("2.0.0")


# ------------------------------------------------------------------- notifying

def test_a_release_raises_the_prompt(qtbot, state_file, monkeypatch):
    window = _window(qtbot)
    monkeypatch.setattr(app_update, "check", lambda *a, **k: RELEASE)
    raised = _capture_prompts(monkeypatch)
    _run_worker_inline(monkeypatch)

    UpdateNotifier(window).check_in_background()

    assert [r.version for r in raised] == ["2.0.0"]


def test_a_skipped_release_is_not_raised_again(qtbot, state_file, monkeypatch):
    window = _window(qtbot)
    app_update.skip_version("2.0.0")
    monkeypatch.setattr(app_update, "check", lambda *a, **k: RELEASE)
    raised = _capture_prompts(monkeypatch)
    _run_worker_inline(monkeypatch)

    UpdateNotifier(window).check_in_background()

    assert raised == []


def test_nothing_to_report_raises_nothing(qtbot, state_file, monkeypatch):
    window = _window(qtbot)
    monkeypatch.setattr(app_update, "check", lambda *a, **k: None)
    raised = _capture_prompts(monkeypatch)
    _run_worker_inline(monkeypatch)

    UpdateNotifier(window).check_in_background()

    assert raised == []


def test_a_snooze_stops_the_asking_too(qtbot, state_file, monkeypatch):
    """Seven days of no prompts is seven days of not troubling GitHub."""
    window = _window(qtbot)
    app_update.snooze()
    monkeypatch.setattr(app_update, "check",
                        lambda *a, **k: pytest.fail("should not have asked"))
    raised = _capture_prompts(monkeypatch)
    _run_worker_inline(monkeypatch)

    UpdateNotifier(window).check_in_background()

    assert raised == []


def test_a_closed_window_does_not_crash_the_worker(qtbot, state_file, monkeypatch):
    """The check can still be in flight when the window closes."""
    window = _window(qtbot)
    monkeypatch.setattr(app_update, "check", lambda *a, **k: RELEASE)
    _run_worker_inline(monkeypatch)

    notifier = UpdateNotifier(window)

    class _DeletedBridge:
        """What PySide6 gives you once the C++ side has been destroyed."""

        class found:
            @staticmethod
            def emit(*_args):
                raise RuntimeError("Internal C++ object (_Bridge) already deleted.")

    notifier._bridge = _DeletedBridge()

    notifier.check_in_background()      # must not raise


# ----------------------------------------------------------------------- setup

def _window(qtbot):
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    qtbot.addWidget(widget)
    return widget


def _capture_prompts(monkeypatch):
    """Record what would have been shown instead of blocking on exec()."""
    raised = []

    class _Recorded:
        def __init__(self, release, parent=None):
            raised.append(release)

        def exec(self):
            return 0

    monkeypatch.setattr(up, "UpdatePrompt", _Recorded)
    return raised
