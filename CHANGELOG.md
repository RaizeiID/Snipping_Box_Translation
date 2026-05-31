# CHANGELOG — ORT Translation v8.8.5

## v8.8.5 — Turn Finalizer & OCR Churn Rescue

### Added
- Turn Finalizer: each dialogue turn now tries to produce one final-complete render before the turn is considered finished.
- OCR Churn Rescue for low-OCR profiles (40–45%) using lightweight source repair, churn detection, and corrupted-frame hold.
- Bad Cache Shield: fuzzy/naturalized cache is downgraded from final when the OCR source is heavily corrupted.
- Source Longer Must Win: valid longer source can override `MIN_VISIBLE`, duplicate, and similar suppression.
- Hard repaint last-good overlay to avoid blank/stale boxes during held dialogue.
- Extra recording telemetry: `turn_finalizer_forced`, `bad_cache_shielded`, `ocr_churn_rescued`, `source_suppressed_ratio`, and `new_turn_ratio`.

### Changed
- Auto remains responsive, but valid complete source now has priority over anti-flicker suppression.
- New-turn commit is less aggressive; short/noisy turn-id churn keeps/repaints the last good overlay.
- Low-OCR profiles remain testable and supported as entry-level stress targets instead of being treated as unusable.
- OCR repair is conservative and deterministic; it does not increase global OCR percentage and does not call a heavy model.

### Not changed intentionally
- No new model dependency.
- No global OCR increase for Lite/Fast profiles.
- No Argos story fallback re-enabled when CT2 is available.
- No full rewrite of `TITANMAIN.py`; refactoring remains incremental.

### Next validation target
- Test Lite V1, Lite IDN V1, Lite IDN V2, Normal V1/IDN V2 in Auto and Interval.
- Check whether `final_complete_ratio` increases, `source_longer_but_suppressed` decreases, and blank overlay disappears.
- Use v8.8.6 only after comparing long-session logs.

# CHANGELOG — ORT Translation v8.8.5

## v8.8.5 — GFL2 Recording Stability & Overlay Commit Gate
- Added CT2 Path Resolver so root `models/ct2_opus_mt_en_id` is found without manual junction.
- Added render-level Overlay Commit Gate to reduce flicker without delaying OCR/translation.
- Added normalized render signature to suppress visually-identical cache/preview updates.
- New turn clearing in Auto now keeps last good overlay until a meaningful new payload is ready.
- Speaker-only fragments are suppressed in Auto/Recording.
- Added lightweight recording telemetry for long GFL2 sessions.


## v8.8.2 — Runtime Behavior Refactor

- Added mode-specific runtime policy for Auto, Freeze, and Interval.
- Added Auto Smooth coalescing to reduce overlay flicker from low-OCR progressive text.
- Added Freeze OCR Override so Freeze can use high/100% OCR for screenshot-like accuracy.
- Added Interval Stable/Story-aware policy for manual story reading and VA-assisted story timing.
- Added Turn Transcript Accumulator / best-source-per-turn to avoid 20–90% partial dialog output.
- Added No-Downgrade Source Rule so shorter/noisier OCR frames do not replace a better full sentence.
- Added Speaker Prefix Sanitizer v3 for duplicated labels such as Phaetusa(?) in body text.
- Preserved v8.8.2 GitHub-safe layout and local runtime grouping.

# CHANGELOG — ORT Translation v8.8.2

## v8.8.2 — Project Structure Refactor & GitHub-Ready Layout

### Added
- Root launcher `START_HERE.bat` with simple menu.
- Root launcher `Start WebUI.bat`.
- Root launcher `Start OCR.bat`.
- Root launcher `Runtime.bat`.
- Clean `README.md`, `VERSION.txt`, `CHANGELOG.md`, and `.gitignore`.
- Outer folders under `ORT/` for docs, user_data, logs, cache, backups, and debug bundles.
- Migration map: `ORT/docs/migration/V8_7_9_TO_V8_8_1_STRUCTURE_MAP.md`.
- Structural validation report: `ORT/docs/test_reports/ORT_V8_8_1_STRUCTURE_VALIDATION_REPORT.md`.
- Current master continuity handoff in `ORT/docs/handoff/` and runtime docs.

### Changed
- Runtime is now placed under `ORT/runtime_app/` and launched through compatibility launchers.
- Display/version labels updated to v8.8.2 where relevant.
- Historical logs/cache/backups are not included in the clean v8.8.2 package.

### Not changed intentionally
- OCR behavior.
- Auto/Freeze/Interval runtime policy.
- Translation model behavior.
- v8.7.9 cache namespace `v8_7_9_responsive_turn_safe_ct2`.

### Next target
- v8.8.2: Auto Smooth, Freeze Ultra OCR, Interval Stable/Story-aware, Turn Transcript Accumulator, Overlay Anti-Flicker, and mode-specific runtime policy.


## v8.8.2 R2 — Local Runtime Grouping

- Menambahkan `ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/` sebagai satu lokasi untuk file/folder lokal besar yang mudah dikecualikan saat ZIP/GitHub.
- Menambahkan `EXPORT_GITHUB_SOURCE.bat` dan `ORT/tools/packaging/export_github_source.py` untuk membuat ZIP source bersih.
- Memperbarui `.gitignore`, README, dan migration guide.
- Tidak mengubah perilaku OCR, translation, Auto/Freeze/Interval, atau scheduler.
