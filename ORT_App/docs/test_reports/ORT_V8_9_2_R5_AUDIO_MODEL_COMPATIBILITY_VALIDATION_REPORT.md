# ORT v8.9.2-R5 Audio Model Compatibility Validation Report

## Target regression

R4 classified a complete official `faster-whisper-tiny` layout as incomplete because it required `preprocessor_config.json`. The official tiny, base, and small CTranslate2 repositories do not contain that file, while faster-whisper uses default feature-extractor settings when it is absent. Repeated setup attempts therefore could never make R4 ready.

## Automated coverage

- Official tiny/base/small-style layout acceptance without `preprocessor_config.json`.
- Optional-file diagnostics without a false `MODEL_INCOMPLETE` result.
- Continued rejection when `config.json`, `model.bin`, `tokenizer.json`, or `vocabulary.*` is missing or invalid.
- Complete cached model bypasses network download.
- Local `WhisperModel` construction still runs before setup success.
- CPU INT8, the 3/4/6-thread profile ladder, one worker, and `local_files_only=True` remain intact.
- Compatibility with v8.9.2 core, R2 UI, R3 Audio, and R4 model-recovery contracts.

## Source verification

- The official Systran tiny, base, and small repository file lists contain the four required core assets and no `preprocessor_config.json`.
- faster-whisper's model loader returns default feature-extractor settings when the optional file is absent.

## Result

- Python compilation: PASS.
- v8.9.2 core regression: PASS.
- v8.9.2-R2 Guided/Expert UI regression: PASS.
- v8.9.2-R3 Audio CPU regression: PASS.
- v8.9.2-R4 model recovery regression: PASS.
- v8.9.2-R5 official-layout and offline-load regression: PASS.
