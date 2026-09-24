import re
import time
from typing import List
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, hrefs, sourceforge_rss)
from src.core.logger import log

class PopOSRecipe(DistroRecipe):
    key = "popos"
    name = "Pop!_OS"
    description = "Designed for STEM and creative professionals by System76."

    FLAVORS = [
        FlavorInfo("intel", "Standard (Intel / AMD)"),
        FlavorInfo("nvidia", "NVIDIA Edition")
    ]

    API = "https://api.pop-os.org/builds/{release}/{channel}"

    @staticmethod
    def _releases_to_try(this_year: int) -> List[str]:
        """Release numbers, newest first, back to the oldest one still served.

        Pop!_OS numbers its releases after Ubuntu's, so the candidates are
        known without a list to read them from - and System76 publishes none.
        """
        return [f"{yy}.{month}" for yy in range(this_year % 100, 21, -1) for month in ("10", "04")]

    def _from_api(self, session, channel: str):
        for release in self._releases_to_try(time.gmtime().tm_year):
            r = session.get(self.API.format(release=release, channel=channel), timeout=10)
            if r.status_code != 200 or not r.text.strip():
                continue                      # no such release (yet)
            build = r.json()
            url, number = build.get("url", ""), str(build.get("build", ""))
            if url.endswith(".iso") and number:
                return DownloadInfo(version=f"{build.get('version', release)} (Build {number})",
                                    url=url, filename=url.split("/")[-1],
                                    sha256=build.get("sha_sum", ""))
        return None

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = "nvidia" if flavor_id.lower() == "nvidia" else "intel"

        # The build API, and nothing else. This used to read the download
        # page, whose markup still carries 22.04 links long after 24.04
        # shipped - so a release two years old was served as the current one.
        # Falling back to that page would bring the same answer back.
        try:
            info = self._from_api(session, target)
        except Exception as e:
            log.warning(f"[Pop!_OS] Build API error: {e}")
            raise ScrapeError(self.name, f"could not reach System76's build API ({e})")
        if info:
            return info
        raise ScrapeError(self.name, f"System76's build API listed no {target} ISO")

class KDENeonRecipe(DistroRecipe):
    key = "kde_neon"
    name = "KDE Neon"
    description = "The latest cutting-edge KDE Plasma desktop built on an Ubuntu LTS base."

    FLAVORS = [
        FlavorInfo("user", "User Edition")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://neon.kde.org/download", timeout=10)
            if r.status_code == 200:
                for href in hrefs(r.text):
                    if href.endswith(".iso") and "neon-user-desktop" in href:
                        fname = href.split("/")[-1]
                        m = re.search(r'neon-user-desktop-(\d+-\d+)', fname)
                        ver = m.group(1) if m else "Current"
                        return DownloadInfo(version=ver, url=href, filename=fname)
        except Exception as e:
            log.warning(f"[KDE Neon] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach neon.kde.org ({e})")

        raise ScrapeError(self.name, "neon.kde.org listed no user-edition ISO")

class ZorinRecipe(DistroRecipe):
    key = "zorin"
    name = "Zorin OS"
    description = "Familiar, beautiful, and effortless Linux alternative to Windows and macOS."

    # Zorin's SourceForge project only carries 12.x-16.x; current releases are
    # published on zorin.com behind a mirror list. Lite was discontinued after
    # 17 and Pro is a paid product, so only these two are downloadable.
    DOWNLOAD_PAGE = "https://zorin.com/os/download/"

    FLAVORS = [
        FlavorInfo("core", "Core Edition"),
        FlavorInfo("education", "Education Edition"),
    ]

    def _current_major(self, session) -> str:
        """Discover the newest major release advertised on the download page."""
        r = session.get(self.DOWNLOAD_PAGE, timeout=15)
        r.raise_for_status()
        majors = {int(m) for m in re.findall(r'/os/download/(\d+)/', r.text)}
        if not majors:
            raise ScrapeError(self.name, "download page advertised no release series")
        return str(max(majors))

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower() if flavor_id else "core"
        if target not in {"core", "education"}:
            target = "core"

        try:
            major = self._current_major(session)
            page = f"{self.DOWNLOAD_PAGE}{major}/{target}/"
            r = session.get(page, timeout=15)
            r.raise_for_status()
            isos = re.findall(r'https?://[^"\'\s]+?/Zorin-OS-([\d.]+)-([A-Za-z]+)-64-bit\.iso', r.text)
            urls = re.findall(r'https?://[^"\'\s]+?/Zorin-OS-[\d.]+-[A-Za-z]+-64-bit\.iso', r.text)
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Zorin] scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach zorin.com ({e})")

        if not isos or not urls:
            raise ScrapeError(self.name, f"no {target} ISO listed for series {major}")

        version = isos[0][0]
        url = urls[0]
        return DownloadInfo(version=version, url=url, filename=url.split("/")[-1])


class LinuxLiteRecipe(DistroRecipe):
    key = "linuxlite"
    name = "Linux Lite"
    description = "Ubuntu LTS made easy for people arriving from Windows, light enough for older PCs."

    FLAVORS = [FlavorInfo("standard", "64-bit (Xfce)")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "linux-lite", "limit=100")
        except Exception as e:
            log.warning(f"[Linux Lite] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the SourceForge file list ({e})")

        # Finals only: release candidates ("linux-lite-8.0-rc2-64bit.iso")
        # are published in the same tree.
        found = {}
        for path in re.findall(SOURCEFORGE_PATHS, feed):
            m = re.fullmatch(r'.*/linux-lite-(\d+\.\d+)-64bit\.iso', path)
            if m:
                found[m.group(1)] = path
        if not found:
            raise ScrapeError(self.name, "no released 64-bit ISO listed on SourceForge")

        ver = max(found, key=lambda v: tuple(int(n) for n in v.split(".")))
        path = found[ver]
        return DownloadInfo(version=ver, filename=path.rsplit("/", 1)[-1],
                            url=f"https://downloads.sourceforge.net/project/linux-lite{path}")
