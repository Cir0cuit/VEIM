import re
from email.utils import parsedate_to_datetime
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs
from src.core.logger import log

class BazziteRecipe(DistroRecipe):
    key = "bazzite"
    name = "Bazzite"
    description = "SteamOS alternative built on Fedora Atomic, tailored for PC gaming and handhelds."

    FLAVORS = [
        FlavorInfo("desktop-kde", "Desktop Edition (KDE Plasma)"),
        FlavorInfo("desktop-gnome", "Desktop Edition (GNOME)"),
        FlavorInfo("deck-kde", "Handheld Edition (Steam Deck / Ally)"),
        FlavorInfo("desktop-nvidia", "NVIDIA Desktop (KDE Plasma)")
    ]

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

        # Bazzite publishes one file per edition under a name that never
        # changes, and this used to report it as version "Stable" - which never
        # changes either, so a rebuilt installer was never noticed. The file's
        # own date is the only version it has.
        session = self.get_session()
        try:
            head = session.head(url, allow_redirects=True, timeout=15)
            head.raise_for_status()
            built = parsedate_to_datetime(head.headers["Last-Modified"])
        except Exception as e:
            log.warning(f"[Bazzite] Could not read the image date: {e}")
            raise ScrapeError(self.name, f"download.bazzite.gg did not say when {fname} was built")

        sha256 = ""
        try:
            checksum = session.get(url + "-CHECKSUM", timeout=15)
            m = re.match(r'([0-9a-f]{64})\s', checksum.text) if checksum.status_code == 200 else None
            sha256 = m.group(1) if m else ""
        except Exception as e:
            log.warning(f"[Bazzite] No checksum for {fname}: {e}")

        return DownloadInfo(version=built.strftime("%Y%m%d"), url=url, filename=fname, sha256=sha256)


class GarudaRecipe(DistroRecipe):
    key = "garuda"
    name = "Garuda Linux"
    description = "Performance-focused Arch-based distribution with automated BTRFS snapshots."

    FLAVORS = [
        FlavorInfo("dr460nized", "Dr460nized (KDE)"),
        FlavorInfo("dr460nized-gaming", "Dr460nized Gaming Edition"),
        FlavorInfo("gnome", "GNOME Edition"),
        FlavorInfo("kde-lite", "KDE Lite"),
        FlavorInfo("xfce", "Xfce Edition"),
        FlavorInfo("cinnamon", "Cinnamon Edition"),
        FlavorInfo("mokka", "Mokka (KDE)"),
        FlavorInfo("hyprland", "Hyprland Edition"),
        FlavorInfo("sway", "Sway Edition"),
        FlavorInfo("i3", "i3 Edition"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        if target not in {f.id for f in self.FLAVORS}:
            raise ScrapeError(self.name, f"unknown Garuda edition {flavor_id!r}")
        base_url = f"https://iso.builds.garudalinux.org/iso/garuda/{target}/"

        try:
            r = session.get(base_url, timeout=8)
            if r.status_code == 200:
                dates = [h.strip("/") for h in hrefs(r.text) if h.strip("/").isdigit()]
                if dates:
                    latest_d = sorted(dates)[-1]
                    r_sub = session.get(f"{base_url}{latest_d}/", timeout=8)
                    if r_sub.status_code == 200:
                        isos = [h for h in hrefs(r_sub.text) if h.endswith(".iso")]
                        if isos:
                            iso_name = isos[0]
                            dl_url = f"{base_url}{latest_d}/{iso_name}"
                            return DownloadInfo(version=latest_d, url=dl_url, filename=iso_name)
        except Exception as e:
            log.warning(f"[Garuda] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {target} ISO listed in the Garuda release tree")


class CachyOSRecipe(DistroRecipe):
    key = "cachyos"
    name = "CachyOS"
    description = "Blazing fast Arch-based distribution with x86-64-v3/v4 optimized kernels and packages."

    FLAVORS = [
        FlavorInfo("desktop", "Desktop Edition"),
        FlavorInfo("handheld", "Handheld Edition")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = "handheld" if "handheld" in flavor_id.lower() else "desktop"
        base_url = f"https://mirror.cachyos.org/ISO/{target}/"

        try:
            r = session.get(base_url, timeout=8)
            if r.status_code == 200:
                subfolders = [h.strip("/") for h in hrefs(r.text) if re.match(r"^\d+/?$", h)]
                if subfolders:
                    latest = sorted(subfolders)[-1]
                    r_sub = session.get(f"{base_url}{latest}/", timeout=8)
                    isos = [h for h in hrefs(r_sub.text) if h.endswith(".iso")]
                    if isos:
                        iso_name = isos[0]
                        dl_url = f"{base_url}{latest}/{iso_name}"
                        return DownloadInfo(version=latest, url=dl_url, filename=iso_name)
        except Exception as e:
            log.warning(f"[CachyOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {target} ISO listed on mirror.cachyos.org")


class NobaraRecipe(DistroRecipe):
    key = "nobara"
    name = "Nobara Project"
    description = "Fedora with the gaming, codec and driver fixes applied out of the box."

    FLAVORS = [
        FlavorInfo("official", "Official (GNOME)"),
        FlavorInfo("kde", "KDE Plasma"),
        FlavorInfo("gnome", "GNOME"),
        FlavorInfo("steam-htpc", "Steam HTPC"),
        FlavorInfo("steam-handheld", "Steam Handheld"),
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
    key = "pikaos"
    name = "PikaOS"
    description = "Debian-based gaming distribution with a performance-tuned kernel."

    FLAVORS = [
        FlavorInfo("kde", "KDE Plasma"),
        FlavorInfo("gnome", "GNOME"),
        FlavorInfo("hyprland", "Hyprland"),
        FlavorInfo("nvidia-kde", "KDE Plasma (NVIDIA)"),
        FlavorInfo("nvidia-gnome", "GNOME (NVIDIA)"),
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
