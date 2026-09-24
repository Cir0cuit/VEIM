"""Debian-derived distributions that are not Debian or Ubuntu.

MX Linux and antiX are siblings from the same team; Devuan is Debian without
systemd; Q4OS targets older hardware; Grml is a sysadmin live system.
"""
import re

from src.core.recipe_base import (
    DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, sourceforge_rss, version_key)
from src.core.logger import log


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
                fname = f"MX-{ver}_{edition}_x64.iso"
                url = (f"https://downloads.sourceforge.net/project/mx-linux/"
                       f"Final/{edition.split('_')[0]}/MX-{ver}/{fname}")
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
            matches = re.findall(rf'antiX-(\d+(?:\.\d+)*)[\w.]*_x64-{flavor_id}\.iso', resp.text)
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
                newest = sorted(set(found), key=version_key)[-1]
                if best is None or version_key(newest) > version_key(best[1]):
                    best = (codename, newest)
            except Exception:
                continue
        return best

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in {f.id for f in self.FLAVORS}:
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
                        rf'(devuan_{codename.split("_")[1]}_{re.escape(ver)}[\w.]*_amd64_{flavor_id}\.iso)',
                        listing.text)
                    if match:
                        fname = match.group(1)
                        url = f"https://files.devuan.org/{codename}/{directory}/{fname}"
                        return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Devuan] Scrape error: {e}")

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

    _SUFFIX = {"plasma": "", "trinity": "-tde", "instcd": "-instcd"}

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        suffix = self._SUFFIX.get(flavor_id)
        if suffix is None:
            raise ScrapeError(self.name, f"unknown Q4OS image {flavor_id!r}")

        session = self.get_session()
        try:
            feed = sourceforge_rss(session, "q4os", "path=/")
            # Trailing "-testing" builds share the naming scheme and must not be
            # served as the current release.
            pattern = rf'q4os-(\d+(?:\.\d+)*)-x64{re.escape(suffix)}\.r(\d+)\.iso'
            found = re.findall(pattern, feed)
            if found:
                ver, rev = max(found, key=lambda pair: (version_key(pair[0]), int(pair[1])))
                fname = f"q4os-{ver}-x64{suffix}.r{rev}.iso"
                link = re.search(rf'(https://[^\s<>"]*{re.escape(fname)})[^\s<>"]*', feed)
                url = link.group(1) if link else (
                    f"https://downloads.sourceforge.net/project/q4os/{fname}")
                return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Q4OS] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on SourceForge")


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
