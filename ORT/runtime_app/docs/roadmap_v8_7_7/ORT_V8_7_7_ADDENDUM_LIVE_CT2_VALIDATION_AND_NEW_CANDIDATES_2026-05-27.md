# ORT Translation v8.7.7 — Addendum Validasi Live CT2 Setelah Rebind Environment
**Tanggal:** 27 Mei 2026  
**Basis:** Dua live log pasca-perbaikan environment CT2/SPM: `Teks yang ditempel (1)(44).txt` dan `Teks yang ditempel (2)(17).txt`.  
**Status:** Bukti live untuk roadmap v8.7.7; belum merupakan patch runtime.

## 1. Kesimpulan Utama

Pemulihan manual CT2 telah berhasil sampai tahap aplikasi live. Sebelum perbaikan, Lite/Fast v8.7.6 berulang kali berjalan pada `argos_offline` karena SPM menunjuk folder TitanCORE lama. Pada dua log baru, pipeline translation benar-benar menunjukkan `engine=ct2_fast` pada hampir seluruh MISS.

Namun:
- kedua log tidak memuat boot header lengkap, video POV, `FINAL_OVERLAY`, atau cache/evaluation output final;
- sehingga keberhasilan CT2 dapat dibuktikan, tetapi berkurangnya hallucination semantik belum dapat dinyatakan final;
- seluruh proses masih `responsive=0`, sehingga progressive queue/stable-commit belum diuji dalam mode responsif.

## 2. Statistik Applied Engine dan Latency

| Log Live | Total PIPE | MISS CT2 | HIT Stable | Duplicate Suppression | Argos Offline | Legacy Argos | Median PIPE | P95 PIPE | Max PIPE |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Log 18:57 (`(1)(44)`) | 1.466 | 1.394 | 57 | 15 | 0 | 0 | 167 ms | 315 ms | 484 ms |
| Log 19:21 (`(2)(17)`) | 1.425 | 1.241 | 150 | 33 | 0 | 1 | 142 ms | ±276 ms | 477 ms |

### Timing backend dan queue

| Log Live | Backend Median | Backend P95 | Queue Median | Queue P95 | Queue Maksimum |
|---|---:|---:|---:|---:|---:|
| Log 18:57 | 93 ms | 233 ms | 31 ms | ±1.034 ms | 1.770 ms |
| Log 19:21 | 82 ms | 210 ms | 0 ms | ±163 ms | 671 ms |

Interpretasi:
- CT2 sudah benar-benar menjadi applied backend pada live gameplay;
- latency backend terlihat stabil dan tidak ada pipeline total melewati 500 ms pada cuplikan ini;
- queue progressive masih dapat tinggi pada scene tertentu karena Auto Story baseline masih menerjemahkan prefix bertahap dan `responsive=0`;
- satu `legacy_argos` transient pada 19:23:46 perlu telemetry reason agar diketahui apakah fallback disebabkan source terlalu pendek, error CT2 job-level, atau jalur legacy khusus.

## 3. Hallucination/Marker Internal pada Log Baru

Pencarian string pada dua live log tidak menemukan:
```text
nabi, Quran, Alquran, Mekah, Luth, Syuaib, malaikat,
kafir, mukmin, Al-masyâriq,
ORT_ENTITY, ORT_BKEND, ORT_BKED, ORT_BEND, _ _ ORT
```

Batasan:
- log baru berfokus pada raw OCR dan `PIPE`, bukan teks translation final/overlay/cache;
- tidak ditemukannya kata hallucination di sini belum membuktikan CT2 bebas hallucination;
- Universal Semantic Faithfulness Gate, semantic cache rotation, dan Dialogue Completeness Gate tetap P0 v8.7.7.

## 4. Kandidat Nama Baru/Penguatan Nama dari Log CT2 Live

### Prioritas tinggi untuk speaker exact-only setelah verifikasi visual terakhir

| Kandidat | Bukti di log baru | Rekomendasi |
|---|---:|---|
| `Berryfield` | 186 exact + variasi OCR `Berryfleld` 29, `Berrfield/Berrfleld`; muncul konsisten sebagai prefix dialog | Promosikan ke kandidat `approved_named_story_speaker_exact`; verifikasi visual sebelum auto-live global |
| `Cocoon` | 345 string occurrence pada log 18:57; berulang sebagai prefix dialog; juga pernah muncul pada log lama | Promosikan ke kandidat `approved_named_story_speaker_exact`; verifikasi visual final |

### Pending named-character/role review

| Kandidat | Bukti | Status |
|---|---:|---|
| `Carmen` / OCR `Carmon` | 28 / 12; konteks `Carmen Ignacio...` | Pending named-character review |
| `ATVITA ID` | 133; konteks `Be careful Nikketa` | Pending klasifikasi: speaker, UI tag, atau term |
| `Another Unfamiliar Worker` / `familiar Worker` | Terlihat kembali pada log 19:21 | Tetap role speaker review-only |

### Alias ROI-only, bukan karakter baru

| Bentuk OCR | Canonical | Bukti |
|---|---|---:|
| `Duyhevnaya` | `Dushevnaya` | 13 occurrence pada log 19:21 |

### Lore/special-term review baru

| Term | Bukti | Kategori |
|---|---:|---|
| `Blusphere` | 16; konteks body `Blusphere's the name, right?` | Kandidat lore/entity review, bukan speaker |

## 5. Terms yang Semakin Terkonfirmasi

Term yang sudah direncanakan pada v8.7.7 kembali muncul dalam log CT2 live:

| Term | Bukti Log Baru | Tindakan |
|---|---:|---|
| `Conglomerate` | 13 exact + 2 spaced OCR pada log 18:57; 19 exact pada log 19:21 | Masukkan `special_terms` GFL2 |
| `Yellow Zone` | 11 pada log 18:57 | Masukkan `special_terms` GFL2 |
| `URNC` | 8 pada log 18:57 | Masukkan `special_terms` GFL2 |
| `Griffin` / OCR `Grlffln` | muncul pada kedua log | Protect canonical `Griffin` dan normalisasi term OCR terkontrol |

`Vilyz` tetap **tidak** masuk karakter/NPC global; ia hanya boleh menjadi Commander Name per akun bila dikonfigurasi user.

## 6. Implikasi Roadmap v8.7.7

Tetap wajib:
1. Rebind CT2/SPM permanen di source/UI agar konfigurasi tidak bergantung pada environment manual.
2. Reason telemetry untuk job yang jatuh ke `legacy_argos` saat CT2 live.
3. Universal Semantic Faithfulness Gate sebelum overlay/cache/export.
4. Dialogue Completeness / Stable Commit Gate dan uji Mode Responsif.
5. Tambahkan/persiapkan official terms serta panel review nama/alias sesuai daftar.
6. Minta debug bundle + video POV dari pengujian CT2 aktif untuk menilai terjemahan final, hallucination, label visual, dan completeness.
