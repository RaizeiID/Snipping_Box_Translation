# CHANGELOG — ORT Translation v8.8.1

## v8.8.1 — Project Structure Refactor & GitHub-Ready Layout

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
- Display/version labels updated to v8.8.1 where relevant.
- Historical logs/cache/backups are not included in the clean v8.8.1 package.

### Not changed intentionally
- OCR behavior.
- Auto/Freeze/Interval runtime policy.
- Translation model behavior.
- v8.7.9 cache namespace `v8_7_9_responsive_turn_safe_ct2`.

### Next target
- v8.8.2: Auto Smooth, Freeze Ultra OCR, Interval Stable/Story-aware, Turn Transcript Accumulator, Overlay Anti-Flicker, and mode-specific runtime policy.


## v8.8.1 R2 — Local Runtime Grouping

- Menambahkan `ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/` sebagai satu lokasi untuk file/folder lokal besar yang mudah dikecualikan saat ZIP/GitHub.
- Menambahkan `EXPORT_GITHUB_SOURCE.bat` dan `ORT/tools/packaging/export_github_source.py` untuk membuat ZIP source bersih.
- Memperbarui `.gitignore`, README, dan migration guide.
- Tidak mengubah perilaku OCR, translation, Auto/Freeze/Interval, atau scheduler.
