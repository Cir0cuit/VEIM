import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class KaliRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="kali",
            name="Kali Linux",
            category="Security & Pentest",
            description="The premier standard in penetration testing and security auditing."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("installer", "Complete Live & Installer", "Standard full live & bare-metal installation image."),
            FlavorInfo("purple", "Kali Purple", "Defensive security architecture, SOC in-a-box & incident response.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()

        mirrors = [
            "https://cdimage.kali.org/current/",
            "https://mirrors.dotsrc.org/kali-images/current/",
            "https://mirror.karneval.cz/pub/linux/kali-images/current/"
        ]

        for base_url in mirrors:
            try:
                r = session.get(base_url, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    for a in soup.find_all("a", href=True):
                        href = a["href"]
                        if href.endswith(".iso") and "amd64" in href:
                            if target == "purple" and "purple" in href:
                                m = re.search(r'kali-linux-([\d\.]+)-', href)
                                v = m.group(1) if m else "Current"
                                return DownloadInfo(version=v, url=base_url + href, filename=href)
                            elif target in ("installer", "live") and "purple" not in href and "netinst" not in href:
                                m = re.search(r'kali-linux-([\d\.]+)-', href)
                                v = m.group(1) if m else "Current"
                                return DownloadInfo(version=v, url=base_url + href, filename=href)
            except Exception as e:
                log.warning(f"[Kali] Mirror {base_url} error: {e}")

        raise ScrapeError(self.name, f"no current {target} image listed on cdimage.kali.org")

class ParrotRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="parrot",
            name="Parrot OS",
            category="Security & Pentest",
            description="Security, privacy, and development-oriented Linux distribution."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("security", "Security Edition", "Complete arsenal for penetration testing and digital forensics."),
            FlavorInfo("home", "Home Edition", "Daily-driver lightweight workstation environment.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        base_url = "https://deb.parrot.sh/parrot/iso/"

        try:
            r = session.get(base_url, timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                versions = []
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip("/")
                    if href and href[0].isdigit():
                        versions.append(href)
                
                versions.sort(key=lambda s: [int(u) for u in s.split(".") if u.isdigit()], reverse=True)
                latest_v = versions[0] if versions else "current"

                target_dir = f"{base_url}{latest_v}/"
                r2 = session.get(target_dir, timeout=10)
                if r2.status_code == 200:
                    soup2 = BeautifulSoup(r2.text, "html.parser")
                    for a in soup2.find_all("a", href=True):
                        href = a["href"]
                        if href.endswith(".iso") and target in href.lower() and "amd64" in href:
                            return DownloadInfo(version=latest_v, url=target_dir + href, filename=href)
        except Exception as e:
            log.warning(f"[Parrot] Error scraping parrot mirror: {e}")

        raise ScrapeError(self.name, f"no current amd64 {target} ISO listed on the Parrot mirror")
