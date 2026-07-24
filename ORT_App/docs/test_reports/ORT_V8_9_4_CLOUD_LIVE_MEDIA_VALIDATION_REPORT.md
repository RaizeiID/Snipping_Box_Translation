# ORT Translation v8.9.4 — Cloud Live Media Streaming Validation Report

**Date:** 2026-07-23  
**Base:** ORT Translation v8.9.3  
**Scope:** changed-files release validation without user credentials, models, cache, or runtime data

## Result

The source-level implementation passed compilation and eight regression groups. The Azure integration was exercised with a deterministic fake Speech SDK that accepts a real PCM WAV stream and invokes the same `recognizing` and `recognized` callbacks used by the production sidecar.

This report does not claim a successful connection to Microsoft Azure or real GFL2 translation quality. Those checks require the user's active Azure Speech resource, internet path, Windows WASAPI endpoint, and game audio.

## Automated checks

| Check | Result |
|---|---|
| Compile all runtime Python modules | PASS — 325 modules |
| v8.9.2 core regression | PASS |
| v8.9.2 R2 Guided/Expert UI regression | PASS |
| v8.9.2 R3 Audio CPU regression | PASS |
| v8.9.2 R4 model recovery regression | PASS |
| v8.9.2 R5 model compatibility regression | PASS |
| v8.9.2 R6 native crash isolation regression | PASS |
| v8.9.3 Audio CPU/GPU/Hybrid regression | PASS |
| v8.9.4 Cloud Live Media regression | PASS |

## v8.9.4 contract coverage

- `local`, strict `azure`, and `azure_fallback` resolution.
- `live_media` and `conversation` usage normalization.
- Japanese locale mapping to `ja-JP` and Indonesian target `id`.
- Persistent push-stream construction at PCM signed 16-bit, mono, 16 kHz.
- Interim callback before final callback.
- Interim throttling and duplicate suppression.
- Final replacement without a duplicate overlay line.
- `NO_MATCH` and local quality rejection remain invisible in the translation box.
- Six-second rolling PCM replay and one-way cloud-to-local failover latch.
- Strict Azure does not silently claim a Local engine.
- Azure + Local Fallback selects Azure when both paths are ready and Local Guard when Azure is unavailable.
- Credential presence is represented only as a boolean in status.
- The subscription key is passed to the credential sidecar through stdin, is not placed in launcher arguments or environment variables, and is absent from emitted events in the fake-SDK stream test.

## Deterministic streaming simulation

The sidecar self-test emits:

```text
first_interim_ms=820
final_ms=1840
interim_before_final=True
credential_exposed=False
```

These values are an acceptance fixture proving overlay event order; they are not measured Azure network latency.

The fake-SDK test writes a PCM 16 kHz WAV through the production `_stream_wav` loop. The fake recognizer emits one interim result and one final result through the production event handlers. Both events are parsed from the sidecar protocol, and a sentinel subscription key is verified absent from all captured output.

## Required Windows acceptance test

The release should be evaluated as effective only after all of the following pass on the target laptop:

1. `Simpan & Uji Azure` reports `cloud_connected=True`.
2. GFL2 audio is captured from the endpoint that is actually playing the game.
3. The first useful interim subtitle appears while the character is still speaking.
4. A final subtitle replaces the interim text without creating a duplicate line.
5. `NO_MATCH` and rejected local audio never replace the last useful translation.
6. Network interruption in `azure_fallback` replays the last audio into Local and keeps the overlay open.
7. Strict `azure` stops visibly instead of claiming Local execution.
8. A 30-minute game session records interim latency, final latency, accuracy, cloud cancellation, fallback count, and Azure consumption/cost.

## Known limitations

- Azure Speech usage may incur charges and sends captured audio to Microsoft.
- Cloud latency and accuracy depend on region, connection, source mix, and the Azure model available to the subscription.
- File testing through Azure accepts PCM 16-bit WAV; other formats use the Local engine.
- The local fallback remains segment-based v8.9.3 behavior after failover. The streaming experience is restored on a new Azure session.
- The build environment cannot validate Windows Credential Manager, WASAPI, an RTX 4050, or a live Azure subscription.
