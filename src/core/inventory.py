import json
import os
import re
import time
from typing import Dict, List, Optional, Any
from pathlib import Path
from src.core.logger import log
from src.core.ventoy_config import VentoyConfig

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

class InventoryManager:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.managed_dir = os.path.join(ventoy_root, "Managed_ISOs")
        self.inventory_file = os.path.join(self.managed_dir, "veim_inventory.json")
        self.legacy_inventory_file = os.path.join(self.managed_dir, "vom_inventory.json")
        self.ventoy_config = VentoyConfig(ventoy_root)
        self.items: Dict[str, InventoryItem] = {}  # keyed by f"{key}::{flavor_id}"
        self.load()

    def _composite_key(self, key: str, flavor_id: str) -> str:
        return f"{key}::{flavor_id}" if flavor_id else key

    def load(self):
        self.items = {}
        path_to_read = self.inventory_file if os.path.exists(self.inventory_file) else self.legacy_inventory_file
        if os.path.exists(path_to_read):
            try:
                with open(path_to_read, "r", encoding="utf-8") as f:
                    raw = json.load(f)
                    for k, val in raw.items():
                        if isinstance(val, dict):
                            item = InventoryItem.from_dict(val)
                            ck = self._composite_key(item.key, item.flavor_id)
                            full_path = os.path.join(self.managed_dir, item.filename)
                            if os.path.exists(full_path):
                                if item.size_bytes == 0:
                                    item.size_bytes = os.path.getsize(full_path)
                                self.items[ck] = item
                            else:
                                log.info(f"ISO {item.filename} no longer exists on disk, skipping.")
                log.info(f"Loaded {len(self.items)} installed items from inventory.")
            except Exception as e:
                log.error(f"Error loading inventory from {path_to_read}: {e}")

        self.sync_filesystem()

    def save(self):
        os.makedirs(self.managed_dir, exist_ok=True)
        try:
            data = {k: item.to_dict() for k, item in self.items.items()}
            with open(self.inventory_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            log.debug(f"Saved {len(self.items)} items to {self.inventory_file}")
            
            self.ventoy_config.sync_aliases([item.to_dict() for item in self.items.values()])
        except Exception as e:
            log.error(f"Failed to save inventory: {e}")

    def sync_filesystem(self):
        """Scans Managed_ISOs directory and adds any ISOs that aren't yet tracked."""
        if not os.path.exists(self.managed_dir):
            return

        existing_filenames = {item.filename for item in self.items.values()}
        try:
            for fname in os.listdir(self.managed_dir):
                if fname.lower().endswith(".iso") and fname not in existing_filenames:
                    full_path = os.path.join(self.managed_dir, fname)
                    size = os.path.getsize(full_path)
                    guessed = self.guess_distro_from_filename(fname)
                    key = guessed.get("key", "custom")
                    flavor = guessed.get("flavor_id", "default")
                    name = guessed.get("display_name", fname)
                    ver = guessed.get("version", "Unknown")

                    item = InventoryItem(
                        key=key,
                        flavor_id=flavor,
                        display_name=name,
                        version=ver,
                        filename=fname,
                        size_bytes=size
                    )
                    ck = self._composite_key(key, flavor)
                    # Two unrelated ISOs can guess to the same key (two Fedora spins,
                    # say). Disambiguate rather than overwrite.
                    if ck in self.items and self.items[ck].filename != fname:
                        ck = f"{ck}::{os.path.splitext(fname)[0]}"
                    self.items[ck] = item
                    log.info(f"Auto-discovered untracked ISO in Managed_ISOs: {fname}")
        except Exception as e:
            log.error(f"Error syncing filesystem: {e}")

    def get_all_items(self) -> List[InventoryItem]:
        return list(self.items.values())

    def get_item(self, key: str, flavor_id: str = "") -> Optional[InventoryItem]:
        ck = self._composite_key(key, flavor_id)
        return self.items.get(ck)

    def is_installed(self, key: str, flavor_id: str = "") -> bool:
        return self.get_item(key, flavor_id) is not None

    def _purge_other_entries_for_file(self, filename: str, keep_ck: str):
        """Drop stale entries that point at `filename` under a different key.

        sync_filesystem() guesses a flavor_id from the filename, which need not
        match the flavor_id a recipe later reports for the same download. Without
        this, one ISO occupies two inventory slots and the dashboard draws two
        cards for it - one showing a bogus 0.0 MB because it was never sized.
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
                      filename: str, size_bytes: int = 0, sha256: str = "", url: str = ""):
        ck = self._composite_key(key, flavor_id)
        old_item = self.items.get(ck)

        # Claim this file for `ck`, discarding any entry that tracked it before
        # under a differently-guessed key.
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
        self.save()

    def remove_item(self, key: str, flavor_id: str = "", delete_file: bool = True) -> bool:
        return self.remove_entry(self._composite_key(key, flavor_id), delete_file)

    def remove_entry(self, ck: str, delete_file: bool = True) -> bool:
        """Remove the record stored under `ck`, an inventory key as found in `items`.

        A distro and flavor do not always name one record: sync_filesystem()
        files a second ISO that guesses to the same pair under a longer key.
        Looking that one up by distro and flavor finds the first ISO instead,
        and deletes its file.
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


    @staticmethod
    def guess_distro_from_filename(filename: str) -> Dict[str, str]:
        fn = filename.lower()
        if "fedora" in fn:
            flavor = "kde" if "kde" in fn else ("workstation" if "workstation" in fn else "default")
            m = re.search(r'fedora[^\d]*(\d+)', fn)
            v = m.group(1) if m else "Latest"
            return {"key": "fedora", "flavor_id": flavor, "display_name": f"Fedora {v} {flavor.title()}", "version": v}
        elif "ubuntu" in fn:
            m = re.search(r'(\d+\.\d+(\.\d+)?)', fn)
            v = m.group(1) if m else "Latest"
            flavor = "desktop" if "desktop" in fn else ("server" if "server" in fn else "desktop")
            return {"key": "ubuntu", "flavor_id": flavor, "display_name": f"Ubuntu {v} {flavor.title()}", "version": v}
        elif "linuxmint" in fn or "mint" in fn:
            flavor = "cinnamon" if "cinnamon" in fn else ("mate" if "mate" in fn else "xfce")
            m = re.search(r'mint[^\d]*(\d+(\.\d+)?)', fn)
            v = m.group(1) if m else "22"
            return {"key": "mint", "flavor_id": flavor, "display_name": f"Linux Mint {v} {flavor.title()}", "version": v}
        elif "arch" in fn:
            m = re.search(r'(\d{4}\.\d{2}\.\d{2})', fn)
            v = m.group(1) if m else "Rolling"
            return {"key": "arch", "flavor_id": "standard", "display_name": f"Arch Linux {v}", "version": v}
        elif "debian" in fn:
            m = re.search(r'debian-(\d+(\.\d+)*)', fn)
            v = m.group(1) if m else "Latest"
            return {"key": "debian", "flavor_id": "netinst", "display_name": f"Debian {v}", "version": v}
        elif "kali" in fn:
            m = re.search(r'kali-linux-(\d+(\.\d+)*)', fn)
            v = m.group(1) if m else "Rolling"
            flavor = "live" if "live" in fn else "installer"
            return {"key": "kali", "flavor_id": flavor, "display_name": f"Kali Linux {v} {flavor.title()}", "version": v}
        elif "clonezilla" in fn:
            m = re.search(r'clonezilla-live-([^\s]+)-amd64', fn)
            v = m.group(1) if m else "Live"
            return {"key": "clonezilla", "flavor_id": "alternative", "display_name": f"Clonezilla {v}", "version": v}
        elif "gparted" in fn:
            m = re.search(r'gparted-live-([\d\.\-]+)-amd64', fn)
            v = m.group(1) if m else "Live"
            return {"key": "gparted", "flavor_id": "standard", "display_name": f"GParted Live {v}", "version": v}
        elif "rescuezilla" in fn:
            m = re.search(r'rescuezilla-([\d\.]+)', fn)
            v = m.group(1) if m else "Latest"
            return {"key": "rescuezilla", "flavor_id": "standard", "display_name": f"Rescuezilla {v}", "version": v}
        elif "shredos" in fn:
            return {"key": "shredos", "flavor_id": "standard", "display_name": "ShredOS", "version": "Latest"}
        elif "neon" in fn:
            return {"key": "kde_neon", "flavor_id": "user", "display_name": "KDE Neon", "version": "Current"}
        elif "pop-os" in fn or "pop_os" in fn:
            flavor = "nvidia" if "nvidia" in fn else "intel"
            return {"key": "popos", "flavor_id": flavor, "display_name": f"Pop!_OS ({flavor.upper()})", "version": "22.04"}
        elif "zorin" in fn:
            return {"key": "zorin", "flavor_id": "core", "display_name": "Zorin OS", "version": "Latest"}
        elif "tinycore" in fn or "corepure" in fn:
            return {"key": "tinycore", "flavor_id": "coreplus", "display_name": "Tiny Core Linux", "version": "Latest"}
        elif "pup" in fn:
            return {"key": "puppy", "flavor_id": "bookworm", "display_name": "Puppy Linux", "version": "Latest"}
        elif "alpine" in fn:
            m = re.search(r'alpine-[a-z]+-([\d\.]+)', fn) or re.search(r'(\d+\.\d+(\.\d+)?)', fn)
            v = m.group(1) if m else "Latest"
            flavor = "extended" if "extended" in fn else ("virt" if "virt" in fn else "standard")
            return {"key": "alpine", "flavor_id": flavor, "display_name": f"Alpine Linux {v}", "version": v}
        elif "endeavour" in fn:
            m = re.search(r'(\d{4}\.\d{2}\.\d{2})', fn) or re.search(r'(\d+\.\d+)', fn)
            v = m.group(1) if m else "Galileo"
            return {"key": "endeavour", "flavor_id": "default", "display_name": f"EndeavourOS {v}", "version": v}
        elif "manjaro" in fn:
            flavor = "kde" if "kde" in fn else ("gnome" if "gnome" in fn else "xfce")
            m = re.search(r'manjaro-[a-z]+-([\d\.]+)', fn) or re.search(r'(\d+\.\d+(\.\d+)?)', fn)
            v = m.group(1) if m else "Latest"
            return {"key": "manjaro", "flavor_id": flavor, "display_name": f"Manjaro {v} {flavor.upper()}", "version": v}
        elif "parrot" in fn:
            flavor = "home" if "home" in fn else "security"
            m = re.search(r'parrot-[a-z]+-([\d\.]+)', fn) or re.search(r'(\d+\.\d+)', fn)
            v = m.group(1) if m else "6.0"
            return {"key": "parrot", "flavor_id": flavor, "display_name": f"Parrot OS {v} {flavor.title()}", "version": v}
        
        clean = filename.replace(".iso", "").replace("-", " ").replace("_", " ").title()
        return {"key": "custom", "flavor_id": "default", "display_name": clean, "version": "Manual"}

