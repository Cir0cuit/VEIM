"""Startup drive selection.

Rebuilt as a centred card list: each drive is a real bordered row with a
capacity bar, rather than loose text with a floating "Select Drive" link and a
large dead gap down the middle of the window.
"""
from typing import Callable, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QFileDialog, QSizePolicy
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor

from src import __version__
from src.core.drive import DriveInfo, DriveDetector
from src.core.logger import log
from src.ui.components import CapacityBar, Pill, make_button, EmptyState
from src.ui.theme import ThemeButton
from src.ui.update_button import UpdateCheckButton


class DriveCard(QFrame):
    """One selectable drive."""

    def __init__(self, drive: DriveInfo, on_select: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.drive = drive
        self.on_select = on_select
        self.setObjectName("driveCard")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))

        outer = QHBoxLayout(self)
        outer.setContentsMargins(18, 16, 18, 16)
        outer.setSpacing(16)

        # --- identity + capacity ----------------------------------------
        col = QVBoxLayout()
        col.setSpacing(7)

        header = QHBoxLayout()
        header.setSpacing(9)

        title = QLabel(f"{drive.path}".rstrip("\\/") or drive.path)
        title.setObjectName("rowTitle")
        header.addWidget(title)

        # Ventoy names its partition "Ventoy", which the badge already says.
        if drive.label and not (drive.is_ventoy and drive.label.lower() == "ventoy"):
            lbl = QLabel(drive.label)
            lbl.setObjectName("rowMeta")
            header.addWidget(lbl)

        if drive.is_ventoy:
            header.addWidget(Pill("Ventoy", "accent"))
        elif drive.is_removable:
            header.addWidget(Pill("Removable", "neutral"))

        header.addStretch()
        col.addLayout(header)

        bar = CapacityBar()
        if drive.total_gb > 0:
            bar.set_used_fraction(max(0.0, drive.used_gb) / drive.total_gb)
        col.addWidget(bar)

        meta_bits = [f"{drive.free_gb:.1f} GB free of {drive.total_gb:.0f} GB"]
        if drive.filesystem:
            meta_bits.append(drive.filesystem)
        meta = QLabel("  ·  ".join(meta_bits))
        meta.setObjectName("rowMeta")
        col.addWidget(meta)

        if drive.warning:
            warn = QLabel(drive.warning)
            warn.setObjectName("errorText")
            warn.setWordWrap(True)
            col.addWidget(warn)

        outer.addLayout(col, 1)

        # --- action ------------------------------------------------------
        # Filled for the drive this screen is looking for, not for every disk.
        btn = make_button("Select", "primary" if drive.is_ventoy else "tonal", self._choose)
        btn.setMinimumWidth(110)
        outer.addWidget(btn, 0, Qt.AlignmentFlag.AlignVCenter)

    def _choose(self):
        self.on_select(self.drive.path)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._choose()
        super().mouseReleaseEvent(event)


class DrivePickerView(QWidget):
    """Full-window drive chooser shown before the main UI."""

    def __init__(self, on_drive_selected: Callable[[str], None], parent=None):
        super().__init__(parent)
        self.on_drive_selected = on_drive_selected
        self._build_ui()
        self.refresh()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # App-level controls pinned top-right: the two things on this screen
        # that are about VEIM rather than about a drive.
        topbar = QHBoxLayout()
        topbar.setContentsMargins(20, 16, 20, 0)
        topbar.setSpacing(10)
        topbar.addStretch()
        self.btn_update = UpdateCheckButton()
        topbar.addWidget(self.btn_update)
        topbar.addWidget(ThemeButton())
        root.addLayout(topbar)

        # Capped so cards do not stretch across a wide window.
        centre = QHBoxLayout()
        centre.addStretch(1)

        column = QVBoxLayout()
        column.setContentsMargins(0, 0, 0, 0)
        column.setSpacing(0)

        holder = QWidget()
        holder.setMaximumWidth(720)
        holder.setMinimumWidth(520)
        holder.setLayout(column)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(7)
        brand_row.addStretch()
        brand = QLabel("VEIM")
        brand.setObjectName("brandMark")
        brand_row.addWidget(brand, 0, Qt.AlignmentFlag.AlignBottom)
        version = QLabel(f"v{__version__}")
        version.setObjectName("brandVersion")
        brand_row.addWidget(version, 0, Qt.AlignmentFlag.AlignBottom)
        brand_row.addStretch()
        column.addLayout(brand_row)

        title = QLabel("Choose a Ventoy drive")
        title.setObjectName("pageTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addSpacing(10)
        column.addWidget(title)

        subtitle = QLabel("Pick the drive holding your bootable ISOs, or browse to a folder.")
        subtitle.setObjectName("pageSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        column.addSpacing(4)
        column.addWidget(subtitle)

        column.addSpacing(24)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.list_host = QWidget()
        self.list_layout = QVBoxLayout(self.list_host)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(10)
        self.list_layout.addStretch()
        self.scroll.setWidget(self.list_host)
        # Sized to content: a two-drive list should not push the actions to
        # the bottom of a tall window.
        self.scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        self.scroll.setMaximumHeight(430)
        column.addWidget(self.scroll, 0)

        column.addSpacing(18)
        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(make_button("Refresh", "ghost", self.refresh))
        actions.addWidget(make_button("Browse Folder…", "ghost", self._browse))
        actions.addStretch()
        column.addLayout(actions)

        centre.addWidget(holder, 0)
        centre.addStretch(1)

        # Vertically centre the whole block.
        root.addStretch(1)
        root.addLayout(centre, 0)
        root.addStretch(1)

    def showEvent(self, event):
        super().showEvent(event)
        # Not the update button in the corner, whose focus ring would read as
        # the thing this screen is asking for.
        self.scroll.setFocus()

    # -- data ------------------------------------------------------------

    def refresh(self):
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()

        try:
            drives: List[DriveInfo] = DriveDetector.get_drives()
        except Exception as e:
            log.error(f"Drive detection failed: {e}")
            drives = []

        if not drives:
            self.list_layout.insertWidget(0, EmptyState(
                "No removable drives found",
                "Plug in your Ventoy USB drive and choose Refresh, "
                "or browse to a folder directly.",
                "Browse Folder…",
                self._browse,
            ))
            return

        for drive in drives:
            self.list_layout.insertWidget(
                self.list_layout.count() - 1,
                DriveCard(drive, self.on_drive_selected),
            )

    def _browse(self):
        path = QFileDialog.getExistingDirectory(self, "Select Ventoy drive or folder")
        if path:
            self.on_drive_selected(path)
