# Third-party notices

Bundled in the interface (`ui/vendor`):
- **Handjet** — SIL Open Font License 1.1, see `ui/vendor/fonts/OFL-Handjet.txt`.
- **IBM Plex Sans / IBM Plex Mono** — SIL Open Font License 1.1, see `ui/vendor/fonts/OFL-IBMPlexSans.txt` and `OFL-IBMPlexMono.txt`.
- **Chart.js** — MIT, see `ui/vendor/LICENSE-chartjs.md`.

Python dependencies (bundled into the frozen app): **pywebview** (BSD-3-Clause), **cryptography** (Apache-2.0 / BSD-3-Clause).
Build tool: **PyInstaller** (GPL-2.0-or-later with the bootloader exception; the produced app is not affected).

Downloaded at runtime, on the user's machine, from their official sources and under their own terms:
- **Ollama** (MIT), verified against the SHA-256 list of the official GitHub release.
- **Models** pulled through Ollama: Gemma models are subject to Google's Gemma Terms of Use; Qwen models are Apache-2.0. Read them before use.
