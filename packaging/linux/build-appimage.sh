#!/usr/bin/env bash
# Wrap PyInstaller's dist/VEIM directory into a double-clickable AppImage.
#
#   packaging/linux/build-appimage.sh <version>
#
# Writes dist/VEIM-<version>-x86_64.AppImage.
set -euo pipefail

VERSION="${1:?usage: build-appimage.sh <version>}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/dist"
APPDIR="$DIST/VEIM.AppDir"

[ -d "$DIST/VEIM" ] || { echo "dist/VEIM is missing; run pyinstaller first" >&2; exit 1; }

# Qt's xcb plugin needs these and many desktops do not install them. PyInstaller
# copies them only when the build host has them, and skips them with a warning.
for lib in libxcb-cursor.so.0 libxcb-icccm.so.4 libxcb-image.so.0 \
           libxcb-keysyms.so.1 libxcb-render-util.so.0 libxkbcommon-x11.so.0; do
    [ -n "$(find "$DIST/VEIM" -name "$lib*" -print -quit)" ] ||
        { echo "dist/VEIM lacks $lib; install it on the build host" >&2; exit 1; }
done

rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin" "$APPDIR/usr/share/applications"

cp -a "$DIST/VEIM/." "$APPDIR/usr/bin/"
cp "$ROOT/packaging/linux/veim.desktop" "$APPDIR/usr/share/applications/veim.desktop"
cp "$ROOT/packaging/linux/veim.desktop" "$APPDIR/veim.desktop"

# appimagetool wants the icon at the AppDir root under the name the desktop
# entry gives, and in the icon theme for desktops that install the file.
cp "$ROOT/src/assets/branding/veim-256.png" "$APPDIR/veim.png"
for size in 16 24 32 48 64 128 256 512; do
    install -Dm644 "$ROOT/src/assets/branding/veim-$size.png" \
        "$APPDIR/usr/share/icons/hicolor/${size}x${size}/apps/veim.png"
done

cat >"$APPDIR/AppRun" <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/VEIM" "$@"
EOF
chmod +x "$APPDIR/AppRun"

OUT="$DIST/VEIM-$VERSION-x86_64.AppImage"
ARCH=x86_64 appimagetool --appimage-extract-and-run "$APPDIR" "$OUT"
echo "$OUT"
