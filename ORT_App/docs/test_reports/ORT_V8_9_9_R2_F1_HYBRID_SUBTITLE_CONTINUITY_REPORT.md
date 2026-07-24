# ORT v8.9.9 R2 F1 Validation Report

Validated contracts:

- Hybrid Japanese can promote CPU Guard to Hybrid only when the GPU runtime probe is ready and a fresh `validated_cuda_small.json` marker reports successful real inference.
- The active model must still pass its own CUDA preflight.
- CPU fallback remains enabled.
- Punctuation-only ASR output is suppressed before translation.
- Guard diagnostics do not replace the visible subtitle.
- First meaningful partial is accepted immediately.
- Minor rolling revisions are coalesced; meaningful updates are not converted to final-only output.
- EMPTY/NO_SPEECH reject telemetry is throttled.
- Existing R2 GPU/CPU regression suite remains PASS.
