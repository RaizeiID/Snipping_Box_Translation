# ORT v8.8.1 Structure Validation Report

## Scope
v8.8.1 validates structural refactor only. Runtime behavior remains based on v8.7.9.

## Root files
```text
.gitignore
CHANGELOG.md
FULL_PROJECT_MANIFEST_V8_8_1.txt
README.md
Runtime.bat
START_HERE.bat
Start OCR.bat
Start WebUI.bat
VERSION.txt
```

## Root directories
```text
ORT
```

## Compile checks
| File | Result |
|---|---|
| `TITANMAIN.py` | PASS |
| `webui.py` | PASS |
| `launcher_backend.py` | PASS |
| `model_strategy.py` | PASS |
| `translation_engine.py` | PASS |
| `app/runtime/turn_safe_overlay.py` | PASS |
| `app/translation/semantic_fidelity_guard.py` | PASS |

## Regression/smoke checks
| Script | Result | Notes |
|---|---|---|
| `tools/v8_7_9_regression_test.py` | PASS | v8.7.9 reconstructed regression PASS |
| `tools/v8_7_gfl_smoke_test.py` | PASS | v8.7 GFL smoke test PASS - footer artifact normalization - normalized GFL cache key - credit/non-dialog candidate guard - Name/Body ROI + footer bbox mask - cache contamination rejection - GFL game selection/env contract - GFL seeded glossary |

## Generated data cleanup
Large historical generated files in logs/cache/backups over 200KB: 0

## Notes
- Runtime is placed in `ORT/runtime_app/` and remains current working directory for compatibility.
- Historical logs/cache/backups are intentionally not included.
- Cache namespace remains `v8_7_9_responsive_turn_safe_ct2` because v8.8.1 does not change translation behavior.
- v8.8.2 is reserved for mode behavior refactor.
