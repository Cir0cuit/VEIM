import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class MintRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="mint",
            name="Linux Mint",
            category="Popular & Desktop",
            description="Polished, intuitive, and remarkably stable desktop experience."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("cinnamon", "Cinnamon", "Flagship, modern, full-featured Cinnamon desktop."),
            FlavorInfo("mate", "MATE", "Traditional, responsive, and lightweight MATE desktop."),
            FlavorInfo("xfce", "Xfce", "Ultra-fast, resource-friendly Xfce desktop.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        url = "https://www.linuxmint.com/download_all.php"

        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

            versions = []
            for tr in soup.find_all("tr"):
                tds = [td.get_text().strip() for td in tr.find_all("td")]
                if tds:
                    v_candidate = tds[0]
                    if re.match(r'^\d+(\.\d+)?$', v_candidate):
                        versions.append(v_candidate)

            def ver_key(v):
                try:
                    return [int(x) for x in v.split(".")]
                except Exception:
                    return [0]

            versions.sort(key=ver_key, reverse=True)
            if versions:
                latest_ver = versions[0]
                filename = f"linuxmint-{latest_ver}-{target}-64bit.iso"
                download_url = f"https://mirrors.edge.kernel.org/linuxmint/stable/{latest_ver}/{filename}"
                
                try:
                    resp = session.head(download_url, timeout=5)
                    if resp.status_code == 200:
                        return DownloadInfo(version=latest_ver, url=download_url, filename=filename)
                except Exception:
                    pass

                return DownloadInfo(version=latest_ver, url=download_url, filename=filename)

        except Exception as e:
            log.warning(f"[Mint] Failed scraping Mint download page: {e}")

        raise ScrapeError(self.name, f"no current {target} ISO listed in the Linux Mint stable tree")
