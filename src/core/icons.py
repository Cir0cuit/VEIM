import os
from typing import Dict, Optional, Tuple
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtCore import Qt
from src.core import paths
from src.core.logger import log

ICON_URLS = {
    # Desktop & Core
    "alpine": "https://commons.wikimedia.org/wiki/Special:FilePath/Alpine_Linux_Logo.svg",
    "arch": "https://commons.wikimedia.org/wiki/Special:FilePath/Arch_Linux_%22Crystal%22_icon.svg",
    "debian": "https://commons.wikimedia.org/wiki/Special:FilePath/Debian-OpenLogo.svg",
    "endeavour": "https://commons.wikimedia.org/wiki/Special:FilePath/EndeavourOS_Logo.svg",
    "fedora": "https://commons.wikimedia.org/wiki/Special:FilePath/Fedora_icon_%282021%29.svg",
    # Four catalog entries, one project.
    "fedora_atomic": "https://commons.wikimedia.org/wiki/Special:FilePath/Fedora_icon_%282021%29.svg",
    "fedora_spins": "https://commons.wikimedia.org/wiki/Special:FilePath/Fedora_icon_%282021%29.svg",
    "fedora_labs": "https://commons.wikimedia.org/wiki/Special:FilePath/Fedora_icon_%282021%29.svg",
    "kali": "https://commons.wikimedia.org/wiki/Special:FilePath/Kali-dragon-icon.svg",
    "mint": "https://commons.wikimedia.org/wiki/Special:FilePath/Linux_Mint_logo_without_wordmark.svg",
    "manjaro": "https://commons.wikimedia.org/wiki/Special:FilePath/Manjaro-logo.svg",
    "ubuntu": "https://commons.wikimedia.org/wiki/Special:FilePath/Logo-ubuntu_cof-orange-hex.svg",
    "popos": "https://commons.wikimedia.org/wiki/Special:FilePath/Pop_OS-Logo-nobg.svg",
    "zorin": "https://commons.wikimedia.org/wiki/Special:FilePath/Zorin_Logomark.svg",
    "kde_neon": "https://commons.wikimedia.org/wiki/Special:FilePath/Neon-logo.svg",

    # Security & Pentesting
    "parrot": "https://commons.wikimedia.org/wiki/Special:FilePath/Parrot_OS_logo,_2023.svg",

    # Diagnostics & Utilities
    "gparted": "https://commons.wikimedia.org/wiki/Special:FilePath/Scalable_gparted.svg",
    "clonezilla": "https://commons.wikimedia.org/wiki/Special:FilePath/Clonezilla.svg",
    "puppy": "https://commons.wikimedia.org/wiki/Special:FilePath/Puppy_logo.svg",
    "rescuezilla": "https://raw.githubusercontent.com/rescuezilla/rescuezilla/master/src/apps/rescuezilla/rescuezilla/usr/share/pixmaps/rescuezilla.svg",
    "netboot": "https://netboot.xyz/img/nbxyz-logo.svg",
    "shredos": "https://raw.githubusercontent.com/PartialVolume/shredos.x86_64/master/images/shred_db.png",
    "tinycore": "https://commons.wikimedia.org/wiki/Special:FilePath/Tcl_logo.png",

    # Newly Added Distributions (Official full-color vector & high-res branding)
    "cachyos": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/cachyos-linux.svg",
    "bazzite": "https://bazzite.gg/content/uploads/2024/02/icon.svg",
    "opensuse": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/opensuse.svg",
    "nixos": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/nixos.svg",
    "elementary": "https://commons.wikimedia.org/wiki/Special:FilePath/Elementary%20logo.svg",
    "artix": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/artix.png",
    "garuda": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/png/garuda-linux.png",
    "sparky": "https://commons.wikimedia.org/wiki/Special:FilePath/SparkyLinux-logo-200px.png",
    # Ships with the app: every fetchable file is a wordmark on baked-in white.
    "tails": "bundled:tails.svg",
    "fydeos": "https://cdn-web.fydeos.io/logo_light_b87eb97f33.svg",
    "mageia": "https://www.mageia.org/g/media/logo/mageia-2013.svg",
    "almalinux": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/alma-linux.svg",

    "tuxedo": "https://os.tuxedocomputers.com/html/icon.svg",
    "hackeros": "https://avatars.githubusercontent.com/u/213236994?v=4&s=460",

    # Debian family
    "mxlinux": "https://commons.wikimedia.org/wiki/Special:FilePath/Logo-MX_big.png",
    "antix": "https://avatars.githubusercontent.com/u/1210948?v=4&s=460",
    "devuan": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/devuan.svg",
    "q4os": "https://avatars.githubusercontent.com/u/41686011?v=4&s=460",
    "grml": "https://grml.org/logoflat.svg",

    # Independent
    "void": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/void-linux.svg",
    "gentoo": "https://commons.wikimedia.org/wiki/Special:FilePath/Gentoo_Linux_logo_matte.svg",
    # Wikimedia's PNG rendering, not the SVG: Qt paints a white rectangle over
    # this particular file. 500px is the largest pre-rendered width.
    "slackware": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Slackware_logo.svg/500px-Slackware_logo.svg.png",

    # Enterprise / virtualisation / high security
    "rocky": "https://commons.wikimedia.org/wiki/Special:FilePath/Rocky_Linux_logo.svg",
    "proxmox": "https://raw.githubusercontent.com/walkxcode/dashboard-icons/main/svg/proxmox.svg",
    "qubes": "https://commons.wikimedia.org/wiki/Special:FilePath/Qubes_OS_Logo.svg",
    "centos": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/centos.svg",
    "oracle": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/oracle.svg",
    "talos": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/talos.svg",
    "xcpng": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/xcp-ng.svg",
    "openeuler": "https://avatars.githubusercontent.com/u/59104494?v=4&s=460",
    "freebsd": "https://commons.wikimedia.org/wiki/Special:FilePath/Daemon-phk.svg",
    "ipfire": "https://www.ipfire.org/static/img/ipfire-tux.png",
    # The feather, from the project's GitHub account: the logo on Wikimedia is
    # a dark wordmark, which disappears on a dark chip.
    "linuxlite": "https://avatars.githubusercontent.com/u/5382578?v=4&s=460",
    # The only mark the project publishes that is not a banner.
    "caine": "https://distrowatch.com/images/yvzhuwbpy/caine.png",
    "supergrub2": "https://avatars.githubusercontent.com/u/17692608?v=4&s=460",
    # hrmpf has no logo of its own; it is a Void Linux system.
    "hrmpf": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/svg/void-linux.svg",

    # Gaming
    "nobara": "https://avatars.githubusercontent.com/u/155680587?v=4&s=460",
    "pikaos": "https://git.pika-os.com/website/pika-branding/raw/branch/main/logos/pika-logo.svg",

    # Rolling / rescue
    "omarchy": "https://raw.githubusercontent.com/homarr-labs/dashboard-icons/main/png/omarchy.png",
    "systemrescue": "https://commons.wikimedia.org/wiki/Special:FilePath/System-rescue-cd-logo-new.svg",
    "memtest": "https://avatars.githubusercontent.com/u/99513462?v=4&s=460",
}

# Logos that ship with the app because no fetchable mark-only file exists.
# They live outside the icon cache so the cache stays disposable.
BUNDLED_PREFIX = "bundled:"

# Every logo is rendered ahead of time and ships with the app. Fetching them on
# first run left rows blank until fifty sequential requests had finished, and
# blank for good on a machine behind a proxy or with no network at all.
BUNDLED_ICON_DIR = os.path.join(paths.resource_dir(), "src", "assets", "icons")


class IconManager:
    def __init__(self):
        self.cache_dir = paths.icon_cache_dir()
        self.pixmap_cache: Dict[Tuple[str, int, float], QPixmap] = {}
        self._backdrop_cache: Dict[str, bool] = {}

    def _icon_path(self, key: str) -> Optional[str]:
        """A copy in the icon cache wins; otherwise the one that ships with the app."""
        for directory in (self.cache_dir, BUNDLED_ICON_DIR):
            path = os.path.join(directory, f"{key}.png")
            if os.path.exists(path):
                return path
        return None

    def available_keys(self) -> set:
        keys = set(ICON_URLS)
        for directory in (self.cache_dir, BUNDLED_ICON_DIR):
            try:
                keys.update(fn[:-4] for fn in os.listdir(directory)
                            if fn.endswith(".png") and not fn.startswith("chevron"))
            except OSError:
                pass
        return keys

    def preload_all(self, sizes=(56, 48, 64), dpr: float = 2.0):
        """Pre-render and cache high-resolution, High-DPI QPixmaps for all cached icons."""
        for key in self.available_keys():
            for sz in sizes:
                self.get_pixmap(key, sz, dpr)

    def get_pixmap(self, key: str, size: int = 56, dpr: float = 2.0) -> Optional[QPixmap]:
        k = key.lower()
        cache_key = (k, size, dpr)
        if cache_key in self.pixmap_cache:
            return self.pixmap_cache[cache_key]

        cache_file = self._icon_path(k)
        if cache_file:
            try:
                pix = QPixmap(cache_file)
                if not pix.isNull():
                    target_px = int(size * dpr)
                    scaled = pix.scaled(
                        target_px, target_px,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    scaled.setDevicePixelRatio(dpr)
                    self.pixmap_cache[cache_key] = scaled
                    return scaled
            except Exception as e:
                log.debug(f"Error loading pixmap for {k}: {e}")
        return None

    def needs_light_backdrop(self, key: str) -> bool:
        """True when a logo is dark enough to disappear on a dark chip.

        The chip used to be hardcoded white on every dark theme so that the
        handful of black-on-transparent logos stayed readable, which left a
        bright box behind the other thirty that did not need one. Measuring
        each logo lets the chip follow the theme and plate only the few that
        would otherwise vanish.
        """
        k = key.lower()
        if k in self._backdrop_cache:
            return self._backdrop_cache[k]

        needs = False
        path = self._icon_path(k)
        image = QImage(path) if path else QImage()
        if not image.isNull():
            # A thumbnail is enough to judge overall darkness.
            small = image.scaled(24, 24, Qt.AspectRatioMode.IgnoreAspectRatio,
                                 Qt.TransformationMode.SmoothTransformation)
            pixels = [small.pixelColor(x, y) for y in range(24) for x in range(24)]
            visible = [c for c in pixels if c.alpha() > 128]
            if visible:
                dark = sum(
                    1 for c in visible
                    if 0.2126 * c.red() + 0.7152 * c.green() + 0.0722 * c.blue() < 70
                )
                # Nearly every visible pixel dark => the logo IS the dark shape.
                needs = dark / len(visible) >= 0.85

        self._backdrop_cache[k] = needs
        return needs


icon_manager = IconManager()

