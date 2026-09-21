import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class DebianRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="debian",
            name="Debian",
            category="Popular & Desktop",
            description="The Universal Operating System: legendary rock-solid stability."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("netinst", "Netinst (Network Installer)", "Minimal installer; fetches packages during setup."),
            FlavorInfo("gnome", "Live GNOME", "Full live environment with GNOME desktop."),
            FlavorInfo("kde", "Live KDE Plasma", "Full live environment with KDE Plasma desktop."),
            FlavorInfo("xfce", "Live Xfce", "Lightweight live environment with Xfce desktop."),
            FlavorInfo("cinnamon", "Live Cinnamon", "Full live environment with Cinnamon desktop."),
            FlavorInfo("mate", "Live MATE", "Full live environment with MATE desktop."),
            FlavorInfo("lxqt", "Live LXQt", "Very light live environment with LXQt desktop."),
            FlavorInfo("lxde", "Live LXDE", "Very light live environment with LXDE desktop."),
            FlavorInfo("standard", "Live Standard (Console)", "Minimal console-only live rescue environment.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        if target == "netinst":
            base_url = "https://cdimage.debian.org/debian-cd/current/amd64/iso-cd/"
            try:
                r = session.get(base_url, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".iso") and "netinst" in href:
                        m = re.search(r'debian-([\d\.]+)-amd64', href)
                        v = m.group(1) if m else "Current"
                        return DownloadInfo(version=v, url=base_url + href, filename=href)
            except Exception as e:
                log.warning(f"[Debian] Error scraping netinst: {e}")
        else:
            base_url = "https://cdimage.debian.org/debian-cd/current-live/amd64/iso-hybrid/"
            try:
                r = session.get(base_url, timeout=10)
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
                    if href.endswith(".iso") and (f"-{target}.iso" in href.lower() or f"-{target}-" in href.lower()):
                        m = re.search(r'debian-live-([\d\.]+)-', href)
                        v = m.group(1) if m else "Current"
                        return DownloadInfo(version=v, url=base_url + href, filename=href)
            except Exception as e:
                log.warning(f"[Debian] Error scraping live: {e}")

        raise ScrapeError(self.name, f"no current amd64 {target} image listed on cdimage.debian.org")
