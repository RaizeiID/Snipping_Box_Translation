# ORT v8.9.7 — Continuous Rolling-Partial Real-Time Update

v8.9.7 replaces the local Live Media segment-final path with a rolling-partial path. Active speech is repeatedly recognized and translated before endpointing. Silence/VAD only commits the final result.

Key safeguards:

- `local_live` replaces `local_guard` for Live Media local delivery.
- Latest-only partial snapshots prevent inference backlog.
- CUDA failure falls back inside the same rolling-partial worker.
- Mixed WebUI/Audio versions are blocked.
- A packaged verifier tests version consistency and continuous-speech event flow.
