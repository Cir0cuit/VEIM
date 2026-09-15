"""Persistent left navigation.

Replaces the old floating toolbar, where the drive path, four buttons and the
theme picker competed for one 64px strip and the path ended up clipped
underneath the buttons.
"""
from typing import Callable, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QButtonGroup, QFrame
)
from PySide6.QtCore import Qt, Signal

from src.ui.components import CapacityBar, ElidingLabel, make_button
from src.ui.theme import theme_manager, ThemeButton
from src.ui.version_panel import VersionPanel

SIDEBAR_WIDTH = 232


class Sidebar(QWidget):
    """Brand, section navigation, the active-drive summary, and the version."""

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
        brand = QLabel("VEIM")
        brand.setObjectName("brandMark")
        root.addWidget(brand)

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

        # --- The app itself ----------------------------------------------
        # Below the drive, not beside it: what VEIM is running is a different
        # question from what is on the stick, and the Installed page owns the
        # second one.
        root.addSpacing(18)
        self.version = VersionPanel()
        root.addWidget(self.version)

    # -- public API -------------------------------------------------------

    def select(self, key: str):
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)

    def set_drive(self, path: str, free_gb: float = 0.0, total_gb: float = 0.0):
        self.lbl_drive.setFullText(path or "No drive")
        if total_gb > 0:
            used = total_gb - free_gb
            self.capacity.set_used_fraction(used / total_gb)
            self.lbl_space.setText(f"{free_gb:.1f} GB free of {total_gb:.0f} GB")
            self.capacity.show()
        else:
            self.capacity.hide()
            self.lbl_space.setText("")
