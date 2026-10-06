import re
from urllib.parse import urljoin
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, published_sha256, version_key)
from src.core.logger import log


class KaliRecipe(DistroRecipe):
    key = "kali"
    name = "Kali Linux"
    description = "The premier standard in penetration testing and security auditing."

    CURRENT = "https://cdimage.kali.org/current/"

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
        FlavorInfo("netinst", "Net Install"),
        FlavorInfo("purple", "Kali Purple"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        image = self.IMAGES.get(target)
        if image is None:
            raise ScrapeError(self.name, f"unknown Kali image {flavor_id!r}")

        # cdimage.kali.org only. The third-party mirrors this once fell back
        # to sync current/ hours or days later, so with cdimage down on a
        # release day they would have offered the release before as current.
        try:
            r = session.get(self.CURRENT, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Kali] Could not read {self.CURRENT}: {e}")
            raise ScrapeError(self.name, f"could not read cdimage.kali.org ({e})")

        # The whole name. Matching on a word in it served the installer for
        # "live", and would take "installer-everything" for "installer".
        pattern = re.compile(rf'kali-linux-(\d{{4}}\.\d+[a-z]?)-{re.escape(image)}-amd64\.iso')
        found = [m for m in map(pattern.fullmatch, hrefs(r.text)) if m]
        if not found:
            raise ScrapeError(self.name, f"no current {target} image listed on cdimage.kali.org")
        # By number, then a respin ("2026.2a") above the release it replaces.
        newest = max(found, key=lambda m: (version_key(m.group(1)), m.group(1)))
        fname = newest.group(0)
        return DownloadInfo(version=newest.group(1), url=self.CURRENT + fname, filename=fname,
                            sha256=published_sha256(session, self.CURRENT + "SHA256SUMS", fname, "Kali"))

class ParrotRecipe(DistroRecipe):
    key = "parrot"
    name = "Parrot OS"
    description = "Security, privacy, and development-oriented Linux distribution."

    BASE = "https://deb.parrot.sh/parrot/iso/"

    FLAVORS = [
        FlavorInfo("security", "Security Edition"),
        FlavorInfo("home", "Home Edition")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        if target not in ("security", "home"):
            raise ScrapeError(self.name, f"unknown Parrot edition {flavor_id!r}")
        pattern = re.compile(rf'Parrot-{target}-(\d+(?:\.\d+)*)_amd64\.iso')

        try:
            r = session.get(self.BASE, timeout=10)
            r.raise_for_status()
            # Releases ("7.4/") and respins ("5.2-1/"); "latest/" is a label
            # and "caine/" another project.
            folders = [h.strip("/") for h in hrefs(r.text) if re.fullmatch(r'\d+(?:\.\d+)*(?:-\d+)?/?', h)]
            # By number: 7.10 above 7.9, and a respin above its release.
            for folder in sorted(folders, key=version_key, reverse=True):
                listing = session.get(f"{self.BASE}{folder}/", timeout=10)
                listing.raise_for_status()
                names = [h for h in hrefs(listing.text) if h.endswith(".iso")]
                if not names and re.search(r'-\d+$', folder):
                    # A respin of torrents only - 5.2-1/ - says nothing about
                    # which release is current. A release folder without
                    # images (6.3.2/ holds only torrents and hashes) is the
                    # release all the same, and falls through to the refusal.
                    continue
                for href in names:
                    m = pattern.fullmatch(href)
                    if m:
                        # The version the name carries, not the folder's: a
                        # respin's files are named for the release (5.2-1/
                        # lists Parrot-home-5.2_amd64.iso.torrent).
                        url = f"{self.BASE}{folder}/"
                        return DownloadInfo(version=m.group(1), url=url + href, filename=href,
                                            sha256=published_sha256(session, url + "signed-hashes.txt",
                                                                    href, "Parrot"))
                # The newest release has no image of this edition under its
                # usual name, or none yet at all. An older folder's would be stale.
                raise ScrapeError(self.name, f"Parrot {folder} lists no amd64 {target} ISO")
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Parrot] Error scraping parrot mirror: {e}")
            raise ScrapeError(self.name, f"could not read the Parrot mirror ({e})")

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

        # The page keeps every release it ever linked, on several mirrors, some
        # by relative link, and not always with a minor version: caine10.iso
        # and caine11.iso came between caine9.0.iso and caine12.4.iso.
        links = [urljoin(self.PAGE, h) for h in hrefs(r.text)]
        found = []
        for url in links:
            m = re.fullmatch(r'caine(\d+(?:\.\d+)?)\.iso', url.rsplit("/", 1)[-1])
            if m and url.startswith(("http://", "https://")):
                found.append((url, m.group(0), m.group(1)))
        if not found:
            raise ScrapeError(self.name, "caine-live.net listed no ISO")
        newest = max((f[2] for f in found), key=version_key)
        urls = [f for f in found if f[2] == newest]
        # The project's own host first; the others are third-party mirrors.
        url, fname, ver = min(urls, key=lambda f: "caine-live.net" not in f[0])
        sums = [u for u in links if u.rsplit("/", 1)[-1] in (f"{fname}.sha256.txt", f"caine{ver}_sha256.txt")]
        sha256 = published_sha256(session, min(sums, key=lambda u: "caine-live.net" not in u), fname,
                                  "CAINE") if sums else ""
        return DownloadInfo(version=ver, url=url.replace("http://", "https://", 1), filename=fname,
                            sha256=sha256)
