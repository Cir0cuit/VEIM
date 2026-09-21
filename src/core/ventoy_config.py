import json
import os
from typing import Dict, List, Any
from src.core.logger import log

class VentoyConfig:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.config_dir = os.path.join(ventoy_root, "ventoy")
        self.config_file = os.path.join(self.config_dir, "ventoy.json")
        self.data: Dict[str, Any] = {
            "control": [
                { "VTOY_DEFAULT_SEARCH_ROOT": "/Managed_ISOs" }
            ],
            "menu_alias": [],
            "theme": {
                "file": "/ventoy/theme/theme.txt",
                "gfxmode": "1920x1080",
                "display_mode": "GUI",
                "ventoy_color": "#1e1e2e"
            }
        }
        self.load()

    def load(self):
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        self.data = json.loads(content)
                        log.debug(f"Loaded existing ventoy.json from {self.config_file}")
            except Exception as e:
                log.warning(f"Could not parse ventoy.json, will rebuild: {e}")

    def search_root(self) -> str:
        """The one directory Ventoy is told to look in, or "" if it looks everywhere.

        Read from the file on the drive, not from the defaults above: until
        VEIM has saved once there is no ventoy.json, and Ventoy still lists
        every ISO it can find. A ventoy.json somebody wrote themselves may not
        restrict the search at all.
        """
        if not os.path.exists(self.config_file):
            return ""
        for entry in self.data.get("control") or []:
            if isinstance(entry, dict) and entry.get("VTOY_DEFAULT_SEARCH_ROOT"):
                return str(entry["VTOY_DEFAULT_SEARCH_ROOT"])
        return ""

    def sync_aliases(self, managed_items: List[Dict[str, Any]]):
        """
        managed_items: list of dicts with 'filename' and 'display_name'.
        Preserves non-Managed_ISOs aliases and replaces/updates Managed_ISOs entries.
        """
        existing_aliases = self.data.get("menu_alias", [])
        
        # Keep aliases for non-Managed_ISOs files
        preserved_aliases = [
            a for a in existing_aliases
            if not isinstance(a, dict) or not a.get("image", "").startswith("/Managed_ISOs/")
        ]

        new_aliases = []
        for item in managed_items:
            fname = item.get("filename", "")
            dname = item.get("display_name") or item.get("distro_name", fname)
            if fname:
                new_aliases.append({
                    "image": f"/Managed_ISOs/{fname}",
                    "alias": dname
                })

        self.data["menu_alias"] = preserved_aliases + new_aliases
        self.save()

    def save(self):
        try:
            os.makedirs(self.config_dir, exist_ok=True)
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=4)
            log.debug(f"Saved ventoy.json to {self.config_file}")
        except Exception as e:
            log.error(f"Failed to save ventoy.json: {e}")
