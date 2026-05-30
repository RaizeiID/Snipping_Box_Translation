# ORT Translation v8.5.1 — Numeric ROI OCR & VRAM Guard Hotfix

## Goal
This hotfix is the final dedicated pass for GFL2 numeric OCR before moving to Lite/Lite IDN optimization.

## Numeric OCR policy
v8.5 introduced numeric dual-pass OCR, but logs showed the second pass often scanned too wide and captured UI/progress noise such as `821`, `8261`, `6102`, and `7.18/31.20`. v8.5.1 changes the behavior:

- Use ROI-first digit OCR for wide dialog regions.
- Reject candidates containing UI-like separators `/`, `:`, `;` or long counter-like digits.
- Validate candidates by context: degree/bearing/angle/distance/meter.
- If no safe candidate exists, keep the original text and log known limitation.

## VRAM policy
v8.5 sometimes switched OCR to CPU too aggressively when free VRAM dipped. v8.5.1 applies staged relief:

1. Downscale OCR temporarily.
2. Increase sleep / reduce runtime pressure.
3. Only fallback to CPU when explicitly enabled and sustained critical pressure occurs.

## Development handoff
Remaining number misses are now considered a known minor OCR limitation when the digits are visually unreadable. Next work should prioritize Lite/Lite IDN: naturalized cache, profile tuning, VRAM telemetry, and stable efficient gameplay presets.
