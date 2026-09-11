# Changelog

## 1.0.8 — 2026-09-11
- **`BOT_SELF_CHECK` was never written to `engine/.env`.** In 1.0.7 the new `BOT_PARALLEL` entry swallowed the line that
  followed it into its own trailing comment, so the self-check pass fell back to the worker's default and ran on every
  tier, including the low-power ones it is meant to spare. Reported by [@0xKr4kN](https://github.com/0xKr4kN) in #1, with
  the exact line and the fallback that masked it.
- **One parallel generation is no longer offered, because it stops the agent from claiming.** The worker only takes a new
  job while `backlog < BOT_PARALLEL`, so at 1 it goes quiet as soon as a single generation is in flight. The setting now
  offers 2, 3 or 4, the automatic value never picks 1, and the server rejects it.
## 1.0.7 — 2026-09-10
- **Allocated power is now adjustable after setup**, in Settings: pace (50/75/100% of what your machine measured),
  parallel generations (1, 2 or 4 — fewer means a cooler machine), and a thermal limit.
- **Thermal pause.** Set a limit (75/80/85 °C) and FLOPPY stops above it and resumes 5 °C lower, telling you on Telegram
  if you paired it. NVIDIA cards only, off by default. Asked for by a beta tester whose laptop was already running hot.

## 1.0.6 — 2026-09-10
- **Simulation mode was too easy to run by accident.** The README's own "run from source" example enabled it, so a tester
  spent hours watching invented jobs and invented numbers. The default example now runs for real; simulation is opt-in and
  documented as a development mode. The dashboard shows a banner saying nothing is sent to the board, the header badge is
  orange, and the server prints the same warning on startup.

## 1.0.5 — 2026-09-10
- **Key backup worked nowhere but on the machine itself.** Reveal, Copy and Save all failed silently when the interface was
  opened from another machine or from outside a container: the request arrives from the Docker gateway, not from loopback.
  The rescue file is now written by the app on its own machine (only the path travels), so Save works from any browser, and
  the blocked Reveal explains where to read the key instead (`docker exec <container> cat /data/engine/seed.hex`).
  `FLOPPY_ALLOW_REMOTE_KEY=1` opts into sending the key over the network; it stays off by default.
- In a container the rescue file goes to the data folder (the mounted volume), not to a Downloads folder that does not exist.
- Confirming the backup now warns when the key was never revealed nor saved in that window.

## 1.0.4 — 2026-09-10
- **Linux support.** The Engine step used to fail on Linux with "install Ollama yourself". FLOPPY now downloads the
  official `ollama-linux-<arch>.tar.zst`, verifies its checksum and extracts it into the FLOPPY folder — no root needed.
- Autostart on Linux through a systemd user service (skipped with a clear message where systemd is absent, e.g. containers).
- Dockerfile, and a Linux/Docker section in the README.
- Downloads create their destination folder, so a cleaned-out data folder no longer breaks the Engine step.
- Local generation budget raised so long answers are no longer cut mid-sentence.

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
