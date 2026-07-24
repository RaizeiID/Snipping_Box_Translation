# ORT v8.9.7 Continuous Real-Time Validation Report

## Root cause confirmed from user log

- WebUI process: v8.9.5.
- Audio process: v8.9.6.
- Requested engine: Azure fallback.
- Effective engine: local guard.
- Cloud ready: false.
- Local ASR segments reached 8.0 seconds.
- CUDA failed because `cublas64_12.dll` could not be loaded.

The observed session therefore did not exercise cloud interim recognition and did not contain a local partial-recognition path.

## Deterministic integration test

Input: four seconds of uninterrupted synthetic speech followed by silence only for final commit.

Expected:

- At least three partial subtitle revisions before final.
- First partial based on less than one second of audio.
- No pause/end-of-turn required for first translation.
- Final result emitted after endpoint/flush.

Observed:

- First partial audio position: 300 ms.
- Partial translation revisions before final: 4.
- Final count: 1.
- Pause required for first translation: false.

## Additional contract tests

- Local engine resolves to `local_live`.
- Azure fallback resolves to `local_live` when cloud is unavailable.
- Azure fallback resolves to Azure when cloud is ready.
- Simulated `cublas64_12.dll` failure switches to CPU and still returns a transcript through the rolling-partial adapter.
- Root, ORTCore, and TitanCore versions must all equal v8.9.7.

## Scope limitation

The container does not provide Windows WASAPI, the user's Faster-Whisper model cache, Azure credentials, NVIDIA driver, CUDA DLLs, or PyQt desktop display. The test validates program control flow and event integration deterministically; hardware/audio accuracy and real wall-clock latency must be verified on the user's Windows laptop.
