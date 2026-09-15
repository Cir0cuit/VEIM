r"""Render the screenshots the README embeds.

Builds one drive carrying every update state: two ISOs with newer releases
upstream, two already current, one whose mirror could not be reached, and one
transfer in flight.

The sidebar is made to report K:\ rather than the throwaway temporary
directory the ISOs actually live in, so the images carry no local path. The
guard at the end of build() enforces that.

    python tools/capture_docs_screenshots.py [output_dir]

Defaults to docs/images/. Needs a real display: Qt's offscreen platform has no
fonts here, so text renders as empty boxes.
"""
import os
import sys
import tempfile
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PySide6.QtWidgets import QApplication

from src.core.downloader import DownloadTask
from src.core.drive import DriveDetector, DriveInfo
from src.ui.app import VEIMMainWindow
from src.ui.dashboard import DashboardView
from src.ui.downloading_card import DownloadingCard
from src.ui.theme import theme_manager, THEMES
from src.ui.workspace import Workspace

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "docs", "images")

# What the sidebar reports. Never the real working directory.
DRIVE_LABEL = "K:\\"
DRIVE_TOTAL_GB = 119.2
DRIVE_FREE_GB = 64.8

# (key, flavor, display name, installed version, filename, size, latest upstream)
# "latest" equal to the installed version means up to date; None means the
# recipe could not resolve a current release.
INSTALLED = [
    ("fedora", "kde", "Fedora KDE Plasma", "43", "Fedora-KDE-Live-x86_64-43.iso",
     2_400_000_000, "44"),
    ("mint", "cinnamon", "Linux Mint Cinnamon", "22.1", "linuxmint-22.1-cinnamon-64bit.iso",
     2_900_000_000, "22.3"),
    ("arch", "standard", "Arch Linux", "2026.09.01", "archlinux-2026.09.01-x86_64.iso",
     1_200_000_000, "2026.09.01"),
    ("systemrescue", "standard", "SystemRescue", "13.02", "systemrescue-13.02-amd64.iso",
     900_000_000, "13.02"),
    ("tails", "standard", "Tails", "6.19", "tails-amd64-6.19.iso",
     1_500_000_000, None),
]


def build(app, theme: str, page: str):
    theme_manager.set_theme(theme)

    workdir = tempfile.mkdtemp(prefix="veim_docs_")
    managed = os.path.join(workdir, "Managed_ISOs")
    os.makedirs(managed, exist_ok=True)
    for _, _, _, _, filename, _, _ in INSTALLED:
        with open(os.path.join(managed, filename), "wb") as handle:
            handle.write(b"iso")

    # Downloads must never actually start while capturing.
    DashboardView._worker_fetch_and_start_download = lambda *a, **kw: None
    DriveDetector.inspect_path = staticmethod(lambda path, *_: DriveInfo(
        path=DRIVE_LABEL, label="VENTOY", total_gb=DRIVE_TOTAL_GB,
        free_gb=DRIVE_FREE_GB, used_gb=DRIVE_TOTAL_GB - DRIVE_FREE_GB,
        free_pct=DRIVE_FREE_GB / DRIVE_TOTAL_GB * 100, is_removable=True,
        is_ventoy=True, has_managed_folder=True, filesystem="exFAT"))

    window = VEIMMainWindow()
    workspace = Workspace(drive_path=workdir, on_change_drive=lambda: None)
    window.setCentralWidget(workspace)
    library = workspace.library

    for key, flavor, name, version, filename, size, _ in INSTALLED:
        library.inventory_mgr.add_or_update(
            key=key, flavor_id=flavor, display_name=name, version=version,
            filename=filename, size_bytes=size, sha256="",
            url="https://example.invalid/x.iso")

    card = DownloadingCard("ubuntu", "Ubuntu", "Desktop", on_cancel=lambda: None)
    task = DownloadTask("https://example.invalid/u.iso", "u.iso")
    task.total_bytes = 4800 * 1024 ** 2
    task.downloaded_bytes = int(task.total_bytes * 0.38)
    task.speed_mbps, task.eta_seconds = 24.6, 122
    card.update_progress(task)
    library.download_cards["ubuntu::desktop"] = card
    library.download_layout.addWidget(card)
    library.lbl_downloads.show()

    library.refresh_installed_list()
    window.resize(1180, 780)
    window.show()
    pump(app)

    # Fill in the update column the way a finished "Check All Updates" would.
    for key, flavor, _, version, _, _, latest in INSTALLED:
        composite = library.inventory_mgr._composite_key(key, flavor)
        row = library.cards.get(composite)
        if row is None:
            continue
        row.set_status_result(latest if latest else "Unavailable", "")

    workspace.go_to(page)
    pump(app)

    # Last, because a drive refresh would otherwise put the temp path back.
    workspace.sidebar.set_drive(DRIVE_LABEL, DRIVE_FREE_GB, DRIVE_TOTAL_GB)
    pump(app)

    # These images go into the repository.
    shown = workspace.sidebar.lbl_drive.fullText()
    if shown != DRIVE_LABEL:
        raise SystemExit(
            f"refusing to save: the sidebar reads {shown!r}, not {DRIVE_LABEL!r}"
        )
    return window, workdir


def pump(app, times: int = 8):
    for _ in range(times):
        app.processEvents()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")

    shots = [
        ("library.png", "Dark Modern", "library"),
        ("catalog.png", "Dark Modern", "catalog"),
        ("theme-gruvbox.png", "Gruvbox Dark", "catalog"),
        ("theme-amoled.png", "Amoled Black", "library"),
        ("theme-solarized.png", "Solarized Light", "catalog"),
    ]
    for filename, theme, page in shots:
        assert theme in THEMES, f"unknown theme {theme!r}"
        window, workdir = build(app, theme, page)
        path = os.path.join(OUT_DIR, filename)
        window.grab().save(path, "PNG")
        window.close()
        pump(app)
        shutil.rmtree(workdir, ignore_errors=True)
        print(f"[OK] {path}  ({theme}, {page})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
