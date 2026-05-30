# ORT Translation v8.7.4 — Audit Uji Gameplay, Regression Speaker Label, dan Rencana Perbaikan Berikutnya
**Tanggal audit:** 26 Mei 2026  
**Basis audit:** ZIP runtime aktual `ORT_Translation_v8_7_4.zip`, 10 sesi uji gameplay GFL2 v8.7.4, structured event logs, `idn_evaluation_v8_7_4.jsonl`, cache aktual, dan source runtime.  
**Catatan video:** pesan pengguna menyebut video POV, tetapi unggahan yang tersedia pada sesi audit hanya file log teks dan ZIP runtime; tidak ditemukan file video di unggahan atau di dalam ZIP.

## 1. Kesimpulan Eksekutif

v8.7.4 berhasil memperbaiki sebagian masalah besar v8.7.3:
- namespace cache baru `v8_7_4_entity_span_responsive` sudah benar-benar aktif setelah rotasi cache lama dijalankan;
- kasus `ORT_ENTITY_*` lama tidak lagi menjadi pola utama;
- `Helen`/`Helena`, `KSVK`, `Phaetusa`, `Alya Kujou`, dan sejumlah seed prioritas dapat dipilih oleh speaker ROI pada sesi yang sesuai.

Namun audit menemukan dua masalah serius yang masih tersisa:

### P0-A — Label karakter valid banyak luput karena registry live terlalu sempit dan migration salah schema
Katalog referensi GFL2 berisi 69 nama karakter, tetapi Name ROI hanya mempercayai 13 speaker aktif (12 protected + Commander `Alya Kujou`). Banyak nama yang sudah valid di katalog tidak boleh menjadi label speaker:
- `Ullrid`, `Colphne`, `Groza`, `Vector` berada di `legacy_untrusted`;
- `Zhaohui` hanya berada di reference catalog, tidak aktif sebagai speaker.

Lebih fatal, fungsi migrasi registry membaca field `reference_names`, padahal katalog aktual menyimpan nama dalam `entries[].display_name`. Karena itu, nama lama yang valid tidak pernah dipromosikan berdasarkan katalog dan jatuh ke `legacy_untrusted`.

### P0-B — EntitySpan belum benar-benar bebas token backend
v8.7.4 masih mengirim token backend `__ORT_BKEND_###__` melalui mesin terjemahan. Backend dapat merusaknya menjadi `_ _ ORT _ BKED ...` atau `_ ORT _ BEND ...`. Guard v8.7.4 hanya mengenali pola `ENTITY|BKEND`, sehingga varian `BEND/BKED` dapat lolos ke output final dan cache baru.

## 2. Statistik 10 Sesi Gameplay v8.7.4

Sesi yang dihitung:
- ORTCore IDN V1, V2, V3, V4, V5
- ORTCore Lite IDN V5, Lite IDN V3
- ORTCore Fast IDN
- ORTCore Lite V5
- ORTCore Fast V1

| Total PIPE | MISS | HIT_STABLE_FINAL | DUPLICATE Suppression | Median | P90 | P95 | Maksimum |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 9.957 | 9.578 (96,2%) | 261 | 118 | 183 ms | 352 ms | 431 ms | 2.318 ms |

Tambahan:
- PIPE >= 500 ms: 284
- PIPE >= 1.000 ms: 13
- Semua sesi uji menggunakan `responsive_story=0` dan `latest_frame_wins=0`, sehingga Mode Responsif belum benar-benar diuji.
- Applied backend tetap `argos_offline`.
- Fast IDN/Lite IDN melaporkan CT2 tidak tersedia karena file `source.spm` dan `target.spm` hilang pada folder model.

## 3. Timing Tahap Runtime

Berdasarkan 9.809 output `TRANSLATION_RESULT` dari `TITANMAIN.py`:

| Tahap | Median | P95 | Maksimum |
|---|---:|---:|---:|
| OCR Body | 93,25 ms | 201,99 ms | 674,66 ms |
| Name ROI OCR | 42,57 ms | 109,04 ms | 331,53 ms |
| Entity Match | 0 ms (dibulatkan) | 0 ms | 6 ms |
| Backend Translation | 120 ms | 365,60 ms | 2.244 ms |
| IDN Post | 4 ms | 8 ms | 26 ms |
| Queue Wait | 40,19 ms | 1.502,16 ms | 3.819,85 ms |

Diagnosis performa:
- Two-Pass/Name ROI menambah biaya nyata, tetapi bukan bottleneck dominan.
- Backend Argos dan penumpukan queue pada baseline Auto Story masih menjadi beban terbesar.
- Mode Responsif belum diuji, sehingga belum dapat dinilai efektivitas latest-frame-wins/coalescing pada gameplay pengguna.

## 4. Root Cause Pelabelan Nama Karakter

### 4.1 Source runtime hanya memakai trusted live registry untuk label
`TITANMAIN.py` membuat tracker sebagai:

```python
GFL2SpeakerTracker(trusted_speaker_names("GFL2_EXILIUM"), ...)
```

`split_speaker_and_dialog()` juga memakai `trusted_speaker_names(...)`, bukan katalog referensi.

### 4.2 Seed/active live hanya 13 nama
`app/ocr/gfl2_speaker_roi.py::SEED_NAMES` hanya memuat:

```text
DP-12, KSVK, Helen, Helena, Melanie, Balthilde, Phaetusa,
Alya Kujou, Lentine, Dushevnaya, Descender Zero, Dandelion, Suomi
```

`speaker_registry_v2.json` mempunyai protected list yang sama (kecuali Commander berada di `user_configured`).

### 4.3 Katalog lengkap tidak berfungsi untuk speaker labeling
`configs/reference_roster_catalog_v8_7_3.json` memiliki 69 entry GFL2. Katalog ini dipakai untuk Named Entity Protection, tetapi tidak dipakai sebagai speaker candidate yang boleh dilabel Name ROI.

Akibatnya, karakter yang diketahui sistem tetap tidak dapat dilabel bila tidak berada di active registry.

### 4.4 Bug migration schema
Di `app/identity/speaker_registry.py::_migrate_legacy()`:

```python
catalog_keys = {_key(n) for n in catalog.get(game, {}).get("reference_names", [])}
```

Padahal katalog aktual berbentuk:

```json
{
  "entries": [
    {"display_name": "Ullrid", ...},
    {"display_name": "Zhaohui", ...}
  ]
}
```

Karena `reference_names` kosong/tidak ada, promosi legacy verified catalog gagal. Nama valid masuk `legacy_untrusted` alih-alih protected/verified speaker.

## 5. Bukti Nama yang Luput dalam Log v8.7.4

| Nama | Status Registry Aktual | Prefix OCR Terbaca | ROI Selected | Final Overlay Label | Diagnosis |
|---|---|---:|---:|---:|---|
| `Suomi` | Active/protected | 4 | 44 | 20 | Bekerja pada sesi V3; tidak rusak total |
| `Ullrid` | `legacy_untrusted` | 0; scene speaker terbaca `rid Ahem...` | 0 | 0 | Registry salah + OCR kehilangan awal nama |
| `Zhaohui` | Reference-only | 139 | 0 | 0 | OCR sudah dapat benar pada Lite V5, tetapi registry melarang label |
| `Colphne` | `legacy_untrusted` | 331 | 0 | 3 parsial/text-parser | Exact OCR banyak, tetapi tidak live-trusted |
| `Groza` | `legacy_untrusted` | 129 | 0 | 0 | Exact OCR ada, tetapi tidak live-trusted |
| `Vector` | `legacy_untrusted` | 109 | 0 | 0 | Exact OCR ada, tetapi tidak live-trusted |
| `Helen` | Active/protected | 231 | 2.107 | 969 | Berfungsi dominan |
| `KSVK` | Active/protected | 0 | 523 | 136 | Name ROI bekerja pada scene terkait |
| `Alya Kujou` | Active/user-configured | 156 | 1.848 | 874 | Berfungsi dominan |
| `Phaetusa` | Active/protected | 369 | 1.351 | 539 | Berfungsi dominan |

Kesimpulan: pengamatan pengguna bahwa pelabelan terlihat hanya berfokus pada `Helen`, `KSVK`, dan Commander sesuai dengan implementasi registry aktual. Ini bukan sekadar kesalahan OCR.

## 6. Root Cause EntitySpan yang Masih Bocor

### 6.1 EntitySpan baru hanya mengamankan post-processing
v8.7.4 sudah memproses bagian setelah backend sebagai `TextSpan` dan `EntitySpan`, sehingga token `ORT_ENTITY` versi lama berkurang.

Namun sebelum backend, `translation_engine.py` masih menjalankan:

```python
entity_protection = protect_named_entities(translate_src, game_profile)
backend_raw = self._translate_offline(entity_protection.source)
backend_out = restore_named_entities(backend_raw, entity_protection)
```

`protect_named_entities()` sekarang memakai token backend:

```text
__ORT_BKEND_000__
```

### 6.2 Backend masih dapat merusak token
Dalam structured event ditemukan bentuk:

```text
_ _ ORT _ BKED _ 000 _ _
_ ORT _ BEND _ 000 _ _
```

### 6.3 Guard belum mencakup variasi rusak
Regex internal-token saat ini hanya mencari:

```text
ENTITY | BKEND
```

Ia tidak mencakup variasi:

```text
BKED | BEND
```

Akibatnya:
- 19 `ENTITY_RESIDUAL_BLOCKED` tercatat;
- `idn_evaluation_v8_7_4.jsonl` masih memiliki 6 final output marker internal;
- `FINAL_OVERLAY` masih mengandung marker pada 6 output;
- cache namespace baru telah terkontaminasi pada beberapa file.

## 7. Solusi Wajib untuk Update Berikutnya

### 7.1 Tambahkan tier `verified_character_speaker_exact`
Jangan kembali mempercayai seluruh legacy NPC, tetapi jangan juga membatasi seluruh playable/story character hanya ke 12 seed.

Untuk GFL2:
- semua 69 karakter terverifikasi dalam katalog masuk `verified_character_speaker_exact`;
- nama pada tier ini boleh menjadi label **hanya melalui Name ROI exact / longest-match-first** atau prefix exact yang benar-benar berada di awal dialog;
- fuzzy matching dan alias tidak otomatis dibuka untuk seluruh katalog;
- title/role NPC tetap manual-approved.

Dampak:
- `Zhaohui`, `Ullrid`, `Colphne`, `Groza`, `Vector`, dan karakter GFL2 sah lain dapat kembali berlabel bila benar terbaca pada Name ROI;
- false words seperti `Dontworry`/`Her` tetap tidak dipercaya.

### 7.2 Perbaiki migrasi catalog
Ganti pemeriksaan katalog agar membaca:

```python
entries[].display_name
```

bukan hanya `reference_names`.

Sediakan dry-run yang menunjukkan:
```text
Ullrid  : legacy_untrusted → verified_character_speaker_exact
Colphne : legacy_untrusted → verified_character_speaker_exact
Groza   : legacy_untrusted → verified_character_speaker_exact
Vector  : legacy_untrusted → verified_character_speaker_exact
Zhaohui : reference_only   → verified_character_speaker_exact
```

### 7.3 Tambahkan telemetry rejected ROI
Saat Name ROI membaca nama tetapi ditolak karena tidak berada di registry, log saat ini hampir tidak menjelaskannya.

Tambahkan:
```text
GFL2_NAME_ROI_RAW_ALL
GFL2_NAME_ROI_REJECTED
GFL2_NAME_ROI_REJECT_REASON
GFL2_REFERENCE_EXACT_PROMOTED
```

Ini membedakan:
- OCR gagal: `Ullrid → rid`, `Zhaohui → Zhohul`;
- registry menolak meskipun OCR benar: `Zhaohui`, `Colphne`, `Groza`, `Vector`.

### 7.4 EntitySpan harus mencakup backend
Opsi A pengguna belum diterapkan penuh. Update berikutnya harus menghindari token string pada backend:

```text
TextSpan → translate backend
EntitySpan → tidak masuk backend sebagai token
Compose final → postprocess TextSpan saja
```

Bila diperlukan strategi khusus untuk menjaga grammar, gunakan composer span terstruktur; jangan kembali memakai literal `ORT_BKEND`.

Sementara itu, residual guard harus segera mencakup semua variasi:
```text
ORT_ENTITY
ORT_BKEND
ORT_BKED
ORT_BEND
_ _ ORT
```

Dan output residual:
- tidak tampil;
- tidak masuk export final;
- tidak disimpan ke cache.

### 7.5 Cache v8.7.4 perlu rotasi ulang setelah fix
Rotasi cache lama sudah berhasil, tetapi sebagian cache baru v8.7.4 kembali tercemar oleh `ORT_BEND/BKED`.

Setelah fix EntitySpan backend:
- gunakan namespace baru lagi;
- rotate cache `v8_7_4_entity_span_responsive` yang mengandung marker;
- jangan menyentuh registry/nama user yang valid.

### 7.6 Uji Mode Responsif sesudah correctness diperbaiki
Semua sesi saat ini memakai:
```text
responsive_story=0
latest_frame_wins=0
```

Jadi Mode Responsif belum dinilai.

Urutan uji yang benar:
1. perbaiki registry dan EntitySpan backend;
2. uji baseline correctness pada scene nama yang sama;
3. uji ulang scene sama dengan Mode Responsif aktif;
4. bandingkan label accuracy, queue wait, p95 latency, final overlay.

## 8. Prioritas Rilis Berikutnya

| Prioritas | Perubahan |
|---|---|
| P0 | Full backend-safe EntitySpan; tidak ada `ORT_BKEND/BEND/BKED` |
| P0 | Guard/caching/export memblok semua marker internal |
| P0 | Perbaiki catalog migration `entries[].display_name` |
| P0 | `verified_character_speaker_exact` untuk seluruh karakter GFL2 terverifikasi |
| P1 | Telemetry semua raw Name ROI dan rejected reason |
| P1 | Cache namespace baru setelah cache v8.7.4 tercemar |
| P1 | Uji Baseline vs Responsive menggunakan scene yang sama |
| P1 | CT2 setup/repair terpisah untuk Fast/Lite agar tidak selalu fallback Argos |

## 9. Kesimpulan Profesional

Masalah pelabelan karakter pada v8.7.4 bukan karena sistem perlu kembali ke database NPC liar. Masalahnya adalah desain baru terlalu ketat dan migrasinya salah membaca schema catalog, sehingga karakter resmi yang seharusnya aman malah tidak dipercaya untuk label.

Desain perbaikan yang tepat:
```text
Verified official character catalog
→ exact-only speaker label dari Name ROI
→ fuzzy/alias hanya setelah review
→ role/title tetap manual approved
→ legacy noise tetap untrusted
```

Sementara itu, EntitySpan harus diperbaiki lagi karena sekarang hanya melindungi tahap IDN/QA, tetapi token backend masih dapat bocor dan mencemari cache/output.
