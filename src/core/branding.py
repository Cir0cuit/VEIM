"""The application's own mark, as opposed to the distribution logos."""
import os
import sys

from PySide6.QtGui import QIcon

from src.core import paths

BRANDING_DIR = os.path.join(paths.resource_dir(), "src", "assets", "branding")

APP_ID = "Cir0cuit.VEIM"


def app_icon() -> QIcon:
    """Every rendered size, so Qt picks rather than rescales."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256, 512, 1024):
        path = os.path.join(BRANDING_DIR, f"veim-{size}.png")
        if os.path.exists(path):
            icon.addFile(path)
    if icon.isNull():
        icon = QIcon(os.path.join(BRANDING_DIR, "veim.svg"))
    return icon


def claim_taskbar_identity() -> None:
    """Without its own AppUserModelID, Windows groups us under python.exe and
    shows the interpreter's icon on the taskbar."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass
