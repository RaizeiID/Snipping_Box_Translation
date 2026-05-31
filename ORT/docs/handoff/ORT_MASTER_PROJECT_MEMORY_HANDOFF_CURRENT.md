# ORT Master Project Memory Handoff — Current through v8.8.5

## Current version
v8.8.5 — Turn Finalizer & OCR Churn Rescue

## Latest project direction
The project is in incremental runtime behavior refactoring after the v8.8.1 structural cleanup. v8.8.3 reduced flicker using an overlay commit gate. v8.8.4 added final-completeness and never-empty overlay, but logs showed final_complete_ratio remained low, source_longer_but_suppressed remained high, and low-OCR profiles still caused churn. v8.8.5 focuses on making each turn finish with a complete final render while keeping Auto responsive.

## Important principle
Low-OCR models such as Lite V1, Lite IDN V1, and other 40–45% OCR profiles must continue to be tested and optimized. They are entry-level/stress targets, not disposable modes. The system should improve their output using software-side cleaning, churn detection, cache shielding, and per-turn source handling without simply raising global OCR.

## v8.8.5 additions
- Turn Finalizer.
- OCR Churn Rescue.
- Bad Cache Shield.
- Source Longer Must Win.
- Hard repaint last-good overlay.
- Extra telemetry for final completeness and low-OCR analysis.

## Next likely focus
Use v8.8.5 logs to decide v8.8.6. If issues remain, prioritize mode policy separation for Interval/Freeze and deeper turn lifecycle refactoring, not heavy semantic preview gates.
