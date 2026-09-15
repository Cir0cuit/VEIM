"""Installed-ISO library.

The download orchestration (worker threads, the Qt signal bridge, inventory
writes) is unchanged; only the presentation is rebuilt. Drive status and the
theme picker now live in the sidebar, so the old 64px toolbar - where a long
drive path ran underneath the buttons and got clipped - is gone.
"""
import os
import shutil
import threading
from typing import Callable, Dict, Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QMessageBox
)
from PySide6.QtCore import Qt, Signal, QObject

from src.core.inventory import InventoryManager, InventoryItem
from src.core.drive import DriveDetector
from src.recipes.registry import registry
from src.core.recipe_base import DistroRecipe, ScrapeError
from src.core.downloader import DownloadTask
from src.core.logger import log
from src.ui.theme import theme_manager, ThemeColors
from src.ui.components import make_button, EmptyState
from src.ui.distro_card import DistroCard
from src.ui.downloading_card import DownloadingCard


class DashboardWorkerBridge(QObject):
    """
    Thread-safe signal bridge marshaling events from background worker threads
    directly onto the main Qt event loop.
    """
    progress_signal = Signal(str, object)         # composite_key, DownloadTask
    complete_signal = Signal(str, bool, str)      # composite_key, success, msg
    check_signal = Signal(str, str, str)          # composite_key, version, url
    error_signal = Signal(str, str)               # composite_key, error_msg


class DashboardView(QWidget):
    """Library page: active downloads on top, installed ISOs below."""

    drive_changed = Signal()          # ask the shell to re-read drive stats
    browse_catalog = Signal()         # ask the shell to switch to the catalog

    # Download lifecycle, addressed by (distro key, flavor id) rather than
    # the inventory's composite key, so any view can follow a transfer
    # without knowing how the inventory names things.
    download_started = Signal(str, str)                    # key, flavor_id
    download_progress = Signal(str, str, int, float, int)  # key, flavor, pct, MB/s, eta
    download_ended = Signal(str, str, bool, str)           # key, flavor, ok, message

    def __init__(self, drive_path: str, on_change_drive: Callable[[], None], parent=None):
        super().__init__(parent)
        self.drive_path = drive_path
        self.on_change_drive = on_change_drive

        self.inventory_mgr = InventoryManager(drive_path)
        self.cards: Dict[str, DistroCard] = {}
        self.download_cards: Dict[str, DownloadingCard] = {}
        self.active_tasks: Dict[str, Optional[DownloadTask]] = {}
        # Composite key -> (distro key, flavor id), so a progress or completion
        # event can be reported back in terms the catalog understands.
        self.download_targets: Dict[str, tuple] = {}

        self.bridge = DashboardWorkerBridge(self)
        self.bridge.progress_signal.connect(self._on_progress_slot)
        self.bridge.complete_signal.connect(self._on_complete_slot)
        self.bridge.check_signal.connect(self._on_check_slot)
        self.bridge.error_signal.connect(self._on_error_slot)

        self._build_ui()
        self.refresh_installed_list()
        theme_manager.add_listener(self.apply_theme)

    # ------------------------------------------------------------------ UI

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 24, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        # A nested layout inherits its parent's spacing, and the root is 0.
        header.setSpacing(10)

        titles = QVBoxLayout()
        titles.setSpacing(3)

        title = QLabel("Installed")
        title.setObjectName("pageTitle")
        titles.addWidget(title)

        self.subtitle = QLabel("")
        self.subtitle.setObjectName("pageSubtitle")
        titles.addWidget(self.subtitle)

        header.addLayout(titles)
        header.addStretch()

        self.btn_adopt = make_button("Adopt Root ISOs", "ghost", self._adopt_root_isos)
        self.btn_adopt.hide()
        header.addWidget(self.btn_adopt)

        self.btn_check_all = make_button("Check All Updates", "ghost", self._handle_check_all)
        header.addWidget(self.btn_check_all)

        self.btn_add = make_button("Add Distribution", "primary", self.browse_catalog.emit)
        header.addWidget(self.btn_add)

        root.addLayout(header)
        root.addSpacing(18)

        # --- scrolling body ---------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 6, 0)
        body_layout.setSpacing(8)

        self.lbl_downloads = QLabel("DOWNLOADING")
        self.lbl_downloads.setObjectName("sectionLabel")
        self.lbl_downloads.hide()
        body_layout.addWidget(self.lbl_downloads)

        self.download_layout = QVBoxLayout()
        self.download_layout.setSpacing(8)
        body_layout.addLayout(self.download_layout)

        self.lbl_installed = QLabel("ON THIS DRIVE")
        self.lbl_installed.setObjectName("sectionLabel")
        self.lbl_installed.hide()
        body_layout.addSpacing(6)
        body_layout.addWidget(self.lbl_installed)

        self.installed_layout = QVBoxLayout()
        self.installed_layout.setSpacing(8)
        body_layout.addLayout(self.installed_layout)

        body_layout.addStretch()
        self.scroll.setWidget(body)
        root.addWidget(self.scroll, 1)

        # --- empty state --------------------------------------------------
        self.empty_container = EmptyState(
            "No distributions yet",
            "This drive has no managed ISOs. Browse the catalog to add your first one.",
            "Browse Catalog",
            self.browse_catalog.emit,
        )
        self.empty_container.hide()
        root.addWidget(self.empty_container, 1)

    # -------------------------------------------------------------- drive

    def _find_root_isos(self) -> List[str]:
        if not os.path.exists(self.drive_path):
            return []
        try:
            return [
                f for f in os.listdir(self.drive_path)
                if f.lower().endswith(".iso") and os.path.isfile(os.path.join(self.drive_path, f))
            ]
        except Exception as e:
            log.warning(f"Error scanning root ISOs: {e}")
            return []

    def _adopt_root_isos(self, filenames: Optional[List[str]] = None):
        # Qt passes the button's `checked` bool positionally; ignore it.
        if not isinstance(filenames, list):
            filenames = self._find_root_isos()
        if not filenames:
            return

        dest_dir = os.path.join(self.drive_path, "Managed_ISOs")
        os.makedirs(dest_dir, exist_ok=True)

        adopted = 0
        for fname in filenames:
            src = os.path.join(self.drive_path, fname)
            dst = os.path.join(dest_dir, fname)
            try:
                if os.path.exists(src):
                    if not os.path.exists(dst):
                        shutil.move(src, dst)
                    else:
                        os.remove(src)
                    adopted += 1
            except Exception as e:
                log.error(f"Error adopting {fname}: {e}")

        self.inventory_mgr.sync_filesystem()
        self.refresh_installed_list()
        QMessageBox.information(
            self, "Root ISOs adopted",
            f"Moved {adopted} ISO(s) into Managed_ISOs."
        )

    def drive_stats(self):
        """(free_gb, total_gb) for the sidebar, or (0, 0) if unavailable."""
        info = DriveDetector.inspect_path(self.drive_path)
        if info:
            return info.free_gb, info.total_gb
        return 0.0, 0.0

    # ------------------------------------------------------------- listing

    def refresh_installed_list(self):
        self.cards.clear()
        while self.installed_layout.count():
            item = self.installed_layout.takeAt(0)
            w = item.widget()
            if w:
                # deleteLater() is deferred, and a widget that has only been removed
                # from its layout keeps painting at its old geometry until then.
                w.hide()
                w.deleteLater()

        items = self.inventory_mgr.get_all_items()
        has_downloads = bool(self.download_cards)

        self.lbl_downloads.setVisible(has_downloads)
        self.lbl_installed.setVisible(bool(items))

        if not items and not has_downloads:
            self.empty_container.show()
            self.scroll.hide()
            self.btn_check_all.setEnabled(False)
        else:
            self.empty_container.hide()
            self.scroll.show()
            self.btn_check_all.setEnabled(bool(items))

        for it in items:
            card = DistroCard(
                item=it,
                on_check_update=self._handle_single_check,
                on_download=self._handle_single_download,
                on_remove=self._handle_single_remove,
            )
            self.installed_layout.addWidget(card)
            ck = self.inventory_mgr._composite_key(it.key, it.flavor_id)
            self.cards[ck] = card

        total_gb = sum(i.size_bytes for i in items) / (1024 ** 3)
        count = len(items)
        if count:
            self.subtitle.setText(
                f"{count} distribution{'s' if count != 1 else ''}  ·  {total_gb:.1f} GB on drive"
            )
        else:
            self.subtitle.setText("Nothing installed yet")

        root_isos = self._find_root_isos()
        if root_isos:
            self.btn_adopt.setText(f"Adopt Root ISOs ({len(root_isos)})")
            self.btn_adopt.show()
        else:
            self.btn_adopt.hide()

        self.drive_changed.emit()

    def installed_flavors(self, key: str) -> set:
        """Flavor ids already installed for a distro (used by the catalog)."""
        return {i.flavor_id for i in self.inventory_mgr.get_all_items() if i.key == key}

    # ------------------------------------------------------------ download

    def open_catalog(self):
        self.browse_catalog.emit()

    def _on_catalog_install_request(self, recipe: DistroRecipe, flavor_id: str):
        flavor_obj = next((f for f in recipe.get_flavors() if f.id == flavor_id), None)
        flavor_name = flavor_obj.name if flavor_obj else flavor_id.title()
        dname = f"{recipe.name} {flavor_name}"
        ck = self.inventory_mgr._composite_key(recipe.key, flavor_id)

        if ck in self.download_cards:
            # Already running; the row is showing its progress already.
            return

        self.download_targets[ck] = (recipe.key, flavor_id)
        self.download_started.emit(recipe.key, flavor_id)

        card = DownloadingCard(
            key=recipe.key,
            distro_name=recipe.name,
            flavor_name=flavor_name,
            on_cancel=lambda k=ck: self._cancel_download(k),
        )
        self.download_cards[ck] = card
        self.download_layout.addWidget(card)
        self.active_tasks[ck] = None

        self.lbl_downloads.show()
        self.empty_container.hide()
        self.scroll.show()

        threading.Thread(
            target=self._worker_fetch_and_start_download,
            args=(recipe, flavor_id, flavor_name, dname, ck),
            daemon=True,
        ).start()

    def _worker_fetch_and_start_download(self, recipe: DistroRecipe, flavor_id: str,
                                         flavor_name: str, dname: str, ck: str):
        try:
            log.info(f"Fetching download info for {recipe.name} ({flavor_id})...")
            info = recipe.fetch_download_info(flavor_id)
            if not info.url:
                self.bridge.error_signal.emit(ck, f"Could not resolve download URL for {recipe.name}")
                return

            dest_dir = os.path.join(self.drive_path, "Managed_ISOs")
            os.makedirs(dest_dir, exist_ok=True)
            fname = info.filename or f"{recipe.key}_{flavor_id}.iso"
            dest_path = os.path.join(dest_dir, fname)

            # Pass the published checksum through so the finished file is
            # verified before it is promoted to a bootable .iso.
            task = DownloadTask(url=info.url, dest_path=dest_path, sha256=info.sha256,
                                archive=info.archive)
            task._distro_meta = {
                "key": recipe.key,
                "flavor_id": flavor_id,
                "display_name": dname,
                "version": info.version,
                "filename": fname,
                "url": info.url,
                "sha256": info.sha256,
            }
            self.active_tasks[ck] = task

            task.start_async(
                progress_callback=lambda t: self.bridge.progress_signal.emit(ck, t),
                completion_callback=lambda s, m: self.bridge.complete_signal.emit(ck, s, m),
            )

        except ScrapeError as e:
            # The recipe refused to guess. Surface why, so the user knows this is
            # an upstream/mirror problem and not a silent stale download.
            log.warning(f"Could not resolve a current download for {recipe.name}: {e.reason}")
            self.bridge.error_signal.emit(ck, f"Couldn't find a current release - {e.reason}")
        except Exception as e:
            log.exception(f"Download setup failed for {recipe.name}: {e}")
            self.bridge.error_signal.emit(ck, str(e))

    # --------------------------------------- thread-safe slots (main loop)

    def _on_progress_slot(self, ck: str, task: DownloadTask):
        dcard = self.download_cards.get(ck)
        if dcard:
            dcard.update_progress(task)

        target = self.download_targets.get(ck)
        if target:
            pct = (int(task.downloaded_bytes / task.total_bytes * 100)
                   if task.total_bytes > 0 else -1)   # -1 means "size unknown yet"
            self.download_progress.emit(target[0], target[1], pct,
                                        task.speed_mbps, task.eta_seconds)

    def _on_error_slot(self, ck: str, err_msg: str):
        dcard = self.download_cards.get(ck)
        if dcard:
            dcard.show_error(err_msg)

        target = self.download_targets.pop(ck, None)
        if target:
            self.download_ended.emit(target[0], target[1], False, err_msg)

    def _on_check_slot(self, ck: str, version: str, url: str):
        card = self.cards.get(ck)
        if card:
            card.set_status_result(version, url)

    def _on_complete_slot(self, ck: str, success: bool, msg: str):
        task = self.active_tasks.pop(ck, None)
        dcard = self.download_cards.get(ck)

        if success:
            if task and hasattr(task, "_distro_meta"):
                meta = task._distro_meta
                actual_size = os.path.getsize(task.dest_path) if os.path.exists(task.dest_path) else 0
                self.inventory_mgr.add_or_update(
                    key=meta["key"],
                    flavor_id=meta["flavor_id"],
                    display_name=meta["display_name"],
                    version=meta["version"],
                    filename=meta["filename"],
                    size_bytes=actual_size,
                    sha256=meta["sha256"],
                    url=meta["url"],
                )
            if dcard:
                self.download_layout.removeWidget(dcard)
                dcard.hide()
                dcard.deleteLater()
                self.download_cards.pop(ck, None)

            # Report the outcome before refreshing: a row still marked as
            # downloading would ignore the refresh and keep its progress bar.
            target = self.download_targets.pop(ck, None)
            if target:
                self.download_ended.emit(target[0], target[1], True, msg)

            self.inventory_mgr.sync_filesystem()
            self.refresh_installed_list()
        else:
            if dcard:
                dcard.show_error(msg or "Download interrupted")
            target = self.download_targets.pop(ck, None)
            if target:
                self.download_ended.emit(target[0], target[1], False,
                                         msg or "Download interrupted")

        if not self.download_cards:
            self.lbl_downloads.hide()

    def cancel_by_flavor(self, key: str, flavor_id: str):
        """Cancel a transfer addressed the way the catalog knows it."""
        self._cancel_download(self.inventory_mgr._composite_key(key, flavor_id))

    def _cancel_download(self, ck: str):
        task = self.active_tasks.pop(ck, None)
        if task:
            task.cancel()

        target = self.download_targets.pop(ck, None)
        if target:
            self.download_ended.emit(target[0], target[1], False, "Cancelled")
        dcard = self.download_cards.pop(ck, None)
        if dcard:
            self.download_layout.removeWidget(dcard)
            dcard.hide()
            dcard.deleteLater()
        if not self.download_cards:
            self.lbl_downloads.hide()
        self.refresh_installed_list()

    def _dismiss_download(self, ck: str):
        self._cancel_download(ck)

    # ------------------------------------------------------------ actions

    def _handle_single_check(self, item: InventoryItem, card: DistroCard):
        recipe = registry.get_recipe(item.key)
        if not recipe:
            card.set_status_result("Unknown", "")
            return

        ck = self.inventory_mgr._composite_key(item.key, item.flavor_id)

        def _worker():
            try:
                info = recipe.fetch_download_info(item.flavor_id)
                self.bridge.check_signal.emit(ck, info.version, info.url)
            except ScrapeError as e:
                log.warning(f"Update check for {item.key} found no current release: {e.reason}")
                self.bridge.check_signal.emit(ck, "Unavailable", "")
            except Exception as e:
                log.warning(f"Update check failed for {item.key}: {e}")
                self.bridge.check_signal.emit(ck, "Failed", "")

        threading.Thread(target=_worker, daemon=True).start()

    def _handle_check_all(self):
        for ck, card in list(self.cards.items()):
            self._handle_single_check(card.item, card)

    def _handle_single_download(self, item: InventoryItem, card: DistroCard):
        recipe = registry.get_recipe(item.key)
        if recipe:
            self._on_catalog_install_request(recipe, item.flavor_id)

    def _handle_single_remove(self, item: InventoryItem, card: DistroCard):
        reply = QMessageBox.question(
            self,
            "Confirm removal",
            f"Remove {item.display_name} ({item.version}) from the drive?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.inventory_mgr.remove_item(item.key, item.flavor_id, delete_file=True)
            self.refresh_installed_list()

    def apply_theme(self, colors: ThemeColors = None):
        """Styling comes from the global stylesheet; nothing to repaint here."""
        return
