# ORT v8.9.9 R1 - Live Preview & CPU Dual-Stream Performance Hotfix

- Restored English/source preview by default (`ORT_AUDIO_SHOW_SOURCE=1`).
- Added `FAST_PREVIEW_MODEL_LOADING/READY` and `JAPANESE_DUAL_STREAM_ACTIVE`.
- Normal/Instant Japanese Specialist on CPU now uses fast provisional ASR for the live path instead of synchronously waiting 7-15 seconds for Kotoba.
- Accurate profile retains direct Kotoba CPU inference.
- Background specialist correction is opt-in only to avoid competing with the live CPU path.
- Added deterministic preview/performance regression and R1 verifier.

