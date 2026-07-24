# ORT v8.8.7 Strategy Memory — Name/Term Prediction Guard & Dialogue Safety

Key decisions:
- General feature name: Name/Term Ambiguity Guard, not Helen/Helena-only.
- Example names from the user are examples/test cases, not the whole scope.
- Prediction/Repair Text must be anti-hallucination and confidence-labeled.
- Raizei is main Commander.
- Mangi Security Team Leader is a story speaker/NPC display label.
- Tlazo is a unique term/review Yellow, not NPC global.
- UI/loading/battle text must be filtered before translate/cache.
- Dialogue Timeout Safety must prevent missed dialog when translation is held.
- Stale Last-Good Limit v2 must prevent old overlay from masking new dialog.
- Preserve v8.8.6 OCR 40% improvements.
