#!/usr/bin/env bash
# macOS disk image: dist/FLOPPY.app → dist/FLOPPY-<version>.dmg (drag to Applications). Signing/notarization: see build-sign.sh (Apple Developer account required).
set -euo pipefail; cd "$(dirname "$0")"; V="$(grep -oE '^VERSION = "[^"]+"' app.py | cut -d'"' -f2)"
[ -d dist/FLOPPY.app ] || { echo "dist/FLOPPY.app manquant : lance ./build-mac.sh"; exit 1; }
rm -rf dist/dmg "dist/FLOPPY-$V.dmg"; mkdir -p dist/dmg; cp -R dist/FLOPPY.app dist/dmg/; ln -s /Applications dist/dmg/Applications
cat > dist/dmg/README.txt <<'TXT'
FLOPPY — drag FLOPPY.app to Applications, then open it.
If macOS refuses ("unidentified developer"): right-click the app → Open → Open. This happens while the app is not signed.
Everything stays on your machine: key, engine, model. Back up your key when the app asks.

FLOPPY — glisse FLOPPY.app dans Applications, puis ouvre-le. Si macOS refuse : clic droit → Ouvrir → Ouvrir.
TXT
hdiutil create -volname "FLOPPY $V" -srcfolder dist/dmg -ov -format UDZO -quiet "dist/FLOPPY-$V.dmg"
echo "built: $(du -h "dist/FLOPPY-$V.dmg" | cut -f1) → dist/FLOPPY-$V.dmg"
