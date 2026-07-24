# ORT Open Architecture Lab

The Lab is an isolated experimental architecture layer. It does not import or copy complete third-party applications into the production ORT pipeline.

## Layers

1. Source provider — OCR, WASAPI, multi-region OCR, or external text connector.
2. VAD provider — ORT RMS/VAD, Silero ONNX, or hybrid trigger/confirmation.
3. ASR provider — ORT Faster-Whisper, Japanese Specialist, or external worker adapter.
4. Streaming policy — ORT Rolling Turn Context, Confirmed Prefix, or Local Agreement.
5. Translation route — ORTCore, Japanese bridge, direct Japanese route, or external API.
6. Overlay provider — ORT Overlay.

## Safety boundary

Selecting a Lab preset only writes an experiment plan. It does not start a second hidden OCR/audio process and does not modify the Original pipeline configuration.

## Planned implementation order

1. Silero VAD adapter and model installer.
2. Confirmed-prefix integration with recorded/offline replay.
3. Per-turn queue and A/B metrics.
4. Direct Japanese transcript → Indonesian provider.
5. Multi-region OCR adapter.
6. External GPL connector bridge.
