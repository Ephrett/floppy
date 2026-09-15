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

The battery and thermal transition logic was tested with fixtures; no physical unplug/overheat test was performed. Windows/Linux tests are configured in CI but were not run here. No signed installer, release or automatic internet updater is claimed. Changes are local in this repository. The pre-existing prompt/A-B edits in engine/kibble-bot.py were preserved.
