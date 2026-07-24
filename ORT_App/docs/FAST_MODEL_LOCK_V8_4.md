# Fast Model Lock for v8.4

Fast behavior is considered stable after v8.3.4 and must not be changed accidentally during v8.4 Lite IDN/OCR/Diagnose work.

Locked items:
- Fast CT2 activation path using `models/ct2_opus_mt_en_id`.
- Fast V1 = speed-first.
- Fast V2 = balanced.
- Fast IDN = compatibility profile based on Fast V2 + light IDN naturalization.
- Auto story mode progressive behavior.
- Interval mode as automated Freeze behavior.
- Per-model autosave/default reset UX.
- Fast-specific bridge postprocess guard.

Allowed changes:
- Bug fixes that do not alter runtime semantics.
- Documentation and diagnostic reporting.
- Regression tests.

Not allowed unless explicitly requested:
- Retuning Fast V1/V2/Fast IDN latency, OCR, scheduler, or postprocess defaults.
- Changing Fast fallback behavior.
- Making Fast IDN the main IDN optimization target.
