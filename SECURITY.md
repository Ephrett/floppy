# Security policy

FLOPPY creates and stores a private key on the user's machine. Please treat anything that could expose that key, or make the app talk to an
unexpected destination, as a security issue.

## Reporting

Use GitHub's **private vulnerability reporting** on this repository ("Security" tab → "Report a vulnerability"). Do not open a public issue for
anything exploitable. You will get an answer within a week, and credit in the release notes if you want it.

## In scope

- Key handling: generation, storage (`engine/seed.hex`, owner-only permissions), the local-only backup endpoint.
- The local server: loopback binding, `X-Floppy` CSRF header, `Host` validation, static file routing.
- Downloads: SHA-256 verification of Ollama installers against the official release, model downloads through Ollama.
- The frozen builds (PyInstaller) and the installers (DMG, Inno Setup).

## Out of scope

- The kibble board and technocore.chat themselves (independent services).
- Ollama and the models (report upstream).
- Behaviour of forks.
