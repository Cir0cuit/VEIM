import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, sourceforge_rss,
    version_key)
from src.core.logger import log

class ClonezillaRecipe(DistroRecipe):
    key = "clonezilla"
    name = "Clonezilla"
    description = "Bare-metal partition and disk imaging / cloning tool."

    FLAVORS = [
        FlavorInfo("alternative", "Alternative Stable (Ubuntu Base)"),
        FlavorInfo("stable", "Standard Stable (Debian Base)")
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
    key = "gparted"
    name = "GParted Live"
    description = "Complete partition manager for resizing, copying, and creating partitions."

    FLAVORS = [
        FlavorInfo("standard", "Live AMD64")
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
    key = "rescuezilla"
    name = "Rescuezilla"
    description = "The Swiss Army knife of system recovery with a friendly point-and-click GUI."

    FLAVORS = [
        FlavorInfo("standard", "Standard 64-bit")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        tag, assets = self.github_latest("rescuezilla/rescuezilla")
        for asset in assets:
            aname = asset.get("name", "")
            if aname.endswith(".iso") and "64bit" in aname:
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        raise ScrapeError(self.name, "the Rescuezilla release feed listed no 64-bit ISO")

class ShredOSRecipe(DistroRecipe):
    key = "shredos"
    name = "ShredOS"
    description = "Fast, autonomous disk wiping utility supporting DoD 5220.22-M, Gutmann, and Blancco."

    FLAVORS = [
        FlavorInfo("standard", "Standard x86-64")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        tag, assets = self.github_latest("PartialVolume/shredos.x86_64")
        for asset in assets:
            aname = asset.get("name", "")
            if (aname.endswith(".img") or aname.endswith(".iso")) and "x86-64" in aname:
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        raise ScrapeError(self.name, "the ShredOS release feed listed no x86-64 image")

class NetbootRecipe(DistroRecipe):
    key = "netboot"
    name = "netboot.xyz"
    description = "Boot almost any operating system directly over the network via iPXE."

    FLAVORS = [
        FlavorInfo("standard", "Standard ISO")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        tag, assets = self.github_latest("netbootxyz/netboot.xyz")
        for asset in assets:
            aname = asset.get("name", "")
            if aname == "netboot.xyz.iso":
                return DownloadInfo(version=tag, url=asset.get("browser_download_url"), filename=aname)
        raise ScrapeError(self.name, "the netboot.xyz release feed listed no netboot.xyz.iso asset")


class SystemRescueRecipe(DistroRecipe):
    key = "systemrescue"
    name = "SystemRescue"
    description = "Arch-based rescue toolkit for repairing and administering a broken system."

    FLAVORS = [
        FlavorInfo("standard", "Live AMD64"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "systemrescuecd", "path=/sysresccd-x86")
            versions = sorted(
                set(re.findall(r'systemrescue-(\d+(?:\.\d+)*)-amd64\.iso', feed)),
                key=lambda v: tuple(int(p) for p in v.split(".")))
            if versions:
                ver = versions[-1]
                fname = f"systemrescue-{ver}-amd64.iso"
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                url = link.group(1) if link else (
                    "https://downloads.sourceforge.net/project/systemrescuecd/"
                    f"sysresccd-x86/{ver}/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[SystemRescue] Scrape error: {e}")

        raise ScrapeError(self.name, "no current release listed on SourceForge")


class MemtestRecipe(DistroRecipe):
    key = "memtest"
    name = "Memtest86+"
    description = "Stand-alone memory tester that boots before any operating system."

    FLAVORS = [
        FlavorInfo("x86_64", "64-bit"),
        FlavorInfo("grub", "64-bit (GRUB)"),
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


class SuperGrub2Recipe(DistroRecipe):
    key = "supergrub2"
    name = "Super GRUB2 Disk"
    description = "Boots an installed system whose own bootloader is broken or missing."

    # flavor -> the platform named in the image file
    PLATFORMS = {
        "multiarch": "multiarch",
        "x86_64-efi": "x86_64_efi",
        "i386-pc": "i386_pc",
        "i386-efi": "i386_efi",
    }

    FLAVORS = [
        FlavorInfo("multiarch", "Hybrid (BIOS and UEFI)"),
        FlavorInfo("x86_64-efi", "64-bit UEFI"),
        FlavorInfo("i386-pc", "Legacy BIOS"),
        FlavorInfo("i386-efi", "32-bit UEFI"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        platform = self.PLATFORMS.get(flavor_id)
        if platform is None:
            raise ScrapeError(self.name, f"unknown Super GRUB2 Disk image {flavor_id!r}")
        session = self.get_session()
        try:
            paths = re.findall(SOURCEFORGE_PATHS, sourceforge_rss(session, "supergrub2", "limit=100"))
        except Exception as e:
            log.warning(f"[Super GRUB2 Disk] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the SourceForge file list ({e})")

        # Finals only: betas are published as "2.06s5-beta1" in the same tree.
        found = {}
        for path in paths:
            m = re.fullmatch(rf'.*/(supergrub2-classic-(\d+\.\d+s\d+)-{platform}-CD\.iso)', path)
            if m:
                found[m.group(2)] = path
        if not found:
            raise ScrapeError(self.name, f"no released {platform} image listed on SourceForge")

        ver = max(found, key=version_key)
        path = found[ver]
        return DownloadInfo(version=ver, filename=path.rsplit("/", 1)[-1],
                            url=f"https://downloads.sourceforge.net/project/supergrub2{path}")


class HrmpfRecipe(DistroRecipe):
    key = "hrmpf"
    name = "hrmpf"
    description = "Void Linux-based rescue system: a console packed with repair and recovery tools."

    FLAVORS = [FlavorInfo("standard", "x86_64")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        _, assets = self.github_latest("leahneukirchen/hrmpf")
        for asset in assets:
            m = re.fullmatch(r'hrmpf-x86_64-(\d{8})\.iso', asset.get("name", ""))
            if m:
                return DownloadInfo(version=m.group(1), url=asset.get("browser_download_url"),
                                    filename=asset["name"])
        raise ScrapeError(self.name, "the latest hrmpf release carries no x86_64 ISO")
