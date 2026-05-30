## v8.3.3 - Fast Model Identity & Preset Memory Patch
Date: 2026-05-20
Type: Optimization Patch / Fast profile tuning / WebUI UX
Base: v8.3.2

Summary:
- Fast V1, Fast V2, and Fast IDN now have clearer runtime identities while preserving Freeze/Interval/Auto as global mode semantics.
- Fast V1 is speed-first: lower latency, more aggressive progressive commits, lighter post-processing.
- Fast V2 is balanced: moderate stability, stronger cleanup/fuzzy cache, and better story reliability.
- Fast IDN uses the Fast V2-like pipeline plus an offline Indonesian naturalizer/post-edit layer for cleaner Indonesian phrasing.
- Added model-level custom default memory in WebUI: users can save the current mode/engine/interval/OCR as the default for the selected model.
- Switching away from a model and returning to it now restores the saved custom default when available.
- Added Reset Default Model button to return a model to its built-in defaults.
- Improved OCR typo/cache normalization and stricter speaker candidate filtering for common GFL2 OCR noise.

Changed/Added Files:
- webui.py
- launcher_backend.py
- TITANMAIN.py
- translation_engine.py
- runtime_bridge.py
- model_registry.py
- model_strategy.py
- app/runtime/model_user_presets.py
- app/translation/indonesian_naturalizer.py
- app/ocr/ocr_noise_normalizer.py
- app/translation/fuzzy_cache_normalizer.py
- app/translation/speaker_candidate_gate.py
- ORTCORE_VERSION.txt
- TITANCORE_VERSION.txt
- docs/CHANGELOG.md
- docs/VERSION_HISTORY.txt
- docs/IMPLEMENTATION_STATUS.txt
- docs/NEXT_RECOMMENDATIONS.txt
- docs/KNOWN_ISSUES.txt
- docs/V8_3_3_COMPILE_REPORT.txt
- PATCH_APPLY_NOTES_V8_3_3.txt

Validation:
- Python compile sweep: 198 files checked, 0 syntax errors.

Known limitations:
- Fast IDN naturalization is lightweight/offline rule-based, not a full LLM rewrite.
- OCR region quality still matters; overly wide crops can still create noise.
- NPC merge/review UI is still planned for v8.4.
