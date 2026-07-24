# ORT Translation v8.6 — IDN Quality Layer & IDN Model Optimization

## Summary
v8.6 starts the IDN-focused phase. The update does not retune Fast or Lite timing. Instead, it improves Indonesian output quality through a shared deterministic IDN Quality Layer used by Fast IDN, Lite IDN, and Normal IDN.

## IDN Mode Mapping
- Fast IDN: `fast_light`
- Lite IDN V1: `lite_light`
- Lite IDN V2: `lite_balanced`
- Lite IDN V3: `balanced`
- Lite IDN V4: `natural` with optional controlled V4 Online Assist
- Lite IDN V5: `quality`
- Normal IDN V1: `lite_light`
- Normal IDN V2: `balanced`
- Normal IDN V3/V4: `natural`
- Normal IDN V5: `quality`

## Implemented
- Shared IDN Quality Layer with Light/Balanced/Natural/Quality modes.
- Deterministic terminology consistency for game/story terms.
- v8.6 naturalized cache versioning (`ORT_IDN_CACHE_VERSION=v8_6`).
- Fast IDN naturalizer now delegates to the shared `fast_light` IDN layer.
- RuntimeBridge avoids duplicate IDN quality passes when TranslationEngine performs the v8.6 IDN pass.
- V4 Online Assist remains offline-first and controlled.

## Preserved from v8.5
- Fast V1/V2/Fast IDN latency and OCR tuning.
- Lite/Lite IDN OCR ladder and Lite GPU Efficient behavior.
- Numeric OCR remaining misses are treated as minor known limitation unless a regression appears.

## Next recommendation
After v8.6 testing, optimize IDN terminology profiles per game, add a user-editable glossary, and add Analyze Last Session scoring for IDN quality/consistency.
