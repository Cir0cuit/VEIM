"""Installed-ISO library.

The download orchestration (worker threads, the Qt signal bridge, inventory
writes) is unchanged; only the presentation is rebuilt. Drive status and the
theme picker now live in the sidebar, so the old 64px toolbar - where a long
drive path ran underneath the buttons and got clipped - is gone.
"""
import os
import threading
from typing import Callable, Dict, Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QMessageBox, QDialog
)
from PySide6.QtCore import Qt, Signal, QObject

from src.core.inventory import InventoryManager, InventoryItem, AdoptionCandidate
from src.core.drive import DriveDetector
from src.recipes.registry import registry
from src.core.recipe_base import DistroRecipe, ScrapeError
from src.core.downloader import DownloadTask
from src.core.logger import log
from src.ui.theme import theme_manager, ThemeColors
from src.ui.components import make_button, EmptyState
from src.ui.distro_card import DistroCard
from src.ui.downloading_card import DownloadingCard
from src.ui.adopt_dialog import AdoptDialog, ADOPT, EXCLUDE, UNDECIDED


class DashboardWorkerBridge(QObject):
    """
    Thread-safe signal bridge marshaling events from background worker threads
    directly onto the main Qt event loop.
    """
    ready_signal = Signal(str, object, object)    # composite_key, token, DownloadTask
    progress_signal = Signal(str, object)         # composite_key, DownloadTask
    complete_signal = Signal(str, bool, str)      # composite_key, success, msg
    check_signal = Signal(str, str, str)          # composite_key, version, url
    error_signal = Signal(str, str)               # composite_key, error_msg


ADOPT_TEXT = "Adopt ISOs"
EXCLUDED_TEXT = "Excluded ISOs"
CHECK_ALL_TEXT = "Check All Updates"
CHECK_ALL_BUSY_TEXT = "Checking…"


class DashboardView(QWidget):
    """Library page: new downloads on top, installed ISOs below.

    A transfer that replaces an ISO already on the drive is shown on that ISO's
    own row; only a distribution with no row yet gets one under DOWNLOADING.
    """

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
        # Composite key -> identity of the transfer currently allowed to use
        # it. A worker still resolving a recipe after its transfer was
        # cancelled holds a token that no longer matches, and is ignored.
        self._download_tokens: Dict[str, object] = {}
        # Rows a "Check All Updates" is still waiting on.
        self._pending_checks: set = set()

        self.bridge = DashboardWorkerBridge(self)
        self.bridge.ready_signal.connect(self._on_ready_slot)
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

        self.btn_adopt = make_button(ADOPT_TEXT, "ghost", self._open_adopt_dialog)
        self.btn_adopt.hide()
        header.addWidget(self.btn_adopt)

        self.btn_check_all = make_button(CHECK_ALL_TEXT, "ghost", self._handle_check_all)
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

        # ISOs in Managed_ISOs that are none of VEIM's business. Said once,
        # here, instead of giving each a row that can do nothing.
        self.lbl_unmanaged = QLabel("")
        self.lbl_unmanaged.setObjectName("rowMeta")
        self.lbl_unmanaged.setWordWrap(True)
        self.lbl_unmanaged.hide()
        body_layout.addSpacing(6)
        body_layout.addWidget(self.lbl_unmanaged)

        # ISOs in the drive root, which VEIM's own ventoy.json hides from the
        # boot menu. Only adopted ISOs are moved now, so without this an ISO
        # the catalog does not know would stay hidden with no way to fix it.
        self.hidden_notice = QFrame()
        self.hidden_notice.setObjectName("row")
        notice_layout = QHBoxLayout(self.hidden_notice)
        notice_layout.setContentsMargins(14, 10, 14, 10)
        notice_layout.setSpacing(14)
        self.lbl_hidden = QLabel("")
        self.lbl_hidden.setObjectName("rowMeta")
        self.lbl_hidden.setWordWrap(True)
        notice_layout.addWidget(self.lbl_hidden, 1)
        self.btn_move_in = make_button("Move Into Managed_ISOs", "ghost", self._move_hidden_isos)
        notice_layout.addWidget(self.btn_move_in, 0, Qt.AlignmentFlag.AlignVCenter)
        self.hidden_notice.hide()
        body_layout.addWidget(self.hidden_notice)

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

    def _display_name(self, candidate: AdoptionCandidate) -> str:
        """Named the way a download of the same thing would be."""
        found = candidate.identity
        recipe = registry.get_recipe(found.key)
        if not recipe:
            return candidate.filename
        flavor = next((f for f in recipe.get_flavors() if f.id == found.flavor_id), None)
        return f"{recipe.name} {flavor.name if flavor else found.flavor_id.title()}"

    def _adoptable(self, include_excluded: bool = False) -> List[AdoptionCandidate]:
        """Candidates the catalog can actually update: a recognised name is not
        enough if the recipe no longer offers that flavor."""
        out = []
        for candidate in self.inventory_mgr.find_candidates(include_excluded):
            recipe = registry.get_recipe(candidate.identity.key)
            if recipe and any(f.id == candidate.identity.flavor_id for f in recipe.get_flavors()):
                out.append(candidate)
        return out

    def _open_adopt_dialog(self, *_):
        # Only what still needs, or has been given, an answer. An ISO that was
        # adopted is a row in the list now; showing it here again looked like
        # the adoption had not taken.
        candidates = sorted(self._adoptable(include_excluded=True), key=lambda c: c.excluded)
        if not candidates:
            return
        listed = {c.filename for c in candidates}
        unrecognised = len([f for f in self.inventory_mgr.unmanaged_files() if f not in listed])

        dialog = AdoptDialog(
            candidates, {c.filename: self._display_name(c) for c in candidates},
            unrecognised=unrecognised, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_adoption(candidates, dialog.choices())

    def _apply_adoption(self, candidates: List[AdoptionCandidate], choices: Dict[str, str]):
        failed = []
        for candidate in candidates:
            choice = choices.get(candidate.filename, UNDECIDED)
            if choice == ADOPT:
                if not self.inventory_mgr.adopt(candidate, self._display_name(candidate)):
                    failed.append(candidate.filename)
            elif (choice == EXCLUDE) != candidate.excluded:
                self.inventory_mgr.set_excluded(candidate.filename, choice == EXCLUDE)

        self.refresh_installed_list()
        if failed:
            QMessageBox.warning(
                self, "Could not adopt",
                "These could not be moved into Managed_ISOs:\n\n" + "\n".join(failed))

    def drive_stats(self):
        """(free_gb, total_gb) for the sidebar, or (0, 0) if unavailable."""
        info = DriveDetector.inspect_path(self.drive_path)
        if info:
            return info.free_gb, info.total_gb
        return 0.0, 0.0

    # ------------------------------------------------------------- listing

    def refresh_installed_list(self):
        """Bring the rows in line with the inventory.

        Rows are kept, not rebuilt: a row holds the answer to its last check
        and any transfer running on it, and rebuilding the list whenever one
        download finished wiped both from every other row.
        """
        # Keyed the way the inventory keys them, so two ISOs that guess to the
        # same distro and flavor still get a row - and a check result - each.
        records = dict(self.inventory_mgr.items)

        for ck in [k for k in self.cards if k not in records]:
            card = self.cards.pop(ck)
            self.installed_layout.removeWidget(card)
            # deleteLater() is deferred, and a widget that has only been removed
            # from its layout keeps painting at its old geometry until then.
            card.hide()
            card.deleteLater()
            self._pending_checks.discard(ck)

        for index, (ck, it) in enumerate(records.items()):
            card = self.cards.get(ck)
            if card is None:
                card = DistroCard(
                    item=it,
                    on_check_update=self._handle_single_check,
                    on_download=self._handle_single_download,
                    on_remove=self._handle_single_remove,
                    on_cancel=self._handle_single_cancel,
                )
                self.cards[ck] = card
            else:
                card.set_item(it)
            if self.installed_layout.indexOf(card) != index:
                self.installed_layout.removeWidget(card)
                self.installed_layout.insertWidget(index, card)

        has_downloads = bool(self.download_cards)
        self.lbl_downloads.setVisible(has_downloads)
        self.lbl_installed.setVisible(bool(records))

        if not records and not has_downloads:
            self.empty_container.show()
            self.scroll.hide()
        else:
            self.empty_container.hide()
            self.scroll.show()

        self._sync_check_all()
        self._refresh_subtitle()

        self._refresh_adoption()

        self.drive_changed.emit()

    def _refresh_subtitle(self):
        items = self.inventory_mgr.get_all_items()
        count = len(items)
        if not count:
            self.subtitle.setText("Nothing installed yet")
            return

        total_gb = sum(i.size_bytes for i in items) / (1024 ** 3)
        bits = [f"{count} distribution{'s' if count != 1 else ''}",
                f"{total_gb:.1f} GB on drive"]

        # What the checks found, so the answer to "Check All Updates" can be
        # read in one place instead of by scrolling the list.
        updates = sum(1 for c in self.cards.values()
                      if c.update_available and not c.is_checking)
        if any(c.is_checking for c in self.cards.values()):
            pass        # an answer being re-asked is not one to summarise yet
        elif updates:
            bits.append(f"{updates} update{'s' if updates != 1 else ''} available")
        elif self.cards and all(c.is_up_to_date for c in self.cards.values()):
            bits.append("all up to date")
        self.subtitle.setText("  ·  ".join(bits))

    def _refresh_adoption(self):
        """The header button, and the note about ISOs that are left alone."""
        candidates = self._adoptable(include_excluded=True)
        waiting = sum(1 for c in candidates if not c.excluded)
        # Still reachable with nothing waiting, so an exclusion can be undone -
        # under a name that does not promise something new to adopt.
        self.btn_adopt.setVisible(bool(candidates))
        self.btn_adopt.setText(f"{ADOPT_TEXT} ({waiting})" if waiting else EXCLUDED_TEXT)

        waiting_names = {c.filename for c in candidates if not c.excluded}
        others = [f for f in self.inventory_mgr.unmanaged_files() if f not in waiting_names]
        if others:
            count = len(others)
            self.lbl_unmanaged.setText(
                f"{count} other ISO{'s' if count != 1 else ''} in Managed_ISOs "
                f"{'are' if count != 1 else 'is'} not managed by VEIM. "
                "They boot as usual and are never checked or changed.")
            self.lbl_unmanaged.setToolTip("\n".join(others))
        self.lbl_unmanaged.setVisible(bool(others))

        hidden = self.inventory_mgr.hidden_root_isos()
        if hidden:
            count = len(hidden)
            self.lbl_hidden.setText(
                f"{count} ISO{'s' if count != 1 else ''} in the drive root "
                f"{'are' if count != 1 else 'is'} missing from the Ventoy boot menu: "
                "VEIM sets Ventoy to look in Managed_ISOs only. Moving them in "
                "brings them back. They are not changed, and not managed.")
            self.hidden_notice.setToolTip("\n".join(hidden))
        self.hidden_notice.setVisible(bool(hidden))

    def _move_hidden_isos(self, *_):
        failed = self.inventory_mgr.move_into_managed(self.inventory_mgr.hidden_root_isos())
        self.refresh_installed_list()
        if failed:
            QMessageBox.warning(
                self, "Could not move",
                "These stay in the drive root - a file of the same name may already "
                "be in Managed_ISOs:\n\n" + "\n".join(failed))

    def _sync_check_all(self):
        """The header button is its own busy indicator, like each row's pill."""
        busy = bool(self._pending_checks)
        if busy and self.btn_check_all.isVisible():
            # Hold the width so the shorter label does not shift the header.
            self.btn_check_all.setMinimumWidth(self.btn_check_all.width())
        self.btn_check_all.setText(CHECK_ALL_BUSY_TEXT if busy else CHECK_ALL_TEXT)
        self.btn_check_all.setEnabled(not busy and bool(self.cards))

    def installed_flavors(self, key: str) -> set:
        """Flavor ids already installed for a distro (used by the catalog)."""
        return {i.flavor_id for i in self.inventory_mgr.get_all_items() if i.key == key}

    # ------------------------------------------------------------ download

    def open_catalog(self):
        self.browse_catalog.emit()

    def _on_catalog_install_request(self, recipe: DistroRecipe, flavor_id: str,
                                    ck: str = ""):
        """Start a download. `ck` names the installed row it replaces.

        The catalog knows only a distro and a flavor, which is the plain
        composite key. A row passes its own key, because a second ISO of the
        same distro and flavor is filed under a longer one - and its update
        used to run on, and then overwrite, the first ISO's row instead.
        """
        flavor_obj = next((f for f in recipe.get_flavors() if f.id == flavor_id), None)
        flavor_name = flavor_obj.name if flavor_obj else flavor_id.title()
        dname = f"{recipe.name} {flavor_name}"
        ck = ck or self.inventory_mgr._composite_key(recipe.key, flavor_id)

        if ck in self.active_tasks:
            # Already running; the row is showing its progress already.
            return
        # A failed attempt stays on screen until dismissed. Asking again is a
        # retry, and used to be swallowed because that row still held the key.
        self._remove_download_card(ck)

        self.download_targets[ck] = (recipe.key, flavor_id)
        self.active_tasks[ck] = None
        token = self._download_tokens[ck] = object()
        self.download_started.emit(recipe.key, flavor_id)

        row = self.cards.get(ck)
        if row is not None:
            # Replacing an ISO that has a row: the row is the progress display.
            row.begin_download()
        else:
            card = DownloadingCard(
                key=recipe.key,
                distro_name=recipe.name,
                flavor_name=flavor_name,
                on_cancel=lambda k=ck: self._cancel_download(k),
            )
            self.download_cards[ck] = card
            self.download_layout.addWidget(card)

            self.lbl_downloads.show()
            self.empty_container.hide()
            self.scroll.show()

        threading.Thread(
            target=self._worker_fetch_and_start_download,
            args=(recipe, flavor_id, flavor_name, dname, ck, token),
            daemon=True,
        ).start()

    def _report_setup_error(self, ck: str, token: object, message: str):
        """Worker thread: a transfer cancelled meanwhile has nowhere to say it."""
        if self._download_tokens.get(ck) is token:
            self.bridge.error_signal.emit(ck, message)

    def _worker_fetch_and_start_download(self, recipe: DistroRecipe, flavor_id: str,
                                         flavor_name: str, dname: str, ck: str,
                                         token: object = None):
        try:
            log.info(f"Fetching download info for {recipe.name} ({flavor_id})...")
            info = recipe.fetch_download_info(flavor_id)
            if not info.url:
                self._report_setup_error(ck, token,
                                         f"Could not resolve download URL for {recipe.name}")
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
            # Started on the UI thread, which is the only one that knows whether
            # this transfer was cancelled while the recipe was still resolving.
            self.bridge.ready_signal.emit(ck, token, task)

        except ScrapeError as e:
            # The recipe refused to guess. Surface why, so the user knows this is
            # an upstream/mirror problem and not a silent stale download.
            log.warning(f"Could not resolve a current download for {recipe.name}: {e.reason}")
            self._report_setup_error(ck, token, f"Couldn't find a current release - {e.reason}")
        except Exception as e:
            log.exception(f"Download setup failed for {recipe.name}: {e}")
            self._report_setup_error(ck, token, str(e))

    # --------------------------------------- thread-safe slots (main loop)

    def _updating_row(self, ck: str) -> Optional[DistroCard]:
        """The installed row showing this transfer, if it is shown on one."""
        row = self.cards.get(ck)
        return row if row is not None and row.is_downloading else None

    def _remove_download_card(self, ck: str):
        dcard = self.download_cards.pop(ck, None)
        if dcard:
            self.download_layout.removeWidget(dcard)
            dcard.hide()
            dcard.deleteLater()
        if not self.download_cards:
            self.lbl_downloads.hide()

    def _on_ready_slot(self, ck: str, token: object, task: DownloadTask):
        if self._download_tokens.get(ck) is not token:
            # Cancelled during "Starting…". Starting it anyway ran a whole
            # download nobody could see or stop.
            return
        if any(other is not None and other.dest_path == task.dest_path
               for other in self.active_tasks.values()):
            # Two rows of one distro resolve to the same file. A second writer
            # on its .part would corrupt both.
            self._on_error_slot(ck, "This ISO is already being downloaded.")
            return
        self.active_tasks[ck] = task

        def _completed(success: bool, msg: str):
            # A cancelled transfer was already cleared away, and by now the
            # same key may belong to a new attempt this must not be mistaken for.
            if not task.is_cancelled:
                self.bridge.complete_signal.emit(ck, success, msg)

        task.start_async(
            progress_callback=lambda t: self.bridge.progress_signal.emit(ck, t),
            completion_callback=_completed,
        )

    def _on_progress_slot(self, ck: str, task: DownloadTask):
        if task.is_cancelled:
            return
        dcard = self.download_cards.get(ck)
        if dcard:
            dcard.update_progress(task)
        row = self._updating_row(ck)
        if row:
            row.update_progress(task)

        target = self.download_targets.get(ck)
        if target:
            pct = (int(task.downloaded_bytes / task.total_bytes * 100)
                   if task.total_bytes > 0 else -1)   # -1 means "size unknown yet"
            self.download_progress.emit(target[0], target[1], pct,
                                        task.speed_mbps, task.eta_seconds)

    def _on_error_slot(self, ck: str, err_msg: str):
        # The transfer is over; leaving the key behind made a retry look like
        # a download that was already running.
        self.active_tasks.pop(ck, None)
        self._download_tokens.pop(ck, None)

        dcard = self.download_cards.get(ck)
        if dcard:
            dcard.show_error(err_msg)
        row = self._updating_row(ck)
        if row:
            row.end_download(False, err_msg)

        target = self.download_targets.pop(ck, None)
        if target:
            self.download_ended.emit(target[0], target[1], False, err_msg)

    def _on_check_slot(self, ck: str, version: str, url: str):
        card = self.cards.get(ck)
        if card:
            card.set_status_result(version, url)
        self._pending_checks.discard(ck)
        self._sync_check_all()
        self._refresh_subtitle()

    def _on_complete_slot(self, ck: str, success: bool, msg: str):
        task = self.active_tasks.pop(ck, None)
        self._download_tokens.pop(ck, None)
        dcard = self.download_cards.get(ck)
        row = self._updating_row(ck)

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
                    # The record this transfer set out to replace, which for a
                    # second ISO of one distro is not the distro-and-flavor one.
                    ck=ck if ck in self.inventory_mgr.items else "",
                )
            self._remove_download_card(ck)
            if row:
                row.end_download(True, version=getattr(task, "_distro_meta", {}).get("version", ""))

            # Report the outcome before refreshing: a row still marked as
            # downloading would ignore the refresh and keep its progress bar.
            target = self.download_targets.pop(ck, None)
            if target:
                self.download_ended.emit(target[0], target[1], True, msg)

            self.refresh_installed_list()
        else:
            msg = msg or "Download interrupted"
            if dcard:
                dcard.show_error(msg)
            if row:
                row.end_download(False, msg)
            target = self.download_targets.pop(ck, None)
            if target:
                self.download_ended.emit(target[0], target[1], False, msg)

    def cancel_by_flavor(self, key: str, flavor_id: str):
        """Cancel a transfer addressed the way the catalog knows it."""
        # Whichever rows are fetching this flavor: the catalog shows one
        # progress bar for it, and its Cancel has to stop what that bar shows.
        running = [ck for ck, target in self.download_targets.items()
                   if target == (key, flavor_id)]
        for ck in running or [self.inventory_mgr._composite_key(key, flavor_id)]:
            self._cancel_download(ck)

    def _cancel_download(self, ck: str):
        task = self.active_tasks.pop(ck, None)
        if task:
            task.cancel()
        self._download_tokens.pop(ck, None)

        target = self.download_targets.pop(ck, None)
        if target:
            self.download_ended.emit(target[0], target[1], False, "Cancelled")
        self._remove_download_card(ck)
        row = self._updating_row(ck)
        if row:
            row.end_download(False)
        self.refresh_installed_list()

    def _dismiss_download(self, ck: str):
        self._cancel_download(ck)

    # ------------------------------------------------------------ actions

    def _key_of(self, card: DistroCard) -> str:
        return next((ck for ck, c in self.cards.items() if c is card), "")

    def _handle_single_check(self, item: InventoryItem, card: DistroCard):
        ck = self._key_of(card)
        self._refresh_subtitle()
        recipe = registry.get_recipe(item.key)
        if not recipe:
            self._on_check_slot(ck, "Unknown", "")
            return

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
        """Check every row, going through the row so it shows that it is asking.

        This used to call the check directly. The rows kept whatever they said
        last time, so a second press changed nothing on screen until - and
        unless - an answer came back different.
        """
        for ck, card in list(self.cards.items()):
            if card.is_downloading:
                continue
            # Registered first: a row with no recipe answers synchronously.
            self._pending_checks.add(ck)
            card.start_check()      # a row already checking just keeps waiting
        self._sync_check_all()

    def _handle_single_download(self, item: InventoryItem, card: DistroCard):
        recipe = registry.get_recipe(item.key)
        if recipe:
            self._on_catalog_install_request(recipe, item.flavor_id, ck=self._key_of(card))

    def _handle_single_cancel(self, item: InventoryItem, card: DistroCard):
        self._cancel_download(self._key_of(card))

    def _ask_removal(self, item: InventoryItem) -> str:
        """"delete", "release" or "" - what Remove should do with this ISO.

        Deleting used to be the only way off the list, which is no way out for
        an ISO that should stay on the drive but not be managed: a customised
        image under an official name, or one adopted by mistake.
        """
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle("Remove from VEIM")
        box.setText(f"Remove {item.display_name} ({item.version})?")
        box.setInformativeText(
            f"{item.filename}\n\n"
            "Delete it from the drive, or keep the file and only stop managing it. "
            "A kept file still boots; VEIM will not check, update or offer it again.")
        delete = box.addButton("Delete File", QMessageBox.ButtonRole.DestructiveRole)
        release = box.addButton("Keep File, Stop Managing", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        return "delete" if clicked is delete else "release" if clicked is release else ""

    def _handle_single_remove(self, item: InventoryItem, card: DistroCard):
        answer = self._ask_removal(item)
        if answer == "release":
            self.inventory_mgr.release(self._key_of(card), exclude=True)
            self.refresh_installed_list()
        elif answer == "delete":
            # By the row's own key: two ISOs can share a distro and flavor, and
            # looking the record up by those removed the other one's file.
            self.inventory_mgr.remove_entry(self._key_of(card), delete_file=True)
            self.refresh_installed_list()

    def apply_theme(self, colors: ThemeColors = None):
        """Styling comes from the global stylesheet; nothing to repaint here."""
        return
