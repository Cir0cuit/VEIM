"""Fedora, as four catalog entries.

Fedora publishes some forty x86_64 images. One selector holding all of them
would not fit on a screen, and the project does not present them as one list
either: fedoraproject.org sorts them into Editions, Atomic Desktops, Spins and
Labs, and that is the split used here.

All four read the same index, releases.json, which names every image by a
`variant` and `subvariant` and carries its SHA-256.
"""
import re
from typing import Dict, List, NamedTuple

from src.core.recipe_base import DistroRecipe, FlavorInfo, DownloadInfo, ScrapeError
from src.core.logger import log

RELEASES_INDEX = "https://fedoraproject.org/releases.json"


class _Image(NamedTuple):
    subvariant: str         # as releases.json spells it
    name: str
    # Part of the filename, where one subvariant publishes several images
    # (Server ships a DVD and a network installer).
    filename_part: str = ""


class _FedoraFamily(DistroRecipe):
    """One group of Fedora images. Subclasses supply IMAGES: flavor id -> _Image."""

    IMAGES: Dict[str, _Image] = {}

    def get_flavors(self) -> List[FlavorInfo]:
        return [FlavorInfo(fid, image.name) for fid, image in self.IMAGES.items()]

    def fetch_download_info(self, flavor_id: str) -> DownloadInfo:
        image = self.IMAGES.get(flavor_id.lower())
        if image is None:
            raise ScrapeError(self.name, f"unknown image {flavor_id!r}")

        session = self.get_session()
        try:
            r = session.get(RELEASES_INDEX, timeout=15)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[{self.name}] Failed fetching releases.json: {e}")
            raise ScrapeError(self.name, f"could not read Fedora's release index ({e})")

        candidates = []
        for entry in data:
            link = entry.get("link", "")
            if entry.get("arch") != "x86_64" or not link.endswith(".iso"):
                continue
            if str(entry.get("subvariant", "")).lower() != image.subvariant.lower():
                continue
            if image.filename_part and image.filename_part not in link.rsplit("/", 1)[-1]:
                continue
            raw_version = str(entry.get("version", ""))
            if not raw_version.isdigit():
                # Skip Rawhide and branched pre-releases.
                continue
            candidates.append((int(raw_version), entry))

        if not candidates:
            raise ScrapeError(self.name, f"release index lists no x86_64 {image.name} image")

        version, entry = max(candidates, key=lambda c: c[0])
        url = entry["link"]
        filename = url.split("/")[-1]

        # IoT is rebuilt between releases and says so in its name
        # ("Fedora-IoT-ostree-44-20260427.0"). The release number alone would
        # call every one of those rebuilds the same version.
        rebuilt = re.search(rf'-{version}-(\d{{8}}\.\d+)\.', filename)
        shown = f"{version} ({rebuilt.group(1)})" if rebuilt else str(version)

        return DownloadInfo(version=shown, url=url, sha256=entry.get("sha256", ""), filename=filename)


class FedoraRecipe(_FedoraFamily):
    key = "fedora"
    name = "Fedora"
    description = "Innovative, cutting-edge RPM distribution backed by Red Hat. The official editions."

    IMAGES = {
        "workstation": _Image("Workstation", "Workstation (GNOME)"),
        "kde": _Image("KDE", "KDE Plasma Desktop"),
        "server": _Image("Server", "Server (DVD)", "-dvd-"),
        "server-netinst": _Image("Server", "Server (Network Install)", "-netinst-"),
        "iot": _Image("IoT", "IoT"),
        "everything": _Image("Everything", "Everything (Network Install)"),
    }


class FedoraAtomicRecipe(_FedoraFamily):
    key = "fedora_atomic"
    name = "Fedora Atomic Desktops"
    description = "Image-based Fedora desktops: updated as a whole, rolled back as a whole."

    IMAGES = {
        "silverblue": _Image("Silverblue", "Silverblue (GNOME)"),
        "kinoite": _Image("Kinoite", "Kinoite (KDE Plasma)"),
        "sway-atomic": _Image("Sericea", "Sway Atomic"),
        "budgie-atomic": _Image("Onyx", "Budgie Atomic"),
        "cosmic-atomic": _Image("COSMIC-Atomic", "COSMIC Atomic"),
    }


class FedoraSpinsRecipe(_FedoraFamily):
    key = "fedora_spins"
    name = "Fedora Spins"
    description = "Fedora with an alternative desktop environment."

    IMAGES = {
        "xfce": _Image("Xfce", "Xfce"),
        "cinnamon": _Image("Cinnamon", "Cinnamon"),
        "budgie": _Image("Budgie", "Budgie"),
        "cosmic": _Image("COSMIC", "COSMIC"),
        "mate": _Image("Mate", "MATE-Compiz"),
        "lxqt": _Image("LXQt", "LXQt"),
        "lxde": _Image("LXDE", "LXDE"),
        "i3": _Image("i3", "i3"),
        "sway": _Image("Sway", "Sway"),
        "miraclewm": _Image("MiracleWM", "Miracle"),
        "kde-mobile": _Image("KDE_Mobile", "KDE Plasma Mobile"),
        "soas": _Image("SoaS", "Sugar on a Stick"),
    }


class FedoraLabsRecipe(_FedoraFamily):
    key = "fedora_labs"
    name = "Fedora Labs"
    description = "Fedora with a curated set of software for one purpose."

    IMAGES = {
        "astronomy": _Image("Astronomy_KDE", "Astronomy"),
        "design-suite": _Image("Design_suite", "Design Suite"),
        "games": _Image("Games", "Games"),
        "jam": _Image("Jam_KDE", "Jam"),
        "python-classroom": _Image("Python_Classroom", "Python Classroom"),
        "robotics": _Image("Robotics", "Robotics Suite"),
        "scientific": _Image("Scientific_KDE", "Scientific"),
        "security": _Image("Security", "Security Lab"),
    }
