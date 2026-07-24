# ORT Translation v8.8.3 — GFL2 Recording Stability & Overlay Commit Gate

## Summary
v8.8.3 is a behavior-focused refactor for GFL2 long story recording. It keeps OCR and CT2 translation fast, but makes the final overlay render more selective so subtitle text does not flicker on every tiny OCR/typewriter change.

## Added
- `app/runtime/ct2_path_resolver.py`: automatically resolves CT2 model folders from `ORT/runtime_app/models`, root `models`, local runtime model folders, and environment variables.
- `app/runtime/render_signature.py`: lightweight visual signature and similarity utilities for render-level dedupe.
- `app/runtime/overlay_commit_gate.py`: final visual commit gate before overlay replacement.
- `app/runtime/recording_telemetry.py`: lightweight counters and periodic summary lines for long GFL2 sessions.
- `tools/v8_8_3_regression_test.py`: regression tests for CT2 path resolution and overlay commit suppression.

## Changed
- Normal new-turn clearing no longer blanks the overlay in Auto Story; it keeps the last good subtitle until the next meaningful payload is ready.
- Speaker-only fragments are suppressed in Auto/Recording so the overlay does not flicker to a speaker-only state.
- Duplicate cache hits and visually-similar translations are suppressed before rendering.
- Final/completeness updates may override the minimum visible time when they provide a better/full result.
- FastModelManager and translation engine now use the CT2 path resolver.
- Version labels updated to v8.8.3.

## Not changed
- No heavy semantic gate is added to preview.
- No new model is introduced.
- Auto is not converted into Freeze; it remains responsive.
- Structure from v8.8.1 GitHub-safe layout is preserved.
