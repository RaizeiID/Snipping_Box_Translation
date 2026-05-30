# ORT Translation — Correction Addendum: Helen & Helena Dual Canonical Identity Guard
**Tanggal:** 26 Mei 2026  
**Status:** Koreksi resmi roadmap calon v8.7.3 setelah konfirmasi pengguna  
**Berlaku untuk:** `GFL2_EXILIUM` speaker identification, overlay, named-entity protection, cache cleanup, dan dokumentasi handoff

## 1. Koreksi Keputusan Sebelumnya

Pengguna mengonfirmasi bahwa:

```text
Helen   = karakter GFL2 yang valid
Helena  = karakter GFL2 yang valid
```

Keduanya adalah karakter berbeda dan harus dipertahankan secara terpisah.

Dengan demikian, rekomendasi lama yang menyatakan `Helena → Helen` sebagai migration umum **dibatalkan dan diganti** dengan desain berikut:

```text
Helen   tetap canonical speaker tersendiri
Helena  tetap canonical speaker tersendiri
Sistem harus mencegah Helen salah dilabel Helena
Sistem harus mencegah Helena salah dilabel Helen
```

## 2. Bug Aktual yang Tetap Valid

Audit source sebelumnya menemukan bahwa:
- raw Name ROI dapat membaca `Helen`;
- known-name/database memuat `Helena`;
- fuzzy canonical matching terlalu longgar;
- sistem dapat memilih label `Helena` ketika raw ROI sebenarnya `Helen`;
- selected label kemudian disisipkan di depan body yang masih berawalan `Helen`;
- hasil overlay menjadi `Helena: Helen ...`.

Koreksi baru tidak membatalkan diagnosis bug tersebut. Yang dibatalkan adalah solusi menghapus/menggabungkan karakter Helena.

## 3. Desain Wajib: Dual Canonical Identity Guard

### Canonical protected names

```text
Helen
Helena
```

Kedua nama masuk dalam trusted GFL2 speaker registry dan Named Entity Protection.

### Aturan identitas

| Raw Name ROI / candidate | Hasil yang benar |
|---|---|
| `Helen` exact | `Helen` |
| `Helena` exact | `Helena` |
| `Helen` | Tidak boleh fuzzy-map menjadi `Helena` |
| `Helena` | Tidak boleh fuzzy-map menjadi `Helen` |
| Alias OCR milik Helen yang disetujui | Hanya boleh kembali ke `Helen` |
| Alias OCR milik Helena yang disetujui | Hanya boleh kembali ke `Helena` |

### Prinsip implementasi

1. Exact-match dan explicit alias-match harus menang sebelum fuzzy matching.
2. Fuzzy mapping antarnama canonical yang merupakan prefix/extension dekat harus diblok:
   - `Helen` vs `Helena`
   - aturan serupa untuk nama lain yang sangat mudah tertukar.
3. Nama dari legacy NPC database tidak boleh otomatis dipercaya oleh Name ROI.
4. Speaker final hanya boleh berasal dari:
   - trusted registry exact match;
   - alias terverifikasi;
   - temporal voting dari ROI nama;
   - koreksi manual pengguna.
5. Speaker tidak boleh ditebak hanya dari body dialog.

## 4. Body Prefix Deduplication yang Aman

Setelah speaker dipilih:

| Selected speaker | Body awal | Output body |
|---|---|---|
| `Helen` | `Helen I am worried...` | `I am worried...` |
| `Helena` | `Helena I have waited...` | `I have waited...` |
| `Helen` | `Helena said...` | Jangan strip; itu dapat merupakan isi kalimat |
| `Helena` | `Helen said...` | Jangan strip; tandai konflik untuk review |

Aturan ini mencegah kasus salah seperti:

```text
Helena: Helen I am worried...
```

tanpa merusak dialog yang benar-benar menyebut karakter lain pada body.

## 5. Telemetry yang Wajib Ditambahkan

Agar bug dapat diverifikasi dan tidak berulang, event berikut harus masuk log/update berikutnya:

```text
GFL2_RAW_NAME_ROI
GFL2_CANONICAL_EXACT_MATCH
GFL2_CANONICAL_ALIAS_MATCH
GFL2_FUZZY_BLOCKED_SIMILAR_CANONICAL
GFL2_SPEAKER_CONFLICT
GFL2_BODY_PREFIX_STRIPPED
FINAL_OVERLAY_SPEAKER
FINAL_OVERLAY_BODY
```

Contoh event yang diharapkan ketika dialog Helen:

```text
raw_name_roi=Helen
canonical_exact_match=Helen
selected_speaker=Helen
body_prefix_stripped=Helen
final_overlay_speaker=Helen
```

Contoh event ketika fuzzy berbahaya dicegah:

```text
raw_name_roi=Helen
candidate=Helena
fuzzy_blocked_reason=protected_distinct_canonical_pair
selected_speaker=Helen
```

## 6. Cache dan Named Entity Protection

### Named Entity Protection

Keduanya harus dilindungi secara terpisah sebelum backend:

```text
Helen   → placeholder tersendiri → restore Helen
Helena  → placeholder tersendiri → restore Helena
```

Jangan menggunakan normalisasi yang menggabungkan keduanya.

### Cache cleanup/invalidation

Cache/output lama yang tercipta dari bug klasifikasi dapat dibersihkan atau di-invalidasi bila mengandung pola tercemar seperti:

```text
Helena Helen ...
```

Namun proses cleanup:
- tidak boleh menghapus canonical `Helena`;
- tidak boleh mengubah dialog Helena yang benar menjadi Helen;
- hanya membuang/memperbaiki entry yang terbukti berasal dari duplikasi/cross-label bug.

## 7. Regression Test Wajib

| Test case | Expected result |
|---|---|
| Raw ROI `Helen`, body `Helen I am worried` | Label `Helen`, body `I am worried` |
| Raw ROI `Helena`, body `Helena I have waited` | Label `Helena`, body `I have waited` |
| Raw ROI `Helen`, candidate fuzzy `Helena` | Fuzzy ditolak, label tetap `Helen` |
| Raw ROI `Helena`, candidate fuzzy `Helen` | Fuzzy ditolak, label tetap `Helena` |
| Speaker `Helen`, body menyebut `Helena` | Label tetap `Helen`, mention body tidak dihapus |
| Speaker `Helena`, body menyebut `Helen` | Label tetap `Helena`, mention body tidak dihapus |
| Cached legacy source `Helena Helen ...` | Ditandai invalid/cleanup tanpa menghapus Helena valid |

## 8. Pembaruan Roadmap Nama Protected GFL2

Daftar protected speaker untuk patch berikutnya tetap mencakup:

```text
DP-12
KSVK
Alya Kujou / configurable Commander Display Name
Melanie
Helen
Helena
Balthilde
Phaetusa
Dushevnaya
Suomi
Lentine
Descender Zero
Dandelion
```

## 9. Keputusan Final

Patch berikutnya tidak boleh berisi aturan global `Helena → Helen`.

Keputusan yang benar:

```text
Pertahankan Helen dan Helena sebagai dua canonical speaker valid.
Perbaiki OCR/ROI/canonical/overlay agar keduanya tidak saling tertukar.
Bersihkan hanya output/cache/legacy classification yang terbukti salah.
```
