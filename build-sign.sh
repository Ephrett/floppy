#!/usr/bin/env bash
# Signature + notarisation macOS (à lancer quand le certificat « Developer ID Application » est dans le trousseau et que les identifiants
# notarytool sont enregistrés : xcrun notarytool store-credentials floppy --apple-id <email> --team-id <TEAM> --password <mot de passe d'app>).
set -euo pipefail; cd "$(dirname "$0")"; V="$(grep -oE 'VERSION = "[^"]+"' app.py | cut -d'"' -f2)"
ID="${SIGN_ID:-$(security find-identity -v -p codesigning | grep -oE '"Developer ID Application: [^"]+"' | head -1 | tr -d '"')}"
[ -n "$ID" ] || { echo "aucun certificat Developer ID Application dans le trousseau"; exit 1; }
codesign --force --deep --options runtime --timestamp --entitlements entitlements.plist --sign "$ID" dist/FLOPPY.app
codesign --verify --deep --strict --verbose=2 dist/FLOPPY.app
./build-dmg.sh; xcrun notarytool submit "dist/FLOPPY-$V.dmg" --keychain-profile floppy --wait; xcrun stapler staple "dist/FLOPPY-$V.dmg"
spctl -a -vv -t install "dist/FLOPPY-$V.dmg" && echo "signé, notarisé, agrafé : dist/FLOPPY-$V.dmg"
