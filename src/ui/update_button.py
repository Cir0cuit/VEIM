"""The button that asks whether a newer VEIM has been released.

It lives on the drive picker, where the app itself is what you are looking at
anyway - not in the workspace, where every other control is about the drive
and its ISOs. "Check All Updates" on the Installed page is the other question
entirely: fifty mirrors, and files that get rewritten on the stick.

The button is its own status display. It offers the check, says it is running
one, and then reports what came back. "No updates found" and "Check failed"
are different answers on purpose, which is why this uses check_now() rather
than the automatic check().
"""
import threading

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QPushButton

from src.core import app_update
from src.ui.components import open_link, set_button_kind

CHECK_TEXT = "Check for VEIM Updates"
BUSY_TEXT = "Checking…"
CURRENT_TEXT = "No updates found"
FAILED_TEXT = "Check failed"

TOOLTIP = ("Checks GitHub for a newer version of VEIM itself.\n"
           "The ISOs on your drive are checked from the Installed page.")

# How long a finished check keeps showing its answer before the button goes
# back to offering another one. Long enough to read, short enough that the
# button is never left stating something that stopped being true.
RESULT_LINGER_MS = 8000


class _Bridge(QObject):
    """Carries the worker thread's result back onto the UI thread."""
    checked = Signal(object)        # app_update.CheckResult


class UpdateCheckButton(QPushButton):
    """Checks for a newer VEIM, and reports the answer in its own label."""

    def __init__(self, parent=None):
        super().__init__(CHECK_TEXT, parent)
        self.setObjectName("ghostBtn")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setMinimumHeight(34)
        self.setToolTip(TOOLTIP)
        self.clicked.connect(self._on_click)

        self._url = app_update.RELEASES_PAGE
        self._state = ""
        self._checking = False

        self._bridge = _Bridge()
        self._bridge.checked.connect(self._report)

        # Owned by the button rather than a bare QTimer.singleShot: closing the
        # window inside the linger would otherwise fire this at a widget whose
        # C++ half is already gone.
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.timeout.connect(self._reset)

    # -- interaction ------------------------------------------------------

    def _on_click(self):
        if self._state == app_update.UPDATE_AVAILABLE:
            # Stays on offer either way: a link that did not open is a reason
            # to press again, not to lose the release.
            open_link(self._url, self)
            return
        self.check()

    def check(self):
        """Ask GitHub, off the UI thread."""
        if self._checking:
            return
        self._checking = True
        self._set_state(BUSY_TEXT, "ghost", enabled=False)

        def _worker():
            result = app_update.check_now()
            try:
                self._bridge.checked.emit(result)
            except RuntimeError:
                # Quitting inside the ten seconds the request can take deletes
                # the widget out from under this thread.
                pass

        threading.Thread(target=_worker, daemon=True).start()

    # -- results ----------------------------------------------------------

    def _report(self, result):
        self._checking = False
        self._state = result.state

        if result.update_available:
            self._url = result.release.url
            self.setToolTip(f"Opens the VEIM {result.latest} download page.")
            self._set_state(f"Download {result.latest}", "primary")
            # No linger: an available release stays on offer until it is taken.
            return

        if result.state == app_update.UP_TO_DATE:
            self._set_state(CURRENT_TEXT, "ghost", enabled=False)
        else:
            self.setToolTip(f"Could not reach GitHub.\n{result.error}".strip())
            self._set_state(FAILED_TEXT, "ghost", enabled=False)

        self._linger.start(RESULT_LINGER_MS)

    def _reset(self):
        """Back to offering a check, unless there is now something better to do."""
        if self._checking or self._state == app_update.UPDATE_AVAILABLE:
            return
        self._state = ""
        self.setToolTip(TOOLTIP)
        self._set_state(CHECK_TEXT, "ghost")

    def _set_state(self, text: str, kind: str, enabled: bool = True):
        self.setText(text)
        self.setEnabled(enabled)
        set_button_kind(self, kind)
