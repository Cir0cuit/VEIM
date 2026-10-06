from PySide6.QtCore import QSize
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow
from src.ui.theme import theme_manager, generate_stylesheet, ThemeColors
from src.ui.drive_picker import DrivePickerView
from src.ui.workspace import Workspace
from src.ui.update_prompt import UpdateNotifier
from src.core.icons import icon_manager

class VEIMMainWindow(QMainWindow):
    """Root window: the drive picker, then the workspace."""

    # Room for the library's three parts at once - a download on its way, the
    # installed rows, and "Not managed by VEIM" below them. A fixed 1100x760
    # cut the last off, and on a small screen opened partly off it.
    PREFERRED = QSize(1240, 1000)
    MINIMUM = QSize(920, 620)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("VEIM - Ventoy Easy ISO Manager")
        self.setMinimumSize(self.MINIMUM)
        self._fit_to_screen()

        icon_manager.preload_all()

        # The automatic check raises a dialog rather than a strip across the
        # top: every button on it is an answer, including the two that stop it
        # coming back.
        self.update_notifier = UpdateNotifier(self)
        self.update_notifier.check_in_background()

        theme_manager.follow_system()
        self.apply_theme(theme_manager.current)
        theme_manager.add_listener(self.apply_theme)

        self.show_drive_picker()

    def _fit_to_screen(self):
        """Open at the preferred size, or as much of it as nine tenths of the
        screen's free area allows, and centred on that area."""
        screen = QGuiApplication.primaryScreen()
        if screen is None:
            self.resize(self.PREFERRED)
            return
        area = screen.availableGeometry()
        room = QSize(int(area.width() * 0.9), int(area.height() * 0.9))
        self.resize(self.PREFERRED.boundedTo(room).expandedTo(self.MINIMUM))
        frame = self.frameGeometry()
        frame.moveCenter(area.center())
        self.move(frame.topLeft())

    # setCentralWidget() hides the view it replaces and deletes it later.
    def show_drive_picker(self):
        self.setCentralWidget(DrivePickerView(on_drive_selected=self.show_workspace))

    def show_workspace(self, drive_path: str):
        self.setCentralWidget(Workspace(drive_path, on_change_drive=self.show_drive_picker))

    def apply_theme(self, colors: ThemeColors):
        qss = generate_stylesheet(colors)
        self.setStyleSheet(qss)
