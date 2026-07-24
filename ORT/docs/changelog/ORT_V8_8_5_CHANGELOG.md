# ORT Translation v8.8.5 — Turn Finalizer & OCR Churn Rescue

v8.8.5 focuses on the remaining issues after v8.8.4:

- translation output sometimes stayed shorter than the full game dialog;
- `source_longer_but_suppressed` remained too high;
- `defer_clear` could still cause blank/stale overlay moments;
- low-OCR profiles (40–45%) produced heavy OCR churn;
- cache could be too trusting toward corrupted OCR frames.

## Implemented

1. Turn Finalizer
   - Tracks best source/translation per turn.
   - Forces final-complete commit when stable/due.
   - Prevents a turn from ending only with a short preview.

2. OCR Churn Rescue
   - Repairs common glyph confusions without raising global OCR percent.
   - Detects low-OCR churn and corrupted fragments.
   - Holds heavily corrupted short fragments instead of letting them overwrite the turn.

3. Bad Cache Shield
   - Prevents heavily corrupted low-OCR source from being treated as stable final cache.
   - Downgrades suspicious cache hits to preview-like behavior.

4. Overlay Gate Improvements
   - Valid longer source can override `MIN_VISIBLE`.
   - Short/noisy new-turn churn keeps the last good overlay.
   - Hard repaint last-good overlay when candidate is held/suppressed.

## Intended user-facing result

- More complete translation output.
- Fewer blank overlay moments.
- Low-OCR models remain useful as entry-level stress tests.
- Auto should stay responsive without returning to v8.7.8-style stutter.
