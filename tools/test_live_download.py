import sys
import os
import shutil
import tempfile
import time
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QCoreApplication

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRATCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRATCH_DIR not in sys.path:
    sys.path.insert(0, SCRATCH_DIR)

from src.recipes.registry import registry
from src.core.downloader import DownloadTask
from src.ui.dashboard import DashboardView

def test_live():
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = tempfile.mkdtemp(prefix="veim_live_test_")
    print(f"[LIVE TEST] Temp drive: {temp_dir}")

    try:
        view = DashboardView(temp_dir, on_change_drive=lambda: None)

        # Let's test netboot.xyz (small ~3 MB ISO)
        recipe = registry.get_recipe("netboot")
        assert recipe is not None, "Netboot recipe not found"
        print(f"[LIVE TEST] Fetching download info for {recipe.name}...")
        info = recipe.fetch_download_info("bios")
        print(f"  URL: {info.url}")
        print(f"  Version: {info.version}")
        print(f"  Filename: {info.filename}")
        assert info.url, "URL must not be empty"

        # Now test Dashboard install request flow
        progress_events = []
        completion_event = []

        view.bridge.progress_signal.connect(lambda ck, t: progress_events.append((t.downloaded_bytes, t.speed_mbps)))
        view.bridge.complete_signal.connect(lambda ck, s, m: completion_event.append((s, m)))

        print("[LIVE TEST] Initiating catalog install request...")
        view._on_catalog_install_request(recipe, "bios")

        # Wait for download to finish while pumping Qt event loop
        start = time.time()
        timeout = 60
        while not completion_event and (time.time() - start < timeout):
            app.processEvents()
            time.sleep(0.05)

        assert completion_event, "Download timed out!"
        success, msg = completion_event[0]
        print(f"[LIVE TEST] Download finished: success={success}, msg={msg}")
        assert success is True, f"Download failed with message: {msg}"
        print(f"  Progress events received on Qt GUI thread: {len(progress_events)}")
        assert len(progress_events) > 0, "Expected progress events"

        # Verify inventory has recorded the item
        items = view.inventory_mgr.get_all_items()
        assert len(items) == 1, f"Expected 1 inventory item, got {len(items)}"
        print(f"  Inventory item: {items[0].display_name}, size: {items[0].size_mb} MB, version: {items[0].version}")
        assert items[0].size_bytes > 0, "Item size must be > 0"
        
        # Verify card exists on dashboard
        assert len(view.cards) == 1, f"Expected 1 card on dashboard, got {len(view.cards)}"
        card = list(view.cards.values())[0]
        print(f"  Card displayed: {card.lbl_title.text()} - {card.lbl_details.text()}")

        print("\n[SUCCESS] Live download test passed perfectly!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_live()
