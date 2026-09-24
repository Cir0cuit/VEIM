import re
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, version_key
from src.core.logger import log


class ArtixRecipe(DistroRecipe):
    key = "artix"
    name = "Artix Linux"
    description = "Rolling-release Arch derivative with OpenRC and Runit init systems in place of systemd."

    FLAVORS = [
        FlavorInfo("plasma-openrc", "KDE Plasma (OpenRC)"),
        FlavorInfo("xfce-openrc", "Xfce Edition (OpenRC)"),
        FlavorInfo("base-openrc", "Base Edition (OpenRC)"),
        FlavorInfo("base-runit", "Base Edition (Runit)"),
        FlavorInfo("cinnamon-openrc", "Cinnamon Edition (OpenRC)"),
        FlavorInfo("mate-openrc", "MATE Edition (OpenRC)")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        sub = flavor_id.lower()

        try:
            r = session.get("https://download.artixlinux.org/iso/", timeout=8)
            if r.status_code == 200:
                # Every image of this edition the directory holds, newest
                # taken. The first link found is only the newest for as long
                # as the mirror keeps nothing older beside it.
                found = {}
                for h in hrefs(r.text):
                    m = re.fullmatch(rf'artix-{re.escape(sub)}-(\d{{8}})-x86_64\.iso', h.split("/")[-1])
                    # The page links the weekly test images too, and those are
                    # always the newest thing on it.
                    if m and "weekly" not in h:
                        found[m.group(1)] = h
                if found:
                    ver = max(found)
                    h = found[ver]
                    url = h if h.startswith("http") else f"https://download.artixlinux.org/iso/{h}"
                    return DownloadInfo(version=ver, url=url, filename=h.split("/")[-1])
        except Exception as e:
            log.warning(f"[Artix] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {sub} ISO listed on download.artixlinux.org")


class SparkyRecipe(DistroRecipe):
    key = "sparky"
    name = "SparkyLinux"
    description = "Fast, lightweight Debian-based operating system designed for old and modern hardware."

    FLAVORS = [
        FlavorInfo("xfce", "Xfce Edition"),
        FlavorInfo("kde", "KDE Plasma Edition"),
        FlavorInfo("lxqt", "LXQt Edition"),
        FlavorInfo("mate", "MATE Edition"),
        FlavorInfo("minimalgui", "MinimalGUI (Openbox)"),
        FlavorInfo("minimalcli", "MinimalCLI (Console)"),
        FlavorInfo("rolling-xfce", "Rolling: Xfce"),
        FlavorInfo("rolling-kde", "Rolling: KDE Plasma"),
        FlavorInfo("rolling-lxqt", "Rolling: LXQt"),
        FlavorInfo("rolling-mate", "Rolling: MATE"),
        FlavorInfo("rolling-minimalgui", "Rolling: MinimalGUI"),
        FlavorInfo("rolling-minimalcli", "Rolling: MinimalCLI"),
        FlavorInfo("rolling-gameover", "Rolling: GameOver"),
        FlavorInfo("rolling-multimedia", "Rolling: Multimedia"),
        FlavorInfo("rolling-rescue", "Rolling: Rescue"),
    ]

    STABLE_PAGE = "https://sparkylinux.org/download/stable/"
    ROLLING_PAGE = "https://sparkylinux.org/download/rolling/"
    STABLE = {"xfce", "kde", "lxqt", "mate", "minimalgui", "minimalcli"}
    ROLLING = STABLE | {"gameover", "multimedia", "rescue"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        rolling = target.startswith("rolling-")
        target = target[len("rolling-"):] if rolling else target
        if target not in (self.ROLLING if rolling else self.STABLE):
            raise ScrapeError(self.name, f"unknown Sparky edition {flavor_id!r}")

        session = self.get_session()
        try:
            r = session.get(self.ROLLING_PAGE if rolling else self.STABLE_PAGE, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Sparky] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach sparkylinux.org ({e})")

        # The stable page links direct ISOs (archive.org) alongside SourceForge
        # checksum/signature files; match the ISO itself and skip the .sig/.txt
        # siblings that share the same stem.
        pattern = rf'https?://[^"\'\s]*?/sparkylinux-([\d.]+)-x86_64-{target}\.iso(?![.\w])'
        matches = re.findall(pattern, r.text)
        urls = re.findall(rf'https?://[^"\'\s]*?/sparkylinux-[\d.]+-x86_64-{target}\.iso(?![.\w])', r.text)
        if not matches or not urls:
            raise ScrapeError(self.name, f"no current {target} ISO listed on the stable download page")

        url = urls[0]
        return DownloadInfo(version=matches[0], url=url, filename=url.split("/")[-1])


class TailsRecipe(DistroRecipe):
    key = "tails"
    name = "Tails"
    description = "The Amnesic Incognito Live System — privacy-preserving OS routing all traffic through Tor."

    FLAVORS = [
        FlavorInfo("standard", "Standard ISO Image")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://tails.net/install/download/", timeout=8)
            if r.status_code == 200:
                m = re.search(r'https://download\.tails\.net/tails/stable/tails-amd64-([0-9\.]+)/tails-amd64-([0-9\.]+)\.iso', r.text)
                if m:
                    url = m.group(0)
                    ver = m.group(1)
                    fname = f"tails-amd64-{ver}.iso"
                    return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Tails] Scrape error: {e}")

        raise ScrapeError(self.name, "no current stable release listed on download.tails.net")


class FydeOSRecipe(DistroRecipe):
    key = "fydeos"
    name = "FydeOS"
    description = "Cloud-first ChromeOS fork with Android subsystem and Linux container support."

    FLAVORS = [
        FlavorInfo("iris", "Intel Modern (6th - 14th Gen)"),
        FlavorInfo("apu", "AMD Graphics & APUs"),
        FlavorInfo("slim", "Intel Slim (Celeron & Pentium)")
    ]

    # flavor -> its download page
    PAGES = {"iris": "intel-iris", "apu": "apu", "slim": "intel-slim"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get(f"https://fydeos.io/download/pc/{self.PAGES[flavor_id]}/", timeout=8)
            if r.status_code == 200:
                for h in hrefs(r.text):
                    if "download.fydeos.io" in h and ".zip" in h:
                        fname = h.split("/")[-1]
                        m = re.search(r'v([0-9\.\-A-Z]+)', fname)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=h, filename=fname)
        except Exception as e:
            log.warning(f"[FydeOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"fydeos.io listed no current {flavor_id} image")


class HackerOSRecipe(DistroRecipe):
    key = "hackeros"
    name = "HackerOS"
    description = "Comprehensive penetration testing and ethical hacking distribution built for cybersecurity professionals."

    FLAVORS = [
        FlavorInfo("lts", "LTS Edition (Long Term Support)"),
        FlavorInfo("official", "Official Edition"),
        FlavorInfo("cybersecurity", "Cybersecurity Edition"),
        FlavorInfo("gaming", "Gaming Edition"),
        FlavorInfo("nvidia", "NVIDIA Edition")
    ]

    RSS = "https://sourceforge.net/projects/hackeros/rss?path=/"

    # Folder name and the filename marker that identifies each edition. The
    # "official" build carries no marker, so it is matched by elimination.
    EDITIONS = {
        "official": ("OFFICIAL", ""),
        "cybersecurity": ("CYBERSECURITY", "-Cybersecurity"),
        "gaming": ("GAMING", "-Gaming"),
        "nvidia": ("NVIDIA", "-NVIDIA"),
        "lts": ("LTS", "-LTS"),
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in self.EDITIONS:
            raise ScrapeError(self.name, f"unknown HackerOS edition {flavor_id!r}")
        folder, marker = self.EDITIONS[flavor_id]

        session = self.get_session()
        try:
            r = session.get(self.RSS, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[HackerOS] RSS error: {e}")
            raise ScrapeError(self.name, f"could not read the HackerOS release feed ({e})")

        # Feed entries look like .../files/<FOLDER>/HackerOS-V5.0-LTS.iso/download
        pattern = re.compile(
            r'/files/' + re.escape(folder) + r'/(?:[A-Z]+/)?(HackerOS-V([\d.]+)' + re.escape(marker) + r'\.iso)/download'
        )
        found = pattern.findall(r.text)
        if not found:
            raise ScrapeError(self.name, f"release feed listed no {flavor_id} ISO")

        # Newest version first.
        found.sort(key=lambda f: tuple(int(x) for x in f[1].split(".") if x.isdigit()), reverse=True)
        fname, ver = found[0]
        url = f"https://downloads.sourceforge.net/project/hackeros/{folder}/{fname}"
        return DownloadInfo(version=ver, url=url, filename=fname)


class AlmaLinuxRecipe(DistroRecipe):
    key = "almalinux"
    name = "AlmaLinux OS"
    description = "1:1 binary compatible Red Hat Enterprise Linux (RHEL) community enterprise operating system."

    FLAVORS = [
        FlavorInfo("minimal", "Minimal Install"),
        FlavorInfo("dvd", "Full DVD"),
        FlavorInfo("boot", "Boot / Netinstall")
    ]

    ROOT = "https://repo.almalinux.org/almalinux/"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        # The repo root lists every series (8, 9, 10, plus point releases);
        # discover the newest major rather than pinning one.
        try:
            r = session.get(self.ROOT, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[AlmaLinux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach repo.almalinux.org ({e})")

        majors = {int(m) for m in re.findall(r'href="(\d+)/"', r.text)}
        if not majors:
            raise ScrapeError(self.name, "repository index advertised no release series")

        # Only the newest major: when its images are not up yet, an older
        # major's point release is not the current one.
        major = max(majors)
        iso_dir = f"{self.ROOT}{major}/isos/x86_64/"
        try:
            listing = session.get(iso_dir, timeout=15)
            listing.raise_for_status()
        except Exception as e:
            log.warning(f"[AlmaLinux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not list the AlmaLinux {major} images ({e})")

        # The point release by name, never the "-latest-" alias beside it:
        # that name and "10-latest" stay the same through every point release,
        # so an image downloaded at 10.2 would read as up to date for good.
        found = re.findall(rf'(AlmaLinux-({major}\.\d+)-x86_64-{flavor_id}\.iso)', listing.text)
        if not found:
            raise ScrapeError(self.name, f"no AlmaLinux {major} {flavor_id} image listed")
        fname, ver = max(found, key=lambda pair: version_key(pair[1]))
        return DownloadInfo(version=ver, url=iso_dir + fname, filename=fname)
