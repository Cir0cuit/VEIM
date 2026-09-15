"""Row for an ISO already installed on the drive.

Was a ~110px card with bare-text actions; now a compact row whose buttons match
the rest of the app.
"""
from typing import Callable

from PySide6.QtWidgets import QLabel, QHBoxLayout, QVBoxLayout, QProgressBar, QWidget
from PySide6.QtCore import Qt

from src.core.inventory import InventoryItem
from src.core.downloader import DownloadTask
from src.core.icons import icon_manager
from src.ui.components import Row, Pill, make_button
from src.ui.theme import ThemeColors


def human_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "unknown size"
    gb = size_bytes / (1024 ** 3)
    if gb >= 1:
        return f"{gb:.2f} GB"
    return f"{size_bytes / (1024 ** 2):.0f} MB"


class DistroCard(Row):
    def __init__(self, item: InventoryItem,
                 on_check_update: Callable[[InventoryItem, "DistroCard"], None],
                 on_download: Callable[[InventoryItem, "DistroCard"], None],
                 on_remove: Callable[[InventoryItem, "DistroCard"], None],
                 parent=None):
        super().__init__(parent)
        self.item = item
        self.on_check_update = on_check_update
        self.on_download = on_download
        self.on_remove = on_remove
        self._latest_url = ""

        self.icon.set_distro(item.key)
        self.title.setText(item.display_name or item.key)
        self._refresh_meta()

        self.status = Pill("", "neutral")
        self.status.hide()
        self.add_action(self.status)

        self.btn_check = make_button("Check", "ghost", self._handle_check)
        self.add_action(self.btn_check)

        self.btn_update = make_button("Update", "primary", self._handle_download)
        self.btn_update.hide()
        self.add_action(self.btn_update)

        self.btn_remove = make_button("Remove", "danger", self._handle_remove)
        self.add_action(self.btn_remove)

        # Progress strip, hidden until this row starts downloading a new version.
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.hide()
        self.text_col.addWidget(self.progress)

    def _refresh_meta(self):
        bits = [f"Version {self.item.version}", human_size(self.item.size_bytes)]
        self.meta.setText("  ·  ".join(b for b in bits if b))

    # -- callbacks --------------------------------------------------------

    def _handle_check(self):
        self.status.setText("Checking…")
        self.status.set_tone("neutral")
        self.status.show()
        self.btn_check.setEnabled(False)
        self.on_check_update(self.item, self)

    def _handle_download(self):
        self.on_download(self.item, self)

    def _handle_remove(self):
        self.on_remove(self.item, self)

    def _handle_cancel(self):
        return

    # -- state ------------------------------------------------------------

    def set_status_result(self, latest_ver: str, download_url: str):
        self.btn_check.setEnabled(True)
        self._latest_url = download_url
        self.status.show()

        if latest_ver in ("Failed", "Unknown"):
            self.status.setText("Check failed")
            self.status.set_tone("warn")
            self.btn_update.hide()
            return
        if latest_ver == "Unavailable":
            # The recipe refused to serve a stale build - say so plainly.
            self.status.setText("No current release")
            self.status.set_tone("warn")
            self.btn_update.hide()
            return

        if str(latest_ver).strip() == str(self.item.version).strip():
            self.status.setText("Up to date")
            self.status.set_tone("ok")
            self.btn_update.hide()
        else:
            self.status.setText(f"Update to {latest_ver}")
            self.status.set_tone("warn")
            self.btn_update.show()

    def show_download_progress(self, task: DownloadTask):
        self.progress.show()
        self.btn_update.hide()
        self.btn_check.setEnabled(False)
        self.update_progress(task)

    def update_progress(self, task: DownloadTask):
        if task.total_bytes > 0:
            self.progress.setRange(0, 100)
            self.progress.setValue(int(task.downloaded_bytes / task.total_bytes * 100))
        else:
            # Unknown total: show an indeterminate bar rather than a fake 0%.
            self.progress.setRange(0, 0)
        self.meta.setText(
            f"Downloading  ·  {task.speed_mbps:.1f} MB/s  ·  {pct_text(task)}"
        )

    def hide_download_progress(self, success: bool, msg: str = ""):
        self.progress.hide()
        self.btn_check.setEnabled(True)
        if success:
            self.status.setText("Updated")
            self.status.set_tone("ok")
            self.status.show()
        elif msg:
            self.status.setText("Failed")
            self.status.set_tone("warn")
            self.status.show()
        self._refresh_meta()

    def apply_theme(self, colors: ThemeColors = None):
        return


def pct_text(task: DownloadTask) -> str:
    if task.total_bytes <= 0:
        return f"{task.downloaded_bytes / (1024 ** 2):.0f} MB"
    done = task.downloaded_bytes / (1024 ** 2)
    total = task.total_bytes / (1024 ** 2)
    return f"{done:.0f} / {total:.0f} MB"
