r"""Render UI states to screenshots/ for local inspection.

These captures use a real temporary working directory, so the sidebar shows a
path from the machine that ran them. They are for looking at while developing,
and screenshots/ is gitignored for that reason.

Do not use these in documentation. capture_docs_screenshots.py builds a scripted
drive reported as K:\ and refuses to save if the sidebar says anything else.
"""
import sys
import os
import tempfile
import shutil
from PySide6.QtWidgets import QApplication

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.ui.app import VEIMMainWindow
from src.ui.dashboard import DashboardView
from src.ui.downloading_card import DownloadingCard
from src.ui.catalog_view import CatalogView
from src.ui.theme import theme_manager
from src.core.drive import DriveInfo, DriveDetector
from src.core.downloader import DownloadTask

ARTIFACTS_DIR = os.environ.get(
    "VEIM_SCREENSHOT_DIR",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots"),
)
os.makedirs(ARTIFACTS_DIR, exist_ok=True)

def capture():
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    theme_manager.set_theme("Dark Modern")

    temp_dir = tempfile.mkdtemp(prefix="veim_snap_")
    try:
        mock_ventoy = DriveInfo(
            path="E:\\",
            label="VENTOY",
            total_gb=64.0,
            free_gb=52.4,
            used_gb=11.6,
            free_pct=81.8,
            is_removable=True,
            is_ventoy=True,
            has_managed_folder=True,
            filesystem="exFAT"
        )
        mock_usb = DriveInfo(
            path="F:\\",
            label="SANDISK",
            total_gb=32.0,
            free_gb=29.1,
            used_gb=2.9,
            free_pct=90.9,
            is_removable=True,
            is_ventoy=False,
            has_managed_folder=False,
            filesystem="NTFS"
        )
        DriveDetector.get_drives = staticmethod(lambda: [mock_ventoy, mock_usb])

        # 1. Capture Drive Picker Screen with 512x512 High-DPI icons
        picker_window = VEIMMainWindow()
        picker_window.resize(900, 680)
        picker_window.show()
        app.processEvents()

        shot1_path = os.path.join(ARTIFACTS_DIR, "drive_picker_preview.png")
        picker_window.grab().save(shot1_path, "PNG")
        print(f"[OK] Saved {shot1_path}")
        picker_window.close()

        # 2. Capture Empty State with 512x512 High-DPI iso_disc.png
        empty_dir = tempfile.mkdtemp(prefix="veim_empty_")
        empty_win = VEIMMainWindow()
        empty_view = DashboardView(drive_path=empty_dir)
        empty_win.setCentralWidget(empty_view)
        empty_win.resize(960, 720)
        empty_win.show()
        app.processEvents()
        shot_empty_path = os.path.join(ARTIFACTS_DIR, "dashboard_empty_state.png")
        empty_win.grab().save(shot_empty_path, "PNG")
        print(f"[OK] Saved {shot_empty_path}")
        empty_win.close()
        shutil.rmtree(empty_dir, ignore_errors=True)

        # 3. Capture Dashboard with multiple simultaneous downloading cards + installed distro
        managed_dir = os.path.join(temp_dir, "Managed_ISOs")
        os.makedirs(managed_dir, exist_ok=True)
        arch_iso = os.path.join(managed_dir, "archlinux-2026.03.01-x86_64.iso")
        with open(arch_iso, "wb") as f: f.write(b"iso")

        dash_window = VEIMMainWindow()
        dash_view = DashboardView(drive_path=temp_dir)
        dash_window.setCentralWidget(dash_view)

        dash_view.inventory_mgr.add_or_update(
            key="arch",
            flavor_id="base",
            display_name="Arch Linux",
            version="2026.03.01",
            filename="archlinux-2026.03.01-x86_64.iso",
            size_bytes=1024*1024*850,
            sha256="",
            url="https://archlinux.org"
        )

        card_deb = DownloadingCard("debian", "Debian", "Netinst", on_cancel=lambda: None)
        task_deb = DownloadTask("http://example.com/deb.iso", "deb.iso")
        task_deb.total_bytes = 650 * 1024 * 1024
        task_deb.downloaded_bytes = 416 * 1024 * 1024
        task_deb.speed_mbps = 18.4
        task_deb.eta_seconds = 12
        card_deb.update_progress(task_deb)
        dash_view.download_cards["deb"] = card_deb
        dash_view.download_layout.addWidget(card_deb)

        card_ubu = DownloadingCard("ubuntu", "Ubuntu", "Desktop", on_cancel=lambda: None)
        task_ubu = DownloadTask("http://example.com/ubu.iso", "ubu.iso")
        task_ubu.total_bytes = 4800 * 1024 * 1024
        task_ubu.downloaded_bytes = 1056 * 1024 * 1024
        task_ubu.speed_mbps = 32.1
        task_ubu.eta_seconds = 114
        card_ubu.update_progress(task_ubu)
        dash_view.download_cards["ubu"] = card_ubu
        dash_view.download_layout.addWidget(card_ubu)

        dash_view.refresh_installed_list()

        dash_window.resize(960, 720)
        dash_window.show()
        app.processEvents()

        shot2_path = os.path.join(ARTIFACTS_DIR, "dashboard_simultaneous_downloads.png")
        dash_window.grab().save(shot2_path, "PNG")
        print(f"[OK] Saved {shot2_path}")
        dash_window.close()

        # 4. Capture Catalog Modal
        cat_modal = CatalogView(on_install=lambda r, f: None,
                                installed_lookup=dash_view.installed_flavors)
        cat_modal.resize(960, 720)
        cat_modal.show()
        app.processEvents()

        shot3_path = os.path.join(ARTIFACTS_DIR, "catalog_preview.png")
        cat_modal.grab().save(shot3_path, "PNG")
        print(f"[OK] Saved {shot3_path}")
        cat_modal.close()

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    capture()
