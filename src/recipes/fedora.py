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
    description: str
    # Part of the filename, where one subvariant publishes several images
    # (Server ships a DVD and a network installer).
    filename_part: str = ""


class _FedoraFamily(DistroRecipe):
    """One group of Fedora images. Subclasses supply IMAGES: flavor id -> _Image."""

    IMAGES: Dict[str, _Image] = {}

    def get_flavors(self) -> List[FlavorInfo]:
        return [FlavorInfo(fid, image.name, image.description) for fid, image in self.IMAGES.items()]

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

        try:
            size = int(entry.get("size") or 0)
        except (TypeError, ValueError):
            size = 0

        return DownloadInfo(version=shown, url=url, sha256=entry.get("sha256", ""),
                            filename=filename, size_bytes=size)


class FedoraRecipe(_FedoraFamily):
    IMAGES = {
        "workstation": _Image("Workstation", "Workstation (GNOME)", "The flagship desktop, with GNOME."),
        "kde": _Image("KDE", "KDE Plasma Desktop", "The KDE Plasma edition."),
        "server": _Image("Server", "Server (DVD)", "Full offline server installer.", "-dvd-"),
        "server-netinst": _Image("Server", "Server (Network Install)",
                                 "Small server installer that fetches packages during setup.", "-netinst-"),
        "iot": _Image("IoT", "IoT", "Image-based system for edge and embedded devices."),
        "everything": _Image("Everything", "Everything (Network Install)",
                             "Network installer offering every package set Fedora has."),
    }

    def __init__(self):
        super().__init__(
            key="fedora",
            name="Fedora",
            category="Popular & Desktop",
            description="Innovative, cutting-edge RPM distribution backed by Red Hat. The official editions."
        )


class FedoraAtomicRecipe(_FedoraFamily):
    IMAGES = {
        "silverblue": _Image("Silverblue", "Silverblue (GNOME)", "Atomic desktop with GNOME."),
        "kinoite": _Image("Kinoite", "Kinoite (KDE Plasma)", "Atomic desktop with KDE Plasma."),
        "sway-atomic": _Image("Sericea", "Sway Atomic", "Atomic desktop with the Sway tiling compositor."),
        "budgie-atomic": _Image("Onyx", "Budgie Atomic", "Atomic desktop with Budgie."),
        "cosmic-atomic": _Image("COSMIC-Atomic", "COSMIC Atomic", "Atomic desktop with System76's COSMIC."),
    }

    def __init__(self):
        super().__init__(
            key="fedora_atomic",
            name="Fedora Atomic Desktops",
            category="Popular & Desktop",
            description="Image-based Fedora desktops: updated as a whole, rolled back as a whole."
        )


class FedoraSpinsRecipe(_FedoraFamily):
    IMAGES = {
        "xfce": _Image("Xfce", "Xfce", "Lightweight, responsive and highly stable desktop."),
        "cinnamon": _Image("Cinnamon", "Cinnamon", "Traditional, elegant desktop experience."),
        "budgie": _Image("Budgie", "Budgie", "Sleek and intuitive modern desktop."),
        "cosmic": _Image("COSMIC", "COSMIC", "System76's new Rust-based desktop."),
        "mate": _Image("Mate", "MATE-Compiz", "Classic MATE desktop with the Compiz window manager."),
        "lxqt": _Image("LXQt", "LXQt", "Very light Qt desktop."),
        "lxde": _Image("LXDE", "LXDE", "Very light GTK desktop for old hardware."),
        "i3": _Image("i3", "i3", "Keyboard-driven tiling window manager."),
        "sway": _Image("Sway", "Sway", "Tiling Wayland compositor, compatible with i3."),
        "miraclewm": _Image("MiracleWM", "Miracle", "Tiling Wayland compositor built on Mir."),
        "kde-mobile": _Image("KDE_Mobile", "KDE Plasma Mobile", "Plasma's touch interface, for tablets and 2-in-1s."),
        "soas": _Image("SoaS", "Sugar on a Stick", "The Sugar learning environment for children."),
    }

    def __init__(self):
        super().__init__(
            key="fedora_spins",
            name="Fedora Spins",
            category="Popular & Desktop",
            description="Fedora with an alternative desktop environment."
        )


class FedoraLabsRecipe(_FedoraFamily):
    IMAGES = {
        "astronomy": _Image("Astronomy_KDE", "Astronomy", "Tools for amateur and professional astronomers."),
        "design-suite": _Image("Design_suite", "Design Suite", "Open creative tools for visual design."),
        "games": _Image("Games", "Games", "A showcase of the games packaged in Fedora."),
        "jam": _Image("Jam_KDE", "Jam", "Audio production and music-making."),
        "python-classroom": _Image("Python_Classroom", "Python Classroom", "A ready-made environment for teaching Python."),
        "robotics": _Image("Robotics", "Robotics Suite", "Free and open robotics software."),
        "scientific": _Image("Scientific_KDE", "Scientific", "Numerical and scientific computing tools."),
        "security": _Image("Security", "Security Lab", "Security auditing, forensics and rescue."),
    }

    def __init__(self):
        super().__init__(
            key="fedora_labs",
            name="Fedora Labs",
            category="Popular & Desktop",
            description="Fedora with a curated set of software for one purpose."
        )
