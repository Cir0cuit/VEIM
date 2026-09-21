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

    MIRROR = "https://download.opensuse.org/"
    # Where openSUSE itself says which Leap is current. The mirror cannot: it
    # already carries images for the next release while that is still a beta.
    LEAP_PAGE = "https://get.opensuse.org/leap/"

    # flavor -> the part of a Tumbleweed image name that says which one it is
    TUMBLEWEED = {
        "tumbleweed-dvd": "DVD",
        "tumbleweed-kde": "KDE-Live",
        "tumbleweed-gnome": "GNOME-Live",
        "tumbleweed-net": "NET",
    }

    def _listing(self, session, path: str) -> List[str]:
        """File names in a mirror directory, from its JSON index."""
        r = session.get(f"{self.MIRROR}{path}?jsontable", timeout=15)
        r.raise_for_status()
        return [entry["name"] for entry in r.json().get("data", [])]

    def _tumbleweed(self, session, kind: str) -> DownloadInfo:
        """The newest snapshot, by its own name.

        This used to hand out the "-Current.iso" alias under the version
        "Tumbleweed". Both stay the same for ever, so a snapshot downloaded a
        year ago still read as up to date.
        """
        found = {}
        for name in self._listing(session, "tumbleweed/iso/"):
            m = re.fullmatch(rf'openSUSE-Tumbleweed-{kind}-x86_64-Snapshot(\d{{8}})-Media\.iso', name)
            if m:
                found[m.group(1)] = name
        if not found:
            raise ScrapeError(self.name, f"no Tumbleweed {kind} snapshot listed on the mirror")
        snapshot = max(found)
        return DownloadInfo(version=snapshot, filename=found[snapshot],
                            url=f"{self.MIRROR}tumbleweed/iso/{found[snapshot]}")

    def _current_leap(self, session) -> str:
        r = session.get(self.LEAP_PAGE, timeout=15)
        r.raise_for_status()
        versions = re.findall(r'leap/(\d+\.\d+)/', r.text)
        if not versions:
            raise ScrapeError(self.name, "get.opensuse.org named no current Leap release")
        # The page links the current release; anything else it mentions
        # (the previous one, a beta) it mentions less.
        return max(set(versions), key=versions.count)

    def _leap(self, session, offline: bool) -> DownloadInfo:
        """The current Leap, in whichever layout that release uses.

        Leap 16 replaced "iso/openSUSE-Leap-15.6-DVD-..." with
        "offline/Leap-16.0-offline-installer-...". The old code knew only the
        first, took 16.0 for a release with no images, and went on serving 15.6.
        """
        version = self._current_leap(session)
        if int(version.split(".")[0]) >= 16:
            kind = "offline" if offline else "online"
            builds = {}
            for name in self._listing(session, f"distribution/leap/{version}/offline/"):
                m = re.fullmatch(rf'Leap-{re.escape(version)}-{kind}-installer-x86_64-Build([\d.]+)\.install\.iso', name)
                if m:
                    builds[m.group(1)] = name
            if builds:
                build = max(builds, key=lambda b: tuple(int(n) for n in b.split(".")))
                return DownloadInfo(
                    version=f"{version} (Build {build})", filename=builds[build],
                    url=f"{self.MIRROR}distribution/leap/{version}/offline/{builds[build]}")
        else:
            fname = f"openSUSE-Leap-{version}-{'DVD' if offline else 'NET'}-x86_64-Current.iso"
            if fname in self._listing(session, f"distribution/leap/{version}/iso/"):
                return DownloadInfo(version=version, filename=fname,
                                    url=f"{self.MIRROR}distribution/leap/{version}/iso/{fname}")
        raise ScrapeError(self.name, f"Leap {version} is current, but the mirror lists no image for it")

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        session = self.get_session()
        try:
            if target in self.TUMBLEWEED:
                return self._tumbleweed(session, self.TUMBLEWEED[target])
            return self._leap(session, offline=target != "leap-net")
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[openSUSE] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read the openSUSE mirror ({e})")


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
            except Exception as e:
                # Not an answer. Moving on to an older channel here would serve
                # the previous release as current because of one timeout.
                raise ScrapeError(self.name, f"could not reach the {channel} channel ({e})")
            if resp.status_code not in (200, 404):
                raise ScrapeError(self.name, f"the {channel} channel answered HTTP {resp.status_code}")
            if resp.status_code == 404:
                continue                      # that release does not exist yet

            # "latest-..." redirects to the build it stands for, e.g.
            # nixos-minimal-26.05.10304.6d663c0533ff-x86_64-linux.iso.
            # Report that build: the alias and the bare "26.05" stay the same
            # for six months of rebuilt images, so one downloaded in May still
            # read as up to date in October.
            real = resp.url.split("/")[-1]
            m = re.fullmatch(rf'nixos-{variant}-(\d+\.\d+\.\d+)\.[0-9a-f]+-x86_64-linux\.iso', real)
            if not m:
                raise ScrapeError(self.name, f"the {channel} channel resolved to an unexpected file ({real})")
            return DownloadInfo(version=m.group(1), url=resp.url, filename=real)

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
                    # No version in the name means the page has changed. A
                    # number written in here would go on being reported as the
                    # latest release long after it stopped being one.
                    if ver_m:
                        return DownloadInfo(version=ver_m.group(1), url=url, filename=fname)
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
                # Every dated image listed, newest taken - not the first link,
                # which is the newest only while the listing is sorted that way.
                found = {}
                for a in soup.find_all("a"):
                    h = a.get("href", "")
                    m = re.fullmatch(r'TUXEDO-OS-(\d{12})\.iso', h.split("/")[-1])
                    if m:
                        found[m.group(1)] = h
                if found:
                    ver = max(found)
                    return DownloadInfo(version=ver, filename=found[ver].split("/")[-1],
                                        url=f"https://os.tuxedocomputers.com/{found[ver]}")
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
