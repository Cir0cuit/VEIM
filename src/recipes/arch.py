from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, version_key
from src.core.logger import log

class ArchRecipe(DistroRecipe):
    key = "arch"
    name = "Arch Linux"
    description = "A lightweight, flexible, and bleeding-edge rolling release distribution."

    FLAVORS = [
        FlavorInfo("standard", "Standard ISO")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://archlinux.org/releng/releases/json/"

        try:
            r = session.get(api_url, timeout=10)
            r.raise_for_status()
            releases = r.json().get("releases", [])
        except Exception as e:
            log.warning(f"[Arch] Failed checking Arch API: {e}")
            raise ScrapeError(self.name, f"could not read the Arch release index ({e})")

        # The newest release by its own version, not the index's
        # "latest_version": where that is missing, the only other "version"
        # in the index is its schema number, and a summary that lags the list
        # names last month's image. A release taken off the mirrors is
        # marked unavailable, and is not on offer.
        available = [rel for rel in releases
                     if rel.get("available") and rel.get("iso_url") and rel.get("version")]
        if not available:
            raise ScrapeError(self.name, "the Arch release index lists no downloadable release")
        rel = max(available, key=lambda rel: version_key(rel["version"]))

        raw_iso = rel["iso_url"]
        iso_url = f"https://geo.mirror.pkgbuild.com{raw_iso}" if raw_iso.startswith("/") else raw_iso
        return DownloadInfo(
            version=rel["version"],
            url=iso_url,
            sha256=rel.get("sha256_sum") or "",
            filename=iso_url.rsplit("/", 1)[-1],
        )
