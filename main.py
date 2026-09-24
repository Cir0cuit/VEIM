#!/usr/bin/env python3
"""
VEIM - Ventoy Easy ISO Manager

Keeps the Linux distributions and bootable utilities on a Ventoy USB drive
up to date.
"""
import sys
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication
from src.ui.app import VEIMMainWindow
from src.core.branding import app_icon, claim_taskbar_identity
from src import __version__
from src.core.logger import log

def main():
    log.info(f"Starting VEIM {__version__}")
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

        window = VEIMMainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as e:
        log.exception(f"Unhandled exception in VEIM: {e}")
        raise

if __name__ == "__main__":
    main()
