r"""Render the screenshots the README embeds.

Builds one drive carrying every state a row can be in: a release that has
moved on, an update running in place, a fresh install on its way, two ISOs
already current, one whose mirror could not be reached. Beside the managed
ones sit two ISOs copied on by hand that VEIM offers to adopt, and one it
does not recognise and leaves alone.

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

from src.core.branding import load_fonts
from src.core.downloader import DownloadTask
from src.core.drive import DriveDetector, DriveInfo
from src.ui.adopt_dialog import AdoptDialog
from src.ui.app import VEIMMainWindow
from src.ui.dashboard import DashboardView
from src.ui.downloading_card import DownloadingCard
from src.ui.theme import theme_manager, THEMES
from src.ui.workspace import Workspace

OUT_DIR = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "docs", "images")

# What the sidebar reports. Never the real working directory.
DRIVE_LABEL = "K:\\"
# A 64 GB stick: the ISOs below, the three loose ones, and the two transfers
# (3.4 GB written, 4.0 GB to go).
DRIVE_TOTAL_GB = 57.7
DRIVE_FREE_GB = 37.3

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

# The row whose update is in flight.
UPDATING = ("mint", "cinnamon")

# Copied onto the drive by hand. The first two are named like official
# downloads and are offered for adoption; the last is not, and is left alone.
LOOSE = [
    ("debian-live-13.1.0-amd64-kde.iso", 3_300_000_000),
    ("caine14.0.iso", 4_900_000_000),
    ("clonezilla-office-custom.iso", 500_000_000),
]


def make_task(total_mb: int, fraction: float, speed: float, eta: int) -> DownloadTask:
    task = DownloadTask("https://example.invalid/x.iso", "x.iso")
    task.total_bytes = total_mb * 1024 ** 2
    task.downloaded_bytes = int(task.total_bytes * fraction)
    task.speed_mbps, task.eta_seconds = speed, eta
    return task


def build(app, theme: str, page: str):
    theme_manager.set_theme(theme)

    workdir = tempfile.mkdtemp(prefix="veim_docs_")
    managed = os.path.join(workdir, "Managed_ISOs")
    os.makedirs(managed, exist_ok=True)
    for _, _, _, _, filename, _, _ in INSTALLED:
        with open(os.path.join(managed, filename), "wb") as handle:
            handle.write(b"iso")
    for filename, size in LOOSE:
        with open(os.path.join(managed, filename), "wb") as handle:
            handle.truncate(size)

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

    # A fresh install from the catalog has no row yet, so it gets a card of
    # its own above the list.
    card = DownloadingCard("ubuntu", "Ubuntu", "Desktop", on_cancel=lambda: None)
    card.update_progress(make_task(4800, 0.38, 24.6, 122))
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

    # An update replaces a file that has a row: that row shows the transfer.
    row = library.cards[library.inventory_mgr._composite_key(*UPDATING)]
    row.begin_download()
    row.update_progress(make_task(2800, 0.61, 31.2, 35))
    library._refresh_subtitle()

    workspace.go_to(page)
    pump(app)

    # Last, because a drive refresh would otherwise put the temp path back.
    # The two transfers above have about 4 GB still to write between them.
    workspace._poll.stop()
    workspace.sidebar.set_drive(DRIVE_LABEL, DRIVE_FREE_GB, DRIVE_TOTAL_GB, reserved_gb=4.0)
    library.drive_map.set_drive(DRIVE_TOTAL_GB, DRIVE_FREE_GB, reserved_gb=4.0, written_gb=3.4)
    pump(app)

    # These images go into the repository.
    shown = workspace.sidebar.lbl_drive.fullText()
    if shown != DRIVE_LABEL:
        raise SystemExit(
            f"refusing to save: the sidebar reads {shown!r}, not {DRIVE_LABEL!r}"
        )
    return window, workdir


def build_adopt_dialog(app, window) -> AdoptDialog:
    """The dialog behind the library's "Adopt ISOs" button, as it opens."""
    library = window.centralWidget().library
    candidates = sorted(library._adoptable(include_excluded=True), key=lambda c: c.excluded)
    listed = {c.filename for c in candidates}
    unrecognised = len([f for f in library.inventory_mgr.unmanaged_files() if f not in listed])
    if not candidates or not unrecognised:
        raise SystemExit("the loose ISOs did not produce both an adoptable and an unknown one")
    dialog = AdoptDialog(candidates, {c.filename: library._display_name(c) for c in candidates},
                         unrecognised=unrecognised, parent=window)
    dialog.resize(820, 420)
    dialog.show()
    pump(app)
    return dialog


def pump(app, times: int = 8):
    for _ in range(times):
        app.processEvents()


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    load_fonts()

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
        print(f"[OK] {path}  ({theme}, {page})")

        if filename == "library.png":
            dialog = build_adopt_dialog(app, window)
            path = os.path.join(OUT_DIR, "adopt.png")
            dialog.grab().save(path, "PNG")
            dialog.close()
            print(f"[OK] {path}  ({theme}, adopt dialog)")

        window.close()
        pump(app)
        shutil.rmtree(workdir, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
