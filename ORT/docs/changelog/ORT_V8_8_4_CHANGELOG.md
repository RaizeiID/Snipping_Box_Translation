# ORT Translation v8.8.4 — Final Completeness & Never-Empty Overlay

## Purpose
v8.8.3 successfully reduced flicker with an overlay commit gate, but live tests showed two remaining problems:

1. Some translations stayed shorter than the full game dialogue because `MIN_VISIBLE`/duplicate suppression could win over a later, more complete source.
2. In some moments the overlay box could appear empty while the character was still speaking and the game text had already finished.

v8.8.4 addresses those without returning to v8.7.8-style stutter.

## Main changes
- Final Complete Override: longer/stable source can override `MIN_VISIBLE` and similar-output suppression.
- Never Empty During Dialogue: held/new-turn/short fragments re-use the last visible subtitle rather than blanking the overlay.
- Render signature improvements for common OCR variants observed in GFL2 logs.
- Freeze skips the Auto Story scheduler so snapshot/freeze usage behaves more like a final-first mode.
- Recording telemetry now exposes `final_complete_ratio`, `last_good_reused`, and `source_longer_but_suppressed`.

## What did not change
- No new heavy semantic model was added.
- CT2 preview/final path remains the default safe path.
- Argos is not reintroduced for story fallback when CT2 is available.
- Auto Story still processes quickly; only visual rendering is more selective and completeness-aware.

## Recommended next evaluation
Run a 10–20 minute GFL2 story test first. If stable, continue with the planned 1–2 hour recording log for v8.8.5/v8.9 analysis.
