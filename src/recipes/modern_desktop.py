import re
from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, hrefs, published_sha256,
    sourceforge_rss, version_key)
from src.core.logger import log

class PopOSRecipe(DistroRecipe):
    key = "popos"
    name = "Pop!_OS"
    description = "Designed for STEM and creative professionals by System76."

    FLAVORS = [
        FlavorInfo("intel", "Standard (Intel / AMD)"),
        FlavorInfo("nvidia", "NVIDIA Edition")
    ]

    DOWNLOAD_PAGE = "https://system76.com/pop/download/"
    API = "https://api.pop-os.org/builds/{release}/{channel}"

    def _offered(self, session, flavor: str):
        """(release, channel) the download page's own buttons fetch.

        The page asks the build API for them in a script -
        fetchRelease('24.04', 'generic', 'amd64') - and that, not the API, is
        where System76 says what is released. The API already serves the next
        release's betas under the release's own number (24.04 build 20 was a
        beta, while the page still offered 22.04), and keeps answering for a
        channel the page has dropped: "intel" became "generic" and went on
        handing out a build a year old. The page's leftover 22.04 links are
        plain links, which this does not read.
        """
        r = session.get(self.DOWNLOAD_PAGE, timeout=15)
        r.raise_for_status()
        calls = re.findall(r"fetchRelease\(\s*'(\d+\.\d+)'\s*,\s*'(\w+)'\s*,\s*'amd64'\s*\)", r.text)
        if not calls:
            raise ScrapeError(self.name, "the download page no longer names a release to fetch")
        release = max((rel for rel, _ in calls), key=version_key)
        channels = {ch for rel, ch in calls if rel == release}
        wanted = channels & {"nvidia"} if flavor == "nvidia" else channels - {"nvidia"}
        if len(wanted) != 1:
            raise ScrapeError(self.name, f"the download page offers no single {flavor} image of {release} "
                                         f"(channels: {', '.join(sorted(channels))})")
        return release, wanted.pop()

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        flavor = "nvidia" if flavor_id.lower() == "nvidia" else "intel"
        try:
            release, channel = self._offered(session, flavor)
            r = session.get(self.API.format(release=release, channel=channel), timeout=10)
            r.raise_for_status()
            build = r.json() if r.text.strip() else {}
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Pop!_OS] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read System76's release ({e})")

        url, number = build.get("url", ""), str(build.get("build", ""))
        if not (url.endswith(".iso") and number):
            raise ScrapeError(self.name, f"System76's build API has no {channel} ISO of {release}")
        return DownloadInfo(version=f"{build.get('version', release)} (Build {number})",
                            url=url, filename=url.split("/")[-1], sha256=build.get("sha_sum", ""))

class KDENeonRecipe(DistroRecipe):
    key = "kde_neon"
    name = "KDE Neon"
    description = "The latest cutting-edge KDE Plasma desktop built on an Ubuntu LTS base."

    FLAVORS = [
        FlavorInfo("user", "User Edition")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            r = session.get("https://neon.kde.org/download", timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[KDE Neon] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach neon.kde.org ({e})")

        # Every dated user build linked, newest taken. An undated link
        # ("-current.iso") says nothing a later check could compare.
        found = {}
        for href in hrefs(r.text):
            m = re.fullmatch(r'neon-user-desktop-(\d{8}-\d{4})\.iso', href.split("/")[-1])
            if m:
                found.setdefault(m.group(1), href)
        if not found:
            raise ScrapeError(self.name, "neon.kde.org listed no dated user-edition ISO")
        ver = max(found)
        url, fname = found[ver], found[ver].split("/")[-1]
        # Beside each image: neon-user-desktop-<ver>.sha256sum, no ".iso".
        sha256 = published_sha256(session, url[:-len(".iso")] + ".sha256sum", fname, self.name)
        return DownloadInfo(version=ver, url=url, filename=fname, sha256=sha256)

class ZorinRecipe(DistroRecipe):
    key = "zorin"
    name = "Zorin OS"
    description = "Familiar, beautiful, and effortless Linux alternative to Windows and macOS."

    # Zorin's SourceForge project only carries 12.x-16.x; current releases are
    # published on zorin.com behind a mirror list. Lite was discontinued after
    # 17 and Pro is a paid product, so only these two are downloadable.
    DOWNLOAD_PAGE = "https://zorin.com/os/download/"

    FLAVORS = [
        FlavorInfo("core", "Core Edition"),
        FlavorInfo("education", "Education Edition"),
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
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Zorin] scrape error: {e}")
            raise ScrapeError(self.name, f"could not reach zorin.com ({e})")

        # Every final image the page links, newest by number and then respin -
        # not the first link, which is the newest only while the page lists
        # it first. "-r2" is a respin of the same release (17.3, then
        # 17.3-r1, 17.3-r2); a Beta has the word in its name and no match here.
        found = {}
        for m in re.finditer(rf'https?://[^"\'\s]+?/Zorin-OS-(\d+(?:\.\d+)*)-{target.capitalize()}'
                             rf'-64-bit(?:-r(\d+))?\.iso', r.text):
            found.setdefault((version_key(m.group(1)), int(m.group(2) or 0)), m)
        if not found:
            raise ScrapeError(self.name, f"no {target} ISO listed for series {major}")
        m = found[max(found)]
        version, respin = m.group(1), m.group(2)
        if respin:
            # "18 r3" would number above "18.1" (18, 3 against 18, 1) and hide
            # that update as a downgrade; "18.0 r3" sorts where it belongs.
            version = f"{version if '.' in version else version + '.0'} r{respin}"
        url = m.group(0)
        return DownloadInfo(version=version, url=url, filename=url.split("/")[-1])


class LinuxLiteRecipe(DistroRecipe):
    key = "linuxlite"
    name = "Linux Lite"
    description = "Ubuntu LTS made easy for people arriving from Windows, light enough for older PCs."

    FLAVORS = [FlavorInfo("standard", "64-bit (Xfce)")]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "linux-lite", "limit=100")
        except Exception as e:
            log.warning(f"[Linux Lite] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the SourceForge file list ({e})")

        # Finals only: release candidates ("linux-lite-8.0-rc2-64bit.iso")
        # are published in the same tree.
        found = {}
        for path in re.findall(SOURCEFORGE_PATHS, feed):
            m = re.fullmatch(r'.*/linux-lite-(\d+\.\d+)-64bit\.iso', path)
            if m:
                found[m.group(1)] = path
        if not found:
            raise ScrapeError(self.name, "no released 64-bit ISO listed on SourceForge")

        ver = max(found, key=lambda v: tuple(int(n) for n in v.split(".")))
        path = found[ver]
        url, fname = f"https://downloads.sourceforge.net/project/linux-lite{path}", path.rsplit("/", 1)[-1]
        sha256 = published_sha256(session, url + ".sha256", fname, self.name,
                                  headers={"User-Agent": "curl/8.4.0"})
        return DownloadInfo(version=ver, filename=fname, url=url, sha256=sha256)
