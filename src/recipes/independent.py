"""Distributions built from their own tree rather than derived from another.

Void has its own package manager and init; Gentoo builds from source; Slackware
is the oldest surviving distribution.
"""
import re
from typing import List

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log


def _version_key(version: str):
    return tuple(int(p) for p in re.findall(r'\d+', version))


class VoidRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="void",
            name="Void Linux",
            category="Rolling Release",
            description="Independent rolling release with the xbps package manager and runit init.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("base", "Base (glibc)", "Console-only image on the glibc C library."),
            FlavorInfo("xfce", "Xfce (glibc)", "Live desktop image on glibc."),
            FlavorInfo("musl-base", "Base (musl)", "Console-only image on the musl C library."),
            FlavorInfo("musl-xfce", "Xfce (musl)", "Live desktop image on musl."),
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
    def __init__(self):
        super().__init__(
            key="gentoo",
            name="Gentoo",
            category="Rolling Release",
            description="Source-based distribution built and tuned for your own machine.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("minimal", "Minimal Install CD", "Small console-only installation medium."),
            FlavorInfo("livegui", "LiveGUI", "Full graphical live environment, around 4.7 GB."),
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
    def __init__(self):
        super().__init__(
            key="slackware",
            name="Slackware",
            category="Popular & Desktop",
            description="The oldest surviving Linux distribution, kept deliberately simple.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("install-dvd", "Install DVD (64-bit)", "Complete installation medium."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        root = "https://mirrors.slackware.com/slackware/"
        try:
            index = session.get(root, timeout=20)
            index.raise_for_status()
            # 15.0 must rank above 14.2, which a string sort gets wrong.
            versions = sorted(set(re.findall(r'href="slackware64-(\d+\.\d+)/"', index.text)),
                              key=_version_key)
            for ver in reversed(versions):
                listing = session.get(f"{root}slackware-iso/slackware64-{ver}-iso/", timeout=20)
                if listing.status_code != 200:
                    continue
                match = re.search(rf'(slackware64-{re.escape(ver)}-install-dvd\.iso)', listing.text)
                if match:
                    fname = match.group(1)
                    url = f"{root}slackware-iso/slackware64-{ver}-iso/{fname}"
                    return DownloadInfo(version=ver, url=url, filename=fname)
        except Exception as e:
            log.warning(f"[Slackware] Scrape error: {e}")

        raise ScrapeError(self.name, "no current install DVD listed on mirrors.slackware.com")
