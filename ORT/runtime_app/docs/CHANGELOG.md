## v8.7.8 — Faithfulness v2, Strict CT2 Story & IDN-over-CT2 (28 Mei 2026)

- Expanded Semantic Faithfulness Gate with diacritic/apostrophe-normalized detection for `al-Qur 'ân`, `ayat`, `zakat`, `neraka`, and tafsir-style injection patterns.
- Added Qur Corruption Quarantine for observed OCR corruption of `our/your` into `Qur`; safe contexts are repaired, ambiguous contexts are held.
- Added Strict CT2 Story behavior that suppresses Argos fallback for progressive/noisy requests when CT2 is available.
- Added IDN-over-CT2 and final-only safe commit paths for accuracy profiles, plus unsafe QA fallback correction.
- Rotated namespace to `v8_7_8_faithfulness_v2_strict_ct2_safe` and expanded safety telemetry/debug reporting.
- Added exact-only `Kalina`, `Farkas`, role-exact `Client`, special terms `Satellite City` and `ODE-01 Municipal Center`; retained manual-review policies and Commander exclusions.
- Added review-only Candidate Miner and documented v9.0 full-ZIP/GitHub-ready restructuring plan.

## v8.7.7 — Translation Faithfulness, Stable Commit & CT2 Rebind (27 Mei 2026)

- Added Universal Semantic Faithfulness Gate to block unsupported hallucination before overlay/cache/export/learning.
- Added Dialogue Completeness / Stable Commit hold for short progressive fragments and omission telemetry.
- Rotated cache namespace to `v8_7_7_faithful_complete_ct2_safe` with semantic-contamination detection.
- Permanently rebinds CT2 model/SPM paths in launcher and adds Repair/Rebind UI plus job-level fallback reason telemetry.
- Added IDN accuracy quality-lock hysteresis for transient runtime warnings.
- Added CT2-live exact-only names (`Berryfield`, `Cocoon`, `Carmen`, `Another Unfamiliar Worker`) and new GFL2 special terms; excluded Commander-only `Vilyz`, `ARVITA ID`, and `ATVITA ID` globally.
- Added v8.7.7 debug bundle, test ledger, replay benchmark, migration/rotation tooling, and cumulative handoff docs.

## v8.7.6 — Adaptive OCR Readability, Exact Fallback Gate & Test Ledger (27 Mei 2026)

- Added adaptive OCR readability rescue for low-quality GFL2 Fast/Lite frames; low presets may retry at a safer resolution only when corruption is detected.
- Respected explicit OCR override when resource policy permits and added truthful requested/applied/rescue/CT2 status reporting.
- Blocked generic GFL2 fallback speaker promotion unless an exact official or approved speaker match exists, preventing false labels such as `DP`, `Name`, `TC`, and `Hybrid`.
- Added observed-character and ROI-only alias review metadata without duplicating official roster entries or auto-activating risky aliases.
- Added cache namespace `v8_7_6_adaptive_ocr_exact_safe`, identity/cache migration tools, debug export, replay benchmark, and structured test ledger.
- Preserved full backend-safe EntitySpan, official exact speaker catalog, dual Helen/Helena, Compound Entity, stale-overlay guard, Two-Pass OCR, Responsive mode, and multi-game UI.
- CT2/SPM repair remains a separate follow-up; when CT2 is unavailable the UI now warns against relying on ultra-low OCR for story.

## v8.7.2 — Stable Final Cache v2, GFL2 Speaker ROI & IDN Evaluation (2026-05-25)

- Fixed a critical cache-store blocker: non-gap numeric diagnostics such as `no_numeric_context` no longer prevent ordinary dialogue from being stored.
- Added Stable Final Cache v2 and current-dialog memo telemetry (`CACHE_SKIP_PROGRESSIVE`, `CACHE_STORE_STABLE_FINAL`, `CACHE_HIT_STABLE_FINAL`, `CACHE_DUPLICATE_OCR_SUPPRESSED`).
- Added GFL2 speaker Name ROI pass and temporal speaker hold for seeded names including `DP-12` and `KSVK`; body OCR remains paragraph-based for performance.
- Added scoped thin-glyph/start-of-line recovery trigger for missing initial `I` symptoms without converting global OCR to per-character mode.
- Added contextual GFL2 repair for `KSVKis`, safe `DP-125` possessive cases, and repeated word-join/typo patterns before cache/translation.
- Added IDN Evaluation Export for normalized source, backend output and final IDN output, plus IDN warmup and OCR-resolution reason telemetry.
- Added NPC cleanup/migration v2 dry-run support while preserving canonical `DP-12` and `KSVK`.
- Maintains v8.7.1 Auto defaults and legacy vault isolation.

## v8.7 — GFL Dedicated Dialogue Profile & OCR Contamination Guard (2026-05-25)

- Released as a full-project package for a new folder, based on v8.6.
- Added separate `GFL` game profile rather than treating GFL1 as `GFL2_EXILIUM`.
- Added GFL Dialogue Layout Resolver, lower-right `GFsystem` footer mask, and conservative non-dialog Scene Guard.
- Added GFL footer/credit artifact filter before translation, cache and speaker learning.
- Added seeded GFL glossary, safe Name ROI speaker logic and quarantine/cleanup rules for false learned speakers.
- Added GFL normalized/stable cache protection to address repeated MISS from footer suffixes and partial typing frames.
- Added v8.7 session diagnostic metrics and smoke test tool.
- Preserved v8.6 IDN Quality Layer and known-minor numeric OCR limitation policy.

## v8.6 — IDN Quality Layer & IDN Model Optimization

- Added shared IDN Quality Layer for Fast IDN, Lite IDN, and Normal IDN.
- Added IDN Light / Balanced / Natural / Quality mode mapping.
- Added terminology consistency for game/story terms.
- Versioned Naturalized IDN Cache as v8_6 so old v8.5.x cache does not mask new output polish.
- Updated Fast IDN naturalizer to delegate to shared fast_light IDN layer.
- Prevented duplicate Lite IDN quality pass in RuntimeBridge when TranslationEngine handles IDN Quality Layer.
- Preserved Fast and Lite runtime behavior from v8.5.2.

## v8.5.1 — Numeric ROI OCR & VRAM Guard Hotfix (2026-05-20)
- Added ROI-first numeric dual-pass OCR for wide GFL2 dialog boxes.
- Added semantic numeric candidate validation to reject UI/progress noise such as 821/8261/6102/7.18:31.20-style fragments.
- Mark remaining unreadable tactical numbers as known OCR numeric limitation instead of injecting wrong numbers.
- Changed VRAM guard to staged OCR downscale first; CPU fallback is disabled by default and requires explicit opt-in/sustained pressure.
- Added safer GFL2 normal-model OCR/queue cap to reduce VRAM spikes on Normal V3/V5.
- After this patch, remaining OCR number misses are considered minor limitations; next focus moves to Lite/Lite IDN optimization.

## v8.4.4 — Lite Final Profile Identity & v8.5 Handoff
- Finalized Lite/Lite IDN OCR ladder: V1 40%, V2 45%, V3 50%, V4 55%, V5 60%.
- Preserved v8.4.3 Lite latencies while differentiating OCR/resource/quality behavior more clearly.
- Added level-aware Lite GPU Guard caps so quality modes can use higher OCR when VRAM is healthy but still downscale when VRAM is tight/heavy.
- Added stale Lite preset migration guard for old autosaved defaults.
- Fast retune from v8.4.3 remains unchanged.

## v8.4.3 — Fast OCR Retune & Lite IDN Efficiency Polish

Status: changed-files patch after v8.4.2.

- Fast V1 default OCR 40%, interval 45ms.
- Fast V2 default OCR 45%, interval 60ms.
- Fast IDN default OCR 50%, interval 75ms.
- Fast scheduler thresholds made lower-latency while keeping Auto/Interval semantics.
- WebUI interval slider minimum lowered to 45ms for Fast profiles.
- Lite IDN GPU Efficient caps tightened slightly to reduce VRAM/FPS pressure.
- Added stale Fast preset guard and extra OCR noise normalization.

# ORT Translation Changelog

## v8.4.2 — Lite IDN Efficiency Tuning Patch

Status: changed-files patch after v8.4.1.

### Focus
- Optimize Lite/Lite IDN latency and resource usage after real GFL2 tests.
- Accept wide GFL2 dialog snips and filter OCR noise internally.
- Keep Fast v8.3.4 behavior locked.

### Key changes
- Lite IDN V2 becomes the recommended efficient balanced default.
- Lite IDN intervals/OCR caps are reduced.
- Added lite_efficient and lite_idn_efficient core profiles.
- Added OCR noise rejection for UI fragments and numeric artifacts.
- Lite GPU Efficient now uses stricter queue/CPU/OCR caps and lower loop floor.

## v8.4.1 — WebUI Startup Fix

Status: hotfix after v8.4 full package.

### Fixed
- Fixed Gradio event binding error on `npc_cleanup_btn.click(...)` that caused WebUI startup to fail with `got multiple values for argument 'outputs'`.
- Updated launcher labels to v8.4.1.


## v8.2 — Story/Dialog Performance & Fast Engine Activation

Status: changed-files patch setelah v8.1.

### Fokus utama
- Menambahkan **Story Dialogue Scheduler** agar mode Freeze, Interval, dan Auto tidak saling bersaing:
  - Freeze = manual story click, commit langsung.
  - Interval = Freeze otomatis cepat, menahan teks parsial sampai stabil.
  - Auto = story otomatis, memakai image-hash trigger dan stabilisasi ringan.
- Menambahkan **Image Hash Gate** sebelum EasyOCR untuk melewati OCR saat frame dialog belum berubah, khususnya saat voice masih berjalan tetapi teks sudah selesai tampil.
- Menambahkan **Fuzzy Cache Key** agar typo OCR kecil seperti `Iike/like`, `afrald/afraid`, `yoU/you`, `agaln/again` dapat diarahkan ke cache yang sama.
- Fast Engine status dibuat lebih jujur: jika CT2/model Fast belum aktif, WebUI menampilkan warning bahwa model Fast fallback ke Argos.

### WebUI dan runtime status
- Judul WebUI dinaikkan ke v8.2.
- Label mode diperjelas menjadi Auto / Story Otomatis, Freeze Manual / Klik User, dan Interval / Freeze Otomatis.
- Menambahkan panduan mode v8.2 langsung di Dashboard.
- Runtime cards menampilkan Fast status, scheduler profile, dan performance reason.
- Launcher mengirim env scheduler v8.2 ke runtime: `ORT_DIALOG_SCHEDULER_PROFILE`, `ORT_IMAGE_HASH_GATE`, `ORT_FUZZY_CACHE_KEY`, dan parameter stabilisasi per mode.

### OCR, cache, dan speaker gate
- `TITANMAIN.py` memakai Image Hash Gate sebelum OCR pada Auto/Interval, tetapi tetap menghormati Freeze manual.
- TranslatorWorker memakai Story Dialogue Scheduler sebelum split speaker/translation agar teks yang masih mengetik tidak diterjemahkan berkali-kali.
- `cache_store.py` menyimpan/membaca raw key dan normalized fuzzy key.
- Speaker Candidate Gate menahan narrative starter seperti Contrary, Seemingly, Unsure, Seeing, However, While, After, Before.
- Default speaker promote hits dinaikkan dari 2 ke 3 untuk mengurangi speaker palsu.

### Analyze Last Session
- Benchmark v8.2 menghitung dialog scheduler hold, OCR hash skip, dan Argos fallback events.
- Rekomendasi session report sekarang memberi peringatan jika Fast fallback Argos terdeteksi.

### File penting yang berubah / ditambahkan
- `TITANMAIN.py`
- `launcher_backend.py`
- `webui.py`
- `model_registry.py`
- `model_strategy.py`
- `v7_system_profile.py`
- `fast_model_manager.py`
- `benchmark_session_report.py`
- `cache_store.py`
- `app/runtime/app_state.py`
- `app/ocr/image_hash_gate.py`
- `app/runtime/story_dialogue_scheduler.py`
- `app/translation/fuzzy_cache_normalizer.py`
- `app/translation/speaker_candidate_gate.py`
- `docs/*`
- `ORTCORE_VERSION.txt`
- `TITANCORE_VERSION.txt`

## v8.1 — WebUI Stability & Runtime Integration Hotfix

Status: changed-files patch setelah full package v8.0.

### Perbaikan WebUI
- Memperbaiki tombol **Exit** agar tidak lagi melempar `SystemExit` ke ASGI/FastAPI request handler.
- Tombol **Reset Live Log** sekarang membersihkan buffer log internal WebUI, bukan hanya textbox tampilan.
- Tombol Runtime & Tools yang sebelumnya belum tersambung kini aktif: Analyze Last Session, GPU/Torch CUDA Diagnostic, Conflict Detector, Reset UI, Reset Runtime, Reset Online Assist, Reset All.
- Menambahkan tombol **Clean NPC Database** untuk membersihkan speaker palsu/noise OCR dari `npc_database.json` dengan backup otomatis.
- Mode **Normal / Manual** tidak lagi tertimpa oleh rekomendasi saat user mengganti game/dropdown.
- Tombol **Terapkan Rekomendasi Profil** kini menjadi aksi eksplisit yang mengembalikan mode ke Recommended dan menerapkan preset sistem.
- Mode UI **Basic / Recommended / Expert** mulai berfungsi secara nyata melalui visibility panel.
- Menambahkan status cards requested vs effective untuk engine, interval, OCR, health, dan profile.
- CSS status card dan mode note dirapikan agar tampilan kanan tidak terlihat menempel.

### Integrasi runtime dan OCR
- `TITANMAIN.py` sekarang memakai `OCR Noise Normalizer` pada jalur `normalize_ocr_text()` sebelum speaker detection/cache/translation.
- `StableTextCommitter` dihubungkan ke OCR queue untuk mode STABLE agar teks setengah terbaca tidak langsung diterjemahkan.
- Translator worker melakukan normalisasi ulang setelah runtime bridge preprocessing untuk menjaga pipeline tetap bersih.
- `launcher_backend.py` menyimpan app state v8.1 berisi requested/effective engine, mode, interval, dan OCR resolution.
- Hardware detection di `v7_system_profile.py` diberi cache TTL agar perubahan dropdown tidak berulang kali menjalankan `nvidia-smi`/`wmic`.

### Diagnostic dan maintenance
- Analyze Last Session v8.1 menambahkan deteksi OCR noise dan speaker candidate hold.
- Speaker Candidate Gate diperketat untuk menahan nama palsu seperti token OCR/noise/simbol.
- NPC cleanup tool sekarang membuat backup dan menjelaskan contoh item yang dibersihkan.
- `Clean_ORT_Translation.bat` dibuat aman: tidak lagi menghapus folder project secara otomatis.

### File penting yang berubah
- `webui.py`
- `launcher_backend.py`
- `TITANMAIN.py`
- `v7_system_profile.py`
- `benchmark_session_report.py`
- `app/ocr/ocr_noise_normalizer.py`
- `app/ocr/stable_text_commit.py`
- `app/translation/speaker_candidate_gate.py`
- `app/runtime/app_state.py`
- `tools/npc_database_cleanup.py`
- `Clean_ORT_Translation.bat`
- `Start_ORT_Translation.bat`
- `README.md`
- `READ_THIS_FIRST_V8.txt`
- `docs/*`
- `ORTCORE_VERSION.txt`
- `TITANCORE_VERSION.txt`

## v8.0 — Major Maturity / Foundation Build

- Modular runtime foundation melalui folder `app/`.
- Mode Pengaturan: Rekomendasi Sistem vs Normal / Manual.
- Reset Live Log, Reset Settings, Analyze Last Session.
- Profile Resolver, Safe Mode Guard, Conflict Detector.
- GPU/Torch CUDA Diagnostic.
- OCR Noise Normalizer, Speaker Candidate Gate, dan awal Stable Text Commit.
- SQLite cache adapter prototype.
- Dokumentasi version history/update tracking.

## v8.3 - Runtime Repair & Fast CT2 Setup Patch
- Locked Torch/Torchvision/Torchaudio install path to prevent dependency mismatch.
- Added CUDA/CPU repair and validation BAT scripts.
- Improved Fast CT2 setup wizard with model folder validation, missing file report, and fallback explanation.
- Translation engine now reads detected Fast CT2 model path from FastModelManager.
- Added GFL2 story voice-hold tuning for Fast Interval mode.
- Added OCR region quality status when snipping region is locked.
- Compile sweep: 196 Python files, 0 syntax errors.

## v8.3.1 - Mode Mapping & Interval Restore Hotfix

- Fixed Auto mode being overwritten/displayed as Interval/FREEZE after strategy environment injection.
- Restored default Interval floor to 90ms after user requested returning to the previous safer interval timing.
- Updated WebUI interval slider minimum to 90ms.
- Updated scheduler debug label from v8.2.1 to v8.3.1.
- Added clearer Auto/Freeze/Interval shortcut display behavior in TITANMAIN boot help.
- Fast CT2 active path remains unchanged.


## v8.3.2 - Auto/Interval Classic Story Flow Hotfix
- Auto mode restored to visual-novel style progressive translation behavior.
- Interval mode restored to classic automated-Freeze quick commit behavior.
- Fast CT2 activation path unchanged.
- Known remaining work: OCR typo/name alias normalization, NPC merge UI, OCR preprocessing profiles, Diagnose & Repair Center v8.4.


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


## v8.3.4 - Fast Final Lock & Auto Preset UX Patch
Date: 2026-05-20
Type: final v8.3 tuning / WebUI UX / Fast Lock
Base: v8.3.3

Summary:
- Removed manual Save Default button; model settings now auto-save when user changes Mode/Engine/Interval/OCR.
- Added orange "• Modification" badge below the selected model when custom settings exist.
- Reset Default is now red/oval and appears only for modified models.
- Added Fast Model Lock documentation for v8.4 so Lite IDN/OCR/Diagnose work does not accidentally alter Fast behavior.
- Added Fast lightweight post-process guard to reduce rare first-use latency spikes in Fast profiles.

Validation:
- Python compile sweep: 198 files checked, 0 syntax errors.

## v8.4.5 — Number-Safe OCR & Lite IDN Final Polish

- Added `app/ocr/number_guard.py` for numeric OCR correction, numeric UI-noise rejection, and translation-time number preservation.
- Updated OCR noise normalizer to reject GFL2 wide-dialog numeric garbage such as `11+1115141`, `30,L`, `TIIII`, `LLI`-style fragments.
- Updated `TITANMAIN.py` so meaningful standalone numbers are no longer blindly removed by old digit cleanup.
- Updated `translation_engine.py` so source numbers are normalized and restored after CT2/Argos/IDN post-processing when possible.
- Preserved v8.4.4 Lite/Lite IDN OCR ladder and v8.4.3 Fast retune.
- Added final Lite IDN recommendations and v8.5 handoff notes.


## v8.5 — Numeric Dual-Pass OCR & Lite Optimization Foundation

- Added numeric dual-pass OCR trigger for GFL2 tactical number contexts.
- Added cache protection for missing-number lines.
- Preserved v8.4.5 Lite/Fast OCR identity while opening v8.5 Lite optimization work.
- Next focus: ROI numeric OCR, naturalized cache, VRAM telemetry, per-game Lite tuning.

## v8.5.2 - Lite/Lite IDN Maturity & Stability Patch
- Added Naturalized IDN Cache for Lite IDN/IDN final output.
- Added GFL2 Name Alias Normalizer.
- Improved Lite GPU telemetry requested vs applied OCR/queue.
- Added Controlled Online Assist Guard so only V4 uses official online assist.
- Improved Analyze Last Session recommendations for Lite profiles.

## v8.7.1 — Auto Default, GFL2 Name Integrity & Diagnostic Truth Patch

- Set built-in default mode of every model family to **Auto** while keeping Interval/Freeze as manual choices.
- Added GFL2 canonical names `DP-12` and `KSVK`, plus contextual repairs for observed variants such as `Dp-12`, `KSVKs`, and `KSVKand`.
- Added conservative GFL2 speaker gate/quarantine behavior to stop narrative starters from becoming NPC names.
- Isolated legacy MemoryVault by default for clean validation sessions (`ORT_ENABLE_LEGACY_VAULT=1` is explicit opt-in).
- Added progressive short-prefix cache guard and moved naturalized-cache writes behind cache eligibility checks.
- Fixed WebUI runtime cards to read real translation backend applied status rather than strategy label.
- PIPE log now distinguishes requested mode, capture mode, and scheduler profile.

## v8.7.2 Documentation Continuity Integration
- Bundled the current Master Project Memory/Handoff and Development Ledger directly inside the ORT project patch structure.
- Future ORT patches/full-project releases must include updated project-memory documentation in the same ZIP as runtime changes, not as a separate optional download.
- Source code and the newest test logs remain the primary source of truth when restoring context in a new chat.


## v8.7.3 — Trusted Identity, Multi-Game Data UI & Named Entity Protection
Date: 2026-05-26
Type: Changed-files patch over v8.7.2; install first on a cloned test folder.

Implemented:
- Trusted Speaker Registry v2 with protected/user-configured/approved-role/unsorted-simple/legacy-untrusted separation.
- Dual Canonical Identity Guard: `Helen` and `Helena` remain distinct valid speakers; exact matching and metadata routing prevent cross-label duplication.
- GFL2 Name ROI v3 no longer trusts the contaminated legacy NPC database and no longer prepends guessed speaker names into raw body text.
- ROI-selected speaker metadata is committed to overlay processing with structured trace events.
- Named Entity Protection / restore around backend and IDN layers to preserve names such as `Phaetusa`, `Balthilde`, `Alya Kujou`, `KSVK`, `Helen`, and `Helena`.
- Critical Token Guard blocks final-cache commit for ambiguous OCR tokens such as `Level Il` until a safer final reading is available.
- Cache namespace bump (`v8_7_3_identity_guard`) for scoped and naturalized caches to avoid reusing contaminated v8.7.2 outputs.
- New multi-game `Pengolahan Data & Identitas` panel: visible Game Profile selector, `Tampilan Sederhana` checkbox default ON, and category-aware Normal/Detail workflow.
- Simple-mode names are stored as unsorted protected entities and appear as orange/migratable items in Normal mode; sorted detail names remain green/non-migratable.
- Clickable selection workflow for deleting/migrating a complete compound speaker entity rather than manual checkbox hunting.
- Verified reference roster catalog architecture for GFL2, WUWA and broad GFL/story seeds; catalog names support entity protection without opening unrestricted fuzzy live speaker labels.
- GFL story-faction category design for Paradeus/Sangvis Ferri metadata and spoiler-aware expansion, without generic enemy auto-labeling.
- New identity/cache migration dry-run tool and one-click debug bundle export helper.

Compatibility and safety:
- User data files (`data_processing_store.json`, `npc_database.json`, existing preferences/cache/logs) are not overwritten inside the ZIP patch.
- First runtime/UI load can generate the new registry from defaults plus safe legacy review data; cleanup/migration is reviewable.
- Legacy Advanced tabs remain available for compatibility while the new panel becomes the safe workflow.

### v8.7.3 — Simple-Origin Sorting UX
- Names entered through `Tampilan Sederhana` are retained as valid unsorted protected speaker entities and shown as orange selectable items in Normal/Detail view.
- Added delete-or-migrate action flow for orange unsorted names, avoiding manual delete-and-retype categorization.
- Sorted detail-category entities remain selectable for delete/edit but are not offered simple-origin migration.
- Selection and migration preserve compound entities such as `Alya Kujou`, `URNC Leader`, and `M4 SOPMOD II` as one identity.

## v8.7.4 — EntitySpan Safety, Responsive Story & v8.7.3 Fatal Bug Recovery (26 Mei 2026)
- Treats v8.7.3 as a defective release for the entity-output path: replaces the post-translation `ORT_ENTITY_*` string pass with immutable EntitySpan processing.
- Adds residual-internal-token blocking/fallback so `ORT_ENTITY`, malformed `_ _ ORT`, or backend tokens are not displayed or cached.
- Fixes cache-version override left in `model_strategy.py`; v8.7.4 uses `v8_7_4_entity_span_responsive` and includes backup/rotation tools for contaminated caches.
- Adds `Mode Responsif / Story Cepat (Tanpa Voice)` with latest-frame-wins and progressive queue coalescing; Two-Pass Name ROI remains enabled in normal/responsive play.
- Adds Diagnostic A/B profile selection, including a warned `Diagnostic No-Name-ROI` test-only option.
- Caches/precompiles protected-entity matching per game and removes the unsafe second placeholder/string pass through IDN/QA.
- Adds stage timing data for body OCR, Name ROI, numeric/thin-glyph passes, entity matching, backend translation, IDN post-process, and queue wait.
- Preserves v8.7.3's correct capabilities: Trusted Speaker Registry, dual Helen/Helena identity, Compound Speaker Entity, multi-game identity UI, simple-mode orange migration, roster catalogs, and GFL Paradeus/Sangvis organization.


## v8.7.5 — Verified Character Speaker Recovery, Full Backend-Safe EntitySpan & Stale Overlay Guard (26 Mei 2026)
- Menambahkan tier speaker GFL2 `verified_character_speaker_exact`: karakter resmi katalog seperti `Zhaohui`, `Vector`, `Colphne`, `Groza`, `Ullrid`, dan `Harpsy` dapat menjadi label melalui exact Name ROI/exact-prefix, tanpa fuzzy liar atau auto-learning narasi.
- Memperbaiki migrasi registry yang pada v8.7.4 membaca field catalog yang salah; tool v8.7.5 memakai `entries[].display_name` dan menyediakan backup/dry-run.
- Menulis ulang EntitySpan agar berlaku hingga sebelum backend: `EntitySpan` tidak lagi diubah menjadi token `ORT_BKEND`; hanya `TextSpan` yang masuk backend/IDN rewrite.
- Memperluas residual guard untuk memblok `ORT_ENTITY`, `ORT_BKEND`, `ORT_BKED`, `ORT_BEND`, dan `_ _ ORT` sebelum overlay/cache/export.
- Menambahkan speaker-transition epoch dan stale-overlay drop agar hasil `Alya Kujou`/`Vector` lama tidak bertahan saat game telah berpindah ke `Zhaohui`/`Harpsy`.
- Menggunakan cache namespace baru `v8_7_5_verified_exact_entity_safe` dan tool rotasi cache v8.7.4 tercemar.
- Menambahkan debug export v8.7.5 serta regression test khusus bukti video/log v8.7.4.
