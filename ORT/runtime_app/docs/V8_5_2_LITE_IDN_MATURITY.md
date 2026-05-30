ORT Translation v8.5.2 — Lite/Lite IDN Maturity & Stability Patch
======================================================================
Base version: v8.5.1
Type: Changed-files patch
Date: 2026-05-20

Purpose
-------
This patch is the v8.5 maturity pass before v8.6.  It deliberately does not keep chasing
GFL2 numeric OCR edge cases; remaining number misses after v8.5.1 are treated as a known
minor OCR limitation unless a clear regression appears.

Main changes
------------
1. Added Naturalized IDN Cache for Lite IDN / IDN models.
   - Stores final Indonesian output after IDN quality/naturalization.
   - Avoids re-running the IDN polish layer for repeated or stable dialog.
   - Separate from scoped raw translation cache to prevent raw CT2 output from overwriting polished IDN output.

2. Added GFL2 Name Alias Normalizer.
   - Corrects high-confidence OCR speaker/name typos such as Ralzel/Ralzei/Raizel -> Raizei,
     Voymastlna/Vaymastina -> Voymastina, and AIVa/AIva -> Alva.
   - Integrated in OCR noise cleanup, cache-key normalization, runtime bridge, and translation engine.

3. Lite GPU Efficient telemetry improved.
   - Writes requested vs applied OCR, applied queue cap, applied CPU thread cap, VRAM free/total, and reason.
   - WebUI log line now shows requested_ocr/applied_ocr/queue for Lite/Lite IDN.

4. Controlled Online Assist Guard.
   - V4 remains offline-first + optional online assist.
   - Non-V4/Fast/Lite live loop should not trigger uncontrolled online resource paths.
   - Online assist must pass through the official V4 controlled route.

5. Analyze Last Session recommendations improved.
   - Adds Lite/Naturalized cache/number gap awareness.
   - Recommends Lite IDN V2/V3 and treats remaining numeric OCR gaps as known limitation.

Files changed / added
---------------------
Added:
- app/translation/name_alias_normalizer.py
- app/translation/naturalized_cache.py
- PATCH_APPLY_NOTES_V8_5_2.txt
- CHANGED_FILES_MANIFEST_V8_5_2.txt
- docs/V8_5_2_LITE_IDN_MATURITY.md
- docs/V8_5_2_COMPILE_REPORT.txt

Updated:
- TITANMAIN.py
- translation_engine.py
- runtime_bridge.py
- model_strategy.py
- launcher_backend.py
- webui.py
- runtime_health_applier.py
- benchmark_session_report.py
- app/runtime/lite_gpu_guard.py
- app/ocr/ocr_noise_normalizer.py
- app/translation/fuzzy_cache_normalizer.py
- ORTCORE_VERSION.txt
- TITANCORE_VERSION.txt
- docs/CHANGELOG.md
- docs/VERSION_HISTORY.txt
- docs/IMPLEMENTATION_STATUS.txt
- docs/NEXT_RECOMMENDATIONS.txt
- docs/KNOWN_ISSUES.txt

Known limitations
-----------------
- Numeric OCR for tiny/blurred GFL2 tactical values can still fail.  This is now considered a known/minor limitation.
- Naturalized cache improves repeated/stable text, but it needs a few sessions to become effective.
- V4 Online Assist depends on user configuration and network/API availability.

Next direction
--------------
v8.6 should focus on the broader IDN model/quality layer: shared IDN architecture, smarter Indonesian style modes,
terminology consistency, IDN cache maturity, and model-family polish beyond Lite.
