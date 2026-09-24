"""Check that Qt rendered each Wikimedia SVG logo the way Wikimedia does.

Qt's SVG renderer handles a subset of SVG, and a file it cannot handle fails
silently: it produces an image, just the wrong one. Slackware's rendered as a
blue orb with a white rectangle over the mark, which still looked like an icon
at 44px.

Both images are trimmed to their content before comparing, since our pipeline
crops transparent margins and Wikimedia's thumbnails do not. A reported
difference means "look at this", not "this is broken" - elementary OS renders
better under Qt than under Wikimedia's renderer.

    python tools/audit_icons.py

Needs network. Not part of the pytest suite.
"""
import io
import os
import sys
import urllib.parse

import requests
from PIL import Image, ImageChops, ImageStat

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from src.core.icons import ICON_URLS  # noqa: E402

HEADERS = {"User-Agent": "VEIM-icon-audit/1.0 (+https://github.com/Cir0cuit/VEIM)"}
CACHE_DIR = os.path.join(BASE_DIR, "src", "assets", "icons")

# Below this the two renderings are the same picture; above it, worth a look.
DIFFERENCE_THRESHOLD = 25.0


def wikimedia_rendering(file_url: str, width: int = 400):
    """Ask Wikimedia to rasterise one of its own SVGs, and return the PNG URL."""
    name = urllib.parse.unquote(file_url.rstrip("/").split("/")[-1])
    if not name.lower().endswith(".svg"):
        return None
    resp = requests.get(
        "https://commons.wikimedia.org/w/api.php", headers=HEADERS, timeout=30,
        params={"action": "query", "format": "json", "titles": f"File:{name}",
                "prop": "imageinfo", "iiprop": "url", "iiurlwidth": str(width)},
    )
    for page in resp.json().get("query", {}).get("pages", {}).values():
        info = (page.get("imageinfo") or [{}])[0]
        if info.get("thumburl"):
            return info["thumburl"]
    return None


def normalise(img: Image.Image) -> Image.Image:
    """Trim to content, flatten onto white, and scale - so only the drawing counts."""
    img = img.convert("RGBA")
    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)
    flat = Image.alpha_composite(Image.new("RGBA", img.size, (255, 255, 255, 255)), img)
    return flat.convert("L").resize((64, 64), Image.Resampling.LANCZOS)


def main() -> int:
    suspect = []
    checked = 0

    for key, url in sorted(ICON_URLS.items()):
        if "wikimedia.org" not in url or not url.lower().endswith(".svg"):
            continue
        cached = os.path.join(CACHE_DIR, f"{key}.png")
        if not os.path.exists(cached):
            print(f"  {key:14s} not cached yet - run the app once")
            continue

        thumb = wikimedia_rendering(url)
        if not thumb:
            print(f"  {key:14s} no Wikimedia rendering available")
            continue

        try:
            reference = normalise(Image.open(io.BytesIO(
                requests.get(thumb, headers=HEADERS, timeout=30).content)))
            ours = normalise(Image.open(cached))
        except Exception as exc:
            print(f"  {key:14s} ERROR {type(exc).__name__}: {exc}")
            continue

        score = ImageStat.Stat(ImageChops.difference(reference, ours)).mean[0]
        checked += 1
        if score > DIFFERENCE_THRESHOLD:
            suspect.append((score, key, thumb))
            print(f"  {key:14s} differs by {score:6.1f}   <-- compare against {thumb}")
        else:
            print(f"  {key:14s} matches    ({score:4.1f})")

    print(f"\nChecked {checked} Wikimedia SVG logos.")
    if suspect:
        print("Worth looking at, worst first:",
              ", ".join(k for _, k, _ in sorted(suspect, reverse=True)))
        print("Where Qt is the one at fault, point ICON_URLS at Wikimedia's "
              "pre-rendered PNG instead of the SVG (see the slackware entry).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
