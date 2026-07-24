# ORT v8.8.5 Validation Report

## Static validation

- Compile `TITANMAIN.py`: PASS
- Compile `translation_engine.py`: PASS
- Compile `fast_model_manager.py`: PASS
- Compile `launcher_backend.py`: PASS
- Compile `webui.py`: PASS
- Compile runtime modules: PASS
- Run `tools/v8_8_5_regression_test.py`: PASS
- Run legacy v8.8.4 regression: PASS

## Regression cases covered

- Valid longer source overrides min-visible suppression.
- Short noisy new-turn waits and keeps last good overlay.
- OCR churn repair normalizes common low-OCR errors such as `Berryflold` and `proflted`.
- Bad cache shield blocks corrupted low-OCR stable-final cache.
- Turn finalizer can force a final-complete render.
- Telemetry includes final completeness and turn-finalizer counters.

## Live validation still required

- GFL2 Auto: Normal V1 / IDN V2, OCR 65–70%.
- GFL2 Auto: Lite V1 / Lite IDN V1 / Lite IDN V2, OCR 40–45%.
- GFL2 Interval: verify semi-stable behavior and no blank overlay.
- Check that v8.8.5 improves final_complete_ratio and reduces source_longer_but_suppressed.
