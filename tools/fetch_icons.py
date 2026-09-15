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

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PIL import Image
from PySide6.QtWidgets import QApplication

from src.core.icons import ICON_URLS, IconManager

ICON_DIR = os.path.join(BASE_DIR, "src", "assets", "icons")
MIN_EDGE = 32
MIN_OPAQUE_FRACTION = 0.01


def inspect(path: str) -> str:
    """An empty string when the rendered logo is usable."""
    if not os.path.exists(path):
        return "no file produced"
    try:
        with Image.open(path) as image:
            rgba = image.convert("RGBA")
            width, height = rgba.size
            opaque = sum(1 for pixel in rgba.getdata() if pixel[3] > 8)
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

    manager = IconManager()
    manager.cache_dir = ICON_DIR
    os.makedirs(ICON_DIR, exist_ok=True)
    manager._download_all(force=force)

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
