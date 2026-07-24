# ORT Translation v8.7.5 — Runtime & UI Guide

## Pengujian pertama
Gunakan **Baseline Correctness** setelah migrasi/rotasi cache pada folder TEST. Verifikasi label `Zhaohui`, `Vector`, `Helen`, `Helena`, `Alya Kujou`, dan `Phaetusa` sebelum mencoba Mode Responsif.

## Verified character speaker exact
Pada GFL2, karakter resmi di katalog boleh menjadi label speaker bila Name ROI atau prefix dialog cocok tepat. Kebijakan ini tidak memberi fuzzy bebas dan tidak mempromosikan NPC title/kata narasi.

## Mode Responsif / Story Cepat
Aktifkan setelah baseline benar. Mode ini mengutamakan frame terbaru dan mengurangi queue progresif; Two-Pass OCR tetap aktif agar identitas speaker tidak hilang.

## Tool penting
```bash
python tools/v8_7_5_cache_rotation.py --base-dir .
python tools/v8_7_5_identity_migration.py --base-dir .
python tools/v8_7_5_cache_rotation.py --base-dir . --apply
python tools/v8_7_5_identity_migration.py --base-dir . --apply
python tools/export_debug_bundle_v8_7_5.py
```
