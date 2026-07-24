ORT Translation v8.5 — Numeric Dual-Pass OCR & Lite Optimization Foundation

Base version: v8.4.5 final
Type: changed-files patch
Date: 2026-05-20

Main goals:
- Treat v8.4.5 as final v8.4 and open v8.5 directly.
- Address the observed GFL2 issue where tactical numbers disappear from OCR text before translation.
- Reduce cache poisoning for lines that look like they should contain numbers but do not.
- Keep Lite/Lite IDN OCR ladder from v8.4.4/v8.4.5, but add numeric dual-pass on demand instead of raising all OCR globally.
- Begin Lite optimization foundation with tighter queue caps and clearer Lite GPU Guard telemetry.

Implemented:
1. Numeric Dual-Pass OCR trigger
   - Detects number-gap contexts such as bearing/elevation/degrees/distance/meters.
   - If a number appears missing, OCRWorker runs a digit-focused second pass on the same frame.
   - Uses contrast/sharpen/threshold variants and EasyOCR allowlist where supported.
   - Conservatively merges detected numeric candidates into text only for high-confidence gaps.

2. Number gap cache protection
   - TranslationEngine now skips scoped/vault cache lookup and cache store for text that appears to be missing tactical numbers.
   - This prevents stale translations of incomplete lines like "bearing elevation degrees, distance meters" from dominating future frames.

3. Lite GPU Guard v8.5 foundation
   - Slightly tighter Lite queue caps.
   - Numeric dual-pass is enabled on demand for Lite/Lite IDN.
   - Status text documents v8.5 numeric dual-pass behavior.

4. Version and tracking
   - Runtime and WebUI labels updated to v8.5.
   - Docs updated with v8.5 recommendations and compile report.

Known limitations:
- Numeric dual-pass can only recover numbers that are visually present and readable in the captured frame.
- If the number is fully missing/blurred/occluded in the screenshot, the system will not invent it.
- OCR second pass is deliberately conservative to avoid inserting wrong tactical numbers.

Next priorities for v8.5.x:
- ROI-based numeric OCR around units instead of whole dialog box.
- Naturalized IDN cache.
- VRAM telemetry separating OCR/CT2/runtime/game overhead.
- Per-game Lite profile tuning.
- Analyze Last Session recommendations for numeric OCR failures.
