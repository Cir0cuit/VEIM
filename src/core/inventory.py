import json
import os
import logging

log = logging.getLogger("VOM")

class InventoryManager:
    def __init__(self, ventoy_path):
        self.ventoy_path = ventoy_path
        self.inventory_file = os.path.join(ventoy_path, "Managed_ISOs", "vom_inventory.json")
        self.data = {}
        self.load()

    def load(self):
        if os.path.exists(self.inventory_file):
            try:
                with open(self.inventory_file, 'r') as f:
                    self.data = json.load(f)
            except Exception as e:
                log.error(f"Failed to load inventory: {e}")
                self.data = {}

    def save(self):
        try:
            os.makedirs(os.path.dirname(self.inventory_file), exist_ok=True)
            with open(self.inventory_file, 'w') as f:
                json.dump(self.data, f, indent=4)
        except Exception as e:
            log.error(f"Failed to save inventory: {e}")

    def get_installed_version(self, distro_name):
        return self.data.get(distro_name, {}).get("version", "--")

    def update_entry(self, distro_name, version, filename, url):
        # Remove old file if exists and different?
        old_entry = self.data.get(distro_name)
        if old_entry:
            old_file = old_entry.get("filename")
            if old_file and old_file != filename:
                full_path = os.path.join(self.ventoy_path, "Managed_ISOs", old_file)
                if os.path.exists(full_path):
                    try:
                        os.remove(full_path)
                        log.info(f"Removed old version: {full_path}")
                    except Exception as e:
                        log.error(f"Could not remove old file: {e}")

        self.data[distro_name] = {
            "version": version,
            "filename": filename,
            "url": url,
            "updated_at": "now" # Todo: timestamp
        }
        self.save()
