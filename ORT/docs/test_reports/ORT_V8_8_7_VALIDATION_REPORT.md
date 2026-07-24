# ORT v8.8.7 Validation Report

Validation performed:
- Python compile for changed runtime modules: PASS.
- v8.8.7 regression test: PASS.
- ZIP integrity: PASS.

Regression coverage:
- UI/Loading/Battle text is filtered before translation/cache.
- Mangi Security Team Leader is resolved as exact speaker label.
- Tlazo remains unique term/review Yellow, not NPC global.
- Raizei resolves as main Commander.
- ARVITA/ATVITA/AFVITA cluster does not become main Commander.
- Ambiguous fragments around Helen/Helena are blocked as general Name/Term ambiguity examples.
- Emergency commit triggers when a held dialogue exceeds timeout.
- Prediction Yellow/Red blocks final cache.
