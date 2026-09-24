from PySide6.QtWidgets import QMainWindow
from src.ui.theme import theme_manager, generate_stylesheet, ThemeColors
from src.ui.drive_picker import DrivePickerView
from src.ui.workspace import Workspace
from src.ui.update_prompt import UpdateNotifier
from src.core.icons import icon_manager

class VEIMMainWindow(QMainWindow):
    """Root window: the drive picker, then the workspace."""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("VEIM - Ventoy Easy ISO Manager")
        self.resize(1100, 760)
        self.setMinimumSize(920, 620)

        icon_manager.preload_all()

        # The automatic check raises a dialog rather than a strip across the
        # top: every button on it is an answer, including the two that stop it
        # coming back.
        self.update_notifier = UpdateNotifier(self)
        self.update_notifier.check_in_background()

        self.apply_theme(theme_manager.current)
        theme_manager.add_listener(self.apply_theme)

        self.show_drive_picker()

    # setCentralWidget() hides the view it replaces and deletes it later.
    def show_drive_picker(self):
        self.setCentralWidget(DrivePickerView(on_drive_selected=self.show_workspace))

    def show_workspace(self, drive_path: str):
        self.setCentralWidget(Workspace(drive_path, on_change_drive=self.show_drive_picker))

    def apply_theme(self, colors: ThemeColors):
        qss = generate_stylesheet(colors)
        self.setStyleSheet(qss)
