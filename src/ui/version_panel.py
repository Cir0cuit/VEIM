"""What version of VEIM this is, and whether a newer one exists.

Kept deliberately apart from "Check All Updates" on the Installed page. That
button asks fifty distribution mirrors what they have published and rewrites
the rows on the drive; this one asks GitHub about VEIM itself and can only
ever send you to a download page. They sit in different places, are worded
differently, and share no state - so pressing one never looks like it might
have done the other.

The button is the whole status display: it offers a check, says it is running
one, and then reports what came back. "No updates found" and "Check failed"
are different answers on purpose, which is why this uses app_update.check_now()
rather than the banner's check().
"""
import threading
import webbrowser

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from src import __version__
from src.core import app_update
from src.ui.components import make_button, set_button_kind

CHECK_TEXT = "Check for Updates"
BUSY_TEXT = "Checking…"
CURRENT_TEXT = "No updates found"
FAILED_TEXT = "Check failed"

TOOLTIP = ("Checks GitHub for a newer version of VEIM itself.\n"
           "The ISOs on your drive are checked from the Installed page.")

# How long a finished check keeps showing its answer before the button goes
# back to offering another one. Long enough to read, short enough that the
# panel is never left stating something that stopped being true.
RESULT_LINGER_MS = 8000


class _Bridge(QObject):
    """Carries the worker thread's result back onto the UI thread."""
    checked = Signal(object)        # app_update.CheckResult


class VersionPanel(QWidget):
    """Version readout plus its own update check."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("versionPanel")

        self._url = app_update.RELEASES_PAGE
        self._state = ""
        self._checking = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        heading = QLabel("VEIM")
        heading.setObjectName("navSection")
        root.addWidget(heading)

        self.lbl_version = QLabel(f"Version {__version__}")
        self.lbl_version.setObjectName("rowMeta")
        root.addWidget(self.lbl_version)

        self.btn = make_button(CHECK_TEXT, "ghost", self._on_click)
        self.btn.setToolTip(TOOLTIP)
        root.addWidget(self.btn)

        self._bridge = _Bridge()
        self._bridge.checked.connect(self._report)

        # Owned by the panel rather than a bare QTimer.singleShot: closing the
        # window inside the linger would otherwise fire this at a widget whose
        # C++ half is already gone.
        self._linger = QTimer(self)
        self._linger.setSingleShot(True)
        self._linger.timeout.connect(self._reset)

    # -- interaction ------------------------------------------------------

    def _on_click(self):
        if self._state == app_update.UPDATE_AVAILABLE:
            webbrowser.open(self._url)
            return
        self.check()

    def check(self):
        """Ask GitHub, off the UI thread."""
        if self._checking:
            return
        self._checking = True
        self._set_button(BUSY_TEXT, "ghost", enabled=False)

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
            self.lbl_version.setText(f"Version {__version__} · {result.latest} is out")
            self.btn.setToolTip(f"Opens the VEIM {result.latest} download page.")
            self._set_button(f"Download {result.latest}", "primary")
            # No linger: an available release stays on offer until it is taken.
            return

        if result.state == app_update.UP_TO_DATE:
            self._set_button(CURRENT_TEXT, "ghost", enabled=False)
        else:
            self.btn.setToolTip(f"Could not reach GitHub.\n{result.error}".strip())
            self._set_button(FAILED_TEXT, "ghost", enabled=False)

        self._linger.start(RESULT_LINGER_MS)

    def _reset(self):
        """Back to offering a check, unless there is now something better to do."""
        if self._checking or self._state == app_update.UPDATE_AVAILABLE:
            return
        self._state = ""
        self.btn.setToolTip(TOOLTIP)
        self._set_button(CHECK_TEXT, "ghost")

    def _set_button(self, text: str, kind: str, enabled: bool = True):
        self.btn.setText(text)
        self.btn.setEnabled(enabled)
        set_button_kind(self.btn, kind)
