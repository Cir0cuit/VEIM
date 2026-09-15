import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class UbuntuRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="ubuntu",
            name="Ubuntu",
            category="Popular & Desktop",
            description="The world's most widely used desktop Linux distribution."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("desktop", "Ubuntu Desktop", "Standard flagship GNOME desktop environment."),
            FlavorInfo("server", "Ubuntu Server", "Headless, enterprise-grade server installation."),
            FlavorInfo("kubuntu", "Kubuntu", "KDE Plasma edition of Ubuntu."),
            FlavorInfo("xubuntu", "Xubuntu", "Fast and lightweight Xfce desktop."),
            FlavorInfo("lubuntu", "Lubuntu", "Extremely lightweight LXQt desktop."),
            FlavorInfo("mate", "Ubuntu MATE", "Classic, comfortable MATE desktop."),
            FlavorInfo("budgie", "Ubuntu Budgie", "Refined and elegant Budgie desktop.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        if target in ("desktop", "server"):
            base_url = "https://releases.ubuntu.com/"
        else:
            slug_map = {
                "kubuntu": "kubuntu",
                "xubuntu": "xubuntu",
                "lubuntu": "lubuntu",
                "mate": "ubuntu-mate",
                "budgie": "ubuntu-budgie"
            }
            slug = slug_map.get(target, "ubuntu")
            base_url = f"https://cdimage.ubuntu.com/{slug}/releases/"

        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")
            
            versions = []
            for a in soup.find_all("a", href=True):
                href = a["href"].strip("/")
                if href and href[0].isdigit() and re.match(r'^\d+\.\d+(\.\d+)?$', href):
                    versions.append(href)

            def ver_key(s):
                try:
                    return [int(u) for u in s.split(".") if u.isdigit()]
                except Exception:
                    return [0]

            versions.sort(key=ver_key, reverse=True)
            
            for ver in versions[:8]:
                paths_to_test = [f"{base_url}{ver}/", f"{base_url}{ver}/release/"]
                for p in paths_to_test:
                    try:
                        r2 = session.get(p, timeout=6)
                        if r2.status_code != 200:
                            continue
                        soup2 = BeautifulSoup(r2.text, "html.parser")
                        for a2 in soup2.find_all("a", href=True):
                            href2 = a2["href"]
                            if not href2.endswith(".iso") or "beta" in href2.lower():
                                continue
                            
                            hl = href2.lower()
                            if "amd64" in hl:
                                if target == "desktop" and "live-server" not in hl and "desktop" in hl:
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                                elif target == "server" and ("live-server" in hl or "server" in hl):
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                                elif target in hl or (target == "mate" and "ubuntu-mate" in hl) or (target == "budgie" and "ubuntu-budgie" in hl):
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                    except Exception:
                        continue

        except Exception as e:
            log.warning(f"[Ubuntu] Error scraping {base_url}: {e}")
            raise ScrapeError(self.name, f"could not read the {target} release index ({e})")

        raise ScrapeError(self.name, f"no current amd64 {target} ISO found under {base_url}")
