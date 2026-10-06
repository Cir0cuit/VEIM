import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, hrefs,
    published_sha256,
    sourceforge_rss, version_key)
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
            r.raise_for_status()
        except Exception as e:
            # Not an empty listing: Cloudflare in front of the mirror answers
            # 403 to some networks, and that has to say so.
            log.warning(f"[Artix] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach download.artixlinux.org ({e})")

        # Every image of this edition the directory holds, newest taken. The
        # first link found is only the newest for as long as the mirror keeps
        # nothing older beside it.
        found = {}
        for h in hrefs(r.text):
            parts = h.split("/")
            m = re.fullmatch(rf'artix-{re.escape(sub)}-(\d{{8}})-x86_64\.iso', parts[-1])
            # Only what sits in an /iso/ directory, whichever mirror. The page
            # also links weekly-iso/ and testing-iso/ builds, and those are
            # usually the newest thing on it; naming each one to skip lets the
            # next such directory through.
            if m and (len(parts) == 1 or parts[-2] == "iso"):
                found[m.group(1)] = h
        if not found:
            raise ScrapeError(self.name, f"no current {sub} ISO listed on download.artixlinux.org")
        ver = max(found, key=int)
        h = found[ver]
        url = h if h.startswith("http") else f"https://download.artixlinux.org/iso/{h}"
        fname = h.split("/")[-1]
        sha256 = published_sha256(session, url.rsplit("/", 1)[0] + "/sha256sums", fname, self.name)
        return DownloadInfo(version=ver, url=url, filename=fname, sha256=sha256)


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
        FlavorInfo("minimalcli", "MinimalCLI"),
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

        # The pages link direct ISOs (archive.org) alongside SourceForge
        # checksum/signature files; match the ISO itself and skip the .sig/.txt
        # siblings that share the same stem. Each line has its own version
        # shape (8.4 against 2026.09), so a page that links the other line's
        # image cannot pass it off as this one's.
        ver = r'\d{4}\.\d{2}' if rolling else r'\d{1,2}\.\d+'
        found = re.findall(
            rf'(https?://[^"\'\s<>]*?/(sparkylinux-({ver})-x86_64-{target}\.iso)(?![.\w])[^"\'\s<>]*)', r.text)
        if not found:
            page = "rolling" if rolling else "stable"
            raise ScrapeError(self.name, f"no current {target} ISO listed on the {page} download page")

        # The newest by number, not the first listed: a page that keeps the
        # previous point release beside the new one lists either first. Of the
        # two links to one release, the direct ISO over SourceForge's
        # /download redirect.
        url, fname, version = max(
            found, key=lambda f: (version_key(f[2]), not f[0].endswith("/download")))
        return DownloadInfo(version=version, url=url, filename=fname)


class TailsRecipe(DistroRecipe):
    key = "tails"
    name = "Tails"
    description = "The Amnesic Incognito Live System — privacy-preserving OS routing all traffic through Tor."

    FLAVORS = [
        FlavorInfo("standard", "Standard ISO")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://tails.net/install/download/", timeout=8)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[Tails] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach tails.net ({e})")

        # Every stable image the page links, newest by number: while a release
        # rolls out, or in an upgrade note, the previous one can be listed
        # first. The directory and the file have to name the same release.
        found = [m for m in re.findall(
            r'https://download\.tails\.net/tails/stable/tails-amd64-([\d.]+)/tails-amd64-([\d.]+)\.iso', r.text)
            if m[0] == m[1]]
        if not found:
            raise ScrapeError(self.name, "no current stable release listed on download.tails.net")
        ver = max((m[0] for m in found), key=version_key)
        fname = f"tails-amd64-{ver}.iso"
        url = f"https://download.tails.net/tails/stable/tails-amd64-{ver}/{fname}"
        return DownloadInfo(version=ver, url=url, filename=fname, sha256=self._sha256(session, url))

    LATEST = "https://tails.net/install/v2/Tails/amd64/stable/latest.json"

    def _sha256(self, session, url: str) -> str:
        """The hash Tails publishes for exactly `url`, or "".

        latest.json lists each image of the current release with its URL and
        hash. Matched on the whole URL, which carries the version: if it
        already describes a newer release than the download page, nothing
        matches and the image downloads unverified, as before - never checked
        against another release's hash, which would fail a good download.
        Any trouble reading it costs the check, never the release.
        """
        try:
            r = session.get(self.LATEST, timeout=8)
            r.raise_for_status()
            for inst in r.json().get("installations", []):
                for path in inst.get("installation-paths", []):
                    for target in path.get("target-files", []):
                        sha = str(target.get("sha256", "")).lower()
                        if target.get("url") == url and re.fullmatch(r"[0-9a-f]{64}", sha):
                            return sha
        except Exception as e:
            log.warning(f"[Tails] No checksum from latest.json: {e}")
        return ""


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
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[FydeOS] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach fydeos.io ({e})")

        # Every image the page links, by the version in its name. A link with
        # none ("/latest/FydeOS_for_PC_iris.zip") says nothing a later check
        # could compare, so it is never the answer; and the newest by number,
        # since the page may keep an earlier build for older hardware.
        found = []
        for h in hrefs(r.text):
            fname = h.split("/")[-1]
            # Only what follows the version in a final's name ("-io.bin.zip");
            # "_v24.0-beta-io.bin.zip" is not 24.0.
            m = re.search(r'_v(\d+(?:\.\d+)*(?:-SP\d+)?)(?=-io|\.bin|\.zip)', fname)
            if "download.fydeos.io" in h and fname.endswith(".zip") and m:
                found.append((m.group(1), h, fname))
        if not found:
            raise ScrapeError(self.name, f"fydeos.io listed no {flavor_id} image carrying a version")
        ver, url, fname = max(found, key=lambda f: version_key(f[0]))
        return DownloadInfo(version=ver, url=url, filename=fname)


class HackerOSRecipe(DistroRecipe):
    key = "hackeros"
    name = "HackerOS"
    description = "Comprehensive penetration testing and ethical hacking distribution built for cybersecurity professionals."

    FLAVORS = [
        FlavorInfo("lts", "LTS Edition"),
        FlavorInfo("official", "Official Edition"),
        FlavorInfo("cybersecurity", "Cybersecurity Edition"),
        FlavorInfo("gaming", "Gaming Edition"),
    ]

    # Folder name and the filename marker that identifies each edition. The
    # "official" build carries no marker, so it is matched by elimination.
    #
    # Each edition keeps its own schedule (the project's README): LTS ships
    # with x.0 releases, Gaming with x.3 and x.7, and Cybersecurity follows
    # Debian Stable rather than Testing. So an edition's newest image is its
    # current one even when Official has moved on, and the next build is
    # offered as an update when it lands. NVIDIA is gone: the README calls it
    # a "frozen edition".
    EDITIONS = {
        "official": ("OFFICIAL", ""),
        "cybersecurity": ("CYBERSECURITY", "-Cybersecurity"),
        "gaming": ("GAMING", "-Gaming"),
        "lts": ("LTS", "-LTS"),
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in self.EDITIONS:
            raise ScrapeError(self.name, f"unknown HackerOS edition {flavor_id!r}")
        folder, marker = self.EDITIONS[flavor_id]

        # The edition's own folder feed, which lists the whole folder. The
        # project-wide feed holds only the newest few dozen files, and an
        # edition rebuilt rarely (Gaming) drops out of it.
        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "hackeros", f"path=/{folder}")
        except Exception as e:
            log.warning(f"[HackerOS] RSS error: {e}")
            raise ScrapeError(self.name, f"could not read the HackerOS release feed ({e})")

        # Every image directly in the folder; its subfolders (OFFICIAL/GNOME,
        # OFFICIAL/ARCHIVED) are other desktops or retired builds. Upload names
        # vary in case ("Gnome", "Xfce"), so match without it, and refuse an
        # image whose name does not parse rather than skip it: a renamed newer
        # build skipped leaves the previous one reported as current.
        name = re.compile(rf'HackerOS-V(\d+(?:\.\d+)*){re.escape(marker)}\.iso', re.I)
        found = []
        for path in re.findall(SOURCEFORGE_PATHS, feed):
            parts = path.split("/")
            if len(parts) != 3 or parts[1].upper() != folder or not parts[2].lower().endswith(".iso"):
                continue
            m = name.fullmatch(parts[2])
            if not m:
                raise ScrapeError(self.name, f"cannot tell which release {path} is")
            found.append((m.group(1), parts[2]))
        if not found:
            raise ScrapeError(self.name, f"release feed listed no {flavor_id} ISO")

        ver, fname = max(found, key=lambda f: version_key(f[0]))

        url = f"https://downloads.sourceforge.net/project/hackeros/{folder}/{fname}"
        return DownloadInfo(version=ver, url=url, filename=fname)


class AlmaLinuxRecipe(DistroRecipe):
    key = "almalinux"
    name = "AlmaLinux OS"
    description = "1:1 binary compatible Red Hat Enterprise Linux (RHEL) community enterprise operating system."

    FLAVORS = [
        FlavorInfo("minimal", "Minimal Install"),
        FlavorInfo("dvd", "Full DVD"),
        FlavorInfo("boot", "Boot (Net Install)")
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
