# ORT v8.9.2-R4 Audio Model Recovery Validation Report

## Target regression

R3 could accept an incomplete Hugging Face snapshot when `model.bin` or a stale prepared marker existed. The observed failure contained a complete weight file but lacked `config.json`, `tokenizer.json`, and `vocabulary.txt`, then stopped when the Hub connection was interrupted.

## Automated coverage

- Partial snapshot rejection even when `model.bin` exists.
- Complete local model acceptance only after all required assets exist.
- Interrupted first download followed by a successful retry into the canonical folder.
- Existing cache root propagation for reuse/resume.
- Single-worker recovery transfer after the first interrupted attempt.
- Offline-only model loading after setup.
- CPU INT8 and one-worker runtime contract.
- Stale marker bypass removal.
- Dependency-install skip on a healthy Audio environment.
- Concurrent setup lock contract.
- UI distinction between dependency readiness and model readiness.
- Compatibility with v8.9.2 core, R2 UI, and R3 Audio contracts.

## Environment boundary

The repository test environment does not reproduce the user's Windows WASAPI driver or the external Hugging Face transfer. Network recovery is therefore tested with a deterministic interrupted-download simulation. The final first-run download and WASAPI capture still require validation on the user's Windows device.

## Result

- 312 Python modules compiled: PASS.
- v8.9.1 compatibility regression: PASS.
- v8.9.2 core regression: PASS.
- v8.9.2-R2 Guided/Expert UI regression: PASS.
- v8.9.2-R3 Audio CPU regression: PASS.
- v8.9.2-R4 model recovery regression: PASS.
- Interrupted-download retry simulation: PASS.
- Offline-only local model-load simulation: PASS.
- Changed-files comparison: 19 required files, 0 missing, 0 extra, 0 byte mismatches.
- Patch installation over a clean v8.9.2-R3 copy: PASS.
