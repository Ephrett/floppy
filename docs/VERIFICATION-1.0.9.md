# FLOPPY 1.0.9 — local verification

Flow: settings and dashboard → local HTTP API → persisted options / engine records → dashboard.

Verified on macOS in a separate FLOPPY_SIMULATE=1 folder and port 8793:

- Browser renders dashboard and settings, with visible simulation badge; no console warnings/errors observed.
- Mains-only switch saves via /api/options and remains enabled in the UI.
- Changing cadence to 75 persists options.cadence=75; /api/stats returns cap_per_hour=75 separately from rate60=9 simulated deliveries.
- Play starts fake_worker; its log/dataset/attestations feed dashboard deliveries and votes.
- Pause returns running=false and worker_status=paused while retaining nine deliveries.
- Missing temperature sensor is explicitly described in settings.
- 11 regression tests pass: vote attribution/deduplication, held responses, engine content upgrade with identity preserved, power/thermal interaction, manual pause, generation checks and duplicate-delivery protection.
- JavaScript syntax check, Python compilation and git diff whitespace checks pass.

The battery and thermal transition logic was tested with fixtures; no physical unplug/overheat test was performed. CI run [34948181012](https://github.com/Ephrett/floppy/actions/runs/34948181012) at source commit `1e06296` passes all 11 tests on macOS, Windows and Linux. Packaged Mac arm64 and Windows x64 applications boot successfully with empty isolated profiles; bundled engine files, HTTP API and UI are checked. The DMG integrity check passes. The Windows installer is also executed silently and the installed application passes the same startup checks. Installers remain unsigned for distribution; there is no automatic internet updater. The pre-existing prompt/A-B edits in engine/kibble-bot.py were preserved.
