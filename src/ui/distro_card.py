"""Row for an ISO already installed on the drive.

Was a ~110px card with bare-text actions; now a compact row whose buttons match
the rest of the app.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import QProgressBar

from src.core.inventory import InventoryItem
from src.core.downloader import DownloadTask
from src.core.recipe_base import is_older
from src.ui.components import Row, Pill, make_button, fmt_eta
from src.ui.theme import ThemeColors


def human_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "unknown size"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    return f"{size_bytes / (1024 ** 2):.0f} MB"


class DistroCard(Row):
    """One installed ISO. It is also where that ISO's update is watched.

    A new version used to download in a separate row at the top of the page
    while this one sat unchanged, still offering "Update". The row now carries
    the transfer itself: progress under the title, Cancel where the other
    buttons were.
    """

    # Answers a check can give that are not a version number.
    CHECK_FAILURES = {
        "Failed": "Check failed",
        "Unknown": "Check failed",
        # The recipe refused to serve a stale build - say so plainly.
        "Unavailable": "No current release",
    }

    def __init__(self, item: InventoryItem,
                 on_check_update: Callable[[InventoryItem, "DistroCard"], None],
                 on_download: Callable[[InventoryItem, "DistroCard"], None],
                 on_remove: Callable[[InventoryItem, "DistroCard"], None],
                 on_cancel: Optional[Callable[[InventoryItem, "DistroCard"], None]] = None,
                 parent=None):
        super().__init__(parent)
        self.item = item
        self.on_check_update = on_check_update
        self.on_download = on_download
        self.on_remove = on_remove
        self.on_cancel = on_cancel or (lambda item, card: None)

        self._latest_ver = ""       # the last check's answer, "" before any
        self._latest_url = ""
        self._checking = False
        self._downloading = False
        # How the last transfer on this row ended, as (pill text, tone), and
        # the reason when it failed. Both last until the row is used again.
        self._outcome: Optional[tuple] = None
        self._error = ""

        self.icon.set_distro(item.key)

        self.status = Pill("", "neutral")
        self.add_action(self.status)

        self.btn_check = make_button("Check", "ghost", self.start_check)
        self.add_action(self.btn_check)

        self.btn_update = make_button("Update", "primary", self._handle_download)
        self.add_action(self.btn_update)

        self.btn_remove = make_button("Remove", "danger", self._handle_remove)
        self.add_action(self.btn_remove)

        self.btn_cancel = make_button("Cancel", "danger", self._handle_cancel)
        self.add_action(self.btn_cancel)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.text_col.addWidget(self.progress)

        self.set_item(item)

    def set_item(self, item: InventoryItem):
        """Show a (possibly newer) inventory record without losing row state."""
        self.item = item
        self.title.setText(item.display_name or item.key)
        self._render()

    @property
    def is_checking(self) -> bool:
        return self._checking

    @property
    def is_downloading(self) -> bool:
        return self._downloading

    @property
    def _answered(self) -> bool:
        return bool(self._latest_ver) and self._latest_ver not in self.CHECK_FAILURES

    @property
    def is_ahead(self) -> bool:
        """The drive holds a later release than the catalog found.

        Either the recipe has fallen behind upstream or this is a pre-release.
        Whichever it is, offering the catalog's version would be a downgrade.
        """
        return self._answered and is_older(self._latest_ver, self.item.version)

    @property
    def update_available(self) -> bool:
        return (self._answered and not self.is_ahead
                and self._latest_ver.strip() != str(self.item.version).strip())

    @property
    def is_up_to_date(self) -> bool:
        """A check answered, and with nothing newer than what is on the drive."""
        return self._answered and not self.update_available

    # -- callbacks --------------------------------------------------------

    def start_check(self, *_):
        """Show that a check is running, then ask for one."""
        if self._checking or self._downloading:
            return
        self._checking = True
        self._outcome = None
        self._error = ""
        self._render()
        self.on_check_update(self.item, self)

    def _handle_download(self):
        self.on_download(self.item, self)

    def _handle_remove(self):
        self.on_remove(self.item, self)

    def _handle_cancel(self):
        self.on_cancel(self.item, self)

    # -- state ------------------------------------------------------------

    def set_status_result(self, latest_ver: str, download_url: str):
        self._checking = False
        self._latest_ver = str(latest_ver)
        self._latest_url = download_url
        self._render()

    def begin_download(self):
        self._downloading = True
        self._outcome = None
        self._error = ""
        self.progress.setRange(0, 0)     # indeterminate until a size is known
        self.meta.setText("Starting…")
        self._render()

    def update_progress(self, task: DownloadTask):
        if not self._downloading:
            return
        if task.total_bytes > 0:
            pct = int(task.downloaded_bytes / task.total_bytes * 100)
            self.progress.setRange(0, 100)
            self.progress.setValue(pct)
            if task.note:
                # Between attempts: what is being waited for, not a speed of 0.
                self.meta.setText(f"{task.note}  ·  {pct_text(task)}")
                return
            self.meta.setText(
                f"Downloading {pct}%  ·  {task.speed_mbps:.1f} MB/s  ·  "
                f"{pct_text(task)}  ·  {fmt_eta(task.eta_seconds)} left"
            )
        else:
            # Unknown total: show an indeterminate bar rather than a fake 0%.
            self.progress.setRange(0, 0)
            self.meta.setText(
                f"Downloading  ·  {task.speed_mbps:.1f} MB/s  ·  {pct_text(task)}"
            )

    def end_download(self, success: bool, msg: str = "", version: str = ""):
        """Back to an ordinary row. A cancelled transfer passes no message."""
        self._downloading = False
        if success:
            # What was just fetched is, by definition, the latest there is; the
            # old answer described the file that has now been replaced.
            self._latest_ver = str(version)
            self._outcome = ("Updated", "ok")
        elif msg:
            self._outcome = ("Download failed", "warn")
            self._error = msg
        self._render()

    # -- drawing ----------------------------------------------------------

    def _render(self):
        busy = self._downloading
        self._set_name(self, "rowActive" if busy else "row")

        self.progress.setVisible(busy)
        self.btn_cancel.setVisible(busy)
        self.btn_check.setVisible(not busy)
        self.btn_check.setEnabled(not self._checking)
        # Removing the file mid-update would be undone when the transfer lands.
        self.btn_remove.setVisible(not busy)
        self.btn_update.setVisible(not busy and not self._checking
                                   and self.update_available)

        text, tone = ("", "neutral") if busy else self._status()
        self.status.setText(text)
        self.status.set_tone(tone)
        self.status.setVisible(bool(text))

        if busy:
            # begin_download() and update_progress() own the meta line.
            self._set_name(self.meta, "rowMeta")
            self.meta.setWordWrap(False)
            return
        self._set_name(self.meta, "errorText" if self._error else "rowMeta")
        self.meta.setWordWrap(bool(self._error))
        if self._error:
            self.meta.setText(self._error)
        else:
            bits = [f"Version {self.item.version}", human_size(self.item.size_bytes)]
            self.meta.setText("  ·  ".join(b for b in bits if b))

    def _status(self) -> tuple:
        if self._checking:
            return "Checking…", "neutral"
        if self._outcome:
            return self._outcome
        if not self._latest_ver:
            return "", "neutral"
        if self._latest_ver in self.CHECK_FAILURES:
            return self.CHECK_FAILURES[self._latest_ver], "warn"
        if self.update_available:
            return f"Update to {self._latest_ver}", "warn"
        if self.is_ahead:
            return f"Newer than {self._latest_ver}", "neutral"
        return "Up to date", "ok"

    @staticmethod
    def _set_name(widget, name: str):
        if widget.objectName() == name:
            return
        widget.setObjectName(name)
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    def apply_theme(self, colors: ThemeColors = None):
        return


def pct_text(task: DownloadTask) -> str:
    if task.total_bytes <= 0:
        return f"{task.downloaded_bytes / (1024 ** 2):.0f} MB"
    done = task.downloaded_bytes / (1024 ** 2)
    total = task.total_bytes / (1024 ** 2)
    return f"{done:.0f} / {total:.0f} MB"
