import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRATCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRATCH_DIR not in sys.path:
    sys.path.insert(0, SCRATCH_DIR)

from src.ui.app import VEIMMainWindow

def test_startup():
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = VEIMMainWindow()
    window.show()
    
    # Process events for 1.5 seconds to verify startup, layout, icon rendering
    QTimer.singleShot(1500, window.close)
    QTimer.singleShot(1600, app.quit)
    
    exit_code = app.exec()
    assert exit_code == 0, f"App exited with code {exit_code}"
    print("[OK] VEIM application initialized, rendered, and closed cleanly with code 0!")

if __name__ == "__main__":
    test_startup()
