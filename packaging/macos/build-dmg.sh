#!/usr/bin/env bash
# Wrap PyInstaller's dist/VEIM.app into a drag-to-Applications disk image.
#
#   packaging/macos/build-dmg.sh <version> [arch]
#
# Writes dist/VEIM-<version>-macos-<arch>.dmg.
set -euo pipefail

VERSION="${1:?usage: build-dmg.sh <version> [arch]}"
ARCH="${2:-$(uname -m)}"
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST="$ROOT/dist"
STAGE="$DIST/dmg"

[ -d "$DIST/VEIM.app" ] || { echo "dist/VEIM.app is missing; run pyinstaller first" >&2; exit 1; }

# An ad-hoc signature is not notarization, but without any signature at all
# Apple Silicon refuses to run the bundle and reports it as damaged rather than
# unsigned, which sends people looking for the wrong problem.
codesign --force --deep --sign - "$DIST/VEIM.app"
codesign --verify --deep --strict "$DIST/VEIM.app"

rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$DIST/VEIM.app" "$STAGE/VEIM.app"
ln -s /Applications "$STAGE/Applications"

OUT="$DIST/VEIM-$VERSION-macos-$ARCH.dmg"
rm -f "$OUT"
hdiutil create -volname "VEIM $VERSION" -srcfolder "$STAGE" \
    -ov -format UDZO "$OUT" >/dev/null
echo "$OUT"
