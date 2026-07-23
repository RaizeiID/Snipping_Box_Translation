# ORT v8.8.9 Strategy Memory — Prediction Guard Activation & Commit Stability

## User-confirmed direction
The user confirmed that the OCR readability issue at 40–50% is currently sufficiently improved. v8.8.9 must not disturb that low-OCR progress. The next layer to fix is above OCR: Prediction/Repair Guard, full output translation, new-dialog commit, and stale overlay prevention.

## Key decisions
- `Kenny` must be an approved exact named story speaker.
- `bathildel` is a visible failure case for Prediction Guard. It must be repaired through a guarded alias family, not through blind autocorrect.
- `Bathilde`/`Balthilde` spelling remains an alias-family issue until final visual confirmation; v8.8.9 maps common OCR typo variants to existing canonical `Balthilde` while retaining `Bathilde` as exact/alias evidence.
- `Heli`, `Helen`, and `Helena` must stay separate.
- New dialogue must start translation and must not be hidden by previous last-good overlay.
- If final translation coverage is too low, show current-source safe preview/no-cache instead of repainting stale old dialogue.

## Runtime principle
v8.8.9 is an Activation & Commit Reliability Patch, not an OCR retune patch. Do not raise all OCR profiles to 55/60 as a workaround.
