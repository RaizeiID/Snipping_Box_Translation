# ORT Translation v8.9.3

**Release:** Audio Tri-Mode & Japanese Quality Update  
**Base:** v8.9.2-R6 Audio Native Crash Isolation Hotfix

## Execution contracts

| Mode | ASR | Translation | Failure policy |
|---|---|---|---|
| CPU | `base`/`small`, CPU INT8 | CPU INT8 | No CUDA probe or allocation |
| GPU | `small`/`medium`, CUDA INT8-FP16 | CPU INT8 | Strict stop; no hidden fallback |
| Hybrid | CUDA primary, CPU fallback | CPU INT8 | CPU replay; one GPU retry; two-strike circuit |

## Japanese quality

- GFL2 Auto language resolves to `ja`.
- Pause-aware capture, adaptive energy pre-gate, pre-roll, speech padding, and Silero VAD.
- One higher-beam retry for borderline results.
- Quality rejection for no-speech, low log probability, high compression, repetition, token density, language mismatch, and promotional hallucinations.
- Conservative GFL2 Audio glossary.
- Preserve-all-clauses Audio translation.

## Runtime boundaries

- Main PyQt overlay process.
- WASAPI capture/VAD process.
- CPU or CUDA faster-whisper ASR process.
- R6 isolated CT2/Argos translation process.

The shared model cache remains under `audio_cpu/models`. The GPU dependencies live
under `audio_gpu/.venv`. OCR behavior and user data are not migrated.
