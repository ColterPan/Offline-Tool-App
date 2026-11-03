#!/usr/bin/env bash
# Build the macOS .app (PyInstaller) and wrap it in a drag-to-Applications .dmg.
# Run from an activated venv on a Mac:  bash packaging/macos/build_dmg.sh
# PyInstaller ad-hoc signs the app, which Apple Silicon needs to run it. It is NOT notarised,
# so users must allow it once in System Settings > Privacy & Security.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
BUILD_ROOT="${BUILD_ROOT:-$ROOT/build}"
PYTHON="${PYTHON:-python}"

APP_NAME="$("$PYTHON" -c 'import offline_tools as m; print(m.APP_NAME)')"
EXE_NAME="$("$PYTHON" -c 'import offline_tools as m; print(m.EXE_NAME)')"
VERSION="$("$PYTHON" -c 'import offline_tools as m; print(m.__version__)')"
echo "Building $APP_NAME $VERSION into $BUILD_ROOT"

"$PYTHON" -m PyInstaller --noconfirm --clean \
    --workpath "$BUILD_ROOT/work" \
    --distpath "$BUILD_ROOT/dist" \
    "$ROOT/packaging/offline_tools.spec"

STAGE="$BUILD_ROOT/dmg-stage"
DMG="$BUILD_ROOT/$EXE_NAME.dmg"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$BUILD_ROOT/dist/$APP_NAME.app" "$STAGE/"
ln -s /Applications "$STAGE/Applications"
hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE" -ov -format UDZO "$DMG"

echo "Disk image: $DMG ($(du -h "$DMG" | cut -f1))"
echo "SHA-256:    $(shasum -a 256 "$DMG" | cut -d' ' -f1)"
