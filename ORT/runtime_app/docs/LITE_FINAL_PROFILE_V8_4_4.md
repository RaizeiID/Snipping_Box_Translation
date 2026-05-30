# Lite Final Profile v8.4.4

This patch finalizes the Lite and Lite IDN identity before the next major Lite optimization pass.

## OCR ladder

| Model level | Role | OCR | Notes |
|---|---|---:|---|
| V1 | Ultra Efficient | 40% | Lowest VRAM/OCR load; for heavy games and tight VRAM. |
| V2 | Recommended Efficient Balanced | 45% | Recommended default for Lite/Lite IDN heavy-game use. |
| V3 | Balanced Quality | 50% | Better OCR while still resource-capped. |
| V4 | Quality Safe | 55% | Higher quality, still guarded by GPU Efficient. |
| V5 | Quality | 60% | Cleanest Lite OCR target; not default for heavy games. |

Latencies from v8.4.3 are preserved so this patch separates quality/resource identity without changing the scheduler feel again.

## Lite IDN

Lite IDN remains slightly heavier than Lite because it adds IDN Quality Layer processing, but this processing should stay light/cache-aware.

## GPU Efficient policy

The Lite GPU Guard is now level-aware. If VRAM is healthy, V5 may use OCR 60%. If VRAM is tight, unknown, or the game is very heavy, OCR is downscaled safely.

## v8.5 handoff

The next optimization pass should focus on Lite/Lite IDN deeper runtime tuning, adaptive OCR, IDN result caching, Analyze Last Session recommendations, and OCR noise learning.
