# ORT Translation v8.9.2-R5

**Release:** Audio Model Compatibility Hotfix  
**Base:** v8.9.2-R4 Audio Model Recovery Hotfix

## Fixed

- Corrected the R4 validator that required `preprocessor_config.json` even though the official Systran tiny/base/small CTranslate2 model repositories do not ship it.
- Required only the offline runtime assets used by these profiles: `config.json`, `model.bin`, `tokenizer.json`, and one valid `vocabulary.*` file.
- Retained `preprocessor_config.json` as optional metadata and reported its absence without failing readiness.
- Allowed an already complete cached model to skip the download path and proceed directly to local model construction.
- Kept actual `WhisperModel` loading as the final setup gate before Audio is reported ready.

## Preserved

- R4 partial-cache rejection for missing core assets, retry behavior, canonical model folders, and setup lock.
- CPU INT8, offline-only start, bounded queues, and mutually exclusive OCR/Audio sources.
- Guided/Expert UI, user settings, Audio profiles, VAD/Normal processing, and WASAPI device selection.
- Voice Isolation remains unavailable rather than being represented as active.
