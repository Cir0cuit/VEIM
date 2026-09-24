"""Main working area: sidebar plus the Installed / Catalog pages.

The catalog used to be a modal dialog launched from the dashboard toolbar.
Browsing 34 distributions is a primary activity rather than an interruption, so
it is now a page you navigate to and back from without losing your place.
"""
from typing import Callable

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QHBoxLayout, QStackedWidget

from src.ui.sidebar import Sidebar
from src.ui.dashboard import DashboardView
from src.ui.catalog_view import CatalogView

# How often the sidebar re-reads the drive. A download takes space by the
# second; a drive that is also being written to by something else, or that
# was just unplugged, deserves a look now and then regardless.
POLL_BUSY_MS = 2_000
POLL_IDLE_MS = 30_000


class Workspace(QWidget):
    def __init__(self, drive_path: str, on_change_drive: Callable[[], None], parent=None):
        super().__init__(parent)
        self.drive_path = drive_path

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.sidebar = Sidebar()
        layout.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.library = DashboardView(drive_path=drive_path)
        self.catalog = CatalogView(
            on_install=self.library._on_catalog_install_request,
            installed_lookup=self.library.installed_flavors,
            on_cancel=self._cancel,
        )

        self.stack.addWidget(self.library)
        self.stack.addWidget(self.catalog)

        # Wiring
        self.sidebar.navigated.connect(self.go_to)
        self.sidebar.change_drive.connect(on_change_drive)
        self.library.browse_catalog.connect(lambda: self.go_to("catalog"))
        self.library.drive_changed.connect(self._sync_drive)

        # Transfers report back to the catalog so a row shows its own progress.
        self.library.download_started.connect(self.catalog.on_download_started)
        self.library.download_progress.connect(self.catalog.on_download_progress)
        self.library.download_ended.connect(self.catalog.on_download_ended)

        # ...and to the sidebar, whose free-space figure they are changing.
        self.library.download_started.connect(lambda *_: self.refresh_drive())
        self.library.download_ended.connect(lambda *_: self.refresh_drive())
        self._poll = QTimer(self)
        self._poll.timeout.connect(self.refresh_drive)

        self._sync_drive()

    # -- navigation -------------------------------------------------------

    def go_to(self, page: str):
        if page == "catalog":
            self.catalog.refresh_installed()
            self.stack.setCurrentWidget(self.catalog)
        else:
            self.stack.setCurrentWidget(self.library)
        self.sidebar.select(page)

    def _cancel(self, recipe, flavor_id: str):
        """Stop a transfer from the row that started it."""
        self.library.cancel_by_flavor(recipe.key, flavor_id)

    def _sync_drive(self):
        self.refresh_drive()
        self.catalog.refresh_installed()

    def refresh_drive(self):
        """Re-read the drive for the sidebar, and pick the next time to."""
        free_gb, total_gb = self.library.drive_stats()
        self.sidebar.set_drive(self.drive_path, free_gb, total_gb, self.library.reserved_gb())
        busy = bool(self.library.active_tasks)
        interval = POLL_BUSY_MS if busy else POLL_IDLE_MS
        if self._poll.interval() != interval or not self._poll.isActive():
            self._poll.start(interval)
