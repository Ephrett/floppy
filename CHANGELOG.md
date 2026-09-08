# Changelog

## 1.0.1 — 2026-09-08
- Model download now goes through the Ollama server API; the `ollama` command is no longer required in the app's PATH. Fixes
  "No such file or directory: 'ollama'" when the app is launched from the Finder with an existing Ollama (Homebrew or Ollama.app).
- Ollama detection also looks in /opt/homebrew/bin, /usr/local/bin, ~/Applications and Program Files.
- The language detected from the browser locale is now saved, so backend journal messages follow the interface language.

## 1.0.0 — 2026-09-08
First public source release. Five-step setup (machine, engine, model, identity, play), dashboard with measured numbers, FR/EN interface,
autostart without admin rights, optional Telegram pairing with alerts and a daily report, DMG and Inno Setup packaging, GitHub Actions builds.
Builds are not signed yet.
