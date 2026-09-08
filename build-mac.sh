#!/usr/bin/env bash
# Builds FLOPPY.app with PyInstaller. Never ships .env, state/, seeds or backups (see .gitignore).
set -euo pipefail; cd "$(dirname "$0")"; PY="${PYTHON:-python3}"
rm -rf build dist
grep -lE "[0-9]{8,10}:[A-Za-z0-9_-]{30,}" engine/* app.py && { echo "token-looking string in sources — aborting"; exit 1; } || true
"$PY" -m PyInstaller --noconfirm --clean --windowed --name FLOPPY --icon assets/floppy.icns \
  --add-data "ui:ui" --add-data "engine:engine" --add-data "fake_worker.py:." \
  --collect-all cryptography --collect-all webview --hidden-import runpy app.py > build.log 2>&1 || { tail -20 build.log; exit 1; }
echo "built: $(du -sh dist/FLOPPY.app | cut -f1) → dist/FLOPPY.app"
