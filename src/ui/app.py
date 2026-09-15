import sys
from typing import Optional
from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QApplication
from PySide6.QtCore import Qt
from src.ui.theme import theme_manager, generate_stylesheet, ThemeColors
from src.ui.drive_picker import DrivePickerView
from src.ui.workspace import Workspace
from src.ui.update_banner import UpdateBanner
from src.core.icons import icon_manager
from src.core.logger import log

class VEIMMainWindow(QMainWindow):
    """Root window: the drive picker, then the workspace."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VEIM - Ventoy Easy ISO Manager")
        self.resize(1100, 760)
        self.setMinimumSize(920, 620)

        icon_manager.preload_all()
        icon_manager.start_background_download()

        self.central_container = QWidget()
        self.central_container.setObjectName("centralWidget")
        self.central_layout = QVBoxLayout(self.central_container)
        self.central_layout.setContentsMargins(0, 0, 0, 0)
        self.central_layout.setSpacing(0)
        self.setCentralWidget(self.central_container)

        self.update_banner = UpdateBanner()
        self.central_layout.addWidget(self.update_banner)
        self.update_banner.check_in_background()

        self.current_view: Optional[QWidget] = None
        self.active_drive_path: str = ""

        self.apply_theme(theme_manager.current)
        theme_manager.add_listener(self.apply_theme)

        self.show_drive_picker()

    def show_drive_picker(self):
        if self.current_view:
            self.central_layout.removeWidget(self.current_view)
            self.current_view.deleteLater()
            self.current_view = None

        self.active_drive_path = ""
        self.current_view = DrivePickerView(on_drive_selected=self.on_drive_selected, parent=self)
        self.central_layout.addWidget(self.current_view)

    def on_drive_selected(self, drive_path: str):
        self.active_drive_path = drive_path
        self.show_dashboard()

    def show_dashboard(self):
        if self.current_view:
            self.central_layout.removeWidget(self.current_view)
            self.current_view.deleteLater()
            self.current_view = None

        self.current_view = Workspace(
            drive_path=self.active_drive_path,
            on_change_drive=self.show_drive_picker,
            parent=self
        )
        self.central_layout.addWidget(self.current_view)

    def apply_theme(self, colors: ThemeColors):
        qss = generate_stylesheet(colors)
        self.setStyleSheet(qss)
