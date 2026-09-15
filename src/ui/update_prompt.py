"""The automatic update check, and the dialog it raises.

Replaces the strip that used to sit across the top of the window. A strip is
easy to miss and easy to ignore, and ignoring it was the only thing you could
do with it: it came back every day until the release was installed.

So the check now interrupts once, properly, and every button on it is an
answer. Download takes it, Skip This Version retires that release for good,
and Remind Me in a Week stops the asking. Closing the dialog is the fourth
answer - not now - and it is asked again on the next run.
"""
import threading
import webbrowser

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QVBoxLayout

from src import __version__
from src.core import app_update
from src.ui.components import make_button

# Release notes are a courtesy here, not the page: enough to see what changed,
# and the download page has the rest.
NOTES_LIMIT = 420


class UpdatePrompt(QDialog):
    """"VEIM x.y.z is available" - with a way to say no that sticks."""

    def __init__(self, release, parent=None):
        super().__init__(parent)
        self.release = release
        self.setObjectName("updatePrompt")
        self.setWindowTitle("VEIM update")
        self.setModal(True)
        self.setMinimumWidth(460)

        root = QVBoxLayout(self)
        root.setContentsMargins(26, 24, 26, 20)
        root.setSpacing(6)

        title = QLabel(f"VEIM {release.version} is available")
        title.setObjectName("pageTitle")
        root.addWidget(title)

        subtitle = QLabel(f"You are running {__version__}.")
        subtitle.setObjectName("pageSubtitle")
        root.addWidget(subtitle)

        notes = (release.notes or "").strip()
        if notes:
            if len(notes) > NOTES_LIMIT:
                notes = notes[:NOTES_LIMIT].rstrip() + "…"
            self.lbl_notes = QLabel(notes)
            self.lbl_notes.setObjectName("rowDesc")
            self.lbl_notes.setWordWrap(True)
            self.lbl_notes.setTextFormat(Qt.TextFormat.PlainText)
            root.addSpacing(10)
            root.addWidget(self.lbl_notes)

        root.addSpacing(20)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        self.btn_skip = make_button("Skip This Version", "ghost", self._skip)
        self.btn_skip.setToolTip(
            f"Stop offering {release.version}. A newer release is still offered.")
        actions.addWidget(self.btn_skip)

        self.btn_later = make_button("Remind Me in a Week", "ghost", self._snooze)
        self.btn_later.setToolTip("No update prompts for seven days.")
        actions.addWidget(self.btn_later)

        actions.addStretch()

        self.btn_download = make_button("Download", "primary", self._download)
        self.btn_download.setMinimumWidth(120)
        actions.addWidget(self.btn_download)
        root.addLayout(actions)

    def _download(self):
        webbrowser.open(self.release.url)
        self.accept()

    def _skip(self):
        app_update.skip_version(self.release.version)
        self.reject()

    def _snooze(self):
        app_update.snooze()
        self.reject()


class _Bridge(QObject):
    """Carries the worker thread's result back onto the UI thread."""
    found = Signal(object)          # app_update.Release


class UpdateNotifier(QObject):
    """The check that runs on its own, and raises the prompt when it should.

    Parented to the window so it dies with it, which is what keeps a reply
    arriving ten seconds late from reaching a window that has closed.
    """

    def __init__(self, window):
        super().__init__(window)
        self._window = window
        self._bridge = _Bridge()
        self._bridge.found.connect(self._raise_prompt)

    def check_in_background(self):
        def _worker():
            release = app_update.check()
            if not release or app_update.is_muted(release.version):
                return
            try:
                self._bridge.found.emit(release)
            except RuntimeError:
                # Quitting inside the ten seconds the request can take deletes
                # the notifier out from under this thread.
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _raise_prompt(self, release):
        UpdatePrompt(release, self._window).exec()
