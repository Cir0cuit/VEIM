"""A strip across the top of the window when a newer VEIM has been released."""
import threading
import webbrowser

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from src.core import app_update
from src.ui.components import make_button


class _Bridge(QObject):
    """Carries the worker thread's result back onto the UI thread."""
    found = Signal(str, str)


class UpdateBanner(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("updateBanner")
        self.hide()

        self._url = app_update.RELEASES_PAGE

        row = QHBoxLayout(self)
        row.setContentsMargins(20, 10, 12, 10)
        row.setSpacing(12)

        self.label = QLabel()
        self.label.setObjectName("updateBannerText")
        row.addWidget(self.label)
        row.addStretch(1)

        self.btn_get = make_button("Download", "primary",
                                   lambda: webbrowser.open(self._url))
        row.addWidget(self.btn_get)

        dismiss = QPushButton("✕")
        dismiss.setObjectName("updateBannerDismiss")
        dismiss.setToolTip("Dismiss until the next release")
        dismiss.clicked.connect(self.hide)
        row.addWidget(dismiss)

        self._bridge = _Bridge()
        self._bridge.found.connect(self._show_release)

    def check_in_background(self) -> None:
        def _worker():
            release = app_update.check()
            if not release:
                return
            try:
                self._bridge.found.emit(release.version, release.url)
            except RuntimeError:
                # Quitting inside the ten seconds the request can take deletes
                # the widget out from under this thread.
                pass

        threading.Thread(target=_worker, daemon=True).start()

    def _show_release(self, version: str, url: str) -> None:
        self._url = url
        self.label.setText(f"VEIM {version} is available.")
        self.show()
