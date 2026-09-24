import re
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs
from src.core.logger import log

class KaliRecipe(DistroRecipe):
    key = "kali"
    name = "Kali Linux"
    description = "The premier standard in penetration testing and security auditing."

    # flavor -> the part of the image name that says which one it is.
    # The Live image and both "Everything" images are missing on purpose: Kali
    # publishes those by BitTorrent only, and there is no file to fetch.
    IMAGES = {
        "installer": "installer",
        "netinst": "installer-netinst",
        "purple": "installer-purple",
    }

    FLAVORS = [
        FlavorInfo("installer", "Installer"),
        FlavorInfo("netinst", "Network Installer"),
        FlavorInfo("purple", "Kali Purple"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        image = self.IMAGES.get(target)
        if image is None:
            raise ScrapeError(self.name, f"unknown Kali image {flavor_id!r}")

        mirrors = [
            "https://cdimage.kali.org/current/",
            "https://mirrors.dotsrc.org/kali-images/current/",
            "https://mirror.karneval.cz/pub/linux/kali-images/current/"
        ]

        # The whole name. Matching on a word in it served the installer for
        # "live", and would take "installer-everything" for "installer".
        pattern = re.compile(rf'kali-linux-(\d{{4}}\.\d+[a-z]?)-{re.escape(image)}-amd64\.iso')
        for base_url in mirrors:
            try:
                r = session.get(base_url, timeout=10)
                if r.status_code == 200:
                    for href in hrefs(r.text):
                        m = pattern.fullmatch(href)
                        if m:
                            return DownloadInfo(version=m.group(1), url=base_url + href, filename=href)
            except Exception as e:
                log.warning(f"[Kali] Mirror {base_url} error: {e}")

        raise ScrapeError(self.name, f"no current {target} image listed on cdimage.kali.org")

class ParrotRecipe(DistroRecipe):
    key = "parrot"
    name = "Parrot OS"
    description = "Security, privacy, and development-oriented Linux distribution."

    FLAVORS = [
        FlavorInfo("security", "Security Edition"),
        FlavorInfo("home", "Home Edition")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        base_url = "https://deb.parrot.sh/parrot/iso/"

        try:
            r = session.get(base_url, timeout=10)
            if r.status_code == 200:
                versions = []
                for href in hrefs(r.text):
                    href = href.strip("/")
                    if href and href[0].isdigit():
                        versions.append(href)
                
                versions.sort(key=lambda s: [int(u) for u in s.split(".") if u.isdigit()], reverse=True)
                latest_v = versions[0] if versions else "current"

                target_dir = f"{base_url}{latest_v}/"
                r2 = session.get(target_dir, timeout=10)
                if r2.status_code == 200:
                    for href in hrefs(r2.text):
                        if href.endswith(".iso") and target in href.lower() and "amd64" in href:
                            return DownloadInfo(version=latest_v, url=target_dir + href, filename=href)
        except Exception as e:
            log.warning(f"[Parrot] Error scraping parrot mirror: {e}")

        raise ScrapeError(self.name, f"no current amd64 {target} ISO listed on the Parrot mirror")


class CaineRecipe(DistroRecipe):
    key = "caine"
    name = "CAINE"
    description = "Digital forensics live system: mounts every disk read-only until told otherwise."

    PAGE = "https://www.caine-live.net/page5/page5.html"

    FLAVORS = [FlavorInfo("standard", "Live 64-bit")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get(self.PAGE, timeout=20)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[CAINE] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read caine-live.net ({e})")

        # The page keeps every release it ever linked, on several mirrors.
        found = re.findall(r'(https?://[^"\s]+/(caine(\d+\.\d+)\.iso))', r.text)
        if not found:
            raise ScrapeError(self.name, "caine-live.net listed no ISO")
        newest = max((f[2] for f in found), key=lambda v: tuple(int(n) for n in v.split(".")))
        urls = [f for f in found if f[2] == newest]
        # The project's own host first; the others are third-party mirrors.
        url, fname, ver = min(urls, key=lambda f: "caine-live.net" not in f[0])
        return DownloadInfo(version=ver, url=url.replace("http://", "https://", 1), filename=fname)
