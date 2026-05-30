# Lite IDN GPU Efficient v8.4

Lite IDN is not CPU-only. In v8.4 it is allowed to use GPU in a controlled way for heavy games.

Goal:
- Stable game FPS.
- Low VRAM pressure.
- Better than CPU-only latency.
- Light Indonesian cleanup without heavy NLP in live loop.

Default recommendation:
- Model: ORTCore Lite IDN V2
- Engine: Hybrid
- Mode: Interval or Auto
- OCR: 50–55%
- IDN Quality: Lite Balanced
- CT2: allowed if `models/ct2_opus_mt_en_id` exists
- CPU fallback: only if VRAM is critically low

The Lite GPU Guard writes status to:
`status/lite_gpu_guard.json`
