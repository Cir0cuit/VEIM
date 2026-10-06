import re
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, published_sha256, version_key)
from src.core.logger import log


class BazziteRecipe(DistroRecipe):
    key = "bazzite"
    name = "Bazzite"
    description = "SteamOS alternative built on Fedora Atomic, tailored for PC gaming and handhelds."

    FLAVORS = [
        FlavorInfo("desktop-kde", "Desktop Edition (KDE Plasma)"),
        FlavorInfo("desktop-gnome", "Desktop Edition (GNOME)"),
        FlavorInfo("deck-kde", "Handheld Edition (Steam Deck / Ally)"),
        FlavorInfo("deck-gnome", "Handheld Edition (GNOME)"),
        FlavorInfo("desktop-nvidia", "NVIDIA Desktop (KDE Plasma)"),
        FlavorInfo("desktop-nvidia-open", "NVIDIA Open Desktop (KDE Plasma)"),
        FlavorInfo("desktop-gnome-nvidia", "NVIDIA Desktop (GNOME)"),
        FlavorInfo("desktop-gnome-nvidia-open", "NVIDIA Open Desktop (GNOME)"),
    ]

    _IMAGES = {
        "desktop-kde": "bazzite",
        "desktop-gnome": "bazzite-gnome",
        "deck-kde": "bazzite-deck",
        "deck-gnome": "bazzite-deck-gnome",
        "desktop-nvidia": "bazzite-nvidia",
        "desktop-nvidia-open": "bazzite-nvidia-open",
        "desktop-gnome-nvidia": "bazzite-gnome-nvidia",
        "desktop-gnome-nvidia-open": "bazzite-gnome-nvidia-open",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        image = self._IMAGES.get(flavor_id.lower())
        if not image:
            raise ScrapeError(self.name, f"unknown Bazzite edition {flavor_id!r}")
        # The installers became "<image>-stable-live-amd64.iso" after October
        # 2025. The old "-stable-amd64.iso" files were left in place, frozen
        # but still answering, and this reported them as current for a year.
        upstream = f"{image}-stable-live-amd64.iso"
        url = f"https://download.bazzite.gg/{upstream}"

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
            raise ScrapeError(self.name, f"download.bazzite.gg did not say when {upstream} was built")

        version = built.strftime("%Y%m%d")
        # Saved under a name that carries that date, so a copy on the drive
        # still says which build it is.
        return DownloadInfo(version=version, url=url, filename=f"{image}-stable-live-{version}-amd64.iso",
                            sha256=published_sha256(session, url + "-CHECKSUM", upstream, "Bazzite"))


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

    LATEST = "https://iso.builds.garudalinux.org/iso/latest/garuda/{}/latest.iso"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        if target not in {f.id for f in self.FLAVORS}:
            raise ScrapeError(self.name, f"unknown Garuda edition {flavor_id!r}")

        # Not the newest folder in iso/garuda/<edition>/: the builders upload
        # there ahead of a release, and that offered builds Garuda had not
        # announced (261006 while the release was 260819). latest.iso is the
        # redirect Garuda itself keeps pointed at the release.
        pointer = self.LATEST.format(target)
        try:
            r = session.head(pointer, allow_redirects=False, timeout=15)
        except Exception as e:
            log.warning(f"[Garuda] Could not read {pointer}: {e}")
            raise ScrapeError(self.name, f"could not read Garuda's latest {target} release ({e})")
        location = urljoin(pointer, r.headers.get("Location", ""))
        m = re.search(rf'/{re.escape(target)}/(\d{{6}})/(garuda-{re.escape(target)}-linux-[a-z]+-\1\.iso)$',
                      location)
        if not m:
            raise ScrapeError(self.name, f"Garuda's latest {target} release points at no ISO "
                                         f"(HTTP {r.status_code})")
        version, fname = m.groups()
        return DownloadInfo(version=version, url=location, filename=fname,
                            sha256=published_sha256(session, location + ".sha256", fname, "Garuda"))


class CachyOSRecipe(DistroRecipe):
    key = "cachyos"
    name = "CachyOS"
    description = "Blazing fast Arch-based distribution with x86-64-v3/v4 optimized kernels and packages."

    FLAVORS = [
        FlavorInfo("desktop", "Desktop Edition"),
        FlavorInfo("handheld", "Handheld Edition")
    ]

    PAGE = "https://cachyos.org/download/"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        if target not in ("desktop", "handheld"):
            raise ScrapeError(self.name, f"unknown CachyOS edition {flavor_id!r}")

        # The download page rather than the mirror's folders: a folder is
        # there as soon as a build is uploaded, released or not - the way
        # Garuda's tree came to offer builds nobody had announced.
        session = self.get_session()
        try:
            r = session.get(self.PAGE, timeout=20)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[CachyOS] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read cachyos.org ({e})")

        found = re.findall(rf'(https://[\w.-]+/ISO/{target}/(\d{{6}})/cachyos-{target}-linux-\2\.iso)', r.text)
        if not found:
            raise ScrapeError(self.name, f"cachyos.org links no {target} ISO")
        url, version = max(found, key=lambda f: version_key(f[1]))
        fname = url.rsplit("/", 1)[-1]
        return DownloadInfo(version=version, url=url, filename=fname,
                            sha256=published_sha256(session, url + ".sha256", fname, "CachyOS"))


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
            # the newest build is the latest date on the highest base - by
            # number, or "99" would outrank "100".
            builds = re.findall(
                rf'(Nobara-(\d+)-{re.escape(edition)}-(\d{{4}}-\d{{2}}-\d{{2}})\.iso)', page.text)
            if builds:
                fname, base_ver, date = max(builds, key=lambda b: (int(b[1]), b[2]))
                link = re.search(rf'(https://[^\s"\'<>]*{re.escape(fname)})', page.text)
                if not link:
                    raise ScrapeError(self.name, f"found {fname} but no download link for it")
                return DownloadInfo(version=f"{base_ver} ({date})", url=link.group(1), filename=fname,
                                    sha256=published_sha256(session, link.group(1) + ".sha256sum", fname, "Nobara"))
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
        FlavorInfo("cosmic", "COSMIC"),
        FlavorInfo("niri", "Niri"),
        FlavorInfo("nvidia-kde", "KDE Plasma (NVIDIA)"),
        FlavorInfo("nvidia-gnome", "GNOME (NVIDIA)"),
    ]

    _EDITION = {
        "kde": "KDE",
        "gnome": "GNOME",
        "hyprland": "Hyprland",
        "cosmic": "COSMIC",
        "niri": "Niri",
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
            # The whole name, as iso_identity reads it back: anything after
            # the build date but its counter ("-beta1") is not a release.
            pattern = (rf'(https://[^\s"\'<>]*/PikaOS-[A-Za-z]+-{re.escape(edition)}'
                       rf'-(\d+\.\d+)-amd64-v3-(\d\d\.\d\d\.\d\d)-\d+\.iso)(?![\w.\-])')
            matches = re.findall(pattern, page.text)
            if not edition.startswith("NVIDIA"):
                # "NVIDIA-KDE" also contains "KDE", so a plain KDE or GNOME
                # search would otherwise pick up the NVIDIA image too.
                matches = [m for m in matches if "-NVIDIA-" not in m[0]]
            if matches:
                # By number: as text the codename and release sort wrongly
                # (Nest 4.0 above Lark 5.0, 9.0 above 10.0).
                url, release, build = max(matches, key=lambda m: (
                    version_key(m[1]), version_key(m[2]), version_key(m[0])))
                return DownloadInfo(version=f"{release} ({build})", url=url,
                                    filename=url.split("/")[-1])
        except Exception as e:
            log.warning(f"[PikaOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on pika-os.com")
