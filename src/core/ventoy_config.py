import json
import os
from typing import Dict, List, Any, Optional
from src.core.logger import log

# What Ventoy lists in its boot menu. A ".vtoy" file is a virtual disk renamed
# so Ventoy boots it whole ("win11.vhd.vtoy"). These are Ventoy's facts, kept
# here because this module imports nothing of VEIM's but the logger, so the
# downloader, the inventory and the views can all use them.
BOOTABLE_EXTS = (".iso", ".wim", ".img", ".vhd", ".vhdx", ".efi", ".vtoy")

# What VEIM up to 1.1.2 wrote into every ventoy.json: a theme file it never put
# on the drive, and a fixed 1920x1080 that some machines cannot display.
OLD_DEFAULT_THEME = {
    "file": "/ventoy/theme/theme.txt",
    "gfxmode": "1920x1080",
    "display_mode": "GUI",
    "ventoy_color": "#1e1e2e",
}

# The folders VEIM keeps images in. An alias pointing into one at a file that
# is gone is VEIM's leftover; anywhere else it is somebody else's business.
OWN_FOLDERS = ("/Managed_ISOs/",)


def menu_name(item: Dict[str, Any]) -> str:
    """The boot-menu name of a tracked ISO: "Linux Mint Cinnamon 22.3"."""
    name = item.get("display_name") or item.get("filename", "")
    version = item.get("version", "")
    return f"{name} {version}" if version and version != "Unknown" else name


def is_bootable(name: str) -> bool:
    return name.lower().endswith(BOOTABLE_EXTS)


class VentoyConfig:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.config_dir = os.path.join(ventoy_root, "ventoy")
        self.config_file = os.path.join(self.config_dir, "ventoy.json")
        # Menu names are all VEIM writes. Everything else - where Ventoy
        # looks, how it looks - is the user's to set, and by default Ventoy
        # searches the whole drive, so an image boots wherever it was put.
        self.data: Dict[str, Any] = {"menu_alias": []}
        # A ventoy.json that is there but cannot be read holds somebody's
        # settings - a password, persistence, a theme - that VEIM cannot see.
        # Writing over it would replace all of them with VEIM's defaults.
        self.unreadable = False
        # Set when load() took out what VEIM up to 1.1.2 imposed; see
        # _drop_old_defaults.
        self.dropped_old_defaults = False
        self.load()

    def load(self):
        """Read ventoy.json from the drive.

        Called again before every change, not only on opening: VentoyPlugson
        or an editor may have changed the file since, and writing back what
        was read an hour ago would undo that.
        """
        self.unreadable = False
        content = ""
        if os.path.exists(self.config_file):
            try:
                # utf-8-sig: Notepad and PowerShell write UTF-8 with a BOM.
                with open(self.config_file, "r", encoding="utf-8-sig") as f:
                    content = f.read().strip()
                if content:
                    data = json.loads(content)
                    if not isinstance(data, dict):
                        raise ValueError("the top level is not an object")
                    self.data = data
                    log.debug(f"Loaded existing ventoy.json from {self.config_file}")
                    self.dropped_old_defaults |= self._drop_old_defaults()
                    return
            except Exception as e:
                self.unreadable = True
                log.warning(f"Could not parse ventoy.json, leaving it untouched: {e}")
                return
        # Deleted or emptied since it was last read: no settings, not the old ones.
        self.data = {"menu_alias": []}

    def _drop_old_defaults(self) -> bool:
        """Take out what VEIM up to 1.1.2 wrote into ventoy.json on its own account.

        Its VTOY_DEFAULT_SEARCH_ROOT of /Managed_ISOs hid every image anywhere
        else on the drive. Its theme named a file VEIM never put there and
        forced a resolution. Only those exact values are VEIM's: a search
        root set to another folder, or a theme whose file is on the drive,
        is the user's, and stays.
        """
        dropped = False
        control = self.data.get("control")
        if isinstance(control, list):
            kept = [e for e in control
                    if not (isinstance(e, dict) and list(e) == ["VTOY_DEFAULT_SEARCH_ROOT"]
                            and str(e["VTOY_DEFAULT_SEARCH_ROOT"]).rstrip("/").lower()
                            == "/managed_isos")]
            if len(kept) != len(control):
                # A depth limit counted from Managed_ISOs is now counted from
                # the drive root, one level further up: keep it reaching as deep.
                for entry in kept:
                    level = entry.get("VTOY_MAX_SEARCH_LEVEL") if isinstance(entry, dict) else None
                    if isinstance(level, str) and level.strip().isdigit():
                        entry["VTOY_MAX_SEARCH_LEVEL"] = str(int(level) + 1)
                if kept:
                    self.data["control"] = kept
                else:
                    del self.data["control"]
                log.info("Removed the Managed_ISOs search root: Ventoy searches the whole drive.")
                dropped = True
        if (self.data.get("theme") == OLD_DEFAULT_THEME
                and not self._file_exists(OLD_DEFAULT_THEME["file"])):
            del self.data["theme"]
            log.info("Removed the default theme VEIM used to write, whose file is not on the drive.")
            dropped = True
        return dropped

    def _control(self, name: str) -> Optional[str]:
        """A "control" option as Ventoy reads it: only string values, only the
        first key of each entry, and the last occurrence wins."""
        value = None
        for entry in self.data.get("control") or []:
            if isinstance(entry, dict) and entry and next(iter(entry)) == name:
                if isinstance(entry[name], str):
                    value = entry[name]
        return value

    def search_root(self) -> str:
        """The one directory Ventoy is told to look in, or "" if it looks everywhere.

        VEIM sets none; this is a search root the user chose in their own
        ventoy.json. Ventoy ignores one that does not start with "/".
        """
        if not os.path.exists(self.config_file) or self.unreadable:
            return ""
        root = self._control("VTOY_DEFAULT_SEARCH_ROOT") or ""
        return root if root.startswith("/") else ""

    def max_search_level(self) -> Optional[int]:
        """How many folders deep Ventoy looks below its search root; None for all.

        Level 0 is the search root's own files. Anything but a whole number
        ("max", say) leaves the search unlimited, as it does for Ventoy.
        """
        level = self._control("VTOY_MAX_SEARCH_LEVEL")
        return int(level) if level is not None and level.isdigit() else None

    def filters_trash(self) -> bool:
        """Whether Ventoy skips trash folders - its default, unless
        VTOY_FILT_TRASH_DIR is "0"."""
        return self._control("VTOY_FILT_TRASH_DIR") != "0"

    def filters_dot_underscore(self) -> bool:
        """Whether Ventoy skips macOS "._" files: only when asked to."""
        return self._control("VTOY_FILT_DOT_UNDERSCORE_FILE") == "1"

    def _aliases(self) -> list:
        aliases = self.data.get("menu_alias")
        return aliases if isinstance(aliases, list) else []

    def alias_for(self, image_path: str) -> str:
        """The boot-menu name given to `image_path` ("/Managed_ISOs/x.iso"), or ""."""
        for entry in self._aliases():
            if isinstance(entry, dict) and entry.get("image") == image_path:
                return str(entry.get("alias", ""))
        return ""

    def set_alias(self, image_path: str, alias: str):
        """Name an image in the boot menu; an empty alias removes the entry."""
        self.load()
        kept = [a for a in self._aliases()
                if not (isinstance(a, dict) and a.get("image") == image_path)]
        if alias:
            kept.append({"image": image_path, "alias": alias})
        if kept != self._aliases():
            self.data["menu_alias"] = kept
            self.save()

    def move_alias(self, old_path: str, new_path: str):
        """Let everything ventoy.json says about a file, or a whole folder,
        follow it when it moves: its menu name, and its persistence, auto
        install, injection, password and every other plugin entry."""
        self.load()
        moved = [False]

        def follow(value):
            if isinstance(value, str):
                if value == old_path:
                    moved[0] = True
                    return new_path
                if value.startswith(old_path + "/"):
                    moved[0] = True
                    return new_path + value[len(old_path):]
                return value
            if isinstance(value, list):
                return [follow(v) for v in value]
            if isinstance(value, dict):
                return {k: follow(v) for k, v in value.items()}
            return value

        data = follow(self.data)
        if moved[0]:
            self.data = data
            self.save()

    def _file_exists(self, image_path: str) -> bool:
        return os.path.exists(os.path.join(self.ventoy_root, *image_path.strip("/").split("/")))

    def sync_aliases(self, managed_items: List[Dict[str, Any]]):
        """Name every tracked ISO in the boot menu, and leave the rest alone.

        managed_items: inventory records, with 'filename', 'display_name' and
        'version'. A tracked ISO is named for what it is - distro, edition,
        version, "Linux Mint Cinnamon 22.3" - and renamed with every update;
        there is no choosing its name. Every other entry - a name the user
        gave an image VEIM does not track, a "dir" entry, a path outside
        VEIM's folders - is somebody's choice and is kept, unless it points
        into VEIM's own folders at a file that is no longer there.
        """
        self.load()
        tracked = {
            f"/Managed_ISOs/{item['filename']}": menu_name(item)
            for item in managed_items if item.get("filename")
        }

        def keep(entry) -> bool:
            if not isinstance(entry, dict) or "image" not in entry:
                return True
            image = str(entry["image"])
            if image in tracked:
                return False
            # A "*" is Ventoy's fuzzy match, not a file that could be missing.
            return ("*" in image or not image.startswith(OWN_FOLDERS)
                    or self._file_exists(image))

        self.data["menu_alias"] = [a for a in self._aliases() if keep(a)] + [
            {"image": image, "alias": alias} for image, alias in tracked.items()
        ]
        self.save()

    def save(self):
        if self.unreadable:
            log.warning(f"Not writing {self.config_file}: it could not be read, "
                        "and saving would discard its settings.")
            return
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            # Written beside it and swapped in, so a stick pulled mid-write
            # leaves the old file whole, not half of the new one. Ventoy reads
            # ventoy.json as UTF-8 and would show an escape as typed.
            tmp = self.config_file + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.config_file)
            log.debug(f"Saved ventoy.json to {self.config_file}")
        except Exception as e:
            log.error(f"Failed to save ventoy.json: {e}")
