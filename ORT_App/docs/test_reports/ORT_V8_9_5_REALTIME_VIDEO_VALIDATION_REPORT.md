# ORT v8.9.5 Real-Time Video Validation Report

## Static validation

- All changed Python files compile successfully with Python 3.13.
- No API key is written into process arguments, project files, logs, or the patch.
- Patch metadata and version files are aligned to v8.9.5.

## Behavioral regression

Passed:

1. Japanese Instant/Balanced/Accurate endpoint policy ordering.
2. 20 ms live-media chunk contract.
3. Interim callback throttling and same-line revision.
4. Stale interim rejection after final.
5. Same sentence with a different result ID remains displayable.
6. Oversized rolling payload preserves the newest one-second tail.
7. State ordering: CONNECTING before CLOUD_CONNECTED before STREAMING.
8. Delayed final callback after WAV EOF is retained.
9. Credential backend failure returns an error rather than false success.
10. v8.9.4 cloud regression remains compatible with v8.9.5.

## Validation boundary

The Azure SDK was exercised through a deterministic fake recognizer. Real latency, billing, network behavior, WASAPI behavior, Japanese recognition, and GFL2/film accuracy require testing on the user's Windows laptop with a valid Azure Speech resource. The release emulates phone-style live subtitle behavior but does not reproduce a proprietary smartphone translation engine.
