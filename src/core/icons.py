import os
import threading
import requests
from io import BytesIO
from typing import Dict, Optional, Callable, Tuple
from PIL import Image
from PySide6.QtGui import QPixmap, QIcon, QImage, QPainter, QColor
from PySide6.QtCore import Qt, QRectF
from PySide6.QtSvg import QSvgRenderer
from src import __version__
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

# Bump when the on-disk icon format changes; older caches are re-processed.
CACHE_FORMAT = 2

# Cached logos are stored tight against their own edges. Padding is the chip's
# job (see IconChip.FILL); baking it in here would compound with that.
RENDER_PX = 512


# Logos that ship with the app because no fetchable mark-only file exists.
# They live outside the icon cache so the cache stays disposable.
BUNDLED_PREFIX = "bundled:"
BRANDING_DIR = os.path.join(paths.resource_dir(), "src", "assets", "branding")

# Every logo is rendered ahead of time and ships with the app. Fetching them on
# first run left rows blank until fifty sequential requests had finished, and
# blank for good on a machine behind a proxy or with no network at all.
BUNDLED_ICON_DIR = os.path.join(paths.resource_dir(), "src", "assets", "icons")


def _trim_transparent(img: "Image.Image") -> "Image.Image":
    """Crop fully transparent margins so the logo sits flush to its own edges."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


class IconManager:
    def __init__(self):
        self.cache_dir = paths.icon_cache_dir()
        self.pixmap_cache: Dict[Tuple[str, int, float], QPixmap] = {}
        self._backdrop_cache: Dict[str, bool] = {}
        self.listeners: list[Callable[[str], None]] = []
        self._migrate_cache()

    def _icon_path(self, key: str) -> Optional[str]:
        """A downloaded refresh wins; otherwise the copy that ships with the app."""
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

    def _migrate_cache(self):
        """Re-crop icons written before CACHE_FORMAT 2, which had padding baked in."""
        marker = os.path.join(self.cache_dir, ".cache_format")
        try:
            with open(marker, "r", encoding="utf-8") as f:
                if int(f.read().strip()) >= CACHE_FORMAT:
                    return
        except Exception:
            pass

        for fn in os.listdir(self.cache_dir):
            # chevron_down is UI chrome drawn at a fixed size, not a logo.
            if not fn.endswith(".png") or fn.startswith("chevron"):
                continue
            path = os.path.join(self.cache_dir, fn)
            try:
                with Image.open(path) as im:
                    trimmed = _trim_transparent(im.convert("RGBA"))
                trimmed.save(path, format="PNG")
            except Exception as e:
                log.debug(f"Could not re-crop cached icon {fn}: {e}")

        try:
            with open(marker, "w", encoding="utf-8") as f:
                f.write(str(CACHE_FORMAT))
        except Exception as e:
            log.debug(f"Could not write icon cache marker: {e}")

    def preload_all(self, sizes=(56, 48, 64), dpr: float = 2.0):
        """Pre-render and cache high-resolution, High-DPI QPixmaps for all cached icons."""
        for key in self.available_keys():
            cache_file = self._icon_path(key)
            if cache_file:
                try:
                    pix = QPixmap(cache_file)
                    if not pix.isNull():
                        for sz in sizes:
                            target_px = int(sz * dpr)
                            scaled = pix.scaled(
                                target_px, target_px,
                                Qt.AspectRatioMode.KeepAspectRatio,
                                Qt.TransformationMode.SmoothTransformation
                            )
                            scaled.setDevicePixelRatio(dpr)
                            self.pixmap_cache[(key, sz, dpr)] = scaled
                except Exception as e:
                    log.debug(f"Failed to pre-render pixmap for {key}: {e}")

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
        if path:
            try:
                with Image.open(path) as im:
                    # A thumbnail is enough to judge overall darkness.
                    small = im.convert("RGBA").resize((24, 24), Image.Resampling.BILINEAR)
                raw = small.tobytes()
                pixels = [raw[i:i + 4] for i in range(0, len(raw), 4)]
                visible = [p for p in pixels if p[3] > 128]
                if visible:
                    dark = sum(
                        1 for r, g, b, _ in visible
                        if 0.2126 * r + 0.7152 * g + 0.0722 * b < 70
                    )
                    # Nearly every visible pixel dark => the logo IS the dark shape.
                    needs = dark / len(visible) >= 0.85
            except Exception as e:
                log.debug(f"Could not measure backdrop need for {k}: {e}")

        self._backdrop_cache[k] = needs
        return needs

    def get_icon(self, key: str, size: int = 56) -> Optional[QIcon]:
        pix = self.get_pixmap(key, size)
        return QIcon(pix) if pix else None

    def start_background_download(self):
        """Fetch anything the app does not already ship. Normally nothing."""
        threading.Thread(target=self._download_all, daemon=True).start()

    def _download_all(self, force: bool = False):
        headers = {
            "User-Agent": f"VEIM/{__version__} (https://github.com/Cir0cuit/VEIM)"
        }
        for key, url in ICON_URLS.items():
            cache_file = os.path.join(self.cache_dir, f"{key}.png")
            if force or self._icon_path(key) is None:
                try:
                    if url.startswith(BUNDLED_PREFIX):
                        self._render_bundled(key, url[len(BUNDLED_PREFIX):], cache_file)
                        continue
                    r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
                    if r.status_code == 200:
                        content_type = r.headers.get("Content-Type", "").lower()
                        if "svg" in content_type or url.endswith(".svg"):
                            self._render_svg(r.content, cache_file)
                        else:
                            img = _trim_transparent(
                                Image.open(BytesIO(r.content)).convert("RGBA"))
                            img.thumbnail((RENDER_PX, RENDER_PX), Image.Resampling.LANCZOS)
                            img.save(cache_file, format="PNG")

                        self._notify(key)
                except Exception as e:
                    log.debug(f"Could not download icon for {key}: {e}")

    @staticmethod
    def _render_svg(data: bytes, cache_file: str) -> None:
        """Rasterise an SVG to the icon cache, trimmed to its own edges."""
        renderer = QSvgRenderer(data)
        if not renderer.isValid():
            raise ValueError("not a valid SVG")

        img = QImage(RENDER_PX, RENDER_PX, QImage.Format.Format_ARGB32)
        img.fill(QColor(0, 0, 0, 0))
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        vb = renderer.viewBoxF()
        vw = vb.width() if vb.width() > 0 else float(RENDER_PX)
        vh = vb.height() if vb.height() > 0 else float(RENDER_PX)
        # Edge to edge; the chip adds the padding.
        scale = min(RENDER_PX / vw, RENDER_PX / vh)
        dw, dh = vw * scale, vh * scale
        renderer.render(painter, QRectF((RENDER_PX - dw) / 2.0, (RENDER_PX - dh) / 2.0, dw, dh))
        painter.end()
        img.save(cache_file, "PNG")

        # An SVG's viewBox often carries its own margin.
        with Image.open(cache_file) as im:
            _trim_transparent(im.convert("RGBA")).save(cache_file, format="PNG")

    def _render_bundled(self, key: str, filename: str, cache_file: str):
        """Rasterise a logo that ships with the app rather than being fetched."""
        source = os.path.join(BRANDING_DIR, filename)
        if not os.path.exists(source):
            log.debug(f"Bundled icon missing for {key}: {source}")
            return
        try:
            if filename.lower().endswith(".svg"):
                self._render_svg(open(source, "rb").read(), cache_file)
            else:
                img = _trim_transparent(Image.open(source).convert("RGBA"))
                img.thumbnail((RENDER_PX, RENDER_PX), Image.Resampling.LANCZOS)
                img.save(cache_file, format="PNG")
            self._notify(key)
        except Exception as e:
            log.debug(f"Could not render bundled icon for {key}: {e}")

    def _notify(self, key: str):
        # A newly fetched file invalidates whatever we measured from its absence.
        self._backdrop_cache.pop(key.lower(), None)
        for cb in self.listeners:
            try:
                cb(key)
            except Exception:
                pass

icon_manager = IconManager()

