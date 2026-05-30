# ORT Translation v8.4.5 — Final Lite IDN Recommendations

v8.4.5 is the final v8.4 polish before v8.5. The goal is not to make Lite IDN the fastest model, but to make it efficient, stable, and less error-prone for heavy games.

## Final Lite/Lite IDN identity

- V1: Ultra Efficient, OCR 40%, lowest resource use.
- V2: Recommended Efficient Balanced, OCR 45%, default for heavy games.
- V3: Balanced Quality, OCR 50%, recommended when numbers/technical dialog matter.
- V4: Quality Safe, OCR 55%, use when VRAM is still safe.
- V5: Quality/Clean Output, OCR 60%, not the heavy-game default.

## Recommended usage

For GFL2 story/dialog with wide dialog snip:
- Lite IDN V2 for efficiency.
- Lite IDN V3 for better number/text accuracy.
- Keep wide-dialog filtering ON.
- Keep OCR noise reject ON.
- Use Fast IDN if responsiveness matters more than VRAM.

For heavy open-world games:
- Lite IDN V1 or V2.
- GPU Efficient/Hybrid.
- Avoid V5 unless VRAM is healthy.

## Number-safe OCR guard

v8.4.5 adds a rule-based number guard that:
- normalizes common digit OCR confusions, such as `I.5` to `1.5` and `18O degrees` to `180 degrees`;
- rejects numeric UI garbage such as `11+1115141`, `30,L`, and `TIIII`;
- preserves useful numeric tokens through translation where possible.

This improves number handling but does not replace true digit-specialized OCR. If OCR never captures a number, the guard cannot reconstruct it reliably.

## v8.5 handoff

v8.5 should focus on:
- adaptive OCR for Lite/Lite IDN;
- numeric dual-pass OCR for detected numbers/units;
- IDN naturalized cache;
- smarter GFL2 wide-dialog line filtering;
- Analyze Last Session recommendations;
- per-game Lite profile tuning;
- deeper Lite resource/VRAM profiling.
