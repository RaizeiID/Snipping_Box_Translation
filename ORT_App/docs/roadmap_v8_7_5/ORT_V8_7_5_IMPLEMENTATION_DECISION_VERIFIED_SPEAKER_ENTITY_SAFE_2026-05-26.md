# ORT Translation v8.7.5 — Implementation Decision

## Dasar Keputusan
v8.7.4 diuji melalui banyak model, ZIP runtime, structured logs, dan tiga video POV. Bukti visual menunjukkan `Zhaohui` dan `Vector` terbaca di game/overlay body tetapi tidak menjadi label speaker, sedangkan `Alya Kujou` dapat berlabel. Audit registry membuktikan katalog resmi GFL2 tersedia tetapi live speaker tier terlalu sempit dan migrasi membaca field salah. Audit EntitySpan membuktikan marker backend `ORT_BEND/BKED` masih dapat masuk output/cache.

## Implementasi Dipilih
- `verified_character_speaker_exact` bagi semua karakter resmi GFL2 dalam katalog; exact Name ROI/exact prefix saja.
- Fuzzy tetap hanya untuk speaker aktif/reviewed alias; role NPC tetap manual-approved.
- EntitySpan penuh sebelum backend; tidak ada token nama internal yang dikirim ke Argos/CT2/online assist.
- Guard generik memblok marker internal pada overlay/cache/export.
- Speaker transition invalidation membuang hasil overlay lama saat speaker baru sudah terdeteksi.
- Cache namespace baru dan migration/rotation berbasis backup/dry-run.

## Prioritas Validasi Live
Uji `Zhaohui`, `Vector`, `Helen`, `Helena`, `Alya Kujou`, `Phaetusa`, `Suomi`, dan story cepat dengan Baseline lalu Mode Responsif. Debug bundle v8.7.5 menjadi artefak wajib analisis berikutnya.
