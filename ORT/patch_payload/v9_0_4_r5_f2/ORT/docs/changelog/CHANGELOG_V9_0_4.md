# ORT v9.0.4 R5 F2 — Reazon Direct Manifest Download

- Removes Hugging Face snapshot dry-run from the Reazon setup path.
- Downloads only the files required by CPU int8 or CUDA int8-fp32.
- Pins the official ReazonSpeech K2 v2 revision and validates file sizes/SHA-256.
- Resumes interrupted files through HTTP Range and preserves `.part` files.
- Reuses valid legacy Hugging Face snapshot cache files when present.
- Loads Reazon directly from the local Audio model root without a runtime Hub request.
- Verifies CPU and CUDA readiness against device-specific local files.
