# ORT Translation v8.7.7 — Installation & Test Guide

1. Gandakan folder v8.7.6 menjadi `ORT_Translation_v8_7_7_TEST`.
2. Ekstrak patch changed-files v8.7.7 ke folder TEST dan overwrite file yang sama.
3. Jalankan:
   ```powershell
   python tools/v8_7_7_cache_rotation.py --base-dir .
   python tools/v8_7_7_identity_migration.py --base-dir .
   python tools/v8_7_7_cache_rotation.py --base-dir . --apply
   python tools/v8_7_7_identity_migration.py --base-dir . --apply
   ```
4. Di WebUI > Runtime & Tools, tekan **Repair / Rebind CT2 Model & SPM Path**, lalu **Test Fast Engine**.
5. Uji Baseline Correctness terlebih dahulu. Cari event `SEMANTIC_HALLUCINATION_BLOCKED`, `PREVIEW_HELD_INCOMPLETE`, `CT2_JOB_FALLBACK`, dan `IDN_QUALITY_LOCK_HELD`.
6. Ekspor bukti:
   ```powershell
   python tools/v8_7_7_test_ledger.py --base-dir .
   python tools/export_debug_bundle_v8_7_7.py
   ```
7. Setelah baseline aman, uji Mode Responsif pada scene yang sama.

Nama exact-only baru melalui migrasi: `Berryfield`, `Cocoon`, `Carmen`, `Another Unfamiliar Worker`.
Tidak ditambahkan global: `Vilyz`, `ARVITA ID`, `ATVITA ID`.
