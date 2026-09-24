"""Persistent left navigation.

Replaces the old floating toolbar, where the drive path, four buttons and the
theme picker competed for one 64px strip and the path ended up clipped
underneath the buttons.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup
)
from PySide6.QtCore import Qt, Signal

from src import __version__
from src.ui.components import CapacityBar, ElidingLabel, make_button
from src.ui.theme import ThemeButton

SIDEBAR_WIDTH = 232


class Sidebar(QWidget):
    """Brand and version, section navigation, and the active-drive summary."""

    navigated = Signal(str)      # page key
    change_drive = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(SIDEBAR_WIDTH)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 20, 16, 16)
        root.setSpacing(0)

        # --- Brand -------------------------------------------------------
        # The version rides the wordmark: it is the app's own name tag, and
        # belongs nowhere near the drive controls below.
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(7)

        brand = QLabel("VEIM")
        brand.setObjectName("brandMark")
        brand_row.addWidget(brand, 0, Qt.AlignmentFlag.AlignBottom)

        self.lbl_version = QLabel(f"v{__version__}")
        self.lbl_version.setObjectName("brandVersion")
        brand_row.addWidget(self.lbl_version, 0, Qt.AlignmentFlag.AlignBottom)
        brand_row.addStretch()
        root.addLayout(brand_row)

        sub = QLabel("Ventoy Easy ISO Manager")
        sub.setObjectName("brandSub")
        root.addWidget(sub)

        root.addSpacing(26)

        # --- Navigation --------------------------------------------------
        nav_label = QLabel("MANAGE")
        nav_label.setObjectName("navSection")
        root.addWidget(nav_label)
        root.addSpacing(8)

        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._buttons = {}

        for key, text in (("library", "Installed"), ("catalog", "Browse Catalog")):
            btn = QPushButton(text)
            btn.setObjectName("navItem")
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda _=False, k=key: self.navigated.emit(k))
            self._group.addButton(btn)
            self._buttons[key] = btn
            root.addWidget(btn)

        self._buttons["library"].setChecked(True)

        root.addStretch(1)

        # --- Drive summary ----------------------------------------------
        drive_label = QLabel("DRIVE")
        drive_label.setObjectName("navSection")
        root.addWidget(drive_label)
        root.addSpacing(8)

        self.lbl_drive = ElidingLabel("No drive")
        self.lbl_drive.setObjectName("rowTitle")
        root.addWidget(self.lbl_drive)

        self.capacity = CapacityBar()
        root.addSpacing(8)
        root.addWidget(self.capacity)

        self.lbl_space = QLabel("")
        self.lbl_space.setObjectName("rowMeta")
        root.addSpacing(6)
        root.addWidget(self.lbl_space)

        # What the transfers in flight are still going to take. Shown only
        # while there are any, so the summary stays one line the rest of the time.
        self.lbl_reserved = QLabel("")
        self.lbl_reserved.setObjectName("rowMeta")
        self.lbl_reserved.setWordWrap(True)
        self.lbl_reserved.hide()
        root.addWidget(self.lbl_reserved)

        root.addSpacing(12)
        self.btn_change = make_button("Change Drive", "ghost", self.change_drive.emit)
        root.addWidget(self.btn_change)

        root.addSpacing(10)
        theme_row = QHBoxLayout()
        theme_row.setContentsMargins(0, 0, 0, 0)
        self.theme_btn = ThemeButton()
        theme_row.addWidget(self.theme_btn)
        theme_row.addStretch()
        root.addLayout(theme_row)

    # -- public API -------------------------------------------------------

    def select(self, key: str):
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)

    def set_drive(self, path: str, free_gb: float = 0.0, total_gb: float = 0.0,
                  reserved_gb: float = 0.0):
        """`reserved_gb` is what running downloads have still to write: it
        is shown as spoken for, and the free figure is what is left after it."""
        self.lbl_drive.setFullText(path or "No drive")
        if total_gb > 0:
            used = total_gb - free_gb
            reserved = max(0.0, min(reserved_gb, free_gb))
            self.capacity.set_used_fraction(used / total_gb, reserved / total_gb)
            left = free_gb - reserved
            self.lbl_space.setText(f"{left:.1f} GB free of {total_gb:.0f} GB")
            self.lbl_reserved.setText(
                f"{reserved:.1f} GB reserved for downloads" if reserved > 0 else "")
            self.lbl_reserved.setVisible(reserved > 0)
            self.capacity.show()
        else:
            self.capacity.hide()
            self.lbl_space.setText("")
            self.lbl_reserved.hide()
