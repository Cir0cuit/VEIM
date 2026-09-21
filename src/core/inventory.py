import json
import os
import shutil
import time
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from src.core.iso_identity import IsoIdentity, identify
from src.core.logger import log
from src.core.ventoy_config import VentoyConfig

# Reserved entry in the inventory file. Every other entry is a record, and a
# reader that predates this one skips anything that is not a dict.
EXCLUDED_KEY = "_excluded"


class InventoryItem:
    def __init__(self, key: str, flavor_id: str, display_name: str, version: str, filename: str,
                 size_bytes: int = 0, sha256: str = "", url: str = "", installed_at: str = ""):
        self.key = key
        self.flavor_id = flavor_id
        self.display_name = display_name
        self.version = version
        self.filename = filename
        self.size_bytes = size_bytes
        self.sha256 = sha256
        self.url = url
        self.installed_at = installed_at or time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 1)

    @property
    def size_gb(self) -> float:
        return round(self.size_bytes / (1024 * 1024 * 1024), 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "flavor_id": self.flavor_id,
            "display_name": self.display_name,
            "version": self.version,
            "filename": self.filename,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "url": self.url,
            "installed_at": self.installed_at
        }

    @staticmethod
    def from_dict(d: Dict[str, Any]) -> 'InventoryItem':
        return InventoryItem(
            key=d.get("key", ""),
            flavor_id=d.get("flavor_id", ""),
            display_name=d.get("display_name", d.get("key", "Unknown")),
            version=d.get("version", "Unknown"),
            filename=d.get("filename", ""),
            size_bytes=d.get("size_bytes", 0),
            sha256=d.get("sha256", ""),
            url=d.get("url", ""),
            installed_at=d.get("installed_at", "")
        )


@dataclass
class AdoptionCandidate:
    """An ISO on the drive that VEIM could keep up to date, but does not yet."""
    filename: str
    identity: IsoIdentity
    size_bytes: int
    in_root: bool           # still in the drive root, outside Managed_ISOs
    excluded: bool          # the user said to leave this one alone


class InventoryManager:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.managed_dir = os.path.join(ventoy_root, "Managed_ISOs")
        self.inventory_file = os.path.join(self.managed_dir, "veim_inventory.json")
        self.legacy_inventory_file = os.path.join(self.managed_dir, "vom_inventory.json")
        self.ventoy_config = VentoyConfig(ventoy_root)
        self.items: Dict[str, InventoryItem] = {}  # keyed by f"{key}::{flavor_id}"
        # Filenames the user has said to leave alone, so they are not offered
        # for adoption again.
        self.excluded: set = set()
        self.load()

    def _composite_key(self, key: str, flavor_id: str) -> str:
        return f"{key}::{flavor_id}" if flavor_id else key

    def _free_key(self, key: str, flavor_id: str, filename: str) -> str:
        """The inventory key for a record, made unique when the pair is taken.

        Two ISOs of one distro and flavor can sit on a drive at once - an old
        release kept next to a new one. Disambiguate rather than overwrite.
        """
        ck = self._composite_key(key, flavor_id)
        if ck in self.items and self.items[ck].filename != filename:
            ck = f"{ck}::{os.path.splitext(filename)[0]}"
        return ck

    def load(self):
        self.items = {}
        self.excluded = set()
        path_to_read = self.inventory_file if os.path.exists(self.inventory_file) else self.legacy_inventory_file
        if not os.path.exists(path_to_read):
            return
        try:
            with open(path_to_read, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, val in raw.items():
                if k == EXCLUDED_KEY:
                    if isinstance(val, list):
                        self.excluded = {str(name) for name in val}
                    continue
                if not isinstance(val, dict):
                    continue
                item = InventoryItem.from_dict(val)
                full_path = os.path.join(self.managed_dir, item.filename)
                if not os.path.exists(full_path):
                    log.info(f"ISO {item.filename} no longer exists on disk, skipping.")
                    continue
                if not self._still_trackable(item):
                    log.info(f"{item.filename} is not a download VEIM can keep current; "
                             "leaving it alone.")
                    continue
                if item.size_bytes == 0:
                    item.size_bytes = os.path.getsize(full_path)
                self.items[self._free_key(item.key, item.flavor_id, item.filename)] = item
            log.info(f"Loaded {len(self.items)} installed items from inventory.")
        except Exception as e:
            log.error(f"Error loading inventory from {path_to_read}: {e}")

    @staticmethod
    def _still_trackable(item: InventoryItem) -> bool:
        """Re-examine a record that was taken in from the drive, not downloaded.

        Older versions adopted every ISO they found and guessed what it was
        from a word in the name. An inventory written by one can hold a
        customised image filed as the official release - offered an update that
        would overwrite it - and rows for ISOs that nothing can update. A record
        VEIM downloaded itself carries its URL and is never doubted.
        """
        if item.url:
            return True
        found = identify(item.filename)
        if found is None or found.key != item.key:
            return False
        # The guess often had the right distro but a placeholder version
        # ("Latest", "Live"), which made every check report an update.
        item.flavor_id, item.version = found.flavor_id, found.version
        return True

    def save(self):
        os.makedirs(self.managed_dir, exist_ok=True)
        try:
            data: Dict[str, Any] = {k: item.to_dict() for k, item in self.items.items()}
            if self.excluded:
                data[EXCLUDED_KEY] = sorted(self.excluded)
            with open(self.inventory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            log.debug(f"Saved {len(self.items)} items to {self.inventory_file}")

            self.ventoy_config.sync_aliases([item.to_dict() for item in self.items.values()])
        except Exception as e:
            log.error(f"Failed to save inventory: {e}")

    # -- adoption ----------------------------------------------------------

    @staticmethod
    def _iso_names(folder: str) -> List[str]:
        try:
            return sorted(
                f for f in os.listdir(folder)
                if f.lower().endswith(".iso") and os.path.isfile(os.path.join(folder, f))
            )
        except OSError:
            return []

    def find_candidates(self, include_excluded: bool = False) -> List[AdoptionCandidate]:
        """Untracked ISOs named exactly like a download the catalog offers.

        Nothing is taken in from here on its own account: a candidate is only
        ever adopted because the user picked it. An ISO that identify() does
        not recognise is not a candidate at all - see iso_identity.
        """
        tracked = {item.filename for item in self.items.values()}
        found: Dict[str, AdoptionCandidate] = {}
        # Managed_ISOs first: a root file of the same name could not be moved in.
        for in_root, folder in ((False, self.managed_dir), (True, self.ventoy_root)):
            for fname in self._iso_names(folder):
                if fname in tracked or fname in found:
                    continue
                identity = identify(fname)
                if identity is None:
                    continue
                excluded = fname in self.excluded
                if excluded and not include_excluded:
                    continue
                found[fname] = AdoptionCandidate(
                    filename=fname, identity=identity, in_root=in_root, excluded=excluded,
                    size_bytes=os.path.getsize(os.path.join(folder, fname)))
        return list(found.values())

    def unmanaged_files(self) -> List[str]:
        """ISOs in Managed_ISOs that Ventoy boots but VEIM does not track."""
        tracked = {item.filename for item in self.items.values()}
        return [f for f in self._iso_names(self.managed_dir) if f not in tracked]

    def hidden_root_isos(self) -> List[str]:
        """ISOs in the drive root that Ventoy will not list.

        VEIM's ventoy.json points Ventoy at Managed_ISOs alone, so an ISO left
        in the root vanishes from the boot menu. Ones still waiting for an
        answer in the adoption dialog are not counted: adopting moves them.
        """
        if self.ventoy_config.search_root().strip("/") != os.path.basename(self.managed_dir):
            return []
        waiting = {c.filename for c in self.find_candidates() if c.in_root}
        return [f for f in self._iso_names(self.ventoy_root) if f not in waiting]

    def move_into_managed(self, filenames: List[str]) -> List[str]:
        """Move root ISOs into Managed_ISOs so they boot, without tracking them.

        Returns the ones that could not be moved. A file of the same name
        already in Managed_ISOs is never overwritten.
        """
        failed = []
        os.makedirs(self.managed_dir, exist_ok=True)
        for fname in filenames:
            src = os.path.join(self.ventoy_root, fname)
            dst = os.path.join(self.managed_dir, fname)
            try:
                if os.path.exists(dst):
                    raise FileExistsError(dst)
                shutil.move(src, dst)
                log.info(f"Moved {fname} into Managed_ISOs")
            except Exception as e:
                log.error(f"Could not move {fname} into Managed_ISOs: {e}")
                failed.append(fname)
        return failed

    def adopt(self, candidate: AdoptionCandidate, display_name: str) -> bool:
        """Start tracking a candidate, moving it into Managed_ISOs if need be."""
        dst = os.path.join(self.managed_dir, candidate.filename)
        if candidate.in_root:
            try:
                os.makedirs(self.managed_dir, exist_ok=True)
                shutil.move(os.path.join(self.ventoy_root, candidate.filename), dst)
            except Exception as e:
                log.error(f"Could not move {candidate.filename} into Managed_ISOs: {e}")
                return False
        if not os.path.exists(dst):
            return False

        found = candidate.identity
        ck = self._free_key(found.key, found.flavor_id, candidate.filename)
        self.items[ck] = InventoryItem(
            key=found.key, flavor_id=found.flavor_id, display_name=display_name,
            version=found.version, filename=candidate.filename,
            size_bytes=os.path.getsize(dst))
        self.excluded.discard(candidate.filename)
        self.save()
        return True

    def release(self, ck: str, exclude: bool):
        """Stop tracking an ISO. The file stays exactly where it is."""
        item = self.items.pop(ck, None)
        if item is None:
            return
        if exclude:
            self.excluded.add(item.filename)
        self.save()

    def set_excluded(self, filename: str, excluded: bool):
        """Remember that an ISO is to be left alone, or stop remembering it."""
        if excluded:
            self.excluded.add(filename)
        else:
            self.excluded.discard(filename)
        self.save()

    # -- records -----------------------------------------------------------

    def get_all_items(self) -> List[InventoryItem]:
        return list(self.items.values())

    def get_item(self, key: str, flavor_id: str = "") -> Optional[InventoryItem]:
        ck = self._composite_key(key, flavor_id)
        return self.items.get(ck)

    def is_installed(self, key: str, flavor_id: str = "") -> bool:
        return self.get_item(key, flavor_id) is not None

    def _purge_other_entries_for_file(self, filename: str, keep_ck: str):
        """Drop stale entries that point at `filename` under a different key.

        A download can land on a file that is already tracked - the second of
        two ISOs of one distro updating to the release the first already has.
        Without this, one ISO occupies two inventory slots and the dashboard
        draws two cards for it.
        """
        if not filename:
            return
        duplicates = [
            ck for ck, item in self.items.items()
            if ck != keep_ck and item.filename == filename
        ]
        for ck in duplicates:
            log.info(f"Merged duplicate inventory entry {ck} for {filename}")
            del self.items[ck]

    def add_or_update(self, key: str, flavor_id: str, display_name: str, version: str,
                      filename: str, size_bytes: int = 0, sha256: str = "", url: str = "",
                      ck: str = ""):
        """Record an ISO, replacing the record - and the file - it supersedes.

        `ck` names the record to replace when that is not the distro-and-flavor
        one: a second ISO of the same pair is filed under a longer key (see
        _free_key), and updating it must not overwrite the first.
        """
        ck = ck or self._composite_key(key, flavor_id)
        old_item = self.items.get(ck)

        # Claim this file for `ck`, discarding any entry that tracked it before
        # under a different key.
        self._purge_other_entries_for_file(filename, keep_ck=ck)

        if old_item and old_item.filename and old_item.filename != filename:
            old_path = os.path.join(self.managed_dir, old_item.filename)
            if os.path.exists(old_path):
                try:
                    os.remove(old_path)
                    log.info(f"Cleaned up replaced old version: {old_path}")
                except Exception as e:
                    log.warning(f"Could not remove old file {old_path}: {e}")

        item = InventoryItem(
            key=key,
            flavor_id=flavor_id,
            display_name=display_name,
            version=version,
            filename=filename,
            size_bytes=size_bytes,
            sha256=sha256,
            url=url
        )
        self.items[ck] = item
        self.excluded.discard(filename)
        self.save()

    def remove_item(self, key: str, flavor_id: str = "", delete_file: bool = True) -> bool:
        return self.remove_entry(self._composite_key(key, flavor_id), delete_file)

    def remove_entry(self, ck: str, delete_file: bool = True) -> bool:
        """Remove the record stored under `ck`, an inventory key as found in `items`.

        A distro and flavor do not always name one record: a second ISO of the
        same pair is filed under a longer key (see _free_key). Looking that one
        up by distro and flavor finds the first ISO instead, and deletes its file.
        """
        item = self.items.get(ck)
        if not item:
            return False

        if delete_file:
            full_path = os.path.join(self.managed_dir, item.filename)
            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    log.info(f"Deleted ISO file: {full_path}")
                except Exception as e:
                    log.error(f"Failed to delete {full_path}: {e}")
                    return False

        del self.items[ck]
        self.save()
        return True
