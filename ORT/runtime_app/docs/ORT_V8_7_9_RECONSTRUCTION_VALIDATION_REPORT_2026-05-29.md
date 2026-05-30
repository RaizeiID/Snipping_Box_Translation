# ORT Translation v8.7.9 — Reconstruction Validation Report

## Status Rekonstruksi
Patch ini dibangun ulang pada 29 Mei 2026 dari `ORT_Translation_v8_7_8(1).zip` yang diunggah pengguna dan memo/riwayat audit v8.7.8→v8.7.9 yang masih tersedia. Patch ini bukan klaim bahwa byte ZIP identik dengan artefak lama yang gagal diunduh; ini adalah rekonstruksi terverifikasi terhadap fitur dan diagnosis yang diwariskan.

## Fokus Implementasi
- Trusted Preview CT2-only yang tidak cache/training.
- Stable Final tetap melalui safety gate.
- Hard Strict CT2 Story untuk GFL2 saat CT2 tersedia.
- Turn-Safe Overlay dan Scene Exit Guard.
- General Semantic Fidelity Guard dengan fallback ke CT2 literal anchor.
- Sinkronisasi version/UI/log/cache namespace menjadi `v8.7.9` / `v8_7_9_responsive_turn_safe_ct2`.
- Retained safe exact/role identities dan terminology ledger; candidate mining tetap review-only.

## Validasi Source Kerja
- Python compile untuk core modules dan tools changed-files: PASS.
- `tools/v8_7_1_regression_test.py`: PASS.
- `tools/v8_7_2_regression_test.py`: PASS.
- `tools/v8_7_3_regression_test.py`: PASS.
- `tools/v8_7_4_regression_test.py`: PASS setelah assertion kompatibilitas diarahkan ke namespace rilis v8.7.9.
- `tools/v8_7_5_regression_test.py`: PASS setelah assertion kompatibilitas diarahkan ke namespace rilis v8.7.9.
- `tools/v8_7_6_regression_test.py`: PASS setelah assertion kompatibilitas diarahkan ke namespace rilis v8.7.9.
- `tools/v8_7_7_regression_test.py`: PASS setelah assertion kompatibilitas diarahkan ke namespace rilis v8.7.9.
- `tools/v8_7_8_regression_test.py`: PASS setelah assertion kompatibilitas diarahkan ke namespace rilis v8.7.9.
- `tools/v8_7_9_regression_test.py`: PASS; mencakup scene exit, turn-safe progressive/new-turn, semantic drift negation/action, Trusted Preview CT2-only, Hard Strict CT2 Argos suppression, cache namespace, identity exclusion, dan dry-run migration.
- `tools/v8_7_gfl_smoke_test.py`: PASS.
- Identity migration dry-run: PASS; official exact entries 69, approved exact/role retained, Commander exclusions dipertahankan.
- Cache rotation dry-run: PASS; mendeteksi 12 cache lama v8.7.7/v8.7.8 yang harus diisolasi pada folder TEST.
- Candidate miner bounded: PASS; hasil tetap review-only dan tidak dimasukkan sebagai auto-live speaker.

## Validasi Paket pada Baseline Bersih
- ZIP patch diekstrak ulang di atas baseline asli `ORT_Translation_v8_7_8(1).zip`: PASS.
- Archive integrity dan pengecualian data aktif: PASS; 27 file changed-files saja.
- Compile changed modules setelah overlay bersih: PASS.
- Regression v8.7.1 sampai v8.7.9 dan GFL smoke setelah overlay bersih: PASS.
- Identity migration dry-run setelah overlay bersih: PASS.
- Cache rotation dry-run setelah overlay bersih: PASS; mendeteksi 12 cache lama untuk isolasi.
- Candidate Miner reduced/bounded pada clone: PASS; hasil tetap berstatus review-only.
- Identity migration `--apply` dan cache rotation `--apply` pada clone disposable, lalu regression v8.7.9: PASS.

## Batasan Validasi
Validasi ini membuktikan integritas patch statis dan regression/unit/smoke pada baseline. Rekaman POV dan log mentah lama tidak tersedia lagi sebagai file sumber, sehingga pengujian live gameplay v8.7.9 tetap wajib setelah patch diterapkan pada folder TEST. Fokus live test: `TRUSTED_PREVIEW_OVERLAY`, `FINAL_OVERLAY`, `STALE_OVERLAY_CLEARED_ON_NEW_TURN`, `SCENE_EXIT_OVERLAY_CLEARED`, `IDN_POLISH_DRIFT_FALLBACK_TO_CT2_LITERAL`, `STRICT_CT2_STORY_FALLBACK_SUPPRESSED`, serta target Argos story menuju nol saat CT2 aktif.

## Packaging Safety
ZIP changed-files tidak menyertakan registry aktif, settings/prefs aktif, app state, cache, logs, status, backups, reports, ataupun debug bundles pengguna.
