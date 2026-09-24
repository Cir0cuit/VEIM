import re
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, version_key
from src.core.logger import log

class UbuntuRecipe(DistroRecipe):
    key = "ubuntu"
    name = "Ubuntu"
    description = "The world's most widely used desktop Linux distribution."

    FLAVORS = [
        FlavorInfo("desktop", "Ubuntu Desktop"),
        FlavorInfo("server", "Ubuntu Server"),
        FlavorInfo("kubuntu", "Kubuntu"),
        FlavorInfo("xubuntu", "Xubuntu"),
        FlavorInfo("lubuntu", "Lubuntu"),
        FlavorInfo("mate", "Ubuntu MATE"),
        FlavorInfo("budgie", "Ubuntu Budgie"),
        FlavorInfo("cinnamon", "Ubuntu Cinnamon"),
        FlavorInfo("unity", "Ubuntu Unity"),
        FlavorInfo("studio", "Ubuntu Studio"),
        FlavorInfo("edubuntu", "Edubuntu"),
        FlavorInfo("kylin", "Ubuntu Kylin"),
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
                "budgie": "ubuntu-budgie",
                "cinnamon": "ubuntucinnamon",
                "unity": "ubuntu-unity",
                "studio": "ubuntustudio",
                "edubuntu": "edubuntu",
                "kylin": "ubuntukylin",
            }
            slug = slug_map.get(target, "ubuntu")
            base_url = f"https://cdimage.ubuntu.com/{slug}/releases/"

        try:
            r = session.get(base_url, timeout=10)
            r.raise_for_status()

            versions = []
            for href in hrefs(r.text):
                href = href.strip("/")
                if href and href[0].isdigit() and re.match(r'^\d+\.\d+(\.\d+)?$', href):
                    versions.append(href)

            versions.sort(key=version_key, reverse=True)
            
            for ver in versions[:8]:
                paths_to_test = [f"{base_url}{ver}/", f"{base_url}{ver}/release/"]
                for p in paths_to_test:
                    try:
                        r2 = session.get(p, timeout=6)
                        if r2.status_code != 200:
                            continue
                        for href2 in hrefs(r2.text):
                            if not href2.endswith(".iso") or "beta" in href2.lower():
                                continue
                            
                            hl = href2.lower()
                            if "amd64" in hl:
                                if target == "desktop" and "live-server" not in hl and "desktop" in hl:
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                                elif target == "server" and ("live-server" in hl or "server" in hl):
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                                elif target not in ("desktop", "server") and hl.startswith(f"{slug}-"):
                                    return DownloadInfo(version=ver, url=p + href2, filename=href2)
                    except Exception as e:
                        # Not an answer. Moving on to the next-older release
                        # here would serve it as current because of one timeout.
                        raise ScrapeError(self.name, f"could not read {p} ({e})")

        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Ubuntu] Error scraping {base_url}: {e}")
            raise ScrapeError(self.name, f"could not read the {target} release index ({e})")

        raise ScrapeError(self.name, f"no current amd64 {target} ISO found under {base_url}")
