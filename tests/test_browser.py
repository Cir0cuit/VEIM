"""Opening a link from inside a bundle.

The bug these cover: in the AppImage, the Download button did nothing at all.
PyInstaller points LD_LIBRARY_PATH at the bundled Qt and libssl, xdg-open is a
shell script, and the desktop's own binary - kde-open on KDE - inherited that
environment, loaded VEIM's libraries instead of the system's, and died without
a word.
"""
import os
import subprocess
import sys

import pytest

from src.core import browser

BUNDLE = "/tmp/.mount_VEIMabc/usr/bin"


@pytest.fixture
def frozen(monkeypatch):
    """A process that looks like the AppImage: bundled, with the environment
    PyInstaller's bootloader leaves behind."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", BUNDLE, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", BUNDLE)
    monkeypatch.setenv("LD_LIBRARY_PATH_ORIG", "/usr/lib64/haswell")
    return BUNDLE


# ---------------------------------------------------------------- environment

def test_the_original_library_path_is_handed_back(frozen):
    env = browser.system_environment()

    assert env["LD_LIBRARY_PATH"] == "/usr/lib64/haswell"
    assert "LD_LIBRARY_PATH_ORIG" not in env


def test_a_variable_the_bundle_invented_is_dropped(monkeypatch):
    """An empty _ORIG means it did not exist before the bundle set it."""
    monkeypatch.setenv("QT_PLUGIN_PATH", f"{BUNDLE}/PySide6/plugins")
    monkeypatch.setenv("QT_PLUGIN_PATH_ORIG", "")

    assert "QT_PLUGIN_PATH" not in browser.system_environment()


def test_a_bundle_path_with_no_saved_original_is_still_stripped(frozen, monkeypatch):
    """An AppImage runtime can set one without saving what was there."""
    monkeypatch.setenv("GIO_MODULE_DIR", f"{BUNDLE}/gio/modules")
    monkeypatch.delenv("GIO_MODULE_DIR_ORIG", raising=False)

    assert "GIO_MODULE_DIR" not in browser.system_environment()


def test_system_entries_survive_alongside_bundle_ones(frozen, monkeypatch):
    monkeypatch.setenv("XDG_DATA_DIRS", f"{BUNDLE}/share:/usr/share:/usr/local/share")
    monkeypatch.delenv("XDG_DATA_DIRS_ORIG", raising=False)

    kept = browser.system_environment()["XDG_DATA_DIRS"]

    assert kept == "/usr/share:/usr/local/share"


def test_it_leaves_everything_else_alone(frozen, monkeypatch):
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "KDE")
    monkeypatch.setenv("DISPLAY", ":0")

    env = browser.system_environment()

    assert env["XDG_CURRENT_DESKTOP"] == "KDE"
    assert env["DISPLAY"] == ":0"


def test_a_checkout_needs_no_repair(monkeypatch):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv("LD_LIBRARY_PATH", "/usr/lib/mine")

    assert browser.system_environment()["LD_LIBRARY_PATH"] == "/usr/lib/mine"


# --------------------------------------------------------------------- opening

@pytest.fixture
def spawned(monkeypatch):
    """Record what would have been launched instead of launching it."""
    calls = []

    def _popen(command, env=None, **kwargs):
        calls.append((command, env, kwargs))
        return object()

    monkeypatch.setattr(browser.subprocess, "Popen", _popen)
    monkeypatch.setattr(browser.shutil, "which",
                        lambda name, path=None: f"/usr/bin/{name}"
                        if name == "xdg-open" else None)
    monkeypatch.setattr(sys, "platform", "linux")
    return calls


def test_the_opener_runs_with_the_repaired_environment(frozen, spawned):
    """The whole fix: xdg-open must not inherit the bundle's library path."""
    assert browser.open_url("https://example.invalid/releases/latest")

    command, env, kwargs = spawned[0]
    assert command == ["xdg-open", "https://example.invalid/releases/latest"]
    assert env["LD_LIBRARY_PATH"] == "/usr/lib64/haswell"
    assert BUNDLE not in env.get("LD_LIBRARY_PATH", "")
    assert kwargs["start_new_session"], "the browser outlives VEIM"


def test_the_next_opener_is_tried_when_the_first_is_absent(monkeypatch, spawned):
    monkeypatch.setattr(browser.shutil, "which",
                        lambda name, path=None: f"/usr/bin/{name}"
                        if name == "gio" else None)

    assert browser.open_url("https://example.invalid/x")
    assert spawned[0][0] == ["gio", "open", "https://example.invalid/x"]


def test_webbrowser_is_the_last_resort(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(browser.shutil, "which", lambda *a, **k: None)
    opened = []
    monkeypatch.setattr(browser.webbrowser, "open",
                        lambda url: opened.append(url) or True)

    assert browser.open_url("https://example.invalid/x")
    assert opened == ["https://example.invalid/x"]


def test_a_failed_launch_falls_through_rather_than_raising(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(browser.shutil, "which", lambda *a, **k: "/usr/bin/xdg-open")

    def _boom(*_a, **_k):
        raise OSError("Permission denied")

    monkeypatch.setattr(browser.subprocess, "Popen", _boom)
    monkeypatch.setattr(browser.webbrowser, "open", lambda _url: False)

    assert browser.open_url("https://example.invalid/x") is False


def test_windows_is_left_to_webbrowser(monkeypatch):
    """os.startfile does not spawn anything that loads our libraries."""
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(browser.subprocess, "Popen",
                        lambda *a, **k: pytest.fail("should not spawn an opener"))
    monkeypatch.setattr(browser.webbrowser, "open", lambda _url: True)

    assert browser.open_url("https://example.invalid/x")


def test_macos_uses_open(monkeypatch, spawned):
    monkeypatch.setattr(sys, "platform", "darwin")

    assert browser.open_url("https://example.invalid/x")
    assert spawned[0][0] == ["open", "https://example.invalid/x"]
