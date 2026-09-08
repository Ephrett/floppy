# Contributing to FLOPPY

Thanks for helping. A few rules keep the project safe for the people who run it on their machines.

## Ground rules

- **Nothing personal in the repo.** No keys, tokens, seeds, real DIDs, machine names or personal paths, in code, tests, issues or screenshots.
- **Measured, not promised.** Any number shown to the user must be measured on their machine or read from the public board, and labelled with
  its window ("over 24 h", "last hour"). Presets are labelled as presets.
- **Both languages.** Every UI string lives in the `T` dictionary of `ui/index.html`, in `fr` and `en`. Backend journal messages use `L(fr, en)`.
- **Local only.** The app must keep binding `127.0.0.1`, keep the `X-Floppy` header check and the `Host` validation, and must not add network
  destinations without discussing it in an issue first.
- **No airdrop framing.** The README wording about the board and the airdrop is deliberate; keep it.

## Before opening a pull request

1. Run in simulation: `FLOPPY_HOME=~/FLOPPY-dev FLOPPY_PORT=8790 FLOPPY_SIMULATE=1 python3 app.py --open` and walk the five steps.
2. Check the interface still parses: `node -e "const h=require('fs').readFileSync('ui/index.html','utf8');new Function(h.match(/<script>([\s\S]*)<\/script>/)[1])"`.
3. Check the backend: `python3 -c "import ast;ast.parse(open('app.py').read())"`.
4. If you touched a build script, build on your OS and launch the frozen app once on an empty `FLOPPY_HOME`.
5. Describe what you measured in the PR (OS, machine, numbers), not what you expect.

## Good first issues

- Linux support (Ollama install script, autostart via systemd user unit).
- English translation of the engine's log lines (`engine/kibble-bot.py`).
- A "work only when plugged in" mode (the toggle exists, greyed out).
- Automated tests for `app.py` tasks using `FLOPPY_SIMULATE=1`.

## Style

Single-file backend and single-file UI on purpose: easy to audit. Comments may be in English or French. Keep functions short and names explicit.
