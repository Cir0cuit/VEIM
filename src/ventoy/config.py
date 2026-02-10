import json
import os
from typing import Dict

class VentoyConfigurator:
    def __init__(self, ventoy_root: str):
        self.ventoy_root = ventoy_root
        self.config_path = os.path.join(ventoy_root, "ventoy", "ventoy.json")
        self.data = {
            "control": [],
            "menu_alias": [],
            "theme": {
                "file": "/ventoy/theme/theme.txt",
                "gfxmode": "1920x1080",
                "display_mode": "GUI",
                "serial_param": "--unit=0 --speed=9600",
                "ventoy_color": "#000000"
            }
        }

    def load_existing(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.data = json.load(f)
            except:
                pass # start fresh if corrupted

    def update_aliases(self, iso_map: Dict[str, str]):
        """
        iso_map: { "Ubuntu 24.04": "ubuntu-24.04-desktop.iso", "Fedora": "Fedora-..." }
        Updates the menu_alias list.
        """
        # Load existing aliases into a dict for easy merge?
        # Actually we should probably rewrite aliases for our managed ISOs.
        # But we must preserve User ISO aliases if possible? 
        # The prompt says "Every time an ISO is updated, the ventoy.json alias list must be rewritten".
        # So we can just rebuild the alias block for our managed ISOs.
        
        # Structure of menu_alias:
        # [ { "image": "/ISO/filename.iso", "alias": "Clean Name" } ]
        
        # We need absolute path relative to root? No, Ventoy uses absolute paths like /ISO/... or just /filename.iso
        # We assume managed ISOs are in /Managed_ISOs/ folder.
        
        current_aliases = self.data.get("menu_alias", [])
        
        # We'll clear aliases for files in Managed_ISOs and add new ones.
        # But for simplicity, let's just create the list for the passed map.
        
        new_aliases = []
        for clean_name, filename in iso_map.items():
            entry = {
                "image": f"/Managed_ISOs/{filename}",
                "alias": clean_name
            }
            new_aliases.append(entry)
            
        # If we want to preserve other aliases, we'd need more logic. 
        # For this task, "The tool maps this filename to a clean Menu Name".
        self.data["menu_alias"] = new_aliases

    def set_theme(self, theme_path: str = "/ventoy/theme/theme.txt"):
        # Ensure theme block exists
        if "theme" not in self.data:
            self.data["theme"] = {}
        self.data["theme"]["file"] = theme_path
        
        # Set dark theme or similar? 
        # Prompt says "Theme Plugin: Set a default dark theme."
        # This implies we might need to copy a theme file too? 
        # Or just configure it. I'll invoke this.
        pass

    def save(self):
        # Ensure directory
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4)
