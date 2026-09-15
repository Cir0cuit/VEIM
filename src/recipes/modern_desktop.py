import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class PopOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="popos",
            name="Pop!_OS",
            category="Popular & Desktop",
            description="Designed for STEM and creative professionals by System76."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("intel", "Standard (Intel / AMD)", "For systems with Intel or AMD Radeon graphics."),
            FlavorInfo("nvidia", "NVIDIA Edition", "Includes proprietary NVIDIA graphics drivers pre-installed.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = "nvidia" if flavor_id.lower() == "nvidia" else "intel"
        
        try:
            r = session.get("https://system76.com/download-pop/", timeout=10)
            if r.status_code == 200:
                matches = re.findall(r"https?://iso\.pop-os\.org/[^\s'\"]+\.iso", r.text)
                for iso_url in matches:
                    if f"/{target}/" in iso_url:
                        fname = iso_url.split("/")[-1]
                        m = re.search(r'pop-os_([\d\.]+)_amd64_[^_]+_(\d+)\.iso', fname)
                        if m:
                            ver = f"{m.group(1)} (Build {m.group(2)})"
                        else:
                            ver = "22.04 LTS"
                        return DownloadInfo(version=ver, url=iso_url, filename=fname)
        except Exception as e:
            log.warning(f"[Pop!_OS] Download-pop scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach System76's download page ({e})")

        raise ScrapeError(
            self.name,
            f"System76's download page listed no {target} ISO in the expected format",
        )

class KDENeonRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="kde_neon",
            name="KDE Neon",
            category="Popular & Desktop",
            description="The latest cutting-edge KDE Plasma desktop built on an Ubuntu LTS base."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("user", "User Edition", "Stable daily edition featuring the latest KDE software releases.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://neon.kde.org/download", timeout=10)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a", href=True):
                    href = a["href"]
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
    def __init__(self):
        super().__init__(
            key="zorin",
            name="Zorin OS",
            category="Popular & Desktop",
            description="Familiar, beautiful, and effortless Linux alternative to Windows and macOS."
        )

    # Zorin's SourceForge project only carries 12.x-16.x; current releases are
    # published on zorin.com behind a mirror list. Lite was discontinued after
    # 17 and Pro is a paid product, so only these two are downloadable.
    DOWNLOAD_PAGE = "https://zorin.com/os/download/"

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("core", "Core Edition", "Standard edition with full desktop features and apps."),
            FlavorInfo("education", "Education Edition", "Bundled with teaching, learning and classroom-management apps."),
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
