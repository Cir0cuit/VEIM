from typing import List
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class ArchRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="arch",
            name="Arch Linux",
            category="Rolling Release",
            description="A lightweight, flexible, and bleeding-edge rolling release distribution."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard ISO", "Complete official Arch installation media.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://archlinux.org/releng/releases/json/"

        try:
            r = session.get(api_url, timeout=10)
            r.raise_for_status()
            data = r.json()
            
            latest_ver = data.get("latest_version") or data.get("version", "Latest")
            releases = data.get("releases", [])
            
            iso_url = ""
            sha256 = ""
            filename = f"archlinux-{latest_ver}-x86_64.iso"
            
            for rel in releases:
                if rel.get("version") == latest_ver:
                    raw_iso = rel.get("iso_url", "")
                    sha256 = rel.get("sha256_sum", "")
                    if raw_iso:
                        iso_url = f"https://geo.mirror.pkgbuild.com{raw_iso}" if raw_iso.startswith("/") else raw_iso
                    break

            if not iso_url:
                iso_url = f"https://geo.mirror.pkgbuild.com/iso/{latest_ver}/{filename}"

            return DownloadInfo(
                version=latest_ver,
                url=iso_url,
                sha256=sha256,
                filename=filename
            )
        except Exception as e:
            log.warning(f"[Arch] Failed checking Arch API: {e}")
            raise ScrapeError(self.name, f"could not read the Arch release index ({e})")
