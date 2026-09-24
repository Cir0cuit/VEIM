"""The "Check for VEIM Updates" button on the drive picker.

What these pin down is the wording contract: "no updates found" has to mean
GitHub answered and had nothing newer, never that the check failed, and the
button must stay distinguishable from the one that checks the ISOs on a drive.
"""
import threading

import pytest

pytest.importorskip("PySide6")

from src.core import app_update
from src.ui import update_button as ub
from src.ui.update_button import UpdateCheckButton


@pytest.fixture
def button(qtbot):
    widget = UpdateCheckButton()
    qtbot.addWidget(widget)
    return widget


def _result(state, **kwargs):
    return app_update.CheckResult(state, **kwargs)


def _update(version="2.0.0", url="https://example.invalid/releases/v2.0.0"):
    return _result(app_update.UPDATE_AVAILABLE, latest=version,
                   release=app_update.Release(version, url))


# ------------------------------------------------------------------ at rest

def test_it_starts_by_offering_a_check(button):
    assert button.text() == ub.CHECK_TEXT
    assert button.isEnabled()


def test_it_says_which_updates_it_means(button):
    """On a screen about drives, "Check for Updates" alone would be ambiguous."""
    assert "VEIM" in button.text()
    assert "Installed page" in button.toolTip()


# ------------------------------------------------------------------ results

def test_nothing_newer_says_so(button):
    button._report(_result(app_update.UP_TO_DATE, latest="1.0.1"))

    assert button.text() == ub.CURRENT_TEXT
    assert not button.isEnabled(), "an answer is not something to press"


def test_a_failed_check_is_never_reported_as_up_to_date(button):
    """The whole reason this does not use the automatic check()."""
    button._report(_result(app_update.UNREACHABLE, error="offline"))

    assert button.text() == ub.FAILED_TEXT
    assert button.text() != ub.CURRENT_TEXT
    assert "offline" in button.toolTip()


def test_an_update_turns_it_into_a_download(button):
    button._report(_update("2.0.0"))

    assert "2.0.0" in button.text()
    assert button.isEnabled()
    assert button.objectName() == "primaryBtn", "the one state worth pressing"


def test_pressing_download_opens_the_release_page(button, monkeypatch):
    opened = []
    monkeypatch.setattr(ub, "open_link", lambda url, parent=None: opened.append(url) or True)
    button._report(_update("2.0.0", "https://example.invalid/releases/v2.0.0"))

    button.click()

    assert opened == ["https://example.invalid/releases/v2.0.0"]


def test_the_release_stays_on_offer_when_no_browser_opens(button, monkeypatch):
    monkeypatch.setattr(ub, "open_link", lambda url, parent=None: False)
    button._report(_update("2.0.0"))

    button.click()

    assert "2.0.0" in button.text(), "a link that failed is a reason to press again"


# ------------------------------------------------------------------ recovery

def test_a_result_gives_way_to_another_check(button):
    button._report(_result(app_update.UP_TO_DATE))
    assert button._linger.isActive(), "the answer should not be the last word"

    button._reset()

    assert button.text() == ub.CHECK_TEXT
    assert button.isEnabled()
    assert button.toolTip() == ub.TOOLTIP


def test_an_offered_download_is_not_reset_away(button):
    button._report(_update("2.0.0"))

    button._reset()

    assert "2.0.0" in button.text()


# ------------------------------------------------------------------ checking

def test_checking_goes_to_the_network_every_time(button, monkeypatch):
    """A button answered from yesterday's cache looks broken."""
    calls = []
    monkeypatch.setattr(app_update, "check_now",
                        lambda *a, **k: calls.append("now") or _update())
    monkeypatch.setattr(app_update, "check",
                        lambda *a, **k: pytest.fail("used the automatic check"))
    _run_worker_inline(monkeypatch)

    button.check()

    assert calls == ["now"]


def test_it_answers_even_a_release_the_user_skipped(button, monkeypatch, tmp_path):
    """Pressing the button is asking. Refusing a prompt is not refusing to be
    told when you ask."""
    monkeypatch.setattr(app_update.paths, "state_path",
                        lambda _name: str(tmp_path / "update_check.json"))
    app_update.skip_version("2.0.0")
    app_update.snooze()
    monkeypatch.setattr(app_update, "check_now", lambda *a, **k: _update("2.0.0"))
    _run_worker_inline(monkeypatch)

    button.check()

    assert "2.0.0" in button.text()


def test_a_second_press_while_checking_is_ignored(button, monkeypatch):
    calls = []

    def _slow(*_a, **_k):
        calls.append(1)
        button.check()          # as if it were pressed again mid-flight
        return _update()

    monkeypatch.setattr(app_update, "check_now", _slow)
    _run_worker_inline(monkeypatch)

    button.check()

    assert len(calls) == 1


def test_a_deleted_widget_does_not_crash_the_worker(button, monkeypatch):
    """The check can still be in flight when the window closes."""
    monkeypatch.setattr(app_update, "check_now", lambda *a, **k: _update())

    class _DeletedBridge:
        """What PySide6 gives you once the C++ side has been destroyed."""

        class checked:
            @staticmethod
            def emit(*_args):
                raise RuntimeError("Internal C++ object (_Bridge) already deleted.")

    button._bridge = _DeletedBridge()
    _run_worker_inline(monkeypatch)

    button.check()              # must not raise


# ------------------------------------------------------------------ placement

def test_it_is_on_the_drive_picker_and_not_the_workspace(qtbot, tmp_path):
    """The workspace is about the drive; the picker is where VEIM itself is
    still the subject."""
    from src.ui.drive_picker import DrivePickerView
    from src.ui.sidebar import Sidebar

    picker = DrivePickerView(on_drive_selected=lambda _p: None)
    qtbot.addWidget(picker)
    sidebar = Sidebar()
    qtbot.addWidget(sidebar)

    assert picker.findChildren(UpdateCheckButton), "the picker should carry it"
    assert not sidebar.findChildren(UpdateCheckButton), "the sidebar should not"


def test_it_is_not_the_distribution_update_check(button, qtbot, tmp_path):
    """Two different questions: VEIM's own release, and what the mirrors have
    published for the ISOs on the drive."""
    from src.ui.dashboard import DashboardView

    view = DashboardView(drive_path=str(tmp_path))
    qtbot.addWidget(view)

    assert button.text() != view.btn_check_all.text()


def _run_worker_inline(monkeypatch):
    """Run the checking thread's body immediately, so tests do not race it."""

    class _Immediate:
        def __init__(self, target, daemon=False):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", _Immediate)
