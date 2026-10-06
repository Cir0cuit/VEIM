"""Distributions built from their own tree rather than derived from another.

Void has its own package manager and init; Gentoo builds from source; Slackware
is the oldest surviving distribution.
"""
import re

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, version_key
from src.core.logger import log


class VoidRecipe(DistroRecipe):
    key = "void"
    name = "Void Linux"
    description = "Independent rolling release with the xbps package manager and runit init."

    FLAVORS = [
        FlavorInfo("base", "Base (glibc)"),
        FlavorInfo("xfce", "Xfce (glibc)"),
        FlavorInfo("musl-base", "Base (musl)"),
        FlavorInfo("musl-xfce", "Xfce (musl)"),
    ]

    _SEGMENT = {
        "base": ("x86_64", "base"),
        "xfce": ("x86_64", "xfce"),
        "musl-base": ("x86_64-musl", "base"),
        "musl-xfce": ("x86_64-musl", "xfce"),
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        segment = self._SEGMENT.get(flavor_id)
        if not segment:
            raise ScrapeError(self.name, f"unknown Void image {flavor_id!r}")
        arch, variant = segment

        session = self.get_session()
        base = "https://repo-default.voidlinux.org/live/current/"
        try:
            listing = session.get(base, timeout=20)
            listing.raise_for_status()
            # Void publishes dated snapshot directories as well as "current",
            # and the newest dated directory is NOT always the complete set -
            # some carry only an enterprise image. "current" is the project's
            # own pointer at the release it supports, so follow that rather
            # than guessing from directory names.
            dates = re.findall(
                rf'void-live-{re.escape(arch)}-(\d{{8}})-{variant}\.iso', listing.text)
            if dates:
                ver = sorted(set(dates))[-1]
                fname = f"void-live-{arch}-{ver}-{variant}.iso"
                return DownloadInfo(version=ver, url=base + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Void] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} live image listed for Void")


class GentooRecipe(DistroRecipe):
    key = "gentoo"
    name = "Gentoo"
    description = "Source-based distribution built and tuned for your own machine."

    FLAVORS = [
        FlavorInfo("minimal", "Minimal Install CD"),
        FlavorInfo("livegui", "LiveGUI"),
    ]

    _POINTER = {
        "minimal": ("latest-install-amd64-minimal.txt", "install-amd64-minimal"),
        "livegui": ("latest-livegui-amd64.txt", "livegui-amd64"),
    }

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        pointer = self._POINTER.get(flavor_id)
        if not pointer:
            raise ScrapeError(self.name, f"unknown Gentoo image {flavor_id!r}")
        pointer_file, prefix = pointer

        session = self.get_session()
        base = "https://distfiles.gentoo.org/releases/amd64/autobuilds/"
        try:
            # Gentoo publishes a pointer file naming the current build, which
            # saves guessing at the dated directory names.
            resp = session.get(base + pointer_file, timeout=20)
            resp.raise_for_status()
            match = re.search(rf'(\S*{re.escape(prefix)}-(\d{{8}}T\d{{6}}Z)\.iso)', resp.text)
            if match:
                relative, stamp = match.group(1), match.group(2)
                fname = relative.split("/")[-1]
                # The pointer lists an ISO size after the path; keep only the path.
                return DownloadInfo(version=stamp[:8], url=base + relative, filename=fname)
        except Exception as e:
            log.warning(f"[Gentoo] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} build listed for Gentoo")


class SlackwareRecipe(DistroRecipe):
    key = "slackware"
    name = "Slackware"
    description = "The oldest surviving Linux distribution, kept deliberately simple."

    FLAVORS = [
        FlavorInfo("install-dvd", "Install DVD (64-bit)"),
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        iso_root = "https://mirrors.slackware.com/slackware/slackware-iso/"
        try:
            # The ISO tree, not the package tree: a release's packages go up
            # before its DVD does, and walking back from a release with no DVD
            # yet reported the previous one as current.
            index = session.get(iso_root, timeout=20)
            index.raise_for_status()
            versions = set(re.findall(r'href="slackware64-(\d+\.\d+)-iso/"', index.text))
            if versions:
                # A 15.10 must rank above 15.9, which a string sort gets wrong.
                ver = max(versions, key=version_key)
                iso_dir = f"{iso_root}slackware64-{ver}-iso/"
                listing = session.get(iso_dir, timeout=20)
                listing.raise_for_status()
                fname = f"slackware64-{ver}-install-dvd.iso"
                if fname in hrefs(listing.text):
                    return DownloadInfo(version=ver, url=iso_dir + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Slackware] Scrape error: {e}")

        raise ScrapeError(self.name, "no current install DVD listed on mirrors.slackware.com")
