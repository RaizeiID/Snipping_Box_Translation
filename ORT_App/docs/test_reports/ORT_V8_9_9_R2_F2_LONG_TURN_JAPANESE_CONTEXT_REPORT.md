# ORT v8.9.9 R2 F2 Validation Report

## Evidence from user logs

Eight logs were reviewed. Japanese GPU sessions had median ASR latency around 319–682 ms, but Japanese Speed/Normal usually emitted only 3–4 words per hypothesis and generated many `EMPTY,NO_SPEECH` rejects. English GPU sessions had median ASR latency around 126–130 ms and produced longer hypotheses, but still showed 15–69 stale transcript drops and 7–15 superseded translations during long dialogue.

The failure mode was therefore primarily context/queue segmentation, not insufficient GPU throughput.

## Tests

- Python compilation for changed source files.
- Existing R2 GPU/CPU realtime regression.
- Existing R2 F1 hybrid/subtitle continuity regression.
- New rolling-turn overlap merge regression.
- Three-second continuous speech with one-second rolling window retains one segment ID.
- Japanese Specialist Normal partial/final uses beam 2/3.
- Previous-final grace contract exists in parent translation coordinator.
- Packaged deterministic self-test continues to emit four updates before final without requiring pause.

## Result

PASS in deterministic package environment. Real Japanese accuracy must still be validated against the same anime/game scene after installation because model output depends on audio mix, voice clarity, and the local GPU runtime.
