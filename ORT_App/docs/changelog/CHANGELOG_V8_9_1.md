# ORT Translation v8.9.1 Hotfix — Overlay Placeholder Suppression & Sweeper Registry Activation

Tanggal: 2026-06-03

## Fokus hotfix
- Memperbaiki masalah baru setelah v8.9.0: overlay terlihat lebih bersih, tetapi placeholder/ID preview terlalu sering muncul pada rekaman.
- Memastikan `Sweeper` masuk registry aktif yang benar dan tampil sebagai entity speaker Green.
- Menghentikan default lama yang masih memuat `gfl2_entity_registry_v8_8_8_r2.json` dari launcher/runtime.
- Memperkuat filter UI/battle/loading noise dari log v8.9.0: `Coading Resources`, `Marionette Repalr`, `Marlonette Repalr`, dan mixed-script OCR garbage.
- Memastikan label runtime/WebUI/log utama memakai v8.9.1.

## Perubahan utama
1. `ORT_GFL2_ENTITY_REGISTRY` default diarahkan ke `configs/gfl2_entity_registry_v8_9_1.json`.
2. Registry v8.9.1 menambahkan/menjamin `Sweeper`, `Klukai`, `Nyxie`, `Phaetusa`, `Ullrid`, `Littara`, `Groza`, dan `Helen`.
3. Generic waiting preview seperti `Menerjemahkan dialog baru…` tidak lagi muncul default. English source preview disenyapkan sampai final Indonesia siap.
4. UI Filter v4.1 menolak OCR noise dari battle/loading/repair menu dan campuran simbol/CJK.
5. Regression test baru: `tools/v8_9_1_regression_test.py`.

## Catatan
- `ORT_OVERLAY_SHOW_ID_WAITING_PREVIEW=1` dapat digunakan bila pengguna ingin menampilkan pesan tunggu Indonesia.
- Default baru: silent pending, sehingga overlay tidak menampilkan source English atau placeholder generik.
