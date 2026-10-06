"""Installed-ISO library.

The download orchestration (worker threads, the Qt signal bridge, inventory
writes) is unchanged; only the presentation is rebuilt. Drive status and the
theme picker now live in the sidebar, so the old 64px toolbar - where a long
drive path ran underneath the buttons and got clipped - is gone.
"""
import os
import threading
from dataclasses import dataclass
from typing import Dict, Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea, QMessageBox, QDialog,
    QInputDialog, QLineEdit
)
from PySide6.QtCore import Qt, Signal, QObject, QTimer
from PySide6.QtGui import QGuiApplication

from src.core.inventory import InventoryManager, InventoryItem, Tidied, UnmanagedImage
from src.core.drive import DriveDetector
from src.recipes.registry import registry
from src.core.recipe_base import DistroRecipe, ScrapeError
from src.core.downloader import DownloadTask, free_for_download, probe_size, reserved_bytes
from src.core.logger import log
from src.ui.components import make_button, DriveMap, EmptyState
from src.ui.distro_card import DistroCard, human_size
from src.ui.downloading_card import DownloadingCard
from src.ui.adopt_dialog import AdoptDialog, ADOPT, EXCLUDE, UNDECIDED
from src.ui.unmanaged_row import UnmanagedRow


def catalog_name(recipe: DistroRecipe, flavor_id: str) -> str:
    """What the catalog calls an edition: "Debian Net Install".

    A project with one edition is just its name - "Arch Linux", not "Arch
    Linux Standard ISO": the catalog shows no selector for it, and the label
    would only lengthen the row and the boot-menu entry.
    """
    flavors = recipe.get_flavors()
    if len(flavors) == 1 and flavors[0].id == flavor_id:
        return recipe.name
    flavor = next((f for f in flavors if f.id == flavor_id), None)
    name = flavor.name if flavor else flavor_id.title()
    # Some catalog entries group a project's editions under a title of their
    # own ("Fedora Spins"); their editions go by the project's name.
    project = getattr(recipe, "edition_prefix", recipe.name)
    # An edition named after its project already says which it is: "Ubuntu
    # Desktop", "Kubuntu" and "Kali Purple", not "Ubuntu Ubuntu Desktop".
    if (project.replace(" ", "").lower() in name.replace(" ", "").lower()
            or name.split()[0].lower() == project.split()[0].lower()):
        return name
    return f"{project} {name}"


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
    # composite_key, token, DownloadTask, SpacePlan: the new release fits only
    # once the old one is gone, and that is the user's call.
    space_signal = Signal(str, object, object, object)


@dataclass(frozen=True)
class SpacePlan:
    """An update that fits on the drive only once the ISO it replaces is gone."""
    needed: int         # bytes the new release still has to write
    free: int           # free bytes, less what other transfers will take
    old_path: str       # the ISO on the drive now
    old_size: int


def _gb(n: int) -> str:
    return f"{n / (1024 ** 3):.2f} GB"


ADOPT_TEXT = "Adopt ISOs"
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
    download_progress = Signal(str, str, object)           # key, flavor, DownloadTask
    download_ended = Signal(str, str, bool, str)           # key, flavor, ok, message

    def __init__(self, drive_path: str, parent=None):
        super().__init__(parent)
        self.drive_path = drive_path

        self.inventory_mgr = InventoryManager(drive_path)
        self.cards: Dict[str, DistroCard] = {}
        self.download_cards: Dict[str, DownloadingCard] = {}
        # Images VEIM does not manage, by the path ventoy.json knows them by.
        self.unmanaged_rows: Dict[str, UnmanagedRow] = {}
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
        # Updates whose old ISO was deleted up front to make room. If one of
        # these fails, there is no ISO left to show a row for.
        self._reclaimed: set = set()

        # Not a child of this view: a check or download thread can outlive it -
        # the user switches drives mid-check - and would then emit on a deleted
        # object. Unowned, the bridge lives as long as the threads holding it,
        # and its signals reach nothing once the view and its slots are gone.
        self.bridge = DashboardWorkerBridge()
        self.bridge.ready_signal.connect(self._on_ready_slot)
        self.bridge.progress_signal.connect(self._on_progress_slot)
        self.bridge.complete_signal.connect(self._on_complete_slot)
        self.bridge.check_signal.connect(self._on_check_slot)
        self.bridge.error_signal.connect(self._on_error_slot)
        self.bridge.space_signal.connect(self._on_space_slot)

        self._build_ui()
        self.refresh_installed_list()

        # Managed_ISOs holds only what VEIM manages: sort it out once the
        # window is up, and again whenever VEIM comes back to the front -
        # which is when a file the user dropped in there is new.
        self._tidying = False
        self._stays_reported: set = set()
        QTimer.singleShot(0, self.tidy_managed)
        QGuiApplication.instance().applicationStateChanged.connect(self._on_app_state)

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

        # What the drive holds, to scale. Shown once the drive has been read.
        self.drive_map = DriveMap()
        root.addWidget(self.drive_map)
        root.addSpacing(14)

        # --- scrolling body ---------------------------------------------
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 6, 0)
        body_layout.setSpacing(2)

        self.lbl_downloads = QLabel("Downloading")
        self.lbl_downloads.setObjectName("sectionLabel")
        self.lbl_downloads.hide()
        body_layout.addWidget(self.lbl_downloads)

        self.download_layout = QVBoxLayout()
        self.download_layout.setSpacing(2)
        body_layout.addLayout(self.download_layout)

        self.lbl_installed = QLabel("On this drive")
        self.lbl_installed.setObjectName("sectionLabel")
        self.lbl_installed.hide()
        body_layout.addSpacing(6)
        body_layout.addWidget(self.lbl_installed)

        self.installed_layout = QVBoxLayout()
        self.installed_layout.setSpacing(2)
        body_layout.addLayout(self.installed_layout)

        # Bootable files VEIM does not keep up to date. They are never checked
        # or updated, but they can still be named, adopted or deleted.
        self.lbl_unmanaged = QLabel("Not managed by VEIM")
        self.lbl_unmanaged.setObjectName("sectionLabel")
        self.lbl_unmanaged.hide()
        body_layout.addSpacing(6)
        body_layout.addWidget(self.lbl_unmanaged)

        self.unmanaged_layout = QVBoxLayout()
        self.unmanaged_layout.setSpacing(2)
        body_layout.addLayout(self.unmanaged_layout)

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

    def _display_name(self, candidate: UnmanagedImage) -> str:
        """Named the way a download of the same thing would be."""
        found = candidate.identity
        recipe = registry.get_recipe(found.key)
        return catalog_name(recipe, found.flavor_id) if recipe else candidate.filename

    def _adoptable(self, include_excluded: bool = False) -> List[UnmanagedImage]:
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
        # Listing walks the whole drive: once, for both what to offer and
        # how many others there are.
        images = self.inventory_mgr.unmanaged_images()
        candidates = sorted((i for i in images if self._adoptable_image(i)),
                            key=lambda c: c.excluded)
        if not candidates:
            return
        dialog = AdoptDialog(
            candidates, {c.ventoy_path: self._display_name(c) for c in candidates},
            unrecognised=sum(1 for i in images if not self._adoptable_image(i)),
            parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._apply_adoption(candidates, dialog.choices())

    def _unrecognised(self, candidates: List[UnmanagedImage]) -> int:
        """Images in the boot menu with nothing to update from: neither listed in
        the adoption dialog nor adoptable from their own row."""
        listed = {c.ventoy_path for c in candidates}
        return sum(1 for i in self.inventory_mgr.unmanaged_images()
                   if i.ventoy_path not in listed
                   and not self._adoptable_image(i))

    def _apply_adoption(self, candidates: List[UnmanagedImage], choices: Dict[str, str]):
        failed = []
        for candidate in candidates:
            if choices.get(candidate.ventoy_path, UNDECIDED) == ADOPT:
                error = self.inventory_mgr.adopt(candidate, self._display_name(candidate))
                if error:
                    failed.append(error)
        # After the adoptions: being left alone goes by filename, and adopting
        # a same-named file from another folder would clear the answer.
        for candidate in candidates:
            choice = choices.get(candidate.ventoy_path, UNDECIDED)
            if choice != ADOPT and (choice == EXCLUDE) != candidate.excluded:
                self.inventory_mgr.set_excluded(candidate.filename, choice == EXCLUDE)

        self.refresh_installed_list()
        if failed:
            QMessageBox.warning(self, "Could not adopt", "\n\n".join(failed))

    def drive_stats(self):
        """(free_gb, total_gb) for the sidebar, or (0, 0) if unavailable."""
        info = DriveDetector.inspect_path(self.drive_path)
        if info:
            return info.free_gb, info.total_gb
        return 0.0, 0.0

    @staticmethod
    def reserved_gb() -> float:
        """What the transfers in flight have still to write, in GB."""
        return reserved_bytes() / (1024 ** 3)

    def written_gb(self) -> float:
        """What the transfers in flight have written so far, in GB."""
        return sum(t.downloaded_bytes for t in self.active_tasks.values() if t) / (1024 ** 3)

    # ------------------------------------------------------------- listing

    def refresh_installed_list(self):
        """Bring the rows in line with the inventory.

        Rows are kept, not rebuilt: a row holds the answer to its last check
        and any transfer running on it, and rebuilding the list whenever one
        download finished wiped both from every other row.
        """
        self._follow_catalog_names()
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
                card.on_hover = lambda over, ck=ck: self.drive_map.mark(ck if over else None)
                self.cards[ck] = card
            else:
                card.set_item(it)
            if self.installed_layout.indexOf(card) != index:
                self.installed_layout.removeWidget(card)
                self.installed_layout.insertWidget(index, card)

        self.drive_map.set_isos(
            (ck, it.key, it.display_name or it.key, it.size_bytes) for ck, it in records.items())
        images = self._refresh_unmanaged()

        has_downloads = bool(self.download_cards)
        self.lbl_downloads.setVisible(has_downloads)
        self.lbl_installed.setVisible(bool(records))

        if not records and not has_downloads and not images:
            self.empty_container.show()
            self.scroll.hide()
        else:
            self.empty_container.hide()
            self.scroll.show()

        self._sync_check_all()
        self._refresh_subtitle()

        self._refresh_adoption(images)

        self.drive_changed.emit()

    def _refresh_unmanaged(self) -> List[UnmanagedImage]:
        """Bring the unmanaged rows in line with the drive, kept rather than
        rebuilt for the same reason as the installed ones."""
        images = self.inventory_mgr.unmanaged_images()
        by_path = {i.ventoy_path: i for i in images}

        for path in [p for p in self.unmanaged_rows if p not in by_path]:
            row = self.unmanaged_rows.pop(path)
            self.unmanaged_layout.removeWidget(row)
            row.hide()
            row.deleteLater()

        for index, (path, image) in enumerate(by_path.items()):
            adoptable = self._adoptable_image(image)
            row = self.unmanaged_rows.get(path)
            if row is None:
                row = UnmanagedRow(
                    image, adoptable,
                    on_adopt=self._adopt_image,
                    on_rename=self._rename_image,
                    on_delete=self._delete_image,
                )
                self.unmanaged_rows[path] = row
            else:
                row.set_image(image, adoptable)
            if self.unmanaged_layout.indexOf(row) != index:
                self.unmanaged_layout.removeWidget(row)
                self.unmanaged_layout.insertWidget(index, row)

        self.lbl_unmanaged.setVisible(bool(images))
        self.drive_map.set_unmanaged(sum(i.size_bytes for i in images))
        return images

    @staticmethod
    def _adoptable_image(image: UnmanagedImage) -> bool:
        """Adopt is offered only where an update could follow: a recognised
        name is not enough if the recipe no longer offers that flavor."""
        if image.identity is None:
            return False
        recipe = registry.get_recipe(image.identity.key)
        return bool(recipe) and any(f.id == image.identity.flavor_id
                                    for f in recipe.get_flavors())

    def _follow_catalog_names(self):
        """Give each row the name the catalog has for its edition now.

        A row keeps the name it was downloaded under, and that name is its
        boot-menu entry too. Shortening an edition's name in the catalog
        ("Netinst (Network Installer)" became "Net Install") would otherwise
        leave every drive that already had it on the old one.
        """
        changed = False
        for item in self.inventory_mgr.items.values():
            recipe = registry.get_recipe(item.key)
            if recipe is None or item.flavor_id not in {f.id for f in recipe.get_flavors()}:
                continue        # an edition the catalog no longer has keeps its name
            name = catalog_name(recipe, item.flavor_id)
            if item.display_name != name:
                item.display_name, changed = name, True
        if changed:
            self.inventory_mgr.save()

    def _refresh_subtitle(self):
        items = self.inventory_mgr.get_all_items()
        count = len(items)
        if not count:
            self.subtitle.setText("Nothing installed yet")
            return

        # How much they take is on the drive map.
        bits = [f"{count} distribution{'s' if count != 1 else ''}"]

        # What the checks found, so the answer to "Check All Updates" can be
        # read in one place instead of by scrolling the list.
        # An update already on its way is being taken, not waiting to be.
        updates = sum(1 for c in self.cards.values()
                      if c.update_available and not c.is_checking and not c.is_downloading)
        if any(c.is_checking for c in self.cards.values()):
            pass        # an answer being re-asked is not one to summarise yet
        elif updates:
            bits.append(f"{updates} update{'s' if updates != 1 else ''} available")
        elif self.cards and all(c.is_up_to_date for c in self.cards.values()):
            bits.append("all up to date")
        self.subtitle.setText(", ".join(bits))

    def _refresh_adoption(self, images: List[UnmanagedImage]):
        """The header button, counting what still waits for an answer.

        `images` is the listing the rows were just built from: listing walks
        the whole drive, once is enough.
        """
        # An ISO left alone is adopted after all from its own row.
        waiting = sum(1 for i in images if not i.excluded and self._adoptable_image(i))
        self.btn_adopt.setVisible(bool(waiting))
        self.btn_adopt.setText(f"{ADOPT_TEXT} ({waiting})")

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

    def _on_catalog_install_request(self, recipe: DistroRecipe, flavor_id: str,
                                    ck: str = ""):
        """Start a download. `ck` names the installed row it replaces.

        The catalog knows only a distro and a flavor, which is the plain
        composite key. A row passes its own key, because a second ISO of the
        same distro and flavor is filed under a longer one - and its update
        used to run on, and then overwrite, the first ISO's row instead.
        """
        flavor_name = next((f.name for f in recipe.get_flavors() if f.id == flavor_id),
                           flavor_id.title())
        dname = catalog_name(recipe, flavor_id)
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
            self._refresh_subtitle()
        else:
            # Named as its row will be once it lands: "Ubuntu Desktop", not
            # "Ubuntu (Ubuntu Desktop)".
            card = DownloadingCard(
                key=recipe.key,
                distro_name=dname,
                flavor_name="",
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

    def _space_plan(self, ck: str, task: DownloadTask):
        """Worker thread: whether the transfer fits, before it starts.

        None when it does, or when the size cannot be learned - the transfer
        then checks itself once it knows. A SpacePlan when it fits only with
        the ISO it replaces deleted first. A message when it fits either way not.
        """
        size = probe_size(task.url, session=task.session)
        if size <= 0:
            return None
        already = os.path.getsize(task.part_path) if os.path.exists(task.part_path) else 0
        needed = size - already
        free = free_for_download(os.path.dirname(task.dest_path))
        if needed <= free:
            return None

        item = self.inventory_mgr.items.get(ck)
        old_path = os.path.join(self.inventory_mgr.managed_dir, item.filename) if item else ""
        old_size = os.path.getsize(old_path) if old_path and os.path.exists(old_path) else 0
        if old_size and needed <= free + old_size:
            return SpacePlan(needed=needed, free=free, old_path=old_path, old_size=old_size)
        return (f"Not enough space on drive! Required: {_gb(needed)}, "
                f"Available: {_gb(max(free, 0))}")

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
            plan = self._space_plan(ck, task)
            if isinstance(plan, str):
                self._report_setup_error(ck, token, plan)
                return
            # Started on the UI thread, which is the only one that knows whether
            # this transfer was cancelled while the recipe was still resolving.
            if plan is None:
                self.bridge.ready_signal.emit(ck, token, task)
            else:
                self.bridge.space_signal.emit(ck, token, task, plan)

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

    def _on_space_slot(self, ck: str, token: object, task: DownloadTask, plan: SpacePlan):
        if self._download_tokens.get(ck) is not token:
            return          # cancelled while the size was being looked up
        item = self.inventory_mgr.items.get(ck)
        if item is None or not os.path.exists(plan.old_path):
            # The old ISO went away meanwhile; the room is there after all.
            self._on_ready_slot(ck, token, task)
            return
        if not self._ask_reclaim(item, plan):
            self._on_error_slot(
                ck, f"Not enough space for the new release beside the current one: "
                    f"{_gb(plan.needed)} needed, {_gb(max(plan.free, 0))} free.")
            return
        try:
            os.remove(plan.old_path)
        except OSError as e:
            self._on_error_slot(ck, f"Could not delete {item.filename}: {e}")
            return
        log.info(f"Deleted {item.filename} to make room for its update")
        self._reclaimed.add(ck)
        self._on_ready_slot(ck, token, task)

    def _ask_reclaim(self, item: InventoryItem, plan: SpacePlan) -> bool:
        """Delete the old ISO first, so the new one fits? Its terms are plain:
        a failed download then leaves neither on the drive."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Low space on drive")
        box.setText(f"Not enough space to download the new {item.display_name} "
                    f"beside the current one.")
        box.setInformativeText(
            f"The update needs {_gb(plan.needed)} and the drive has {_gb(max(plan.free, 0))} "
            f"free. Deleting {item.filename} ({_gb(plan.old_size)}) first would make room.\n\n"
            "If the download then fails or is cancelled, neither the old ISO nor the "
            "new one will be on the drive. A failed download keeps its partial file "
            "and resumes when started again; a cancelled one is discarded.")
        delete = box.addButton("Delete Old ISO and Download", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is delete

    def _forget_reclaimed(self, ck: str, failure: str = "") -> bool:
        """After a transfer whose old ISO was deleted up front ended without a
        new one: the row has no file behind it any more."""
        if ck not in self._reclaimed:
            return False
        self._reclaimed.discard(ck)
        item = self.inventory_mgr.items.get(ck)
        self.inventory_mgr.remove_entry(ck, delete_file=False)
        if failure and item is not None:
            QMessageBox.warning(
                self, "Download failed",
                f"The new {item.display_name} could not be downloaded: {failure}\n\n"
                f"The previous ISO had been deleted to make room, so {item.display_name} "
                "is no longer on the drive. Download it again from the catalog; the "
                "partial file is kept and the transfer resumes from where it stopped.")
        return True

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
            # The transfer itself, so the catalog says exactly what the rows here do.
            self.download_progress.emit(target[0], target[1], task)

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
            self._refresh_subtitle()

        target = self.download_targets.pop(ck, None)
        if target:
            self.download_ended.emit(target[0], target[1], False, err_msg)
        if self._forget_reclaimed(ck, err_msg):
            self.refresh_installed_list()

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
            self._reclaimed.discard(ck)
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
            if self._forget_reclaimed(ck, msg):
                self.refresh_installed_list()

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
        # Cancelled on purpose, after being told what that would leave.
        self._forget_reclaimed(ck)
        self.refresh_installed_list()

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
            "A kept file moves to the drive root and still boots; VEIM will not "
            "check, update or offer it again.")
        delete = box.addButton("Delete File", QMessageBox.ButtonRole.DestructiveRole)
        release = box.addButton("Keep File, Stop Managing", QMessageBox.ButtonRole.AcceptRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        return "delete" if clicked is delete else "release" if clicked is release else ""

    # ------------------------------------------------------- Managed_ISOs

    def _on_app_state(self, state):
        if state == Qt.ApplicationState.ApplicationActive:
            self.tidy_managed()

    def _adoption_name(self, image: UnmanagedImage) -> Optional[str]:
        return self._display_name(image) if self._adoptable_image(image) else None

    def tidy_managed(self):
        """Adopt or move out whatever in Managed_ISOs VEIM does not manage,
        and say what was done and why."""
        if self._tidying:
            return              # the report below is modal, and focus comes back after it
        self._tidying = True
        try:
            # What a download is writing, or has written and not yet recorded,
            # and the editions being downloaded: an image of one adopted now
            # would be taken for the release the download replaces, and deleted.
            busy = {os.path.basename(t.dest_path) for t in self.active_tasks.values() if t}
            editions = {self.download_targets[ck] for ck in self.active_tasks
                        if ck in self.download_targets}
            before = dict(self.inventory_mgr.items)
            done = self.inventory_mgr.tidy_managed(self._adoption_name, busy, editions)
            if done or self.inventory_mgr.items.keys() != before.keys():
                self.refresh_installed_list()
            # A file that cannot be moved is retried every time, and said once.
            fresh = [d for d in done if d.outcome != "stayed"
                     or (d.name, d.detail) not in self._stays_reported]
            self._stays_reported |= {(d.name, d.detail) for d in done if d.outcome == "stayed"}
            if fresh:
                # Only what is news: a file still stuck was reported the first time.
                self._report_tidy(fresh)
        finally:
            self._tidying = False

    def _report_tidy(self, done: List[Tidied]):
        adopted = [d for d in done if d.outcome == "adopted"]
        moved = [d for d in done if d.outcome == "moved"]
        stayed = [d for d in done if d.outcome == "stayed"]
        lines = [f"Adopted {d.name} as {d.detail}." for d in adopted]
        lines += [f"Moved {d.name} to {d.detail}: {d.reason}." for d in moved]
        lines += [f"Could not move {d.name} ({d.reason}): {d.detail}." for d in stayed]
        bits = []
        if adopted:
            bits.append(f"{len(adopted)} adopted")
        if moved:
            bits.append(f"{len(moved)} moved to the drive root")
        if stayed:
            bits.append(f"{len(stayed)} could not be moved")

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning if stayed else QMessageBox.Icon.Information)
        box.setWindowTitle("Managed_ISOs sorted out")
        box.setText(f"Managed_ISOs had files VEIM did not manage: {', '.join(bits)}.")
        shown = 12
        box.setInformativeText(
            "Managed_ISOs holds only what VEIM keeps up to date. Ventoy boots "
            "everything else from wherever it is on the drive.\n\n"
            + "\n".join(lines[:shown])
            + (f"\n…and {len(lines) - shown} more, under Show Details." if len(lines) > shown else ""))
        if len(lines) > shown:
            box.setDetailedText("\n".join(lines))
        box.exec()

    def _ask_name(self, current: str) -> Optional[str]:
        """The boot-menu name typed, or None when the dialog was cancelled."""
        if self.inventory_mgr.ventoy_config.unreadable:
            QMessageBox.warning(
                self, "Menu names unavailable",
                "ventoy.json on this drive could not be read, so VEIM leaves it alone "
                "rather than write over its settings. Fix or remove it to name images.")
            return None
        text, ok = QInputDialog.getText(
            self, "Menu Name", "Name shown in the Ventoy boot menu:",
            QLineEdit.EchoMode.Normal, current)
        return text if ok else None

    def _rename_image(self, image: UnmanagedImage):
        name = self._ask_name(image.alias or image.filename)
        if name is None:
            return
        # With no name Ventoy shows the filename, so storing that changes nothing.
        self.inventory_mgr.set_image_alias(image, "" if name.strip() == image.filename else name)
        self.refresh_installed_list()

    def _adopt_image(self, image: UnmanagedImage):
        error = self.inventory_mgr.adopt(image, self._display_name(image))
        self.refresh_installed_list()
        if error:
            QMessageBox.warning(self, "Could not adopt", error)

    def _ask_delete(self, image: UnmanagedImage) -> bool:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle("Delete from drive")
        box.setText(f"Delete {image.filename} ({human_size(image.size_bytes)})?")
        box.setInformativeText(f"{image.ventoy_path}\n\nThis cannot be undone.")
        delete = box.addButton("Delete", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        return box.clickedButton() is delete

    def _delete_image(self, image: UnmanagedImage):
        if not self._ask_delete(image):
            return
        error = self.inventory_mgr.delete_image(image)
        self.refresh_installed_list()
        if error:
            QMessageBox.warning(self, "Could not delete", error)

    def _handle_single_remove(self, item: InventoryItem, card: DistroCard):
        answer = self._ask_removal(item)
        if answer == "release":
            moved_to = self.inventory_mgr.release(self._key_of(card), exclude=True)
            self.refresh_installed_list()
            if not moved_to:
                QMessageBox.warning(
                    self, "Could not move",
                    f"VEIM no longer manages {item.filename}, but it could not be moved "
                    "out of Managed_ISOs. VEIM will try again the next time it opens the drive.")
        elif answer == "delete":
            # By the row's own key: two ISOs can share a distro and flavor, and
            # looking the record up by those removed the other one's file.
            self.inventory_mgr.remove_entry(self._key_of(card), delete_file=True)
            self.refresh_installed_list()
