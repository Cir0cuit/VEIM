"""Debian-derived distributions that are not Debian or Ubuntu.

MX Linux and antiX are siblings from the same team; Devuan is Debian without
systemd; Q4OS targets older hardware; Grml is a sysadmin live system.
"""
import re

from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, SOURCEFORGE_PATHS, hrefs, published_sha256,
    sourceforge_rss, version_key)
from src.core.logger import log

PRERELEASE = re.compile(r"[-_.](?:alpha|beta|rc|testing)", re.IGNORECASE)
# SourceForge answers a browser with its download page, not the file.
_CURL = {"User-Agent": "curl/8.4.0"}


class MXLinuxRecipe(DistroRecipe):
    key = "mxlinux"
    name = "MX Linux"
    description = "Midweight Debian-based desktop with Xfce, KDE and Fluxbox editions."

    FLAVORS = [
        FlavorInfo("xfce", "Xfce"),
        FlavorInfo("xfce-ahs", "Xfce AHS"),
        FlavorInfo("kde", "KDE Plasma"),
        FlavorInfo("fluxbox", "Fluxbox"),
    ]

    _NAMES = {
        "xfce": "Xfce", "xfce-ahs": "Xfce_ahs", "kde": "KDE", "fluxbox": "fluxbox",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        edition = self._NAMES.get(flavor_id)
        if not edition:
            raise ScrapeError(self.name, f"unknown MX Linux edition {flavor_id!r}")

        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "mx-linux", "path=/Final")
            # The feed carries beta and release-candidate builds alongside the
            # finals; matching the exact final filename shape excludes them.
            versions = sorted(set(re.findall(rf'MX-(\d+(?:\.\d+)*)_{edition}_x64\.iso', feed)),
                              key=version_key)
            if versions:
                ver = versions[-1]
                # A final named another way (23.x Xfce was MX-23.6_x64.iso)
                # matches nothing above, and the release before it would be
                # served as current for as long as it stays in the feed.
                newer = [path for path in re.findall(SOURCEFORGE_PATHS, feed)
                         for m in [re.search(r"/MX-(\d+(?:\.\d+)*)[^/]*x64[^/]*\.iso$", path)]
                         if m and not PRERELEASE.search(path.rsplit("/", 1)[-1])
                         and version_key(m.group(1)) > version_key(ver)]
                if newer:
                    raise ScrapeError(self.name, f"{newer[0]} is newer than {ver} and not named "
                                                 f"MX-<version>_{edition}_x64.iso")
                fname = f"MX-{ver}_{edition}_x64.iso"
                url = (f"https://downloads.sourceforge.net/project/mx-linux/"
                       f"Final/{edition.split('_')[0]}/MX-{ver}/{fname}")
                # The per-edition folder layout varies, so prefer the direct
                # link the feed itself advertises when one is present.
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                if link:
                    url = link.group(1)
                return DownloadInfo(version=ver, url=url, filename=fname,
                                    sha256=published_sha256(session, url + ".sha256", fname, self.name,
                                                            headers=_CURL))
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[MX Linux] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} release listed on SourceForge")


class AntiXRecipe(DistroRecipe):
    key = "antix"
    name = "antiX"
    description = "Fast, systemd-free Debian base that runs on very old hardware."

    FLAVORS = [
        # antiX 26 publishes only these two for x64; the older base and
        # net images are no longer built.
        FlavorInfo("full", "Full"),
        FlavorInfo("core", "Core"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            # SourceForge blocks the file browser for this project, so the
            # project's own download page is the reliable source.
            resp = session.get("https://antixlinux.com/download/", timeout=20)
            resp.raise_for_status()
            # The whole final name: a suffix after the version is a beta
            # (antiX-27_b1) or another init (antiX-26.1-runit), not this image.
            matches = re.findall(rf'antiX-(\d+(?:\.\d+)*)_x64-{re.escape(flavor_id)}\.iso', resp.text)
            if matches:
                ver = sorted(set(matches), key=version_key)[-1]
                fname = f"antiX-{ver}_x64-{flavor_id}.iso"
                link = re.search(rf'(https://[^\s<>"\']*{re.escape(fname)})', resp.text)
                url = link.group(1) if link else (
                    f"https://downloads.sourceforge.net/project/antix-linux/"
                    f"Final/antiX-{ver}/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[antiX] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on antixlinux.com")


class DevuanRecipe(DistroRecipe):
    key = "devuan"
    name = "Devuan"
    description = "Debian without systemd, using sysvinit, runit or OpenRC."

    FLAVORS = [
        FlavorInfo("desktop-live", "Desktop Live"),
        FlavorInfo("netinstall", "Net Install"),
        FlavorInfo("server", "Server"),
    ]

    def _current_release(self, session):
        """(codename, version) for the newest release that actually has ISOs.

        Devuan keeps every past codename directory served, so picking the
        alphabetically last name would land on an old release: "jessie" sorts
        after "excalibur". The version inside the filenames is what ranks them,
        so every listing has to be read: one that cannot be would let an older
        codename win. Only a 404 - a codename with no installer images - is
        passed over.
        """
        index = session.get("https://files.devuan.org/", timeout=20)
        index.raise_for_status()
        codenames = sorted(set(re.findall(r'href="(devuan_[a-z]+)/?"', index.text)))

        best = None
        for codename in codenames:
            listing = session.get(
                f"https://files.devuan.org/{codename}/installer-iso/", timeout=15)
            if listing.status_code == 404:
                continue
            listing.raise_for_status()
            found = re.findall(r'devuan_[a-z]+_(\d+(?:\.\d+)*)_amd64[\w.\-]*\.iso',
                               listing.text)
            if not found:
                continue
            newest = sorted(set(found), key=version_key)[-1]
            if best is None or version_key(newest) > version_key(best[1]):
                best = (codename, newest)
        return best

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in {f.id for f in self.FLAVORS}:
            raise ScrapeError(self.name, f"unknown Devuan image {flavor_id!r}")

        session = self.get_session()
        try:
            current = self._current_release(session)
            if current:
                codename, ver = current
                fname = f"{codename}_{ver}_amd64_{flavor_id}.iso"
                for directory in ("installer-iso", "desktop-live"):
                    listing = session.get(
                        f"https://files.devuan.org/{codename}/{directory}/", timeout=20)
                    if listing.status_code == 404:
                        continue
                    listing.raise_for_status()
                    if fname in hrefs(listing.text):
                        folder = f"https://files.devuan.org/{codename}/{directory}/"
                        # installer-iso/ has one list for all its images;
                        # desktop-live/ has a .sha256 beside the image.
                        sums = "SHA256SUMS.txt" if directory == "installer-iso" else fname + ".sha256"
                        return DownloadInfo(version=ver, url=folder + fname, filename=fname,
                                            sha256=published_sha256(session, folder + sums, fname, self.name))
        except Exception as e:
            log.warning(f"[Devuan] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read files.devuan.org ({e})")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on files.devuan.org")


class Q4OSRecipe(DistroRecipe):
    key = "q4os"
    name = "Q4OS"
    description = "Debian-based desktop for older hardware, with Plasma or Trinity."

    FLAVORS = [
        FlavorInfo("plasma", "KDE Plasma Live"),
        FlavorInfo("trinity", "Trinity Live"),
        FlavorInfo("instcd", "Install CD"),
    ]

    # 6.x names its Plasma and Trinity images q4os-6.9-x64.r1.iso and
    # q4os-6.9-x64-tde.r1.iso; the 7.0 testing builds say -plasma and -trinity.
    _SUFFIXES = {"plasma": ("", "-plasma"), "trinity": ("-tde", "-trinity"), "instcd": ("-instcd",)}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffixes = self._SUFFIXES.get(flavor_id)
        if suffixes is None:
            raise ScrapeError(self.name, f"unknown Q4OS image {flavor_id!r}")

        session = self.get_session()
        try:
            # /stable only: the project's whole feed also carries /oldstable,
            # /depreciated and /testing, and a release that moved to oldstable
            # went on matching after its successor came out.
            feed = sourceforge_rss(session, "q4os", "path=/stable")
            names = [path.rsplit("/", 1)[-1] for path in re.findall(SOURCEFORGE_PATHS, feed)]
            # The whole name, so a "-testing" build is never one of these.
            pattern = re.compile(r'q4os-(\d+(?:\.\d+)*)-x64(-[a-z]+)?\.r(\d+)\.iso')
            found = [(version_key(m.group(1)), int(m.group(3)), m.group(1), name)
                     for name in names for m in [pattern.fullmatch(name)]
                     if m and (m.group(2) or "") in suffixes]
            if found:
                _, _, ver, fname = max(found)
                # A newer stable image under a name this does not know means
                # the matched one is no longer current.
                newer = [name for name in names
                         for m in [re.fullmatch(r"q4os-(\d+(?:\.\d+)*)-x64\S*\.iso", name)]
                         if m and not PRERELEASE.search(name) and version_key(m.group(1)) > version_key(ver)]
                if newer:
                    raise ScrapeError(self.name, f"stable holds {newer[0]}, newer than {ver} "
                                                 f"and not a {flavor_id} image this knows")
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                url = link.group(1) if link else (
                    f"https://downloads.sourceforge.net/project/q4os/stable/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except ScrapeError:
            raise
        except Exception as e:
            log.warning(f"[Q4OS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on SourceForge")


GRML_DOWNLOAD = "https://grml.org/download/"


class GrmlRecipe(DistroRecipe):
    key = "grml"
    name = "Grml"
    description = "Debian-based live system loaded with system administration and rescue tools."

    FLAVORS = [
        FlavorInfo("full", "Full"),
        FlavorInfo("small", "Small"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("full", "small"):
            raise ScrapeError(self.name, f"unknown Grml image {flavor_id!r}")

        session = self.get_session()
        try:
            # grml.org's own download page links the current release only.
            # download.grml.org redirects to a mirror of its choosing, and a
            # mirror that has not synced a release lists the one before it.
            page = session.get(GRML_DOWNLOAD, timeout=20)
            page.raise_for_status()
        except Exception as e:
            log.warning(f"[Grml] Scrape error: {e}")
            raise ScrapeError(self.name, f"could not read {GRML_DOWNLOAD} ({e})")

        pattern = re.compile(rf'https://download\.grml\.org/'
                             rf'(grml-{flavor_id}-(\d{{4}}\.\d{{2}}(?:\.\d+)*)-amd64\.iso)')
        found = [(version_key(m.group(2)), m.group(2), m.group(1), m.group(0))
                 for href in hrefs(page.text) for m in [pattern.fullmatch(href)] if m]
        if not found:
            raise ScrapeError(self.name, f"no {flavor_id} amd64 image linked on {GRML_DOWNLOAD}")
        _, ver, fname, url = max(found)
        sums = [h for h in hrefs(page.text) if h.endswith(f"/SHA256SUMS-{ver}")]
        return DownloadInfo(version=ver, url=url, filename=fname,
                            sha256=published_sha256(session, sums[0], fname, self.name) if sums else "")
