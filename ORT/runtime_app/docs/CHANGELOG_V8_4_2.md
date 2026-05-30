# ORT Translation v8.4.2 — Lite IDN Efficiency Tuning Patch

## Summary
v8.4.2 optimizes Lite/Lite IDN after v8.4 testing showed that CT2 translation was already fast, but the Lite IDN presets were too conservative and could lag behind story text. The patch lowers Lite IDN latency, caps resource usage more aggressively, adds wide-dialog OCR filtering, and keeps Fast behavior locked.

## Changed
- Lite IDN V2 is now the recommended balanced-efficient default.
- Lite IDN V5 is treated as quality-safe, not as the default heavy-game preset.
- Lite/Lite IDN now use dedicated runtime core profiles instead of the heavier safe-game profile.
- Lite GPU Efficient uses stricter OCR/queue/CPU caps to protect VRAM and FPS.
- Runtime bridge sleep floor for Lite GPU Efficient is lower so the pipeline feels less delayed.
- GFL2 wide dialog boxes are accepted; the program filters internal noise rather than requiring a tighter crop.

## Added
- `lite_efficient` and `lite_idn_efficient` core profiles.
- OCR noise rejection before queue/cache/translation.
- Wider OCR typo dictionary for GFL2 story artifacts.
- `OK_WIDE_DIALOG` region status for large GFL2 dialog-box captures.

## Presets
- Lite IDN V1: 260ms, OCR 48%, ultra efficient.
- Lite IDN V2: 330ms, OCR 50%, recommended efficient balanced.
- Lite IDN V3: 390ms, OCR 52%, balanced quality.
- Lite IDN V4: 430ms, OCR 53%, hybrid safe.
- Lite IDN V5: 480ms, OCR 55%, quality safe.

## Validation
Changed Python files compile successfully with 0 syntax errors.
