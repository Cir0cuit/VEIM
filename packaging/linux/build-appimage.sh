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
