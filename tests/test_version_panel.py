"""The version readout and its own update check.

What these pin down is the wording contract: "no updates found" has to mean
GitHub answered and had nothing newer, never that the check failed, and the
control must stay distinguishable from the one that checks the ISOs on the
drive.
"""
import threading

import pytest

pytest.importorskip("PySide6")

from src import __version__
from src.core import app_update
from src.ui import version_panel as vp
from src.ui.version_panel import VersionPanel


@pytest.fixture
def panel(qtbot):
    widget = VersionPanel()
    qtbot.addWidget(widget)
    return widget


def _result(state, **kwargs):
    return app_update.CheckResult(state, **kwargs)


def _update(version="2.0.0", url="https://example.invalid/releases/v2.0.0"):
    return _result(app_update.UPDATE_AVAILABLE, latest=version,
                   release=app_update.Release(version, url, ""))


# ------------------------------------------------------------------ at rest

def test_it_shows_the_running_version(panel):
    assert __version__ in panel.lbl_version.text()


def test_it_starts_by_offering_a_check(panel):
    assert panel.btn.text() == vp.CHECK_TEXT
    assert panel.btn.isEnabled()


# ------------------------------------------------------------------ results

def test_nothing_newer_says_so(panel):
    panel._report(_result(app_update.UP_TO_DATE, latest=__version__))

    assert panel.btn.text() == vp.CURRENT_TEXT
    assert not panel.btn.isEnabled(), "an answer is not something to press"


def test_a_failed_check_is_never_reported_as_up_to_date(panel):
    """The whole reason the panel does not use the banner's check()."""
    panel._report(_result(app_update.UNREACHABLE, error="offline"))

    assert panel.btn.text() == vp.FAILED_TEXT
    assert panel.btn.text() != vp.CURRENT_TEXT
    assert "offline" in panel.btn.toolTip()


def test_an_update_turns_the_button_into_a_download(panel):
    panel._report(_update("2.0.0"))

    assert "2.0.0" in panel.btn.text()
    assert panel.btn.isEnabled()
    assert panel.btn.objectName() == "primaryBtn", "the one state worth pressing"
    assert "2.0.0" in panel.lbl_version.text()


def test_pressing_download_opens_the_release_page(panel, monkeypatch):
    opened = []
    monkeypatch.setattr(vp.webbrowser, "open", opened.append)
    panel._report(_update("2.0.0", "https://example.invalid/releases/v2.0.0"))

    panel.btn.click()

    assert opened == ["https://example.invalid/releases/v2.0.0"]


# ------------------------------------------------------------------ recovery

def test_a_result_gives_way_to_another_check(panel):
    panel._report(_result(app_update.UP_TO_DATE))
    assert panel._linger.isActive(), "the answer should not be the last word"

    panel._reset()

    assert panel.btn.text() == vp.CHECK_TEXT
    assert panel.btn.isEnabled()
    assert panel.btn.toolTip() == vp.TOOLTIP


def test_an_offered_download_is_not_reset_away(panel):
    panel._report(_update("2.0.0"))

    panel._reset()

    assert "2.0.0" in panel.btn.text()


# ------------------------------------------------------------------- checking

def test_checking_goes_to_the_network_every_time(panel, monkeypatch):
    """A button answered from yesterday's cache looks broken."""
    calls = []
    monkeypatch.setattr(app_update, "check_now",
                        lambda *a, **k: calls.append("now") or _update())
    monkeypatch.setattr(app_update, "check",
                        lambda *a, **k: pytest.fail("used the throttled check"))
    _run_worker_inline(monkeypatch)

    panel.check()

    assert calls == ["now"]


def test_a_second_press_while_checking_is_ignored(panel, monkeypatch):
    calls = []

    def _slow(*_a, **_k):
        calls.append(1)
        panel.check()          # as if the button were pressed again mid-flight
        return _update()

    monkeypatch.setattr(app_update, "check_now", _slow)
    _run_worker_inline(monkeypatch)

    panel.check()

    assert len(calls) == 1


def test_a_deleted_widget_does_not_crash_the_worker(panel, monkeypatch):
    """The check can still be in flight when the window closes."""
    monkeypatch.setattr(app_update, "check_now", lambda *a, **k: _update())

    class _DeletedBridge:
        """What PySide6 gives you once the C++ side has been destroyed."""

        class checked:
            @staticmethod
            def emit(*_args):
                raise RuntimeError("Internal C++ object (_Bridge) already deleted.")

    panel._bridge = _DeletedBridge()
    _run_worker_inline(monkeypatch)

    panel.check()              # must not raise


# ------------------------------------------------------------- separation

def test_it_is_not_the_distribution_update_check(panel, qtbot, tmp_path):
    """Two different questions: VEIM's own release, and what the mirrors have
    published for the ISOs on the drive."""
    from src.ui.dashboard import DashboardView

    view = DashboardView(drive_path=str(tmp_path), on_change_drive=lambda: None)
    qtbot.addWidget(view)

    assert panel.btn.text() != view.btn_check_all.text()
    assert "Installed page" in panel.btn.toolTip()


def _run_worker_inline(monkeypatch):
    """Run the checking thread's body immediately, so tests do not race it."""

    class _Immediate:
        def __init__(self, target, daemon=False):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(threading, "Thread", _Immediate)
