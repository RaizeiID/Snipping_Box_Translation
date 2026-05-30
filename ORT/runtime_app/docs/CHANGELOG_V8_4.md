# ORT Translation v8.4 Changelog

## Type
Major foundation update after v8.3.4 Fast lock.

## Main changes
- Added Lite GPU Efficient guard for Lite/Lite IDN heavy-game usage.
- Lite/Lite IDN no longer default to slow CPU-only behavior for heavy games when GPU can be used safely.
- Added shared IDN Quality Layer for IDN naturalization architecture.
- Added Learning Quarantine to prevent OCR noise from entering NPC/unique-term learning.
- Added GFL2 OCR dictionary skeleton for typo/name/noise corrections.
- Added Diagnose & Repair Center in Runtime & Tools.
- Added Lite GPU Guard status in Runtime & Tools.
- Added release hygiene: removed packaged `__pycache__`, `.pyc`, logs, reports, and backups from the full release folder.
- Added build release packaging helper.

## Fast lock
Fast V1, Fast V2, Fast IDN, Fast CT2, Auto/Interval semantics, and per-model preset behavior from v8.3.4 are treated as locked for v8.4. Fast IDN remains a compatibility profile, not the main v8.4 optimization target.

## Lite IDN direction
Lite IDN is based on the Lite pipeline plus IDN Quality Light/Balanced. It prioritizes stable resource use and game FPS, not raw translation speed.
