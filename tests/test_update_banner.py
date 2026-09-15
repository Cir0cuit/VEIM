"""The "a new version is out" strip."""
import threading

import pytest

from src.core.app_update import Release
from src.ui.update_banner import UpdateBanner


@pytest.fixture
def banner(qtbot):
    widget = UpdateBanner()
    qtbot.addWidget(widget)
    return widget


def test_hidden_until_there_is_something_to_say(banner):
    assert not banner.isVisible()
    assert banner.label.text() == ""


def test_shows_the_released_version(qtbot, banner):
    banner.show()
    banner._show_release("2.0.0", "https://example.invalid/releases/v2.0.0")

    assert banner.isVisible()
    assert "2.0.0" in banner.label.text()
    assert banner._url == "https://example.invalid/releases/v2.0.0"


def test_dismissing_hides_it(qtbot, banner):
    banner.show()
    banner._show_release("2.0.0", "https://example.invalid/x")
    banner.hide()
    assert not banner.isVisible()


def test_no_release_leaves_it_hidden(qtbot, banner, monkeypatch):
    monkeypatch.setattr("src.core.app_update.check", lambda *a, **k: None)
    done = threading.Event()
    monkeypatch.setattr(threading, "Thread",
                        lambda target, daemon=False: _Immediate(target, done))

    banner.check_in_background()
    assert done.is_set()
    assert not banner.isVisible()


def test_a_deleted_widget_does_not_crash_the_worker(banner, monkeypatch):
    """The check can still be in flight when the window closes."""
    monkeypatch.setattr("src.core.app_update.check",
                        lambda *a, **k: Release("9.9.9", "https://example.invalid", ""))

    class _DeletedBridge:
        """What PySide6 gives you once the C++ side has been destroyed."""

        class found:
            @staticmethod
            def emit(*_args):
                raise RuntimeError("Internal C++ object (_Bridge) already deleted.")

    banner._bridge = _DeletedBridge()

    done = threading.Event()
    monkeypatch.setattr(threading, "Thread",
                        lambda target, daemon=False: _Immediate(target, done))

    banner.check_in_background()      # must not raise
    assert done.is_set()


class _Immediate:
    """Runs the worker inline so the test does not race a real thread."""

    def __init__(self, target, done):
        self._target = target
        self._done = done

    def start(self):
        self._target()
        self._done.set()
