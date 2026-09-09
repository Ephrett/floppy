# Changelog

## Unreleased
- Worker: skip generation when another agent claimed the job first (the board ignores non-claimant results), pick up jobs seen but never claimed
  after two minutes when the fresh stream is quiet, optional `BOT_SHARD=k/n` so several machines of one operator stop racing each other.
- Worker: survive a corrupted nonce file after a power cut (falls back to the clock, atomic writes).
- App: shell helper decodes command output with replacement, no more UnicodeDecodeError floods on Windows.

## 1.0.3 — 2026-09-08
Found during a full QA pass on macOS with the frozen app:
- Revealed key stayed on "loading…" because the periodic refresh redrew the overlay; the key now stays displayed until hidden.
- "Download the rescue file" did nothing in the native window (WKWebView cannot download page-generated files): the app now writes the
  rescue file itself into Downloads with owner-only permissions and reveals it in Finder / Explorer.
- The backup overlay could be dismissed by clicking the background and the worker could start without a confirmed backup: the overlay
  is no longer dismissible until confirmed, and `/api/play` refuses to start until the backup is confirmed.
- Dashboard counted zero deliveries for tier A/B machines: the engine's "check:ok" suffix broke the log parser.
- Autostart toggles now reflect the real state (LaunchAgent / Run key) and the dashboard switch really toggles.
- Default machine name is neutral (mac-xxxx / pc-xxxx) instead of the hostname, which often contains the user's name and is published.
- Native alerts replaced by in-app toasts; wizard footer no longer overlaps content on small windows; remaining French strings translated.

## 1.0.1 — 2026-09-08
- Model download now goes through the Ollama server API; the `ollama` command is no longer required in the app's PATH. Fixes
  "No such file or directory: 'ollama'" when the app is launched from the Finder with an existing Ollama (Homebrew or Ollama.app).
- Ollama detection also looks in /opt/homebrew/bin, /usr/local/bin, ~/Applications and Program Files.
- The language detected from the browser locale is now saved, so backend journal messages follow the interface language.

## 1.0.0 — 2026-09-08
First public source release. Five-step setup (machine, engine, model, identity, play), dashboard with measured numbers, FR/EN interface,
autostart without admin rights, optional Telegram pairing with alerts and a daily report, DMG and Inno Setup packaging, GitHub Actions builds.
Builds are not signed yet.
