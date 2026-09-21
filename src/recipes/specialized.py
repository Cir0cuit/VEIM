import re
from typing import List
from bs4 import BeautifulSoup
from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log


class ArtixRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="artix",
            name="Artix Linux",
            category="Rolling Release",
            description="Rolling-release Arch derivative with OpenRC and Runit init systems in place of systemd."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("plasma-openrc", "KDE Plasma (OpenRC)", "Full-featured modern KDE Plasma desktop with OpenRC."),
            FlavorInfo("xfce-openrc", "Xfce Edition (OpenRC)", "Fast and traditional Xfce desktop with OpenRC."),
            FlavorInfo("base-openrc", "Base Edition (OpenRC)", "Minimal console installation image powered by OpenRC."),
            FlavorInfo("base-runit", "Base Edition (Runit)", "Minimal console installation image powered by Runit."),
            FlavorInfo("cinnamon-openrc", "Cinnamon Edition (OpenRC)", "Elegant Cinnamon desktop with OpenRC."),
            FlavorInfo("mate-openrc", "MATE Edition (OpenRC)", "Classic MATE desktop with OpenRC.")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        target = flavor_id.lower()
        mapping = {
            "plasma-openrc": "plasma-openrc",
            "xfce-openrc": "xfce-openrc",
            "base-openrc": "base-openrc",
            "base-runit": "base-runit",
            "cinnamon-openrc": "cinnamon-openrc",
            "mate-openrc": "mate-openrc"
        }
        sub = mapping.get(target, "plasma-openrc")

        try:
            r = session.get("https://download.artixlinux.org/iso/", timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                # Every image of this edition the directory holds, newest
                # taken. The first link found is only the newest for as long
                # as the mirror keeps nothing older beside it.
                found = {}
                for a in soup.find_all("a"):
                    h = a.get("href", "")
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
    def __init__(self):
        super().__init__(
            key="sparky",
            name="SparkyLinux",
            category="Lightweight",
            description="Fast, lightweight Debian-based operating system designed for old and modern hardware."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("xfce", "Xfce Edition", "Default balanced and responsive Xfce desktop."),
            FlavorInfo("kde", "KDE Plasma Edition", "Modern, visually rich KDE Plasma desktop."),
            FlavorInfo("lxqt", "LXQt Edition", "Extremely lightweight modern Qt desktop."),
            FlavorInfo("mate", "MATE Edition", "Classic desktop paradigm with traditional panel layout."),
            FlavorInfo("minimalgui", "MinimalGUI (Openbox)", "Barebones graphical desktop with Openbox window manager."),
            FlavorInfo("minimalcli", "MinimalCLI (Console)", "Console-only installation for custom minimal setups.")
        ]

    DOWNLOAD_PAGE = "https://sparkylinux.org/download/stable/"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        if target not in {"xfce", "kde", "lxqt", "mate", "minimalgui", "minimalcli"}:
            target = "xfce"

        session = self.get_session()
        try:
            r = session.get(self.DOWNLOAD_PAGE, timeout=15)
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
    def __init__(self):
        super().__init__(
            key="tails",
            name="Tails",
            category="Security & Pentest",
            description="The Amnesic Incognito Live System — privacy-preserving OS routing all traffic through Tor."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("standard", "Standard ISO Image", "Direct bootable live image configured to protect privacy via Tor.")
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
    def __init__(self):
        super().__init__(
            key="fydeos",
            name="FydeOS",
            category="Popular & Desktop",
            description="Cloud-first ChromeOS fork with Android subsystem and Linux container support."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("iris", "Intel Modern (6th - 14th Gen)", "Optimized for Intel Core processors with Intel HD/UHD and Iris Xe graphics."),
            FlavorInfo("apu", "AMD Graphics & APUs", "Supports AMD discrete or integrated graphics and AMD or Intel CPUs."),
            FlavorInfo("slim", "Intel Slim (Celeron & Pentium)", "Supports Intel Celeron and Pentium Processors (2015-2019).")
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        model = "iris"
        if "apu" in target or "amd" in target:
            model = "apu"
        elif "slim" in target or "celeron" in target:
            model = "slim"

        session = self.get_session()
        try:
            r = session.get(f"https://fydeos.io/download/pc/{'intel-iris' if model == 'iris' else model if model == 'apu' else 'intel-slim'}/", timeout=8)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                for a in soup.find_all("a"):
                    h = a.get("href", "")
                    if "download.fydeos.io" in h and ".zip" in h:
                        fname = h.split("/")[-1]
                        m = re.search(r'v([0-9\.\-A-Z]+)', fname)
                        ver = m.group(1) if m else "Latest"
                        return DownloadInfo(version=ver, url=h, filename=fname)
        except Exception as e:
            log.warning(f"[FydeOS] Scrape error: {e}")

        raise ScrapeError(self.name, f"fydeos.io listed no current {model} image")


class HackerOSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="hackeros",
            name="HackerOS",
            category="Security & Pentest",
            description="Comprehensive penetration testing and ethical hacking distribution built for cybersecurity professionals."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("lts", "LTS Edition (Long Term Support)", "Rock-solid stable base equipped with essential security suites."),
            FlavorInfo("official", "Official Edition", "Latest rolling tools and updated penetration testing frameworks."),
            FlavorInfo("cybersecurity", "Cybersecurity Edition", "Comprehensive security research and digital forensics edition."),
            FlavorInfo("gaming", "Gaming Edition", "Hybrid cybersecurity environment with gaming toolchains."),
            FlavorInfo("nvidia", "NVIDIA Edition", "Pre-configured proprietary NVIDIA drivers for GPU-accelerated hash cracking.")
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
        target = flavor_id.lower()
        for name in self.EDITIONS:
            if name.startswith(target) or target.startswith(name[:5]):
                edition = name
                break
        else:
            edition = "lts"
        folder, marker = self.EDITIONS[edition]

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
            raise ScrapeError(self.name, f"release feed listed no {edition} ISO")

        # Newest version first.
        found.sort(key=lambda f: tuple(int(x) for x in f[1].split(".") if x.isdigit()), reverse=True)
        fname, ver = found[0]
        url = f"https://downloads.sourceforge.net/project/hackeros/{folder}/{fname}"
        return DownloadInfo(version=ver, url=url, filename=fname)


class AlmaLinuxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="almalinux",
            name="AlmaLinux OS",
            category="Popular & Desktop",
            description="1:1 binary compatible Red Hat Enterprise Linux (RHEL) community enterprise operating system."
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("minimal", "Minimal Install", "Compact basic installation containing only core packages for servers and custom setups."),
            FlavorInfo("dvd", "Full DVD", "Complete offline installation repository with all packages and desktop environments."),
            FlavorInfo("boot", "Boot / Netinstall", "Lightweight network boot installer downloading selected packages during install.")
        ]

    REPO_ROOT = "https://repo.almalinux.org/almalinux/"

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        if "dvd" in target:
            f = "dvd"
        elif "boot" in target:
            f = "boot"
        else:
            f = "minimal"

        session = self.get_session()
        # The repo root lists every series (8, 9, 10, plus point releases);
        # discover the newest major rather than pinning one.
        try:
            r = session.get(self.REPO_ROOT, timeout=15)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[AlmaLinux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach repo.almalinux.org ({e})")

        majors = {int(m) for m in re.findall(r'href="(\d+)/"', r.text)}
        if not majors:
            raise ScrapeError(self.name, "repository index advertised no release series")

        major = max(majors)
        iso_dir = f"{self.REPO_ROOT}{major}/isos/x86_64/"
        try:
            listing = session.get(iso_dir, timeout=15)
            listing.raise_for_status()
        except Exception as e:
            log.warning(f"[AlmaLinux] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not list the AlmaLinux {major} images ({e})")

        # The point release by name, never the "-latest-" alias beside it:
        # that name and "10-latest" stay the same through every point release,
        # so an image downloaded at 10.2 would read as up to date for good.
        found = re.findall(rf'(AlmaLinux-({major}\.\d+)-x86_64-{f}\.iso)', listing.text)
        if not found:
            raise ScrapeError(self.name, f"no AlmaLinux {major} {f} image listed")
        fname, ver = max(found, key=lambda pair: tuple(int(n) for n in pair[1].split(".")))
        return DownloadInfo(version=ver, url=iso_dir + fname, filename=fname)
