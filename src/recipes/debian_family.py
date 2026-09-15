"""Debian-derived distributions that are not Debian or Ubuntu.

MX Linux and antiX are siblings from the same team; Devuan is Debian without
systemd; Q4OS targets older hardware; Grml is a sysadmin live system.
"""
import re
from typing import List

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log


def _sf_rss(session, project: str, path: str, timeout: int = 20) -> str:
    """SourceForge's per-path RSS feed, newest release first."""
    url = f"https://sourceforge.net/projects/{project}/rss?path={path}"
    resp = session.get(url, timeout=timeout, headers={"User-Agent": "curl/8.4.0"})
    resp.raise_for_status()
    return resp.text


def _version_key(version: str):
    """Sort key that orders 10 above 9, which a string sort gets backwards."""
    return tuple(int(p) for p in re.findall(r'\d+', version))


class MXLinuxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="mxlinux",
            name="MX Linux",
            category="Popular & Desktop",
            description="Midweight Debian-based desktop with Xfce, KDE and Fluxbox editions.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("xfce", "Xfce", "The flagship edition; light and conventional."),
            FlavorInfo("xfce-ahs", "Xfce AHS", "Advanced Hardware Support: newer kernel and firmware."),
            FlavorInfo("kde", "KDE Plasma", "Full Plasma desktop."),
            FlavorInfo("fluxbox", "Fluxbox", "Minimal window manager for older machines."),
        ]

    _PATTERNS = {
        "xfce": r'MX-(\d+(?:\.\d+)*)_Xfce_x64\.iso',
        "xfce-ahs": r'MX-(\d+(?:\.\d+)*)_Xfce_ahs_x64\.iso',
        "kde": r'MX-(\d+(?:\.\d+)*)_KDE_x64\.iso',
        "fluxbox": r'MX-(\d+(?:\.\d+)*)_fluxbox_x64\.iso',
    }

    _NAMES = {
        "xfce": "Xfce", "xfce-ahs": "Xfce_ahs", "kde": "KDE", "fluxbox": "fluxbox",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        pattern = self._PATTERNS.get(flavor_id)
        if not pattern:
            raise ScrapeError(self.name, f"unknown MX Linux edition {flavor_id!r}")

        session = self.get_session()
        try:
            feed = _sf_rss(session, "mx-linux", "/Final")
            # The feed carries beta and release-candidate builds alongside the
            # finals; matching the exact final filename shape excludes them.
            versions = sorted(set(re.findall(pattern, feed)), key=_version_key)
            if versions:
                ver = versions[-1]
                fname = f"MX-{ver}_{self._NAMES[flavor_id]}_x64.iso"
                url = (f"https://downloads.sourceforge.net/project/mx-linux/"
                       f"Final/{self._NAMES[flavor_id].split('_')[0]}/MX-{ver}/{fname}")
                # The per-edition folder layout varies, so prefer the direct
                # link the feed itself advertises when one is present.
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                if link:
                    url = link.group(1)
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[MX Linux] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} release listed on SourceForge")


class AntiXRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="antix",
            name="antiX",
            category="Lightweight",
            description="Fast, systemd-free Debian base that runs on very old hardware.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            # antiX 26 publishes only these two for x64; the older base and
            # net images are no longer built.
            FlavorInfo("full", "Full", "Complete desktop with applications included."),
            FlavorInfo("core", "Core", "Command line only; bring your own desktop."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        try:
            # SourceForge blocks the file browser for this project, so the
            # project's own download page is the reliable source.
            resp = session.get("https://antixlinux.com/download/", timeout=20)
            resp.raise_for_status()
            matches = re.findall(rf'antiX-(\d+(?:\.\d+)*)[\w.]*_x64-{flavor_id}\.iso', resp.text)
            if matches:
                ver = sorted(set(matches), key=_version_key)[-1]
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
    def __init__(self):
        super().__init__(
            key="devuan",
            name="Devuan",
            category="Popular & Desktop",
            description="Debian without systemd, using sysvinit, runit or OpenRC.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("desktop-live", "Desktop Live", "Live image with a desktop you can try first."),
            FlavorInfo("netinstall", "Net Install", "Small installer that fetches packages during setup."),
            FlavorInfo("server", "Server", "Installer image without a desktop."),
        ]

    def _current_release(self, session):
        """(codename, version) for the newest release that actually has ISOs.

        Devuan keeps every past codename directory served, so picking the
        alphabetically last name would land on an old release: "jessie" sorts
        after "excalibur". The version inside the filenames is what ranks them.
        """
        index = session.get("https://files.devuan.org/", timeout=20)
        index.raise_for_status()
        codenames = sorted(set(re.findall(r'href="(devuan_[a-z]+)/?"', index.text)))

        best = None
        for codename in codenames:
            try:
                listing = session.get(
                    f"https://files.devuan.org/{codename}/installer-iso/", timeout=15)
                if listing.status_code != 200:
                    continue
                found = re.findall(r'devuan_[a-z]+_(\d+(?:\.\d+)*)_amd64[\w.\-]*\.iso',
                                   listing.text)
                if not found:
                    continue
                newest = sorted(set(found), key=_version_key)[-1]
                if best is None or _version_key(newest) > _version_key(best[1]):
                    best = (codename, newest)
            except Exception:
                continue
        return best

    _SUFFIX = {
        "desktop-live": "desktop-live",
        "netinstall": "netinstall",
        "server": "server",
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffix = self._SUFFIX.get(flavor_id)
        if not suffix:
            raise ScrapeError(self.name, f"unknown Devuan image {flavor_id!r}")

        session = self.get_session()
        try:
            current = self._current_release(session)
            if current:
                codename, ver = current
                for directory in ("installer-iso", "desktop-live"):
                    listing = session.get(
                        f"https://files.devuan.org/{codename}/{directory}/", timeout=20)
                    if listing.status_code != 200:
                        continue
                    match = re.search(
                        rf'(devuan_{codename.split("_")[1]}_{re.escape(ver)}[\w.]*_amd64_{suffix}\.iso)',
                        listing.text)
                    if match:
                        fname = match.group(1)
                        url = f"https://files.devuan.org/{codename}/{directory}/{fname}"
                        return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Devuan] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on files.devuan.org")


class Q4OSRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="q4os",
            name="Q4OS",
            category="Lightweight",
            description="Debian-based desktop for older hardware, with Plasma or Trinity.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("plasma", "KDE Plasma Live", "Live desktop with Plasma."),
            FlavorInfo("trinity", "Trinity Live", "Live desktop with the Trinity (KDE 3) desktop."),
            FlavorInfo("instcd", "Install CD", "Small installer image."),
        ]

    _SUFFIX = {"plasma": "", "trinity": "-tde", "instcd": "-instcd"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffix = self._SUFFIX.get(flavor_id)
        if suffix is None:
            raise ScrapeError(self.name, f"unknown Q4OS image {flavor_id!r}")

        session = self.get_session()
        try:
            feed = _sf_rss(session, "q4os", "/")
            # Trailing "-testing" builds share the naming scheme and must not be
            # served as the current release.
            pattern = rf'q4os-(\d+(?:\.\d+)*)-x64{re.escape(suffix)}\.r(\d+)\.iso'
            found = re.findall(pattern, feed)
            if found:
                ver, rev = max(found, key=lambda pair: (_version_key(pair[0]), int(pair[1])))
                fname = f"q4os-{ver}-x64{suffix}.r{rev}.iso"
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                url = link.group(1) if link else (
                    f"https://downloads.sourceforge.net/project/q4os/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Q4OS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on SourceForge")


class GrmlRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="grml",
            name="Grml",
            category="Rescue & Diagnostics",
            description="Debian-based live system loaded with system administration and rescue tools.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("full", "Full", "Complete toolset, around 1.1 GB."),
            FlavorInfo("small", "Small", "Reduced toolset, around 640 MB."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("full", "small"):
            raise ScrapeError(self.name, f"unknown Grml image {flavor_id!r}")

        session = self.get_session()
        try:
            listing = session.get("https://download.grml.org/", timeout=20)
            listing.raise_for_status()
            # Releases are dated (2026.09), so a plain string sort is correct
            # here and newest-last.
            versions = sorted(set(re.findall(
                rf'grml-{flavor_id}-(\d{{4}}\.\d{{2}})-amd64\.iso', listing.text)))
            if versions:
                ver = versions[-1]
                fname = f"grml-{flavor_id}-{ver}-amd64.iso"
                return DownloadInfo(version=ver,
                                    url=f"https://download.grml.org/{fname}",
                                    filename=fname)
        except Exception as e:
            log.warning(f"[Grml] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on download.grml.org")
