# ORT Translation v8.9.4

**Release:** Cloud Live Media Streaming Update  
**Base:** v8.9.3 Audio Tri-Mode & Japanese Quality Update

## Delivery engines

| Engine | Primary path | Display behavior | Failure policy |
|---|---|---|---|
| Local | faster-whisper + ORTCore | Final per local segment | Existing CPU/GPU/Hybrid rules |
| Azure | Azure Speech Translation | Interim updates, then final lock | Visible stop; no hidden local switch |
| Azure + Local Fallback | Azure primary, Whisper local recovery | Interim/final while cloud is healthy | Replay last six seconds; lock session to Local |

## Live Media

- Captures one-way Windows system audio through WASAPI loopback.
- Streams signed PCM 16-bit, mono, 16 kHz through a persistent Azure Speech connection.
- Uses fixed source locale for interim translation; GFL2 defaults to `ja-JP`.
- Translates directly to Indonesian target `id`.
- Shows interim text in a distinct visual state and replaces it with the final result.
- Drops `NO_MATCH` and noise without changing the last usable overlay.

## Security and isolation

- Azure dependencies live under `audio_cloud/.venv`.
- The subscription key is accepted only by the local WebUI credential form and sent to the credential sidecar over stdin.
- The key is stored through Windows Credential Manager and never placed in process arguments, patch files, preferences, status, or logs.
- Cloud runtime/configuration remains outside the changed-files patch.

## Local recovery

- A six-second PCM rolling buffer is retained in memory.
- On fatal cloud cancellation, a temporary replay segment is written inside the session spool.
- The parent waits for the cloud sidecar to exit before starting local capture.
- Failover is one-way for the session to prevent connection flapping.
- Existing Hybrid GPU→CPU replay and two-strike CUDA circuit behavior remains active inside the local fallback.
