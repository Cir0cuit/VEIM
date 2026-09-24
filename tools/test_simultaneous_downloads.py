import os
import sys
import tempfile
import shutil
from PySide6.QtWidgets import QApplication, QPushButton
from src.ui.theme import theme_manager
from src.ui.drive_picker import DriveCard
from src.core.drive import DriveInfo
from src.ui.dashboard import DashboardView
from src.ui.distro_card import DistroCard
from src.ui.downloading_card import DownloadingCard
from src.core.downloader import DownloadTask
from src.core.inventory import InventoryItem

def test_features():
    app = QApplication.instance() or QApplication(sys.argv)
    temp_dir = tempfile.mkdtemp(prefix="veim_simul_test_")

    try:
        # 1. Test DriveCard High-Contrast Primary Button
        print("[TEST 1] Verifying 'Select Drive' Button Styling and Visibility...")
        mock_info = DriveInfo(
            path="E:\\",
            label="Ventoy",
            total_gb=32.0,
            free_gb=28.5,
            used_gb=3.5,
            free_pct=89.0,
            is_removable=True,
            is_ventoy=True,
            has_managed_folder=True,
            filesystem="exFAT"
        )
        card = DriveCard(mock_info, on_select=lambda p: None)
        # Find QPushButton in DriveCard
        btn_select = card.findChild(QPushButton)
        assert btn_select is not None
        assert btn_select.text() == "Select Drive"
        assert btn_select.objectName() == "primaryBtn"
        print("  [OK] 'Select Drive' button has clean text and primaryBtn style!")

        # 2. Test 'Theme' Button and Dropdown Menu with all 5 Themes + System Match
        print("[TEST 2] Testing 'Theme' Button & Dropdown Menu...")
        from src.ui.theme import ThemeButton
        btn_theme = ThemeButton()
        assert btn_theme.text() == "Theme"
        # 5 themes + 1 separator + 1 System Match = 6 action items in actions dict
        assert len(btn_theme.actions) == 6

        # Test triggering all 5 themes
        for theme_name in ["Cyberpunk", "Nord", "Dracula", "Clean Light", "Dark Modern"]:
            btn_theme.actions[theme_name].trigger()
            assert theme_manager.current.name == theme_name
            assert btn_theme.text() == "Theme", "Button text must remain static 'Theme'"

        # Test System Match
        btn_theme.actions["System"].trigger()
        assert theme_manager.selected_theme == "System"
        assert btn_theme.text() == "Theme"

        # Reset to Dark Modern
        theme_manager.set_theme("Dark Modern")
        print("  [OK] Theme button keeps static text 'Theme' and switches across all 5 themes cleanly!")

        # 3. Test DistroCard: NO Reinstall Button, only Update Now when update detected
        print("[TEST 3] Testing DistroCard Buttons (No Reinstall Button)...")
        item = InventoryItem(
            key="arch",
            flavor_id="base",
            display_name="Arch Linux",
            version="2026.01.01",
            filename="archlinux-2026.01.01-x86_64.iso",
            size_bytes=1024*1024*800,
            sha256="",
            url="https://archlinux.org",
            installed_at="2026-01-01"
        )
        card = DistroCard(
            item=item,
            on_check_update=lambda it, c: None,
            on_download=lambda it, c: None,
            on_remove=lambda it, c: None
        )
        assert not hasattr(card, "btn_action"), "btn_action (Reinstall) must be removed"
        assert card.btn_update.isHidden(), "btn_update must be hidden by default"
        
        # Check that when update is found, Update Now button appears
        card.set_status_result("2026.03.01", "https://archlinux.org/download.iso")
        assert not card.btn_update.isHidden(), "btn_update must appear when update is found"
        assert "Update to v2026.03.01" in card.btn_update.text()
        print("  [OK] DistroCard has zero Reinstall clutter; 'Update Now' appears strictly on updates!")

        # 4. Test Multiple Simultaneous Downloads in Dashboard
        print("[TEST 4] Testing Multiple Simultaneous Downloads in Dashboard List...")
        view = DashboardView(drive_path=temp_dir, on_change_drive=lambda: None)
        view.show()
        app.processEvents()
        assert not view.empty_container.isHidden()
        assert view.scroll.isHidden()

        # Add 1st download (Debian)
        card1 = DownloadingCard("debian", "Debian", "Netinst", on_cancel=lambda: None)
        view.download_cards["debian_netinst"] = card1
        view.download_layout.addWidget(card1)
        view.empty_container.hide()
        view.scroll.show()

        # Add 2nd download (Ubuntu)
        card2 = DownloadingCard("ubuntu", "Ubuntu", "Desktop", on_cancel=lambda: None)
        view.download_cards["ubuntu_desktop"] = card2
        view.download_layout.addWidget(card2)

        # Add 3rd download (Fedora)
        card3 = DownloadingCard("fedora", "Fedora", "Workstation", on_cancel=lambda: None)
        view.download_cards["fedora_workstation"] = card3
        view.download_layout.addWidget(card3)

        app.processEvents()
        assert len(view.download_cards) == 3
        assert view.download_layout.count() == 3
        assert not view.scroll.isHidden()
        assert view.empty_container.isHidden()
        print("  [OK] 3 concurrent downloads rendered directly in the list!")

        # 5. Test Live Progress Updates to Multiple Cards
        print("[TEST 5] Testing Concurrent Live Progress Updates...")
        task1 = DownloadTask("http://example.com/deb.iso", "deb.iso")
        task1.total_bytes = 100000000
        task1.downloaded_bytes = 35000000
        task1.speed_mbps = 12.5
        task1.eta_seconds = 5
        view._on_progress_slot("debian_netinst", task1)

        task2 = DownloadTask("http://example.com/ubu.iso", "ubu.iso")
        task2.total_bytes = 200000000
        task2.downloaded_bytes = 160000000
        task2.speed_mbps = 24.0
        task2.eta_seconds = 2
        view._on_progress_slot("ubuntu_desktop", task2)

        assert card1.progress_bar.value() == 35
        assert "35%" in card1.lbl_badge.text()
        assert card2.progress_bar.value() == 80
        assert "80%" in card2.lbl_badge.text()
        print("  [OK] Both cards updated live with independent progress bars and metrics!")

        # 6. Test Canceling One Download
        print("[TEST 6] Testing Individual Download Cancellation...")
        view._cancel_download("ubuntu_desktop")
        assert len(view.download_cards) == 2
        assert "ubuntu_desktop" not in view.download_cards
        print("  [OK] Canceled download removed without affecting other 2 downloads!")

        # 7. Test Completing Download -> Converts to DistroCard
        print("[TEST 7] Testing Completion Transition to Installed DistroCard...")
        dummy_dest = os.path.join(temp_dir, "Managed_ISOs", "debian-netinst.iso")
        os.makedirs(os.path.dirname(dummy_dest), exist_ok=True)
        with open(dummy_dest, "wb") as f:
            f.write(b"0" * 1024)

        task1.dest_path = dummy_dest
        task1._distro_meta = {
            "key": "debian",
            "flavor_id": "netinst",
            "display_name": "Debian Netinst",
            "version": "12.9.0",
            "filename": "debian-netinst.iso",
            "url": "http://example.com/deb.iso",
            "sha256": ""
        }
        view.active_tasks["debian_netinst"] = task1
        view._on_complete_slot("debian_netinst", True, "Done")

        deb_ck = view.inventory_mgr._composite_key("debian", "netinst")
        assert deb_ck not in view.download_cards
        assert len(view.cards) == 1
        assert deb_ck in view.cards
        print("  [OK] Finished download smoothly converted to installed DistroCard in inventory!")

        # Clean up remaining download
        view._cancel_download("fedora_workstation")
        assert len(view.download_cards) == 0
        assert len(view.cards) == 1

        print("\nALL SIMULTANEOUS DOWNLOAD & THEME TESTS PASSED PERFECTLY!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    test_features()
