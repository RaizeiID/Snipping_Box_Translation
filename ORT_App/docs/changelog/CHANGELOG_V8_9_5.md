# ORT Translation v8.9.5 — Real-Time Video Translation

This release converts Azure Live Media from technically continuous streaming into a phone-style one-line live subtitle workflow.

## Runtime changes

- 20 ms PCM chunks.
- Confirmed connection before `STREAMING`.
- Japanese endpoint profiles: Instant 280 ms, Balanced 350 ms, Accurate 480 ms.
- Maximum phrase duration to reduce multi-speaker merging.
- Partial-result coalescing and result-ID-aware final deduplication.
- Final callback drain after EOF/Stop.
- Japanese GFL2 PhraseListGrammar expansion.
- Rolling replay tail safety.
- Latency and session telemetry.
- Verified credential deletion reporting.

## Compatibility

Apply over a complete ORT v8.9.4 installation. OCR and Local Audio runtimes are preserved. No API key, runtime environment, model, cache, log, status, or user preference is included.
