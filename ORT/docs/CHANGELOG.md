# ORT Translation Changelog

## v9.0.0 — Open Architecture Foundation & Clean Project Layout

### Project layout

- Moves the application folder from `ORT/runtime_app` to surface-level `ORT_App` through a safe migration script.
- Keeps large Python environments, CUDA libraries, downloaded models, and audio spool in `ORT_Runtime`.
- Moves documentation, plugin metadata, logs, cache, status, maintenance scripts, release files, exports, and user data into dedicated `ORT/*` folders.
- Removes generated `__pycache__` and `.pyc` files during migration.
- Redirects runtime-generated `logs`, `cache`, `status`, `backups`, and `debug_bundles` from `ORT_App` into the lightweight support tree through Windows junctions.
- Adds root launchers that resolve both v9 `ORT_App` and legacy `ORT/runtime_app` paths.
- Adds a source-light exporter that excludes local/heavy/generated data.

### Open Architecture Lab

- Adds a separate WebUI tab without replacing the ORT Original pipeline.
- Adds a typed provider registry for source, VAD, ASR, streaming, translation, and overlay layers.
- Adds origin and license labels: ORT Native, Adapted Open Source, ORT Integration, ORT Research, and External Connector.
- Adds presets for Original Audio, Original OCR, Japanese Accuracy, Japanese Safe Bridge, Long Dialogue, and OCR Research.
- Adds pipeline diagram, provider availability table, JSON plan export, custom preset storage, and architecture A/B comparison.
- Adds a clean-room Confirmed Prefix implementation and deterministic Local Agreement demonstration.
- Adds optional Silero VAD adapter health checks without bundling models or dependencies into source.
- Adds an event-bus and adapter interfaces as foundations for future provider execution.

### Compatibility

- Based on v8.9.9 R2 F2 long-turn context and Japanese accuracy behavior.
- Existing runtime configuration is preserved and rewritten with v9 layout metadata.
- Existing OCR/audio behavior remains the production baseline.
- Legacy v8 maintenance and release artifacts are organized instead of deleted.
