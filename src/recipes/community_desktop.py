import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class OpenSUSERecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="opensuse",
            name="openSUSE",
            category="Popular & Desktop",
            description="Enterprise-grade Linux distribution with YaST and Snapper Btrfs integration."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("tumbleweed-dvd", "Tumbleweed (Offline DVD)", "Rolling release with cutting-edge software and complete offline installer."),
            FlavorInfo("tumbleweed-kde", "Tumbleweed Live (KDE Plasma)", "Rolling release bootable live desktop powered by KDE Plasma."),
            FlavorInfo("tumbleweed-gnome", "Tumbleweed Live (GNOME)", "Rolling release bootable live desktop powered by GNOME."),
            FlavorInfo("tumbleweed-net", "Tumbleweed (Network Install)", "Minimal network installer downloading packages directly from online repositories."),
            FlavorInfo("leap-dvd", "Leap (Offline DVD)", "Regular release with rock-solid SLE (SUSE Linux Enterprise) core."),
            FlavorInfo("leap-net", "Leap (Network Install)", "Minimal network installer for the current openSUSE Leap.")
        ]

    # Tumbleweed's "-Current.iso" aliases always point at the newest
    # snapshot, so they need no discovery. Leap is versioned - never pin it.
    TUMBLEWEED_ISO = "https://download.opensuse.org/tumbleweed/iso/{name}"
    LEAP_INDEX = "https://ftp.gwdg.de/pub/opensuse/distribution/leap/"

    TUMBLEWEED = {
        "tumbleweed-dvd": "openSUSE-Tumbleweed-DVD-x86_64-Current.iso",
        "tumbleweed-kde": "openSUSE-Tumbleweed-KDE-Live-x86_64-Current.iso",
        "tumbleweed-gnome": "openSUSE-Tumbleweed-GNOME-Live-x86_64-Current.iso",
        "tumbleweed-net": "openSUSE-Tumbleweed-NET-x86_64-Current.iso",
    }

    def _current_leap(self, session, kind: str) -> str:
        """Newest Leap release that actually publishes an ISO.

        The mirror carries directories for releases that are staged but not yet
        populated (16.0 and 16.1 exist while only 15.6 has images), so taking
        the highest-numbered directory hands back a 404. Walk down from the
        newest until one serves the image we want.
        """
        try:
            r = session.get(self.LEAP_INDEX, timeout=15)
            r.raise_for_status()
        except Exception as e:
            raise ScrapeError(self.name, f"could not list Leap releases ({e})")

        versions = sorted(
            set(re.findall(r'href="(\d+\.\d+)/"', r.text)),
            key=lambda v: tuple(int(p) for p in v.split(".")),
            reverse=True,
        )
        if not versions:
            raise ScrapeError(self.name, "Leap mirror index listed no releases")

        for version in versions[:6]:
            url = self._leap_iso_url(version, kind)
            try:
                if session.head(url, allow_redirects=True, timeout=12).status_code == 200:
                    return version
            except Exception as e:
                log.warning(f"[openSUSE] Leap {version} unreachable: {e}")

        raise ScrapeError(
            self.name,
            f"no published Leap release served a {kind} image (newest checked: {versions[0]})",
        )

    @staticmethod
    def _leap_iso_url(version: str, kind: str) -> str:
        fname = f"openSUSE-Leap-{version}-{kind}-x86_64-Current.iso"
        return f"https://download.opensuse.org/distribution/leap/{version}/iso/{fname}"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()

        name = self.TUMBLEWEED.get(target)
        if name:
            return DownloadInfo(
                version="Tumbleweed",
                url=self.TUMBLEWEED_ISO.format(name=name),
                filename=name,
            )

        session = self.get_session()
        kind = "NET" if target == "leap-net" else "DVD"
        leap = self._current_leap(session, kind)
        url = self._leap_iso_url(leap, kind)
        return DownloadInfo(version=leap, url=url, filename=url.split("/")[-1])


class NixOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="nixos",
            name="NixOS",
            category="Popular & Desktop",
            description="Declarative, purely functional operating system built upon the Nix package manager."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("graphical", "Graphical Live Installer (GNOME)", "Full live desktop environment with Calamares graphical installer."),
            FlavorInfo("minimal", "Minimal Console Edition", "Minimal CLI installation image with complete Nix toolchain.")
        ]

    CHANNEL_ROOT = "https://channels.nixos.org/nixos-{channel}/"

    @staticmethod
    def _candidate_channels(today=None):
        """Plausible channel names, newest first.

        NixOS ships two releases a year, YY.05 and YY.11, and channels.nixos.org
        publishes no machine-readable index (the listing is client-side JS).
        Deriving candidates from the calendar keeps this current without pinning
        a release the way the old code pinned 26.05 forever.
        """
        from datetime import date
        today = today or date.today()
        candidates = []
        year, month = today.year, today.month
        # Walk back from the release that would be current today.
        for _ in range(4):
            candidates.append(f"{year % 100:02d}.11" if month > 11 or month >= 11 else f"{year % 100:02d}.05")
            if month >= 11:
                month = 5
            else:
                month = 11
                year -= 1
        # De-duplicate, preserving order.
        seen, ordered = set(), []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                ordered.append(c)
        return ordered

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        variant = "minimal" if "minimal" in target else "graphical"
        fname = f"latest-nixos-{variant}-x86_64-linux.iso"

        session = self.get_session()
        tried = []
        for channel in self._candidate_channels():
            url = self.CHANNEL_ROOT.format(channel=channel) + fname
            tried.append(channel)
            try:
                resp = session.head(url, allow_redirects=True, timeout=12)
                if resp.status_code == 200:
                    return DownloadInfo(version=channel, url=url, filename=fname)
            except Exception as e:
                log.warning(f"[NixOS] Channel {channel} unreachable: {e}")

        raise ScrapeError(self.name, f"no published channel served {fname} (tried {', '.join(tried)})")


class ElementaryRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="elementary",
            name="elementary OS",
            category="Popular & Desktop",
            description="Thoughtfully crafted, privacy-respecting OS with the custom Pantheon desktop environment."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("stable", "Standard 64-bit Edition", "Latest stable release featuring AppCenter and modern Flatpak integration.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://elementary.io/", timeout=8)
            if r.status_code == 200:
                m = re.search(r'//([a-zA-Z0-9\.\-]+/download/[^"\'<>\s]+amd64[^"\'<>\s]+\.iso)', r.text)
                if m:
                    url = f"https://{m.group(1)}"
                    fname = url.split("/")[-1]
                    ver_m = re.search(r'elementaryos-([0-9\.\-]+)', fname)
                    ver = ver_m.group(1) if ver_m else "8.1"
                    return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[elementary OS] Scrape error: {e}")

        raise ScrapeError(self.name, "elementary.io did not hand out a current download link")


class TuxedoRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="tuxedo",
            name="TUXEDO OS",
            category="Popular & Desktop",
            description="Optimized Ubuntu-based distribution with KDE Plasma, PipeWire, and hardware tuning."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard Edition (KDE Plasma)", "Flagship desktop with custom TUXEDO Control Center and kernel enhancements.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://os.tuxedocomputers.com/", timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a"):
                    h = a.get("href", "")
                    if h.endswith(".iso") and "current" not in h.lower():
                        url = f"https://os.tuxedocomputers.com/{h}"
                        m = re.search(r'TUXEDO-OS-([0-9]+)\.iso', h)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=url, filename=h)
        except Exception as e:
            log.warning(f"[TUXEDO OS] Scrape error: {e}")

        raise ScrapeError(self.name, "os.tuxedocomputers.com listed no dated ISO")


class MageiaRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="mageia",
            name="Mageia",
            category="Popular & Desktop",
            description="Community-driven fork of Mandriva featuring the powerful Mageia Control Center."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("classic-dvd", "Classic Installer (DVD)", "Full offline installation DVD with all desktop environments."),
            FlavorInfo("live-plasma", "Live Edition (KDE Plasma)", "Bootable Live session with KDE Plasma."),
            FlavorInfo("live-gnome", "Live Edition (GNOME)", "Bootable Live session with GNOME."),
            FlavorInfo("live-xfce", "Live Edition (Xfce)", "Bootable Live session with lightweight Xfce.")
        ]

    MIRROR = "https://distrib-coffee.ipsl.jussieu.fr/pub/linux/Mageia/iso/"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        session = self.get_session()

        # The mirror lists one directory per release series. Never pin one.
        try:
            r = session.get(self.MIRROR, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Mageia] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach the Mageia mirror ({e})")

        majors = {int(m) for m in re.findall(r'href="(\d+)/"', r.text)}
        if not majors:
            raise ScrapeError(self.name, "Mageia mirror listed no release series")
        major = max(majors)

        suffix = {
            "live-plasma": f"Mageia-{major}-Live-Plasma-x86_64",
            "live-gnome": f"Mageia-{major}-Live-GNOME-x86_64",
            "live-xfce": f"Mageia-{major}-Live-Xfce-x86_64",
        }.get(target, f"Mageia-{major}-x86_64")

        fname = f"{suffix}.iso"
        url = f"{self.MIRROR}{major}/{suffix}/{fname}"
        return DownloadInfo(version=str(major), url=url, filename=fname)
