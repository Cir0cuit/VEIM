"""Row for a download in flight.

The old card drew the percentage twice - once as a pill and once as text
centred on the whole progress bar - so at 22% the number floated detached in
empty space to the right of the fill. Here the bar is a plain fill and the
numbers live in the meta line, stated once.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import QProgressBar, QLabel
from PySide6.QtCore import Qt

from src.core.downloader import DownloadTask
from src.core.icons import icon_manager
from src.ui.components import Row, make_button, fmt_eta
from src.ui.theme import ThemeColors


class DownloadingCard(Row):
    def __init__(self, key: str, distro_name: str, flavor_name: str,
                 on_cancel: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("rowActive")
        self.key = key
        self.on_cancel = on_cancel
        self._finished = False

        self.icon.set_distro(key)

        label = distro_name
        if flavor_name:
            label = f"{distro_name} ({flavor_name})"
        self.title.setText(label)
        self.meta.setText("Starting…")

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 0)     # indeterminate until a size is known
        self.text_col.addWidget(self.progress)

        self.btn_action = make_button("Cancel", "danger", self._handle_action)
        self.add_action(self.btn_action)

    def _handle_action(self):
        if self._finished:
            # Acts as "Dismiss" once the transfer has ended.
            if self.on_cancel:
                self.on_cancel()
            return
        if self.on_cancel:
            self.on_cancel()

    def update_progress(self, task: DownloadTask):
        done = task.downloaded_bytes / (1024 ** 2)
        if task.total_bytes > 0:
            pct = int(task.downloaded_bytes / task.total_bytes * 100)
            self.progress.setRange(0, 100)
            self.progress.setValue(pct)
            total = task.total_bytes / (1024 ** 2)
            if task.note:
                self.meta.setText(f"{task.note}  ·  {done:.0f} / {total:.0f} MB")
                return
            self.meta.setText(
                f"{pct}%  ·  {task.speed_mbps:.1f} MB/s  ·  "
                f"{done:.0f} / {total:.0f} MB  ·  {fmt_eta(task.eta_seconds)} left"
            )
        else:
            self.progress.setRange(0, 0)
            if task.note:
                self.meta.setText(f"{task.note}  ·  {done:.0f} MB")
                return
            self.meta.setText(f"{done:.0f} MB  ·  {task.speed_mbps:.1f} MB/s")

    def show_error(self, err_msg: str):
        self._finished = True
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self.meta.setText(err_msg)
        self.meta.setObjectName("errorText")
        self.meta.style().unpolish(self.meta)
        self.meta.style().polish(self.meta)
        self.meta.setWordWrap(True)
        self.btn_action.setText("Dismiss")

    def mark_complete(self, message: str = "Completed"):
        self._finished = True
        self.progress.hide()
        self.meta.setText(message)
        self.btn_action.setText("Dismiss")

    def apply_theme(self, colors: ThemeColors = None):
        return
