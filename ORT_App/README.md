# ORT Translation v8.7.2 — Changed-Files Patch

Patch ini diterapkan **di atas folder ORT Translation v8.7 yang sudah ditimpa patch v8.7.1**. ZIP v8.7.2 hanya memuat file baru/berubah dan tidak menimpa data pengguna seperti `npc_database.json`, `data_processing_store.json`, `webui_prefs.json`, maupun state pribadi.

## Fokus v8.7.2

- **Stable Final Cache v2**: mengatasi akar `cache=MISS` terus-menerus, memisahkan preview progresif dari penyimpanan final, dan menambahkan memo dialog pendek.
- **GFL2 Speaker ROI / Name Pass v2**: pass terpisah untuk nama seperti `DP-12` dan `KSVK`, temporal label hold, serta recovery terbatas untuk glyph tipis di awal baris.
- **GFL2 Text Repair v2**: perbaikan kontekstual untuk `KSVKis`, `DP-125`, `Ifshe`, `isan`, `ofthe`, `ofit`, `Iike`, `apologles`, dan `recelved`.
- **IDN Evaluation Export**: log pasangan source normal, output backend, dan output IDN final agar kualitas dapat dinilai nyata.
- **Warmup & telemetry**: prewarm IDN/NLP, alasan perubahan OCR resolution, dan status cache/backend lebih dapat diaudit.
- **NPC cleanup v2**: dry-run/migration untuk false speaker lama tanpa menghapus seed valid `DP-12` dan `KSVK`.

## Cara memasang

1. Backup folder proyek v8.7.1 Anda.
2. Ekstrak isi `ORT_Translation_v8_7_2_CHANGED_FILES_PATCH.zip` ke root folder proyek yang sudah memakai v8.7.1.
3. Pilih **Replace/Overwrite** untuk file yang sama.
4. Jalankan aplikasi dan uji GFL2 pada scene yang memuat `DP-12`, `KSVK`, dialog progresif, serta replay dialog yang sama.

## Indikator uji yang perlu diperiksa

- `CACHE_STORE_STABLE_FINAL` muncul ketika dialog final stabil.
- `CACHE_HIT_STABLE_FINAL` atau `CACHE_DUPLICATE_OCR_SUPPRESSED` muncul saat teks final diulang.
- Event `GFL2_SPEAKER_ROI` membantu mempertahankan label nama `KSVK`/`DP-12`.
- File evaluasi IDN tersimpan di `logs/idn_evaluation_v8_7_2.jsonl`.
- V4 tetap harus dilaporkan sebagai Argos Offline bila online assist tidak benar-benar applied.

## Batas validasi

Patch telah diuji melalui compile dan regression test sintetis. Ketepatan geometry Name ROI, pemulihan glyph `I`, cache HIT pada replay nyata, dan kualitas output Indonesia tetap harus dikonfirmasi melalui sesi game aktual Anda.
