#!/usr/bin/env python3
"""Render src/assets/branding/veim.svg into the launcher icon formats.

Run after editing the SVG:  python tools/build_icons.py
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

BRANDING = os.path.join(BASE, "src", "assets", "branding")
SVG = os.path.join(BRANDING, "veim.svg")
PNG_SIZES = (16, 24, 32, 48, 64, 128, 256, 512, 1024)
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


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
    from PIL import Image

    # Pillow fills the ic07-ic14 slots, 32 to 1024 px, from the frame of each
    # width; macOS scales the 16 px icon down from the 32.
    out = os.path.join(BRANDING, "veim.icns")
    Image.open(paths[1024]).save(
        out, append_images=[Image.open(paths[s]) for s in (32, 64, 128, 256, 512)])
    return out


if __name__ == "__main__":
    pngs = render_pngs()
    print(f"{len(pngs)} PNGs")
    print(build_ico(pngs))
    print(build_icns(pngs))
