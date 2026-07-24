# ORT Translation v8.8.8 R2 — Entity Label & Mode Policy Activation Hotfix

## Fixed
- Fixed Prediction Guard false positive spam where ambiguous aliases like `Hell -> Heli` were logged/blocked even when the OCR text did not contain that alias.
- Exact entity prefixes now become speaker/entity labels: `Raizei`, `Darture`, `Poludnitsa`, `Anfiya Sharapova`, `Mangi Security Team Leader`, `Shadow Figure`, and `Shadowy Figure`.
- Added visible confidence badge support on speaker labels.
- Merged registry names/terms into runtime NPC/unique-term memory at boot.
- Activated Mode Policy telemetry for Auto/Interval/Freeze.
- Connected Interval Fast-Skip Safety into held-dialogue emergency path.
- Added `Poludnitsa` to registry.
- Preserved separate `Heli`, `Helen`, and `Helena`.

## Still Not Stable
This is a hotfix to make v8.8.8 roadmap behavior visible and active. Long-session testing is still required before stable.
