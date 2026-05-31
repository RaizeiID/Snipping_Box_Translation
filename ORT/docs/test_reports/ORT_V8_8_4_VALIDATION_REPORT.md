# ORT Translation v8.8.4 — Validation Report

## Static validation performed during packaging
- Python compile check for modified runtime modules.
- Regression test `tools/v8_8_4_regression_test.py`.
- ZIP integrity check.

## Live validation still required
v8.8.4 must be tested in GFL2 using:
- ORTCore IDN V2 or Normal V1
- Auto mode
- OCR 65–70%
- CT2 active

## Expected live behavior
- Overlay should not blank while dialogue text is still present.
- Later, more complete dialogue should be allowed to replace a shorter preview.
- Flicker should remain controlled.
- Interval/Freeze should feel more stable than Auto.

## Metrics to inspect from logs
- `overlay_committed_final_complete`
- `final_complete_rendered`
- `last_good_reused`
- `source_longer_but_suppressed`
- `overlay_suppressed_min_visible`
- `final_complete_ratio`
- `engine=ct2_fast` and `engine=ct2_trusted_preview`
- `engine=argos_offline` should remain zero or near-zero for story when CT2 is active.


## R2 Hotfix Validation

Issue:
- Running `python tools\v8_8_4_regression_test.py` from `ORT/runtime_app` could fail with `ModuleNotFoundError: No module named 'app'`.

Fix:
- The test script now inserts the `runtime_app` root into `sys.path` before importing `app.runtime.*`.

Runtime behavior:
- Unchanged.
