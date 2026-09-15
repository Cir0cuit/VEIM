import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class ClonezillaRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="clonezilla",
            name="Clonezilla",
            category="Rescue & Diagnostics",
            description="Bare-metal partition and disk imaging / cloning tool."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("alternative", "Alternative Stable (Ubuntu Base)", "Newer Linux kernel with broader hardware support."),
            FlavorInfo("stable", "Standard Stable (Debian Base)", "Rock-solid Debian stable base.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        branch = "alternative" if flavor_id.lower() == "alternative" else "stable"
        url = f"https://clonezilla.org/downloads/{branch}/data/CHECKSUMS.TXT"

        try:
            r = session.get(url, timeout=10)
            if r.status_code == 200:
                m = re.search(r'clonezilla-live-([^\s]+)-amd64\.iso', r.text)
                if m:
                    ver = m.group(1)
                    fname = f"clonezilla-live-{ver}-amd64.iso"
                    dl_branch = "clonezilla_live_alternative" if branch == "alternative" else "clonezilla_live_stable"
                    dl_url = f"https://downloads.sourceforge.net/project/clonezilla/{dl_branch}/{ver}/{fname}"
                    return DownloadInfo(version=ver, url=dl_url, filename=fname)
        except Exception as e:
            log.warning(f"[Clonezilla] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {branch} release listed for Clonezilla")

class GPartedRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="gparted",
            name="GParted Live",
            category="Rescue & Diagnostics",
            description="Complete partition manager for resizing, copying, and creating partitions."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Live AMD64", "Standard 64-bit bootable partition editor.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://gparted.org/download.php", timeout=10)
            if r.status_code == 200:
                m = re.search(r'gparted-live-([\d\.\-]+)-amd64\.iso', r.text)
                if m:
                    ver = m.group(1)
                    fname = f"gparted-live-{ver}-amd64.iso"
                    dl_url = f"https://downloads.sourceforge.net/project/gparted/gparted-live-stable/{ver}/{fname}"
                    return DownloadInfo(version=ver, url=dl_url, filename=fname)
        except Exception as e:
            log.warning(f"[GParted] Scrape error: {e}")

        raise ScrapeError(self.name, "no current stable release listed for GParted Live")

class RescuezillaRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="rescuezilla",
            name="Rescuezilla",
            category="Rescue & Diagnostics",
            description="The Swiss Army knife of system recovery with a friendly point-and-click GUI."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard 64-bit", "Full GUI backup and restore environment.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://api.github.com/repos/rescuezilla/rescuezilla/releases/latest"

        try:
            r = session.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "Latest")
                for asset in data.get("assets", []):
                    aname = asset.get("name", "")
                    if aname.endswith(".iso") and "64bit" in aname:
                        return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        except Exception as e:
            log.warning(f"[Rescuezilla] GitHub API error: {e}")

        raise ScrapeError(self.name, "the Rescuezilla release feed listed no 64-bit ISO")

class ShredOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="shredos",
            name="ShredOS",
            category="Rescue & Diagnostics",
            description="Fast, autonomous disk wiping utility supporting DoD 5220.22-M, Gutmann, and Blancco."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard x86-64", "Autonomous wiping system for SATA, NVMe, and USB.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://api.github.com/repos/PartialVolume/shredos.x86_64/releases/latest"

        try:
            r = session.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "Latest")
                for asset in data.get("assets", []):
                    aname = asset.get("name", "")
                    if (aname.endswith(".img") or aname.endswith(".iso")) and "x86-64" in aname:
                        return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        except Exception as e:
            log.warning(f"[ShredOS] GitHub API error: {e}")

        raise ScrapeError(self.name, "the ShredOS release feed listed no x86-64 image")

class NetbootRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="netboot",
            name="netboot.xyz",
            category="Rescue & Diagnostics",
            description="Boot almost any operating system directly over the network via iPXE."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard ISO", "Lightweight ISO loaded with iPXE scripts.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        api_url = "https://api.github.com/repos/netbootxyz/netboot.xyz/releases/latest"

        try:
            r = session.get(api_url, timeout=10)
            if r.status_code == 200:
                data = r.json()
                tag = data.get("tag_name", "Latest")
                for asset in data.get("assets", []):
                    aname = asset.get("name", "")
                    if aname == "netboot.xyz.iso":
                        return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        except Exception as e:
            log.warning(f"[netboot.xyz] GitHub API error: {e}")

        raise ScrapeError(self.name, "the netboot.xyz release feed listed no netboot.xyz.iso asset")


class SystemRescueRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="systemrescue",
            name="SystemRescue",
            category="Rescue & Diagnostics",
            description="Arch-based rescue toolkit for repairing and administering a broken system.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Live AMD64", "Full rescue environment with disk and filesystem tools."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            feed = session.get(
                "https://sourceforge.net/projects/systemrescuecd/rss?path=/sysresccd-x86",
                timeout=25, headers={"User-Agent": "curl/8.4.0"})
            feed.raise_for_status()
            versions = sorted(
                set(re.findall(r'systemrescue-(\d+(?:\.\d+)*)-amd64\.iso', feed.text)),
                key=lambda v: tuple(int(p) for p in v.split(".")))
            if versions:
                ver = versions[-1]
                fname = f"systemrescue-{ver}-amd64.iso"
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed.text)
                url = link.group(1) if link else (
                    "https://downloads.sourceforge.net/project/systemrescuecd/"
                    f"sysresccd-x86/{ver}/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[SystemRescue] Scrape error: {e}")

        raise ScrapeError(self.name, "no current release listed on SourceForge")


class MemtestRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="memtest",
            name="Memtest86+",
            category="Rescue & Diagnostics",
            description="Stand-alone memory tester that boots before any operating system.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("x86_64", "64-bit", "Standard 64-bit bootable image."),
            FlavorInfo("grub", "64-bit (GRUB)", "GRUB-based image for systems the standard one will not boot."),
        ]

    _SUFFIX = {"x86_64": "x86_64", "grub": "x86_64.grub"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffix = self._SUFFIX.get(flavor_id)
        if not suffix:
            raise ScrapeError(self.name, f"unknown Memtest86+ image {flavor_id!r}")

        session = self.get_session()
        try:
            page = session.get("https://www.memtest.org/", timeout=25)
            page.raise_for_status()
            versions = sorted(
                set(re.findall(rf'mt86plus_(\d+(?:\.\d+)*)_{re.escape(suffix)}\.iso\.zip',
                               page.text)),
                key=lambda v: tuple(int(p) for p in v.split(".")))
            if versions:
                ver = versions[-1]
                zip_name = f"mt86plus_{ver}_{suffix}.iso.zip"
                # Upstream publishes no plain .iso, and Ventoy cannot boot a .zip,
                # so the downloader unpacks this one.
                return DownloadInfo(
                    version=ver,
                    url=f"https://www.memtest.org/download/v{ver}/{zip_name}",
                    filename=f"memtest86plus-{ver}-{suffix}.iso",
                    archive="zip",
                )
        except Exception as e:
            log.warning(f"[Memtest86+] Scrape error: {e}")

        raise ScrapeError(self.name, "no current release listed on memtest.org")
