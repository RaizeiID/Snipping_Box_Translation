# ORT Translation v8.9.2-R4

**Release:** Audio Model Recovery Hotfix  
**Base:** v8.9.2-R3 Audio CPU First-Test

## Fixed

- Replaced the unsafe `model.bin`/marker readiness shortcut with a complete local-model inspection.
- Required `config.json`, `model.bin`, `preprocessor_config.json`, `tokenizer.json`, and one valid `vocabulary.*` file.
- Added a canonical per-profile local model folder.
- Added three download attempts while preserving and reusing the existing cache; retries use one transfer worker to reduce connection-reset pressure.
- Added explicit partial-snapshot diagnostics for the WebUI and launcher.
- Skipped dependency reinstallation when the isolated Audio environment is already healthy.
- Prevented concurrent Audio setup jobs from writing the same model cache.
- Loaded validated models with `local_files_only=True` so normal Audio start is offline-safe.

## Preserved

- Guided/Expert UI layout from R2.
- WASAPI and file-test sources from R3.
- Normal/VAD processing and Speed/Normal/Accurate profiles.
- CPU INT8, bounded queues, generation guards, and OCR/Audio exclusivity.
- Voice Isolation remains unavailable rather than being represented as active.
