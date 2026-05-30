# ORT Translation v8.4.3 — Fast OCR Retune & Lite IDN Efficiency Polish

## Implemented
- Fast V1 default OCR lowered to 40% and interval to 45ms.
- Fast V2 default OCR lowered to 45% and interval to 60ms.
- Fast IDN default OCR lowered to 50% and interval to 75ms.
- Fast scheduler thresholds are more aggressive: lower max wait, duplicate hold, progressive commit delay, and image hash hold.
- WebUI interval slider minimum is now 45ms so Fast low-latency defaults are visible.
- Lite IDN GPU Efficient remains active but gets tighter queue/sleep/core caps.
- Lite IDN efficient core profile is reduced by removing live SpellWeaver to avoid heavy live-loop cost.
- Added OCR cleanup entries for noisy GFL2 wide-dialog fragments.

## Not changed
- Fast CT2 path remains unchanged.
- Auto/Interval/Freeze semantics remain unchanged.
- Lite IDN remains the primary v8.4 focus; Fast retune only changes OCR/latency defaults and scheduler caps.

## Compile
- Changed Python files compile with 0 syntax errors.
