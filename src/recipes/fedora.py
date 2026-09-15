import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class FedoraRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="fedora",
            name="Fedora",
            category="Popular & Desktop",
            description="Innovative, cutting-edge RPM distribution backed by Red Hat."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("workstation", "Workstation (GNOME)", "Default modern GNOME desktop environment."),
            FlavorInfo("kde", "KDE Plasma", "Feature-rich, customizable KDE Plasma desktop."),
            FlavorInfo("cinnamon", "Cinnamon", "Traditional, elegant desktop experience."),
            FlavorInfo("xfce", "Xfce", "Lightweight, responsive and highly stable desktop."),
            FlavorInfo("budgie", "Budgie", "Sleek and intuitive modern desktop."),
            FlavorInfo("server", "Server", "Reliable server operating system.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://fedoraproject.org/releases.json"

        try:
            r = session.get(api_url, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[Fedora] Failed fetching releases.json: {e}")
            raise ScrapeError(self.name, f"could not read Fedora's release index ({e})")

        target = flavor_id.lower()

        # Desktop spins are identified by `subvariant` under a generic "Spins"
        # variant, so match either field. Entries carry a link and a SHA-256.
        candidates = []
        for entry in data:
            if entry.get("arch") != "x86_64":
                continue
            if not entry.get("link", "").endswith(".iso"):
                continue

            variant = str(entry.get("variant", "")).lower()
            subvariant = str(entry.get("subvariant", "")).lower()
            if target not in (variant, subvariant):
                continue

            raw_version = str(entry.get("version", ""))
            if not raw_version.isdigit():
                # Skip Rawhide and branched pre-releases.
                continue
            candidates.append((int(raw_version), entry))

        if not candidates:
            raise ScrapeError(
                self.name,
                f"release index lists no x86_64 {flavor_id} image",
            )

        candidates.sort(key=lambda c: c[0], reverse=True)
        version, entry = candidates[0]
        url = entry["link"]

        try:
            size = int(entry.get("size") or 0)
        except (TypeError, ValueError):
            size = 0

        return DownloadInfo(
            version=str(version),
            url=url,
            sha256=entry.get("sha256", ""),
            filename=url.split("/")[-1],
            size_bytes=size,
        )
