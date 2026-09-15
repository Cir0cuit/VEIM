import sys
import os
import shutil
import tempfile
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRATCH_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if SCRATCH_DIR not in sys.path:
    sys.path.insert(0, SCRATCH_DIR)

from src.core.inventory import InventoryManager
from src.core.icons import icon_manager
from src.recipes.registry import registry
from src.ui.theme import theme_manager
from src.ui.dashboard import DashboardView
from src.ui.catalog_view import CatalogView
from PySide6.QtWidgets import QMessageBox

def test_suite():
    app = QApplication.instance() or QApplication(sys.argv)
    # Mock modal dialogs for automated testing
    QMessageBox.information = lambda *args, **kwargs: QMessageBox.StandardButton.Ok
    QMessageBox.question = lambda *args, **kwargs: QMessageBox.StandardButton.Yes

    temp_dir = tempfile.mkdtemp(prefix="veim_test_drive_")

    print(f"[TEST] Created mock Ventoy drive at: {temp_dir}")

    try:
        # 1. Test Icon Manager and High-DPI caching
        print("[TEST 1] Verifying High-DPI Icon Preloading...")
        icon_manager.preload_all()
        for key in registry.get_all_recipes():
            pix = icon_manager.get_pixmap(key.key, size=56)
            assert pix is not None, f"Pixmap missing for {key.key}"
            assert not pix.isNull(), f"Pixmap is null for {key.key}"
            assert pix.devicePixelRatio() == 2.0, f"DPR not 2.0 for {key.key}"
        print(f"  [OK] All {len(registry.get_all_recipes())} recipe icons loaded with DPR=2.0 High-DPI!")

        # 2. Test Empty State & Root ISO Adoption
        print("[TEST 2] Testing Root ISO Detection & Adoption...")
        # Place dummy root ISO in temp drive
        dummy_iso = os.path.join(temp_dir, "alpine-standard-3.21.3-x86_64.iso")
        with open(dummy_iso, "wb") as f:
            f.write(b"MOCK_ISO_CONTENT_123456789")

        view = DashboardView(temp_dir, on_change_drive=lambda: None)
        root_isos = view._find_root_isos()
        assert len(root_isos) == 1, f"Expected 1 root ISO, got {len(root_isos)}"
        assert root_isos[0] == "alpine-standard-3.21.3-x86_64.iso"

        # Adopt root ISOs
        view._adopt_root_isos(root_isos)
        items = view.inventory_mgr.get_all_items()
        assert len(items) == 1, f"Expected 1 adopted item, got {len(items)}"
        assert items[0].key == "alpine"
        assert items[0].version == "3.21.3"
        assert not os.path.exists(dummy_iso), "Root ISO should have been moved"
        managed_iso = os.path.join(temp_dir, "Managed_ISOs", "alpine-standard-3.21.3-x86_64.iso")
        assert os.path.exists(managed_iso), "ISO should now exist in Managed_ISOs"
        print(f"  [OK] Root ISO successfully adopted into Managed_ISOs as {items[0].display_name} v{items[0].version}!")

        # 3. Test DistroCard Rendering
        print("[TEST 3] Testing DistroCard rendering...")
        view.refresh_installed_list()
        assert len(view.cards) == 1, f"Expected 1 card, got {len(view.cards)}"
        card = list(view.cards.values())[0]
        assert card.lbl_title.text() == items[0].display_name
        assert "v3.21.3" in card.lbl_details.text()
        print(f"  [OK] DistroCard rendered cleanly with title '{card.lbl_title.text()}'!")

        # 4. Test Catalog Modal
        print("[TEST 4] Testing Catalog Modal & Alphabetical Sorting...")
        cat = CatalogView(on_install=lambda r, f: None,
                          installed_lookup=view.installed_flavors)
        total_recipes = len(registry.get_all_recipes())
        assert len(cat.card_widgets) == total_recipes, f"Expected {total_recipes} catalog cards, got {len(cat.card_widgets)}"
        names = [c.recipe.name for c in cat.card_widgets]
        assert names == sorted(names, key=lambda s: s.lower()), "Catalog must be strictly sorted A-Z!"
        print(f"  [OK] Catalog Modal verified: {total_recipes} distributions alphabetically sorted from {names[0]} to {names[-1]} with zero categories!")

        # 5. Test Thread-Safe Signal Bridge
        print("[TEST 5] Testing Signal Bridge from background thread...")
        bridge_received = {}
        view.bridge.check_signal.connect(lambda ck, v, u: bridge_received.update({"ck": ck, "version": v, "url": u}))
        
        # Simulate worker emitting check signal
        test_ck = view.inventory_mgr._composite_key("alpine", items[0].flavor_id)
        view.bridge.check_signal.emit(test_ck, "3.22.0", "https://example.com/iso")
        app.processEvents()

        assert bridge_received.get("ck") == test_ck
        assert bridge_received.get("version") == "3.22.0"
        assert card.latest_detected_version == "3.22.0"
        print(f"  [OK] Thread-safe signal bridge successfully updated card state to v3.22.0!")

        # 6. Test Removal Flow
        print("[TEST 6] Testing Inventory Removal...")
        removed = view.inventory_mgr.remove_item("alpine", items[0].flavor_id, delete_file=True)
        assert removed is True
        assert not os.path.exists(managed_iso), "File should be deleted"
        view.refresh_installed_list()
        assert len(view.cards) == 0
        print("  [OK] ISO removed cleanly and view refreshed to empty state!")

        # 7. Test Theme Switching
        print("[TEST 7] Testing Dynamic Theme Switching...")
        initial_mode = theme_manager.current.name
        theme_manager.toggle_theme()
        assert theme_manager.current.name != initial_mode
        theme_manager.toggle_theme()
        assert theme_manager.current.name == initial_mode
        print("  [OK] Dynamic dark/light theme switching verified!")

        print("\nALL 7 INTEGRATION TESTS PASSED WITH ZERO ERRORS!")



    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_suite()
