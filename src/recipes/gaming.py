import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

class BazziteRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="bazzite",
            name="Bazzite",
            category="Gaming & Performance",
            description="SteamOS alternative built on Fedora Atomic, tailored for PC gaming and handhelds."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("desktop-kde", "Desktop Edition (KDE Plasma)", "Flagship desktop gaming experience with KDE Plasma 6."),
            FlavorInfo("desktop-gnome", "Desktop Edition (GNOME)", "Modern GNOME desktop experience tailored for PC gaming."),
            FlavorInfo("deck-kde", "Handheld Edition (Steam Deck / Ally)", "Boots directly into Steam Big Picture / Game Mode."),
            FlavorInfo("desktop-nvidia", "NVIDIA Desktop (KDE Plasma)", "Pre-packaged with proprietary NVIDIA display drivers.")
        ]

    # Bazzite publishes rolling "-stable-" images: the filename never changes
    # and upstream repoints it at each build, so there is no version to resolve
    # and nothing that can go stale.
    USES_CURRENT_ALIAS = True

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        mapping = {
            "desktop-kde": "bazzite",
            "desktop-gnome": "bazzite-gnome",
            "deck-kde": "bazzite-deck",
            "desktop-nvidia": "bazzite-nvidia"
        }
        image_name = mapping.get(flavor_id.lower(), "bazzite")
        fname = f"{image_name}-stable-amd64.iso"
        url = f"https://download.bazzite.gg/{fname}"
        return DownloadInfo(version="Stable", url=url, filename=fname)


class GarudaRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="garuda",
            name="Garuda Linux",
            category="Gaming & Performance",
            description="Performance-focused Arch-based distribution with automated BTRFS snapshots."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("dr460nized", "Dr460nized (KDE)", "Dark, neon, dragon-themed KDE Plasma desktop."),
            FlavorInfo("dr460nized-gaming", "Dr460nized Gaming Edition", "Pre-loaded with Wine, Proton, Lutris, and emulator suites."),
            FlavorInfo("gnome", "GNOME Edition", "Clean and gesture-friendly modern GNOME desktop."),
            FlavorInfo("kde-lite", "KDE Lite", "Stripped-down, ultra-fast minimal KDE Plasma edition."),
            FlavorInfo("xfce", "Xfce Edition", "Lightweight, responsive and classic desktop environment."),
            FlavorInfo("cinnamon", "Cinnamon Edition", "Traditional, elegant desktop layout.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        folder_map = {
            "dr460nized": "dr460nized",
            "dr460nized-gaming": "dr460nized-gaming",
            "gnome": "gnome",
            "kde-lite": "kde-lite",
            "xfce": "xfce",
            "cinnamon": "cinnamon"
        }
        sub = folder_map.get(target, "dr460nized")
        base_url = f"https://iso.builds.garudalinux.org/iso/garuda/{sub}/"

        try:
            r = session.get(base_url, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                dates = [a.get("href", "").strip("/") for a in soup.find_all("a") if a.get("href", "").strip("/").isdigit()]
                if dates:
                    latest_d = sorted(dates)[-1]
                    r_sub = session.get(f"{base_url}{latest_d}/", timeout=8)
                    if r_sub.status_code == 200:
                        soup_sub = BeautifulSoup(r_sub.text, "html.parser")
                        isos = [a.get("href", "") for a in soup_sub.find_all("a") if a.get("href", "").endswith(".iso")]
                        if isos:
                            iso_name = isos[0]
                            dl_url = f"{base_url}{latest_d}/{iso_name}"
                            return DownloadInfo(version=latest_d, url=dl_url, filename=iso_name)
        except Exception as e:
            log.warning(f"[Garuda] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {sub} ISO listed in the Garuda release tree")


class CachyOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="cachyos",
            name="CachyOS",
            category="Gaming & Performance",
            description="Blazing fast Arch-based distribution with x86-64-v3/v4 optimized kernels and packages."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("desktop", "Desktop Edition", "Universal Calamares installer with KDE, GNOME, XFCE, and Hyprland."),
            FlavorInfo("handheld", "Handheld Edition", "Optimized for Steam Deck, ROG Ally, and portable gaming devices.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = "handheld" if "handheld" in flavor_id.lower() else "desktop"
        base_url = f"https://mirror.cachyos.org/ISO/{target}/"

        try:
            r = session.get(base_url, timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                subfolders = [a.get("href", "").strip("/") for a in soup.find_all("a") if re.match(r"^\d+/?$", a.get("href", ""))]
                if subfolders:
                    latest = sorted(subfolders)[-1]
                    r_sub = session.get(f"{base_url}{latest}/", timeout=8)
                    soup_sub = BeautifulSoup(r_sub.text, "html.parser")
                    isos = [a.get("href", "") for a in soup_sub.find_all("a") if a.get("href", "").endswith(".iso")]
                    if isos:
                        iso_name = isos[0]
                        dl_url = f"{base_url}{latest}/{iso_name}"
                        return DownloadInfo(version=latest, url=dl_url, filename=iso_name)
        except Exception as e:
            log.warning(f"[CachyOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {target} ISO listed on mirror.cachyos.org")


class NobaraRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="nobara",
            name="Nobara Project",
            category="Gaming & Performance",
            description="Fedora with the gaming, codec and driver fixes applied out of the box.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("official", "Official (GNOME)", "The maintainer's recommended desktop build."),
            FlavorInfo("kde", "KDE Plasma", "Plasma desktop edition."),
            FlavorInfo("gnome", "GNOME", "Stock GNOME edition."),
            FlavorInfo("steam-htpc", "Steam HTPC", "Boots into Steam Big Picture for a TV."),
            FlavorInfo("steam-handheld", "Steam Handheld", "Tuned for handheld gaming PCs."),
        ]

    _EDITION = {
        "official": "Official",
        "kde": "KDE",
        "gnome": "GNOME",
        "steam-htpc": "Steam-HTPC",
        "steam-handheld": "Steam-Handheld",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        edition = self._EDITION.get(flavor_id)
        if not edition:
            raise ScrapeError(self.name, f"unknown Nobara edition {flavor_id!r}")

        session = self.get_session()
        try:
            page = session.get("https://nobaraproject.org/download-nobara/", timeout=25)
            page.raise_for_status()
            # Filenames carry both the Fedora base version and a build date, so
            # the newest build is the one with the latest date.
            builds = re.findall(
                rf'(Nobara-(\d+)-{re.escape(edition)}-(\d{{4}}-\d{{2}}-\d{{2}})\.iso)', page.text)
            if builds:
                fname, base_ver, date = max(builds, key=lambda b: (b[1], b[2]))
                link = re.search(rf'(https://[^\s"\'<>]*{re.escape(fname)})', page.text)
                if not link:
                    raise ScrapeError(self.name, f"found {fname} but no download link for it")
                return DownloadInfo(version=f"{base_ver} ({date})", url=link.group(1),
                                    filename=fname)
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Nobara] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on nobaraproject.org")


class PikaOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="pikaos",
            name="PikaOS",
            category="Gaming & Performance",
            description="Debian-based gaming distribution with a performance-tuned kernel.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("kde", "KDE Plasma", "Plasma desktop."),
            FlavorInfo("gnome", "GNOME", "GNOME desktop."),
            FlavorInfo("hyprland", "Hyprland", "Tiling Wayland compositor."),
            FlavorInfo("nvidia-kde", "KDE Plasma (NVIDIA)", "Plasma with NVIDIA drivers preinstalled."),
            FlavorInfo("nvidia-gnome", "GNOME (NVIDIA)", "GNOME with NVIDIA drivers preinstalled."),
        ]

    _EDITION = {
        "kde": "KDE",
        "gnome": "GNOME",
        "hyprland": "Hyprland",
        "nvidia-kde": "NVIDIA-KDE",
        "nvidia-gnome": "NVIDIA-GNOME",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        edition = self._EDITION.get(flavor_id)
        if not edition:
            raise ScrapeError(self.name, f"unknown PikaOS edition {flavor_id!r}")

        session = self.get_session()
        try:
            page = session.get("https://pika-os.com/", timeout=25)
            page.raise_for_status()
            # PikaOS-Nest-KDE-4.0-amd64-v3-26.08.20-4.iso
            #                    ^release       ^build date
            pattern = (rf'(https://[^\s"\'<>]*/PikaOS-\w+-{re.escape(edition)}'
                       rf'-(\d+\.\d+)-amd64-[\w.\-]*?(\d\d\.\d\d\.\d\d)[\w.\-]*\.iso)')
            matches = re.findall(pattern, page.text)
            if not edition.startswith("NVIDIA"):
                # "NVIDIA-KDE" also contains "KDE", so a plain KDE or GNOME
                # search would otherwise pick up the NVIDIA image too.
                matches = [m for m in matches if "-NVIDIA-" not in m[0]]
            if matches:
                url, release, build = sorted(set(matches))[-1]
                return DownloadInfo(version=f"{release} ({build})", url=url,
                                    filename=url.split("/")[-1])
        except Exception as e:
            log.warning(f"[PikaOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on pika-os.com")
