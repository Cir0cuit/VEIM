#!/usr/bin/env python3
r"""Refresh the committed distribution logos in src/assets/icons/.

The app ships these rather than fetching them, so run this after adding an
entry to ICON_URLS, and commit the result.

    python tools/fetch_icons.py            # only what is missing
    python tools/fetch_icons.py --force    # re-fetch everything

Every logo is checked after rendering: Qt renders a subset of SVG and fails
silently on the rest, writing a blank image rather than none.
"""
import os
import sys
from io import BytesIO

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import requests
from PIL import Image
from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

from src import __version__
from src.core.branding import BRANDING_DIR
from src.core.icons import BUNDLED_PREFIX, ICON_URLS
from src.core.logger import log

ICON_DIR = os.path.join(BASE_DIR, "src", "assets", "icons")
MIN_EDGE = 32
MIN_OPAQUE_FRACTION = 0.01

# Logos are stored tight against their own edges. Padding is the chip's job
# (see IconChip.FILL); baking it in here would compound with that.
RENDER_PX = 512


def _trim_transparent(img: Image.Image) -> Image.Image:
    """Crop fully transparent margins so the logo sits flush to its own edges."""
    bbox = img.getbbox()
    return img.crop(bbox) if bbox else img


def _render_svg(data: bytes, out: str) -> None:
    """Rasterise an SVG to `out`, trimmed to its own edges."""
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
    img.save(out, "PNG")

    # An SVG's viewBox often carries its own margin.
    with Image.open(out) as im:
        _trim_transparent(im.convert("RGBA")).save(out, format="PNG")


def _render_bundled(key: str, filename: str, out: str) -> None:
    """Rasterise a logo that ships with the app rather than being fetched."""
    source = os.path.join(BRANDING_DIR, filename)
    if not os.path.exists(source):
        log.debug(f"Bundled icon missing for {key}: {source}")
        return
    try:
        if filename.lower().endswith(".svg"):
            _render_svg(open(source, "rb").read(), out)
        else:
            img = _trim_transparent(Image.open(source).convert("RGBA"))
            img.thumbnail((RENDER_PX, RENDER_PX), Image.Resampling.LANCZOS)
            img.save(out, format="PNG")
    except Exception as e:
        log.debug(f"Could not render bundled icon for {key}: {e}")


def _download_all(force: bool = False) -> None:
    headers = {
        "User-Agent": f"VEIM/{__version__} (https://github.com/Cir0cuit/VEIM)"
    }
    for key, url in ICON_URLS.items():
        out = os.path.join(ICON_DIR, f"{key}.png")
        if force or not os.path.exists(out):
            try:
                if url.startswith(BUNDLED_PREFIX):
                    _render_bundled(key, url[len(BUNDLED_PREFIX):], out)
                    continue
                r = requests.get(url, headers=headers, timeout=12, allow_redirects=True)
                if r.status_code == 200:
                    content_type = r.headers.get("Content-Type", "").lower()
                    if "svg" in content_type or url.endswith(".svg"):
                        _render_svg(r.content, out)
                    else:
                        img = _trim_transparent(
                            Image.open(BytesIO(r.content)).convert("RGBA"))
                        img.thumbnail((RENDER_PX, RENDER_PX), Image.Resampling.LANCZOS)
                        img.save(out, format="PNG")
            except Exception as e:
                log.debug(f"Could not download icon for {key}: {e}")


def inspect(path: str) -> str:
    """An empty string when the rendered logo is usable."""
    if not os.path.exists(path):
        return "no file produced"
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            width, height = rgba.size
            opaque = sum(1 for alpha in rgba.getchannel("A").tobytes() if alpha > 8)
    except Exception as e:
        return f"unreadable: {e}"
    if width < MIN_EDGE or height < MIN_EDGE:
        return f"tiny, {width}x{height}"
    if opaque < width * height * MIN_OPAQUE_FRACTION:
        return "blank after rendering"
    return ""


def main() -> int:
    force = "--force" in sys.argv[1:]
    app = QApplication.instance() or QApplication(sys.argv[:1])

    os.makedirs(ICON_DIR, exist_ok=True)
    _download_all(force=force)

    failures = []
    for key in sorted(ICON_URLS):
        problem = inspect(os.path.join(ICON_DIR, f"{key}.png"))
        if problem:
            failures.append((key, problem))

    print(f"{len(ICON_URLS) - len(failures)}/{len(ICON_URLS)} logos usable in {ICON_DIR}")
    for key, problem in failures:
        print(f"  FAIL {key}: {problem}\n       {ICON_URLS[key]}")
    del app
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
