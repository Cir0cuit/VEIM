"""Debian, from the release image tree.

cdimage.debian.org answers HTTP 500 now and then, for a request or two at a
time. Read as an empty listing, that was reported as "no current image", so
the same tree is asked for again on get.debian.org - Debian's own download
redirector, which serves it too - before giving up. Whatever goes wrong is
named in the error, not dressed up as a missing image.

The newest release in the listing is taken by version number; a directory
that is mid-update can carry two.
"""
import re
from typing import Optional, Tuple

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError, hrefs, version_key
from src.core.logger import log

# The same tree, at Debian's two official front doors.
TREES = (
    "https://cdimage.debian.org/debian-cd/",
    "https://get.debian.org/images/release/",
)
NETINST_DIR = "current/amd64/iso-cd/"
LIVE_DIR = "current-live/amd64/iso-hybrid/"


class DebianRecipe(DistroRecipe):
    key = "debian"
    name = "Debian"
    description = "The Universal Operating System: legendary rock-solid stability."

    FLAVORS = [
        FlavorInfo("netinst", "Netinst (Network Installer)"),
        FlavorInfo("gnome", "Live GNOME"),
        FlavorInfo("kde", "Live KDE Plasma"),
        FlavorInfo("xfce", "Live Xfce"),
        FlavorInfo("cinnamon", "Live Cinnamon"),
        FlavorInfo("mate", "Live MATE"),
        FlavorInfo("lxqt", "Live LXQt"),
        FlavorInfo("lxde", "Live LXDE"),
        FlavorInfo("standard", "Live Standard (Console)")
    ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        target = flavor_id.lower()
        if target == "netinst":
            subdir = NETINST_DIR
            pattern = re.compile(r"debian-(\d+(?:\.\d+)*)-amd64-netinst\.iso")
        else:
            subdir = LIVE_DIR
            pattern = re.compile(rf"debian-live-(\d+(?:\.\d+)*)-amd64-{re.escape(target)}\.iso")

        session = self.get_session()
        reasons = []
        for tree in TREES:
            base_url = tree + subdir
            try:
                resp = session.get(base_url, timeout=20)
                resp.raise_for_status()
            except Exception as e:
                reasons.append(f"{base_url}: {e}")
                log.warning(f"[Debian] Listing not served by {base_url}: {e}")
                continue

            newest: Optional[Tuple[Tuple[int, ...], str, str]] = None
            for href in hrefs(resp.text):
                m = pattern.fullmatch(href)
                if m and (newest is None or version_key(m.group(1)) > newest[0]):
                    newest = (version_key(m.group(1)), m.group(1), href)
            if newest is None:
                reasons.append(f"{base_url}: no {target} image in the listing")
                continue

            _, version, filename = newest
            return DownloadInfo(version=version, url=base_url + filename, filename=filename,
                                sha256=self._sha256(session, base_url, filename))

        raise ScrapeError(self.name, "; ".join(reasons))

    @staticmethod
    def _sha256(session, base_url: str, filename: str) -> str:
        """From the SHA256SUMS beside the image; "" when that cannot be had."""
        try:
            resp = session.get(base_url + "SHA256SUMS", timeout=20)
            resp.raise_for_status()
        except Exception as e:
            log.warning(f"[Debian] No checksum for {filename}: {e}")
            return ""
        for line in resp.text.splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[1].lstrip("*") == filename:
                return parts[0].lower()
        return ""
