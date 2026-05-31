# ORT Translation v8.8.3 — Validation Report

## Static validation
- `python -m py_compile` PASS for:
  - `TITANMAIN.py`
  - `translation_engine.py`
  - `fast_model_manager.py`
  - `launcher_backend.py`
  - `webui.py`
  - `app/runtime/ct2_path_resolver.py`
  - `app/runtime/render_signature.py`
  - `app/runtime/overlay_commit_gate.py`
  - `app/runtime/recording_telemetry.py`
  - `app/runtime/dialogue_stability.py`

## Regression validation
- `tools/v8_8_3_regression_test.py` PASS
- `tools/v8_7_9_regression_test.py` PASS
- `tools/v8_7_gfl_smoke_test.py` PASS

## Live validation still required
v8.8.3 is intended to be tested in GFL2 with Normal V1 OCR 65% Auto for 1–2 hour story recording. The target is to verify:
- CT2 path resolves without manual junction.
- Argos story fallback remains zero when CT2 is available.
- Overlay flicker decreases due to commit suppression.
- Hold/blocked states keep last good overlay instead of blinking.
- Final translations use the best source per turn where possible.
