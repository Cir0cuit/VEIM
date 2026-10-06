import json
import os
import time
from dataclasses import asdict, dataclass, replace
from typing import Callable, Dict, List, Optional, Any, Set, Tuple
from src.core.iso_identity import IsoIdentity, identify
from src.core.logger import log
from src.core.ventoy_config import VentoyConfig, is_bootable

# Where VEIM keeps what it downloads and updates, and nothing else: Ventoy
# searches the whole drive, and anything VEIM does not manage belongs in the
# root. See InventoryManager.tidy_managed.
MANAGED_DIRNAME = "Managed_ISOs"
INVENTORY_FILENAME = "veim_inventory.json"
# A file still being written: VEIM's own downloads (resumed from where they
# stopped), a browser's, or a save swapped in when done. Never touched.
IN_FLIGHT_SUFFIXES = (".part", ".unpacking", ".tmp", ".crdownload", ".download", ".partial")
# A file that has changed this recently may still be arriving - copied in by
# Explorer, say, which writes the final name from the first byte.
SETTLE_SECONDS = 60
# What Windows and macOS put in any folder they open, and put back if moved.
OS_LITTER = {".ds_store", "thumbs.db", "desktop.ini"}
# A folder holding a file whose name starts with this is skipped by Ventoy,
# with everything below it (a ".ventoyignore.txt" from Notepad counts too).
IGNORE_MARKER = ".ventoyignore"
# Ventoy's own helpers for its WIM and VHD boot plugins: .img files Ventoy
# never lists, and that those plugins stop working without.
VENTOY_HELPERS = {"ventoy_wimboot.img", "ventoy_vhdboot.img"}


def _is_trash(dirname: str) -> bool:
    """A trash folder, which Ventoy skips unless VTOY_FILT_TRASH_DIR is "0".
    Compared as Ventoy compares, case and all: ".Trash-1000" is listed."""
    return (dirname.startswith(".trash-") or dirname == ".Trashes"
            or dirname.startswith("$RECYCLE.BIN"))

# Catalog entries that were split after inventories had been written with the
# old key: (key, flavor) as recorded -> the key that flavor lives under now.
MOVED_FLAVORS = {
    ("fedora", "cinnamon"): "fedora_spins",
    ("fedora", "xfce"): "fedora_spins",
    ("fedora", "budgie"): "fedora_spins",
}

# Reserved entry in the inventory file. Every other entry is a record, and a
# reader that predates this one skips anything that is not a dict.
EXCLUDED_KEY = "_excluded"


@dataclass(eq=False)
class InventoryItem:
    key: str
    flavor_id: str
    display_name: str
    version: str
    filename: str
    size_bytes: int = 0
    sha256: str = ""
    url: str = ""
    installed_at: str = ""

    def __post_init__(self):
        self.installed_at = self.installed_at or time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def size_mb(self) -> float:
        return round(self.size_bytes / (1024 * 1024), 1)

    # The fields, in order, are the record's keys in the inventory file.
    to_dict = asdict

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
            installed_at=d.get("installed_at", ""),
        )


_KINDS = {".efi": "EFI application", ".wim": "Windows image", ".img": "disk image",
          ".vhd": "virtual disk", ".vhdx": "virtual disk", ".vtoy": "virtual disk"}


@dataclass
class UnmanagedImage:
    """A bootable file on the drive that VEIM does not keep up to date."""
    path: str                       # from the drive root, "/"-separated
    size_bytes: int
    identity: Optional[IsoIdentity]  # None when not an official download
    excluded: bool                  # the user said to leave this one alone
    alias: str                      # its boot-menu name, "" if it has none

    @property
    def filename(self) -> str:
        return self.path.rsplit("/", 1)[-1]

    @property
    def kind(self) -> str:
        return _KINDS.get(os.path.splitext(self.filename)[1].lower(), "ISO image")

    @property
    def ventoy_path(self) -> str:
        """The path Ventoy and ventoy.json know it by."""
        return f"/{self.path}"

    @property
    def in_managed(self) -> bool:
        """Directly in Managed_ISOs, where adopting leaves it."""
        return self.path.lower() == f"{MANAGED_DIRNAME}/{self.filename}".lower()


@dataclass
class Tidied:
    """What InventoryManager.tidy_managed did with one thing in Managed_ISOs."""
    name: str           # as it was found, relative to Managed_ISOs
    outcome: str        # "adopted", "moved" or "stayed"
    detail: str         # the name it was adopted as, where it went, or why it stayed
    reason: str = ""    # why it had to leave Managed_ISOs


def _is_link(path: str) -> bool:
    isjunction = getattr(os.path, "isjunction", None)     # Python 3.12+
    return os.path.islink(path) or bool(isjunction and isjunction(path))


class InventoryManager:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.managed_dir = os.path.join(ventoy_root, MANAGED_DIRNAME)
        self.inventory_file = os.path.join(self.managed_dir, INVENTORY_FILENAME)
        self.ventoy_config = VentoyConfig(ventoy_root)
        self.items: Dict[str, InventoryItem] = {}  # keyed by f"{key}::{flavor_id}"
        # Filenames the user has said to leave alone, so they are not offered
        # for adoption again.
        self.excluded: set = set()
        # The inventory is there but could not be read: nothing is known about
        # what VEIM manages, so nothing may be moved, adopted or written.
        self.unreadable = False
        self.load()
        # VEIM up to 1.1.2 confined Ventoy to Managed_ISOs, which hid every other
        # image on the drive. Undo that at once, not at the next download.
        if self.ventoy_config.dropped_old_defaults:
            self.ventoy_config.save()

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
        self.unreadable = False
        if not os.path.exists(self.inventory_file):
            return
        try:
            with open(self.inventory_file, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for k, val in raw.items():
                if k == EXCLUDED_KEY:
                    if isinstance(val, list):
                        self.excluded = {str(name) for name in val}
                    continue
                if not isinstance(val, dict):
                    continue
                item = InventoryItem.from_dict(val)
                item.key = MOVED_FLAVORS.get((item.key, item.flavor_id), item.key)
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
            self.items, self.excluded, self.unreadable = {}, set(), True
            log.error(f"Error loading inventory from {self.inventory_file}: {e}")

    @staticmethod
    def _still_trackable(item: InventoryItem) -> bool:
        """Re-examine a record that was taken in from the drive, not downloaded.

        Older versions adopted every ISO they found and guessed what it was
        from a word in the name. An inventory written by one can hold a
        customised image filed as the official release - offered an update that
        would overwrite it - and rows for ISOs that nothing can update. A record
        VEIM downloaded itself carries its URL and is never doubted.

        Its version, though, is read again from the filename when a rule knows
        the name: a recipe that changes how it writes a version ("8.1" became
        "8.1 (20260219)") would otherwise offer every such row an "update" to
        the very file already on the drive.
        """
        if item.url:
            found = identify(item.filename)
            if found and (found.key, found.flavor_id) == (item.key, item.flavor_id):
                item.version = found.version
            return True
        found = identify(item.filename)
        if found is None or found.key != item.key:
            return False
        # The guess often had the right distro but a placeholder version
        # ("Latest", "Live"), which made every check report an update.
        item.flavor_id, item.version = found.flavor_id, found.version
        return True

    def save(self):
        if self.unreadable:
            log.error(f"Not writing {self.inventory_file}: it could not be read, "
                      "and saving would lose what it records.")
            return
        os.makedirs(self.managed_dir, exist_ok=True)
        try:
            data: Dict[str, Any] = {k: item.to_dict() for k, item in self.items.items()}
            if self.excluded:
                data[EXCLUDED_KEY] = sorted(self.excluded)
            # Swapped in whole, so a stick pulled mid-write keeps the old one.
            tmp = self.inventory_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.inventory_file)
            log.debug(f"Saved {len(self.items)} items to {self.inventory_file}")

            self.ventoy_config.sync_aliases([item.to_dict() for item in self.items.values()])
        except Exception as e:
            log.error(f"Failed to save inventory: {e}")

    # -- adoption ----------------------------------------------------------

    @staticmethod
    def _walk_images(folder: str, max_level: Optional[int] = None,
                     skip_trash: bool = True, skip_dot_underscore: bool = False) -> List[str]:
        """Bootable files under `folder` as Ventoy finds them, as "/"-separated paths.

        Ventoy skips a folder below `folder` that holds a .ventoyignore,
        together with everything below it; trash folders; its own plugin
        helpers; and anything more than VTOY_MAX_SEARCH_LEVEL folders deep -
        0 being `folder`'s own files.
        """
        found = []
        for dirpath, dirnames, filenames in os.walk(folder):
            if dirpath != folder and any(f.startswith(IGNORE_MARKER) for f in filenames):
                dirnames.clear()
                continue
            # A link or an NTFS junction leads off the drive, or round in a
            # circle; os.walk follows junctions even with followlinks=False.
            dirnames[:] = [d for d in dirnames
                           if not _is_link(os.path.join(dirpath, d))
                           and not (skip_trash and _is_trash(d))]
            rel = os.path.relpath(dirpath, folder)
            parts = [] if rel == os.curdir else rel.split(os.sep)
            if max_level is not None and len(parts) >= max_level:
                dirnames.clear()
            found += ["/".join(parts + [f]) for f in filenames
                      if is_bootable(f) and f not in VENTOY_HELPERS
                      and not (skip_dot_underscore and f.startswith("._"))]
        return sorted(found, key=str.lower)

    def _tracked_paths(self) -> set:
        """Tracked files as drive paths, lower-cased: FAT, exFAT and NTFS ignore
        case, so a tracked ISO renamed only in case is still the tracked file."""
        return {f"{MANAGED_DIRNAME}/{item.filename}".lower() for item in self.items.values()}

    def _is_tracked(self, image: UnmanagedImage) -> bool:
        """Whether VEIM tracks `image` by now - a download can land on its name
        while a dialog about it is open."""
        return image.path.lower() in self._tracked_paths()

    def _search_base(self) -> str:
        """Where Ventoy starts looking: the drive root, unless the user's own
        ventoy.json names a folder on it."""
        root = self.ventoy_config.search_root().strip("/")
        base = os.path.abspath(os.path.join(self.ventoy_root, *root.split("/")))
        drive = os.path.abspath(self.ventoy_root)
        # A "/../elsewhere" is no folder on the drive; Ventoy finds nothing
        # there, and nothing off the drive is VEIM's to list or delete.
        if os.path.commonpath([base, drive]) != drive:
            return self.ventoy_root
        return base

    def managed_in_menu(self) -> bool:
        """Whether Ventoy lists the top of Managed_ISOs, given the user's own
        search root and depth. VEIM sets neither, so normally it does."""
        rel = os.path.relpath(self.managed_dir, self._search_base())
        if rel.startswith(os.pardir):
            return False                # the search root is elsewhere
        depth = 0 if rel == os.curdir else len(rel.split(os.sep))
        level = self.ventoy_config.max_search_level()
        return level is None or depth <= level

    def unmanaged_images(self) -> List[UnmanagedImage]:
        """Every bootable file on the drive that VEIM does not track.

        That is everything Ventoy lists: the whole drive, as deep as
        ventoy.json lets it look. VEIM tracks only the top of Managed_ISOs, so
        a file anywhere else is unmanaged even when it shares a tracked file's
        name.
        """
        # ponytail: walks the whole drive on every refresh; cache by directory
        # mtimes if a drive holding a great many files makes it slow.
        self.ventoy_config.load()
        tracked = self._tracked_paths()
        base = self._search_base()
        prefix = os.path.relpath(base, self.ventoy_root)
        prefix = "" if prefix == os.curdir else prefix.replace(os.sep, "/") + "/"
        images = []
        for rel in self._walk_images(base, self.ventoy_config.max_search_level(),
                                     self.ventoy_config.filters_trash(),
                                     self.ventoy_config.filters_dot_underscore()):
            path = prefix + rel
            if path.lower() in tracked:
                continue
            name = path.rsplit("/", 1)[-1]
            try:
                size = os.path.getsize(os.path.join(self.ventoy_root, *path.split("/")))
            except OSError:
                continue                # gone since the listing
            images.append(UnmanagedImage(
                path=path, size_bytes=size, identity=identify(name),
                excluded=name in self.excluded, alias=self.ventoy_config.alias_for(f"/{path}")))
        return images

    def find_candidates(self, include_excluded: bool = False) -> List[UnmanagedImage]:
        """Unmanaged images named exactly like a download the catalog offers.

        Nothing is taken in from here on its own account: a candidate is only
        ever adopted because the user picked it. An image that identify() does
        not recognise is not a candidate at all - see iso_identity.
        """
        return [i for i in self.unmanaged_images()
                if i.identity is not None and (include_excluded or not i.excluded)]

    def _full_path(self, image: UnmanagedImage) -> str:
        return os.path.join(self.ventoy_root, *image.path.split("/"))

    def _move(self, image: UnmanagedImage, moved: UnmanagedImage) -> str:
        """Move an image to where `moved` says, menu name and all.

        Returns "" on success, else what went wrong. Never overwrites: the
        drive is FAT or exFAT, where a name differing only in case is the same
        file, and os.path.exists answers the same way. It all happens on the
        one drive, so this is a rename - and os.rename, unlike os.replace,
        refuses to overwrite on Windows should another file appear meanwhile.
        """
        if self._is_tracked(image):
            return f"{image.filename} is managed by VEIM now; it was left where it is."
        dst = self._full_path(moved)
        where = moved.ventoy_path.rsplit("/", 1)[0] or "the drive root"
        if os.path.exists(dst):
            return f"{where} already holds a file named {image.filename}."
        try:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            os.rename(self._full_path(image), dst)
        except OSError as e:
            log.error(f"Could not move {image.ventoy_path} to {where}: {e}")
            return f"Could not move {image.filename}: {e.strerror or e}"
        log.info(f"Moved {image.ventoy_path} to {moved.ventoy_path}")
        self.ventoy_config.move_alias(image.ventoy_path, moved.ventoy_path)
        return ""

    def delete_image(self, image: UnmanagedImage) -> str:
        """Delete an unmanaged image and its boot-menu name. "" on success."""
        if self._is_tracked(image):
            return f"{image.filename} is managed by VEIM now; it was not deleted."
        path = self._full_path(image)
        try:
            os.remove(path)
        except OSError as e:
            log.error(f"Failed to delete {path}: {e}")
            return f"Could not delete {image.filename}: {e.strerror or e}"
        log.info(f"Deleted {path}")
        self.ventoy_config.set_alias(image.ventoy_path, "")
        return ""

    def set_image_alias(self, image: UnmanagedImage, alias: str):
        """Name an unmanaged image in the boot menu; "" goes back to its filename."""
        self.ventoy_config.set_alias(image.ventoy_path, alias.strip())

    def adopt(self, image: UnmanagedImage, display_name: str) -> str:
        """Start tracking an unmanaged image the catalog recognises.

        VEIM tracks and updates only the top of Managed_ISOs, so an image
        anywhere else is moved there first - never over another file. Its
        menu name becomes the automatic one. Returns "" on success, else what
        went wrong.
        """
        if image.identity is None:
            return f"{image.filename} is not an image VEIM can update."
        self.ventoy_config.load()
        if not image.in_managed and not self.managed_in_menu():
            return (f"Ventoy's own settings keep it from looking in {MANAGED_DIRNAME}, "
                    f"where VEIM would move {image.filename}: it would drop out of "
                    "the boot menu. It was left where it is.")
        if self._is_tracked(image):
            return f"{image.filename} is managed by VEIM already."
        if not image.in_managed:
            error = self._move(image, replace(image, path=f"{MANAGED_DIRNAME}/{image.filename}"))
            if error:
                return error
            image = replace(image, path=f"{MANAGED_DIRNAME}/{image.filename}")
        path = self._full_path(image)
        if not os.path.exists(path):
            return f"{image.filename} is no longer on the drive."
        # The file's own name on the drive, which a record must match exactly.
        filename = os.path.basename(path)
        found = image.identity
        ck = self._free_key(found.key, found.flavor_id, filename)
        self.items[ck] = InventoryItem(
            key=found.key, flavor_id=found.flavor_id, display_name=display_name,
            version=found.version, filename=filename, size_bytes=os.path.getsize(path))
        self.excluded.discard(filename)
        self.save()
        return ""

    def release(self, ck: str, exclude: bool) -> str:
        """Stop tracking an ISO, and move it out to the drive root, where it
        still boots: Managed_ISOs holds only what VEIM manages.

        Returns where it went ("/name.iso"), or "" if it could not be moved -
        it is released all the same, and the next tidy_managed() tries again.
        """
        item = self.items.pop(ck, None)
        if item is None:
            return ""
        if exclude:
            self.excluded.add(item.filename)
        self.save()
        # The name VEIM gave it is VEIM's; once it is not managed, its file
        # name is what the menu shows, and the user may choose another.
        self.ventoy_config.set_alias(f"/{MANAGED_DIRNAME}/{item.filename}", "")
        new, error = self._evict(item.filename)
        if error:
            log.error(f"Could not move {item.filename} out of {MANAGED_DIRNAME}: {error}")
            return ""
        return f"/{new}"

    # -- keeping Managed_ISOs to what VEIM manages ---------------------------

    def _free_root_name(self, name: str) -> str:
        """`name`, or "name (2).iso" and so on if the drive root has one already."""
        stem, ext = os.path.splitext(name)
        candidate, n = name, 2
        while os.path.lexists(os.path.join(self.ventoy_root, candidate)):
            candidate, n = f"{stem} ({n}){ext}", n + 1
        return candidate

    def _evict(self, name: str) -> Tuple[str, str]:
        """Move Managed_ISOs/<name>, a file or a folder, to the drive root -
        under a free name, never over anything - and its menu names with it.
        Returns (the name it has now, "") or ("", what went wrong)."""
        new = self._free_root_name(name)
        try:
            os.rename(os.path.join(self.managed_dir, name), os.path.join(self.ventoy_root, new))
        except OSError as e:
            return "", e.strerror or str(e)
        log.info(f"Moved /{MANAGED_DIRNAME}/{name} to /{new}")
        self.ventoy_config.move_alias(f"/{MANAGED_DIRNAME}/{name}", f"/{new}")
        # Ventoy pairs an image with the <image>.vcfg beside it; keep the pair.
        vcfg = os.path.join(self.managed_dir, name + ".vcfg")
        if os.path.isfile(vcfg) and not os.path.lexists(os.path.join(self.ventoy_root, new + ".vcfg")):
            try:
                os.rename(vcfg, os.path.join(self.ventoy_root, new + ".vcfg"))
            except OSError as e:
                log.error(f"Could not move {vcfg} along with {name}: {e}")
        return new, ""

    def tidy_managed(self, name_for: Callable[[UnmanagedImage], Optional[str]],
                     busy: Set[str] = frozenset(),
                     busy_editions: Set[Tuple[str, str]] = frozenset(),
                     now: Optional[float] = None) -> List["Tidied"]:
        """Leave in Managed_ISOs only what VEIM manages.

        Every image VEIM can recognise and update is adopted where it lies -
        one in a subfolder moved to the top first. Everything else - an image
        it does not recognise, one the user said to leave alone, any other
        file, any folder - goes to the drive root, where Ventoy boots it just
        the same. Drives set up by earlier versions, which kept everything in
        Managed_ISOs, are sorted out this way; so is whatever the user drops
        in there later.

        `name_for` gives the name to adopt an image under, or None when the
        catalog cannot update it. Left where they are, for a later pass: the
        filenames in `busy`, which a download is writing or has just written;
        images of an edition in `busy_editions`, which a download of that
        edition would take for the release it replaces; and anything that may
        still be arriving. Returns what was done.
        """
        # What another window, or another stick under the same letter, holds
        # now - not what was read when this one opened.
        self.load()
        self.ventoy_config.load()
        if self.unreadable or not os.path.isdir(self.managed_dir):
            return []
        now = time.time() if now is None else now
        busy = {b.lower() for b in busy}
        done: List[Tidied] = []
        reasons: Dict[str, str] = {}

        def arriving(path: str) -> bool:
            """Being written still: by a browser (a sibling .part and the
            like), or by a copy that started less than a minute ago."""
            if any(os.path.lexists(path + suffix) for suffix in IN_FLIGHT_SUFFIXES):
                return True
            try:
                st = os.stat(path)
            except OSError:
                return True
            return (os.path.isfile(path) and st.st_size == 0) or now - st.st_mtime < SETTLE_SECONDS

        def left_alone(name: str) -> bool:
            low = name.lower()
            return (low in busy or low.endswith(IN_FLIGHT_SUFFIXES)
                    or low in OS_LITTER or low.startswith("._"))

        tracked = {item.filename.lower() for item in self.items.values()}
        found = []
        for dirpath, dirnames, filenames in os.walk(self.managed_dir):
            dirnames[:] = [d for d in dirnames if not _is_link(os.path.join(dirpath, d))]
            rel = os.path.relpath(dirpath, self.managed_dir)
            found += [f if rel == os.curdir else "/".join(rel.split(os.sep) + [f])
                      for f in filenames]
        for rel in sorted(found, key=str.lower):
            name = rel.rsplit("/", 1)[-1]
            full = os.path.join(self.managed_dir, *rel.split("/"))
            if (not is_bootable(name) or left_alone(name) or arriving(full)
                    or ("/" not in rel and name.lower() in tracked)):
                continue
            identity = identify(name)
            if identity and (identity.key, identity.flavor_id) in busy_editions:
                busy.add(rel.split("/", 1)[0].lower())      # until that download is done
                continue
            try:
                size = os.path.getsize(full)
            except OSError:
                continue                    # gone since the listing
            image = UnmanagedImage(path=f"{MANAGED_DIRNAME}/{rel}", size_bytes=size,
                                   identity=identity, excluded=name in self.excluded, alias="")
            if image.identity is None:
                reasons[rel] = "not recognised as an official download from the catalog"
                continue
            if image.excluded:
                reasons[rel] = "you chose to leave it alone"
                continue
            display_name = name_for(image)
            if display_name is None:
                reasons[rel] = "the catalog no longer offers that edition"
                continue
            error = self.adopt(image, display_name)
            if error:
                reasons[rel] = error
            else:
                done.append(Tidied(rel, "adopted", display_name))
                tracked.add(name.lower())

        tracked = {item.filename.lower() for item in self.items.values()}
        try:
            entries = sorted(os.listdir(self.managed_dir), key=str.lower)
        except OSError as e:
            log.error(f"Could not list {self.managed_dir}: {e}")
            return done
        for entry in entries:
            low = entry.lower()
            full = os.path.join(self.managed_dir, entry)
            if (low == INVENTORY_FILENAME or low in tracked or left_alone(entry)
                    or (low.endswith(".vcfg") and low[:-5] in tracked)):
                continue
            if not os.path.lexists(full):
                continue                    # an image's .vcfg, moved along with it
            if arriving(full):
                continue
            is_folder = os.path.isdir(full)
            if is_folder:
                reason = "a folder of your own, and Managed_ISOs holds only what VEIM manages"
                inside = [f"{k.split('/', 1)[1]}: {r}" for k, r in reasons.items()
                          if k.lower().startswith(low + "/")]
                if inside:
                    reason += " (inside, not adopted - " + "; ".join(inside) + ")"
            elif entry in reasons:
                reason = reasons[entry]
            elif is_bootable(entry):
                reason = "not managed by VEIM"
            else:
                reason = "not a bootable image"
            new, error = self._evict(entry)
            if error:
                done.append(Tidied(entry, "stayed", error, reason))
            else:
                done.append(Tidied(entry, "moved", f"/{new}", reason))
        return done

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
