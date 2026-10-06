import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, sha256_in, table_rows, version_key)
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
        except Exception as e:
            log.warning(f"[Mint] Failed scraping Mint download page: {e}")
            raise ScrapeError(self.name, f"could not read {url} ({e})")
        if not versions:
            raise ScrapeError(self.name, f"no current {target} ISO listed in the Linux Mint stable tree")

        latest_ver = versions[0]
        filename = f"linuxmint-{latest_ver}-{target}-64bit.iso"
        folder = f"https://mirrors.edge.kernel.org/linuxmint/stable/{latest_ver}/"
        # The name is built, not read, so the mirror's checksum list is what
        # says the image exists: linuxmint.com can announce a release before
        # the mirror has it, and a release can drop an edition.
        try:
            sums = session.get(folder + "sha256sum.txt", timeout=10)
            sums.raise_for_status()
        except Exception as e:
            raise ScrapeError(self.name, f"could not read the Linux Mint {latest_ver} checksums ({e})")
        sha256 = sha256_in(sums.text, filename)
        if not sha256:
            raise ScrapeError(self.name, f"the mirror lists no {filename}")
        return DownloadInfo(version=latest_ver, url=folder + filename, filename=filename, sha256=sha256)
