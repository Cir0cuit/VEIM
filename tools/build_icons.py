#!/usr/bin/env python3
"""Render src/assets/branding/veim.svg into the launcher icon formats.

Run after editing the SVG:  python tools/build_icons.py
"""
import os
import struct
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

BRANDING = os.path.join(BASE, "src", "assets", "branding")
SVG = os.path.join(BRANDING, "veim.svg")
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)

# macOS names each slot by pixel size; only these are read from an .icns.
ICNS_SLOTS = {
    "icp4": 16, "icp5": 32, "ic11": 32, "ic12": 64,
    "ic07": 128, "ic13": 256, "ic08": 256, "ic14": 512,
    "ic09": 512, "ic10": 1024,
}


def render_pngs():
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    from PySide6.QtCore import Qt

    app = QGuiApplication.instance() or QGuiApplication(sys.argv)
    renderer = QSvgRenderer(SVG)
    if not renderer.isValid():
        raise SystemExit(f"cannot parse {SVG}")

    paths = {}
    for size in PNG_SIZES:
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(Qt.GlobalColor.transparent)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        out = os.path.join(BRANDING, f"veim-{size}.png")
        if not image.save(out, "PNG"):
            raise SystemExit(f"failed to write {out}")
        paths[size] = out
    del app
    return paths


def build_ico(paths):
    from PIL import Image

    # Largest first: Pillow scales the base image down for any size it was not
    # handed, and never up.
    order = sorted(ICO_SIZES, reverse=True)
    frames = [Image.open(paths[s]).convert("RGBA") for s in order]
    out = os.path.join(BRANDING, "veim.ico")
    frames[0].save(out, format="ICO",
                   sizes=[(s, s) for s in order], append_images=frames[1:])
    return out


def build_icns(paths):
    """Write an .icns by hand: Pillow only encodes them on macOS."""
    entries = []
    for slot, size in ICNS_SLOTS.items():
        with open(paths[size], "rb") as fh:
            data = fh.read()
        entries.append(slot.encode("ascii") + struct.pack(">I", len(data) + 8) + data)

    body = b"".join(entries)
    out = os.path.join(BRANDING, "veim.icns")
    with open(out, "wb") as fh:
        fh.write(b"icns" + struct.pack(">I", len(body) + 8) + body)
    return out


if __name__ == "__main__":
    pngs = render_pngs()
    print(f"{len(pngs)} PNGs")
    print(build_ico(pngs))
    print(build_icns(pngs))
