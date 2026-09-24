import re
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, table_rows, version_key
from src.core.logger import log

class MintRecipe(DistroRecipe):
    key = "mint"
    name = "Linux Mint"
    description = "Polished, intuitive, and remarkably stable desktop experience."

    FLAVORS = [
        FlavorInfo("cinnamon", "Cinnamon"),
        FlavorInfo("mate", "MATE"),
        FlavorInfo("xfce", "Xfce")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        url = "https://www.linuxmint.com/download_all.php"

        try:
            r = session.get(url, timeout=10)
            r.raise_for_status()

            versions = []
            for tds in table_rows(r.text):
                if tds:
                    v_candidate = tds[0]
                    if re.match(r'^\d+(\.\d+)?$', v_candidate):
                        versions.append(v_candidate)

            versions.sort(key=version_key, reverse=True)
            if versions:
                latest_ver = versions[0]
                filename = f"linuxmint-{latest_ver}-{target}-64bit.iso"
                download_url = f"https://mirrors.edge.kernel.org/linuxmint/stable/{latest_ver}/{filename}"
                return DownloadInfo(version=latest_ver, url=download_url, filename=filename)

        except Exception as e:
            log.warning(f"[Mint] Failed scraping Mint download page: {e}")

        raise ScrapeError(self.name, f"no current {target} ISO listed in the Linux Mint stable tree")
