"""Row for a download in flight.

The old card drew the percentage twice - once as a pill and once as text
centred on the whole progress bar - so at 22% the number floated detached in
empty space to the right of the fill. Here the bar is a plain fill and the
numbers live in the meta line, stated once.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import QProgressBar

from src.core.downloader import DownloadTask
from src.ui.components import Row, make_button, restyle, show_progress


class DownloadingCard(Row):
    def __init__(self, key: str, distro_name: str, flavor_name: str,
                 on_cancel: Optional[Callable] = None, parent=None):
        super().__init__(parent)
        self.setObjectName("rowActive")

        self.icon.set_distro(key)

        self.title.setText(f"{distro_name} ({flavor_name})" if flavor_name else distro_name)
        self.meta.setText("Starting…")

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setRange(0, 0)     # indeterminate until a size is known
        self.text_col.addWidget(self.progress)

        # Also how a failed transfer is dismissed; see show_error().
        self.btn_action = make_button("Cancel", "danger", lambda: on_cancel and on_cancel())
        self.add_action(self.btn_action)

    def update_progress(self, task: DownloadTask):
        show_progress(self.progress, self.meta, task, lead="")

    def show_error(self, err_msg: str):
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.hide()
        self.meta.setText(err_msg)
        restyle(self.meta, "errorText")
        self.meta.setWordWrap(True)
        self.btn_action.setText("Dismiss")
