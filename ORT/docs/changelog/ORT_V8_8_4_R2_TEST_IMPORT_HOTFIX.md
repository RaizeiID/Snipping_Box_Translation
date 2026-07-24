# ORT Translation v8.8.4 R2 — Test Import Hotfix

Date: 2026-05-31T10:44:43

This hotfix corrects the regression test runner path.

## Fixed

- `tools/v8_8_4_regression_test.py` now adds `ORT/runtime_app` to `sys.path`.
- This prevents `ModuleNotFoundError: No module named 'app'` when running the test from `ORT/runtime_app`.

## Runtime behavior

No OCR, translation, overlay, scheduler, commit gate, or mode-policy behavior was changed.
