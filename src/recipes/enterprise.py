"""Server, virtualisation and high-security platforms.

These are installers for machines rather than desktops to try out, but they are
exactly the images people keep on a Ventoy stick for provisioning work.
"""
import re
from typing import List

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log


def _version_key(version: str):
    return tuple(int(p) for p in re.findall(r'\d+', version))


class RockyLinuxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="rocky",
            name="Rocky Linux",
            category="Popular & Desktop",
            description="Community enterprise OS, binary compatible with Red Hat Enterprise Linux.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("dvd", "DVD", "Full installation medium with a package set included."),
            FlavorInfo("minimal", "Minimal", "Smallest bootable installer."),
            FlavorInfo("boot", "Boot", "Network installer; fetches everything during setup."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        if flavor_id not in ("dvd", "minimal", "boot"):
            raise ScrapeError(self.name, f"unknown Rocky image {flavor_id!r}")

        session = self.get_session()
        root = "https://download.rockylinux.org/pub/rocky/"
        try:
            index = session.get(root, timeout=20)
            index.raise_for_status()
            # The tree carries bare majors ("10") next to point releases
            # ("10.2"); the bare major tracks the newest point release, so
            # prefer it. A string sort would also rank "9.8" above "10".
            majors = sorted({m for m in re.findall(r'href="(\d+)/"', index.text)},
                            key=_version_key)
            for major in reversed(majors):
                listing = session.get(f"{root}{major}/isos/x86_64/", timeout=20)
                if listing.status_code != 200:
                    continue
                match = re.search(
                    rf'(Rocky-{major}[\w.\-]*-x86_64-{flavor_id}\.iso)', listing.text)
                if match:
                    fname = match.group(1)
                    return DownloadInfo(
                        version=major,
                        url=f"{root}{major}/isos/x86_64/{fname}",
                        filename=fname,
                    )
        except Exception as e:
            log.warning(f"[Rocky Linux] Scrape error: {e}")

        raise ScrapeError(self.name, f"no current {flavor_id} image listed on download.rockylinux.org")


class ProxmoxRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="proxmox",
            name="Proxmox VE",
            category="Rescue & Diagnostics",
            description="Bare-metal virtualisation platform with KVM and LXC, managed from a browser.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("installer", "VE Installer", "Bare-metal Proxmox Virtual Environment installer."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        base = "https://enterprise.proxmox.com/iso/"
        try:
            listing = session.get(base, timeout=20)
            listing.raise_for_status()
            found = re.findall(r'(proxmox-ve_(\d+\.\d+-\d+)\.iso)', listing.text)
            if found:
                fname, ver = max(found, key=lambda pair: _version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Proxmox VE] Scrape error: {e}")

        raise ScrapeError(self.name, "no current installer listed on enterprise.proxmox.com")


class QubesRecipe(DistroRecipe):
    def __init__(self):
        super().__init__(
            key="qubes",
            name="Qubes OS",
            category="Security & Pentest",
            description="Security through compartmentalisation: each task runs in its own isolated VM.",
        )

    def get_flavors(self) -> List[FlavorInfo]:
        return [
            FlavorInfo("installer", "Installer", "Full installation image, around 6 GB."),
        ]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        session = self.get_session()
        base = "https://ftp.qubes-os.org/iso/"
        try:
            listing = session.get(base, timeout=25)
            listing.raise_for_status()
            # Release candidates sit in the same directory as finals and must
            # never be served as the current release.
            finals = re.findall(r'(Qubes-R(\d+(?:\.\d+)*)-x86_64\.iso)', listing.text)
            if finals:
                fname, ver = max(finals, key=lambda pair: _version_key(pair[1]))
                return DownloadInfo(version=ver, url=base + fname, filename=fname)
        except Exception as e:
            log.warning(f"[Qubes OS] Scrape error: {e}")

        raise ScrapeError(self.name, "no current stable release listed on ftp.qubes-os.org")
