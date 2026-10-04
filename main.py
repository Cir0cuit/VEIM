#!/usr/bin/env python3
"""
VEIM - Ventoy Easy ISO Manager

Keeps the Linux distributions and bootable utilities on a Ventoy USB drive
up to date.
"""
import ctypes
import os
import sys

from PySide6.QtWidgets import QApplication
from src.ui.app import VEIMMainWindow
from src.core.branding import app_icon, claim_taskbar_identity, load_fonts
from src import __version__
from src.core.logger import log

# What Qt's xcb platform plugin loads beyond libxcb itself, and what stock
# desktops most often lack: Qt aborts with a core dump when one is missing.
XCB_LIBRARIES = {
    "libxcb-cursor.so.0": "libxcb-cursor0 / xcb-util-cursor",
    "libxcb-icccm.so.4": "libxcb-icccm4 / xcb-util-wm",
    "libxcb-image.so.0": "libxcb-image0 / xcb-util-image",
    "libxcb-keysyms.so.1": "libxcb-keysyms1 / xcb-util-keysyms",
    "libxcb-render-util.so.0": "libxcb-render-util0 / xcb-util-renderutil",
    "libxkbcommon-x11.so.0": "libxkbcommon-x11-0 / libxkbcommon-x11",
}


def missing_xcb_libraries(env=os.environ, platform=sys.platform, load=ctypes.CDLL):
    """The packages to install before Qt can open a window on X11, if any."""
    if not platform.startswith("linux"):
        return []
    requested = env.get("QT_QPA_PLATFORM", "").split(";")[0]
    if requested and not requested.startswith("xcb"):
        return []
    if not requested and env.get("XDG_SESSION_TYPE") == "wayland":
        return []
    missing = []
    for soname, package in XCB_LIBRARIES.items():
        try:
            load(soname)
        except OSError:
            missing.append(package)
    return missing


def main():
    log.info(f"Starting VEIM {__version__}")
    missing = missing_xcb_libraries()
    if missing:
        log.error(
            "Qt cannot open a window without these system libraries "
            "(Debian, Ubuntu, Mint / Fedora, Arch, openSUSE): "
            + ", ".join(missing))
    try:
        claim_taskbar_identity()
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        # No setApplicationDisplayName: Qt appends it to every window title,
        # which reads as "VEIM - Ventoy Easy ISO Manager - VEIM".
        app.setApplicationName("VEIM")
        app.setOrganizationName("VEIM")
        app.setApplicationVersion(__version__)
        app.setWindowIcon(app_icon())
        load_fonts()

        window = VEIMMainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        log.exception(f"Unhandled exception in VEIM: {e}")
        raise

if __name__ == "__main__":
    main()
