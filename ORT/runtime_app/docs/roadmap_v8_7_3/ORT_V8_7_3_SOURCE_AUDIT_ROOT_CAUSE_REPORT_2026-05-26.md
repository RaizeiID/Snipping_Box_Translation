# ORT Translation v8.7.2 — Audit Source Aktual dan Root-Cause Analysis GFL2/IDN
**Tanggal audit:** 26 Mei 2026  
**Paket yang diaudit:** `ORT_Translation_v8_7.zip`  
**SHA-256 paket:** `314899b6b6f8485e4f5bc2f3f0d0172545c959a641aece6befbe20525c3cf8c1`  
**Tujuan:** menemukan kesalahan implementasi aktual yang menyebabkan kegagalan label orange/nama karakter, kesalahan output IDN, isu token `I/II`, cache, dan latency sebagai dasar update berikutnya.

---

## 1. Ringkasan Eksekutif

Audit folder proyek aktual membuktikan bahwa sebagian besar gejala yang dilaporkan pengguna memiliki akar penyebab langsung pada source code dan data runtime:

1. **Regression `Helena Helen` memiliki akar pasti.**  
   `data_processing_backend.py` masih menanam seed `Helena`, sementara `Helen` tidak ada sebagai nama trusted. `app/ocr/gfl2_speaker_roi.py` menggunakan fuzzy matching longgar (`SequenceMatcher >= 0.84`) terhadap seluruh `NPC_DATABASE known`; raw ROI yang membaca `Helen` dengan confidence ±0.999 dipetakan menjadi `Helena`. Tracker lalu menyisipkan `Helena` di depan body yang sudah diawali `Helen`, sehingga output menjadi `Helena Helen ...`.

2. **`KSVK` sebenarnya pernah dideteksi oleh Name ROI, tetapi tidak sampai menjadi speaker overlay.**  
   Structured events menunjukkan 126 event speaker `KSVK`, dengan raw ROI `KSVK` sebanyak 100 event. Namun `TRANSLATION_RESULT` jalur tampilan mencatat speaker `KSVK` = 0. Source menunjukkan metadata ROI dimasukkan ke queue tetapi `TranslatorWorker` mengabaikannya dan kembali memecah speaker dari raw text/NPC database; hasil ROI bukan jalur otoritatif untuk label orange.

3. **Nama valid tidak dilabel karena tidak ada pada trusted speaker registry/seed.**  
   `Alya Kujou`, `Melanie`, `Helen`, `Balthilde`, dan `Phaetusa` tidak terdapat di seed Name ROI dan sebagian besar tidak ada di `npc_database.json`/data processing names. Padahal OCR sudah membaca `Alya Kujou`, `Balthilde`, dan `Phaetusa` sebagai prefix dialog berulang.

4. **ROI saat ini terlalu luas dan masih dipercayai oleh database NPC tercemar.**  
   Name ROI memakai 34% lebar x 43% tinggi crop dialog. Pada crop ±1419x176, ini berarti sekitar 482x76 piksel sebelum upscale—cukup luas untuk menangkap awal isi dialog, bukan hanya nama. Structured events membuktikan false selected speaker seperti `Her`, `Dontworry`, `Don't`, `Asimple`, dan `Noticing`.

5. **Kesalahan `Phaetusa → Phaedusa` terjadi pada backend translation, bukan pada raw OCR.**  
   `logs/idn_evaluation_v8_7_2.jsonl` memiliki 2.670 entry dan membuktikan `source_normalized` memuat `Phaetusa`, tetapi `backend_output` Argos telah menjadi `Phaedusa`, lalu `final_idn_output` tetap salah sebanyak 107 baris. Hal serupa terlihat pada contoh `Balthilde → Balthalde`.

6. **Stable Final Cache v2 sebenarnya sudah bekerja parsial.**  
   Live log biasa tidak menampilkan seluruh event terstruktur. Pada structured logs ditemukan 913 `CACHE_STORE_STABLE_FINAL`, 2.670 `CACHE_SKIP_PROGRESSIVE`, 10 `CACHE_HIT_STABLE_FINAL`, dan 2 `CACHE_DUPLICATE_OCR_SUPPRESSED`. Jadi masalah cache sekarang bukan “tidak pernah store”, melainkan hit rate rendah, observability UI kurang, dan cache telah menyimpan output yang tercemar nama salah.

7. **`Level II`/huruf `I` memerlukan final-revision policy.**  
   Evaluation export menunjukkan OCR dan output dapat akhirnya benar membaca `Level II`, tetapi frame lebih awal masih memiliki `Level I`/`Level Il`. Jika tampilan pengguna tetap salah, kesalahan berada pada final commit/cache/overlay timing. Diperlukan Critical Token Revision Guard, bukan sekadar OCR pass tambahan.

---

## 2. Struktur Source dan Data yang Relevan

| File/Area | Peran | Temuan audit |
|---|---|---|
| `TITANMAIN.py` | OCR queue, speaker splitting, overlay | Metadata ROI tidak digunakan langsung oleh `TranslatorWorker`; overlay tetap bergantung pada parsing text/NPC DB |
| `app/ocr/gfl2_speaker_roi.py` | Name ROI dan temporal hold | Seed minim, fuzzy longgar, memakai NPC database tercemar, ROI terlalu besar |
| `data_processing_backend.py` | Seed nama GFL2 | Masih memiliki `Helena`; tidak memiliki `Helen`, `Alya Kujou`, `Melanie`, `Balthilde`, `Phaetusa` |
| `npc_database.json` | Database speaker runtime | Masih mengandung `Helena`, `DP`, `Dp`, serta false legacy speakers |
| `app/translation/name_alias_normalizer.py` | Normalisasi nama/input | Baru melindungi DP-12/KSVK dan beberapa typo; belum melindungi nama baru |
| `translation_engine.py` | Cache/backend/export | Export aktif; belum mempunyai named-entity protection sebelum Argos |
| `cache/naturalized_idn_cache.json` | Cache IDN akhir | Berisi output salah seperti `Phaedusa` |
| `logs/*_events.jsonl` | Structured runtime events | Mengungkap event ROI/cache/export yang tidak tampak pada live log |
| `logs/idn_evaluation_v8_7_2.jsonl` | Source/backend/final IDN | Membuktikan perubahan nama oleh backend Argos |

---

## 3. Root Cause `Helen → Helena Helen`

### 3.1 Bukti data seed salah

Di `data_processing_backend.py` baris 31–37, seed GFL2 masih berisi:

```python
'Helena', 'Girard', 'DP-12', 'KSVK'
```

Tidak terdapat `Helen`.

Di `npc_database.json`:
- `Helena` terdapat dalam `known`;
- `Helen` bukan known speaker;
- false legacy entries seperti `DP`, `Dp`, `Hereyes`, `Dontworry`, dan lainnya masih tersimpan.

### 3.2 Bukti kode fuzzy canonicalization

Di `app/ocr/gfl2_speaker_roi.py`:

```python
if len(target) >= 4 and SequenceMatcher(None, compact, target).ratio() >= 0.84:
    return name
```

`Helen` sangat mirip dengan `Helena`, sehingga raw ROI `Helen` dipetakan ke known name `Helena`.

### 3.3 Bukti structured events

Structured logs mencatat:
- raw ROI `Helen`: **1.404** event;
- selected speaker `Helena`: **1.455** event;
- contoh payload: `raw_roi='Helen'`, `speaker='Helena'`, `confidence≈0.999`.

### 3.4 Bagaimana duplikasi terjadi

`GFL2SpeakerTracker.process()` melakukan:

```python
if speaker:
    if text belum dimulai speaker:
        text = f"{speaker} {text}"
```

Saat body OCR sudah membaca:

```text
Helen Based on the intel...
```

tetapi canonical speaker salah menjadi:

```text
Helena
```

tracker mengubah raw text menjadi:

```text
Helena Helen Based on the intel...
```

`split_speaker_and_dialog()` lalu menghapus hanya `Helena`, sehingga body yang diterjemahkan tetap diawali `Helen`. Overlay akhirnya menampilkan:

```text
Helena: Helen berdasarkan intel...
```

### Perbaikan wajib

- Ganti seed trusted `Helena` menjadi canonical `Helen`.
- Tambahkan migration contextual `Helena → Helen` hanya untuk speaker slot/legacy NPC review.
- Hentikan fuzzy mapping kandidat yang berbeda suffix nama (`Helen` tidak boleh otomatis menjadi `Helena`).
- Terapkan exact alias mapping terlebih dahulu, baru fuzzy dengan threshold ketat dan aturan aman.
- Setelah selected speaker ditetapkan, strip prefix body berdasarkan canonical dan known aliases sehingga tidak ada nama ganda.

---

## 4. Root Cause `KSVK` Tidak Muncul Orange

### 4.1 Temuan structured events

Berbeda dari dugaan berdasarkan live log biasa, `KSVK` sebenarnya dideteksi di internal ROI:

| Data | Jumlah |
|---|---:|
| Event selected speaker `KSVK` | 126 |
| Raw ROI tepat `KSVK` | 100 |
| Contoh confidence awal | ±0,714 |
| `TRANSLATION_RESULT` dengan speaker `KSVK` | 0 |

### 4.2 Kesalahan wiring pipeline

Di `TITANMAIN.py`:
- OCR Worker menyimpan `gfl2_speaker` metadata ke queue.
- Namun `TranslatorWorker` kemudian tetap menjalankan:
  ```python
  kind, speaker, dialog = split_speaker_and_dialog(raw_text)
  ```
- Ia **tidak membaca `ocr_meta["gfl2_speaker"]["speaker"]` sebagai selected speaker otoritatif**.

Artinya, meskipun ROI sukses membaca `KSVK`, hasilnya dapat tidak pernah sampai ke overlay orange karena:
- frame OCR yang membawa detection tidak menjadi frame yang ditampilkan;
- scheduler/queue memproses text lain;
- parser downstream tidak memakai metadata speaker;
- temporal hold tidak membantu bila label yang valid tidak dipropagasikan bersama dialog final.

### Perbaikan wajib

- Bawa `selected_speaker` sebagai metadata terikat pada frame/dialog hingga overlay.
- `TranslatorWorker` harus memakai validated ROI speaker sebelum fallback parsing body.
- Jangan lagi mengandalkan strategi menyisipkan nama ke raw text.
- Tambahkan log:
  ```text
  RAW_NAME_ROI
  CANONICAL_CANDIDATE
  SPEAKER_META_COMMITTED
  FINAL_OVERLAY_SPEAKER
  FINAL_OVERLAY_BODY
  SPEAKER_META_DROPPED_BY_SCHEDULER
  ```

---

## 5. Root Cause Nama Terbaca Tetapi Tidak Dilabel

### Seed v8.7.2 saat ini

`app/ocr/gfl2_speaker_roi.py` hanya memiliki:

```text
DP-12
KSVK
Lentine
Dushevnaya
Descender Zero
Dandelion
Cocoon
Berryfield
Nikketa
```

Tidak terdapat:
- `Alya Kujou`
- `Melanie`
- `Helen`
- `Balthilde`
- `Phaetusa`

### Data hasil OCR/evaluation

| Nama | Bukti source/OCR | Status speaker overlay | Penyebab |
|---|---:|---|---|
| `Alya Kujou` | 347 source evaluation; prefix OCR sangat banyak | Tidak menjadi label | Tidak ada pada trusted registry / Commander belum configurable |
| `Balthilde` | 8 source evaluation; 6 prefix OCR | Tidak menjadi label | Tidak ada pada seed/NPC trusted |
| `Phaetusa` | 332 source evaluation; prefix ratusan frame | Tidak menjadi label | Tidak ada pada seed/NPC trusted |
| `Melanie` | muncul dalam body; prefix sering hilang menjadi `elanie` | Tidak menjadi label | Tidak ada seed + initial glyph loss |
| `Helen` | terbaca jelas pada ROI | Salah menjadi `Helena` | Seed legacy salah + fuzzy terlalu longgar |

### Perbaikan registry

Buat **Trusted GFL2 Speaker Registry** yang terpisah dari database belajar lama:

```text
DP-12
KSVK
Helen
Balthilde
Phaetusa
Melanie
Dushevnaya
Suomi
Colphne
Lentine
Descender Zero
Dandelion
```

Untuk commander:
- tambahkan field UI `Commander / Player Display Name`;
- pada pengguna saat ini nilainya `Alya Kujou`;
- nama pemain tidak seharusnya bergantung pada auto-learning.

---

## 6. ROI Saat Ini Terlalu Lebar dan Dipengaruhi Database Tercemar

### Kode ROI saat ini

```python
roi = img_gray[0:max(22, int(h * 0.43)), 0:max(110, int(w * 0.34))]
```

Pada crop sekitar `1419 x 176`, ROI menjadi sekitar:

```text
482 x 76 piksel sebelum upscale
```

Untuk satu nama pembicara, area ini terlalu besar dan berpotensi menangkap potongan body dialog.

### Bukti false selected speaker

Structured event memilih speaker:

| False / suspicious speaker | Event |
|---|---:|
| `Her` | 77 |
| `Dontworry` | 23 |
| `Don't` | 6 |
| `Asimple` | 9 |
| `Noticing` | 9 |
| `Sensing` | 10 |
| `Griffin's` | 16 |

Ini terjadi karena:
1. ROI menangkap teks body;
2. database lama masih mengandung false speakers;
3. `_canonical()` menerima fuzzy match dengan threshold rendah;
4. tracker menganggap hasil tersebut valid sebagai label.

### Perbaikan

- Jangan memberi tracker seluruh `NPC_DATABASE known`.
- Gunakan trusted seed + nama yang direview user saja.
- Tambahkan UI preview/calibration untuk kotak Name ROI GFL2.
- Perkecil ROI atau tentukan posisinya dari layout aktual/screenshot.
- Validasi nama berdasarkan posisi, confidence, dan temporal consistency.
- Tambahkan daftar `legacy_untrusted_names` yang tidak boleh menjadi speaker otomatis.

---

## 7. Root Cause `Phaetusa → Phaedusa` dan `Balthilde → Balthalde`

### Bukti dari IDN Evaluation Export

File `logs/idn_evaluation_v8_7_2.jsonl` tersedia dan valid dengan **2.670 entry**. Contoh:

```text
source_normalized : Phaetusa Open the database! Hmm...
backend_output    : Phaedusa Buka database! ...
final_idn_output  : Phaedusa Buka database! ...
```

Jumlah baris dengan:
- source mengandung `Phaetusa`;
- final output mengandung `Phaedusa`;

adalah **107**.

Pada contoh body lain:
- source memiliki `Balthilde`;
- backend Argos menghasilkan `Balthalde`.

### Diagnosis

Ini bukan kesalahan speaker ROI saja. Raw source sudah benar, tetapi backend translation mengubah proper name karena nama belum diproteksi sebagai entitas yang tidak boleh diterjemahkan/transliterasi.

### Perbaikan: Named Entity Protection v1

Sebelum teks dikirim ke backend:

```text
Phaetusa → __ORT_NAME_0__
Balthilde → __ORT_NAME_1__
Helen → __ORT_NAME_2__
Alya Kujou → __ORT_NAME_3__
KSVK → __ORT_NAME_4__
DP-12 → __ORT_NAME_5__
```

Setelah backend dan IDN Quality Layer:

```text
__ORT_NAME_0__ → Phaetusa
...
```

Ketentuan:
- hanya protected canonical names yang di-placeholder;
- alias OCR dinormalisasi terlebih dahulu;
- nama tetap dipertahankan pada final overlay dan cache;
- cache lama yang sudah menyimpan `Phaedusa/Balthalde/Helena` perlu di-invalidasi atau dimigrasikan setelah fix.

---

## 8. Cache: Diagnosis Baru Setelah Memeriksa Structured Events

### Hasil yang benar dari folder proyek lengkap

| Event cache | Jumlah |
|---|---:|
| `CACHE_SKIP_PROGRESSIVE` | 2.670 |
| `CACHE_STORE_STABLE_FINAL` | 913 |
| `CACHE_HIT_STABLE_FINAL` | 10 |
| `CACHE_DUPLICATE_OCR_SUPPRESSED` | 2 |

### Koreksi terhadap analisis berdasarkan live log saja

Live log yang dikirim sebelumnya hanya menampilkan PIPE dan tidak mencetak event structured cache. Berdasarkan folder lengkap, Stable Final Cache **tidak gagal total**; fitur sudah melakukan store dan skip progresif. Hit masih rendah, tetapi itu dapat wajar bila dialog final jarang diputar ulang dalam model yang sama.

### Cache scoped per model

Main cache sudah terpisah:

```text
cache/translation_memory_gfl2_exilium_idn_idn_v1.json
cache/translation_memory_gfl2_exilium_idn_idn_v2.json
cache/translation_memory_gfl2_exilium_idn_idn_v3.json
cache/translation_memory_gfl2_exilium_idn_idn_v4.json
cache/translation_memory_gfl2_exilium_idn_idn_v5.json
```

`naturalized_idn_cache.json` menggunakan satu file, tetapi key mencakup model dan mode:

```text
version | game | model_key | mode | normalized_source
```

Jadi kenaikan statistik entry pada boot (`0 → 233 → 340 → 560 → 786`) adalah jumlah global yang membingungkan, bukan bukti langsung bahwa hasil V1 digunakan untuk V5.

### Masalah cache yang masih nyata

Cache sekarang menyimpan output yang salah, misalnya:
- output `Phaedusa`;
- output `Balthalde`;
- source/body hasil pipeline salah terkait `Helen/Helena`;
- potensi token `Level I` sebelum revisi final.

### Perbaikan cache berikutnya

- pertahankan Stable Final Cache v2;
- tampilkan ringkasan STORE/SKIP/HIT pada WebUI/live log;
- tampilkan hit/entries per current model, bukan hanya total global;
- setelah Named Entity/Speaker Integrity fix, buat migration atau clear cache affected namespace;
- cache final tidak boleh commit token kritis sebelum voting/revision guard selesai.

---

## 9. Root Cause `Level II`, `I`, dan Contraction

### Bukti evaluation export

Untuk `Level II`, source berkembang melalui variasi:

```text
Level Il
Level I
Level II
```

Backend/final output juga dapat mencapai bentuk benar `Level II`. Jika pengguna tetap melihat `Level I`, kesalahan kemungkinan terjadi karena:
- overlay sempat menampilkan frame salah dan tidak menggantinya;
- cache/final commit memilih frame terlalu awal;
- token kritis belum diberi late-correction override.

Contoh lain:

```text
II need ...
l'Ve been longing ...
```

### Perbaikan: Critical Token Revision Guard

Tambahkan mekanisme khusus untuk token:

```text
I
II
III
IV
I'm
I've
I'll
I'd
```

Aturan:
- token setelah `Level` wajib menunggu multi-frame agreement atau confidence lebih baik;
- output `Level II` yang muncul belakangan dapat mengganti `Level I` yang telah ditampilkan sementara;
- jangan store stable-final cache sebelum token kritis stabil;
- contraction diperbaiki hanya berdasarkan konteks dan/atau second pass, bukan replace global.

---

## 10. Warmup dan Backend

### Backend aktual

`status/translation_engine.json` menunjukkan:

```text
requested_engine : hybrid
applied_engine   : argos_offline
ct2_active       : false
online_router    : false
```

Jadi IDN V4 belum memakai online/hybrid backend pada pengujian ini.

### Warmup belum memanaskan jalur sebenarnya

Log mencatat warmup hanya `14–23 ms`, tetapi first-pipe spike masih mencapai `17.291 ms` pada V3. Ini berarti warmup belum menjalankan dependency/backend path yang benar-benar berat.

### Perbaikan

- warmup harus melakukan satu translasi representatif melalui jalur Argos/NLP/IDN yang benar-benar digunakan;
- bedakan cold-start latency, warmup latency, dan live latency;
- tampilkan online-assist/Argos fallback per model secara jelas;
- jangan meningkatkan OCR pass global ketika CPU/RAM warning dan downscale masih sering terjadi.

---

## 11. Prioritas Patch Berikutnya

### P0 — GFL2 Speaker Identification & Overlay Integrity v3
- Trusted speaker registry terpisah dari legacy NPC.
- Canonical: `KSVK`, `Alya Kujou`, `Melanie`, `Helen`, `Balthilde`, `Phaetusa`.
- Commander name configurable.
- `Helena → Helen` migration kontekstual.
- Body-prefix deduplication.
- Metadata ROI dipakai langsung oleh overlay, bukan diinjeksi ke raw text.
- ROI calibration/preview UI.
- Log final overlay speaker/body.

### P0 — Named Entity Protection v1
- Placeholder/restore canonical names sebelum dan sesudah backend.
- Lindungi `Phaetusa`, `Balthilde`, `Helen`, `Alya Kujou`, `KSVK`, `DP-12`, serta daftar karakter trusted lain.
- Mencegah Argos mengubah `Phaetusa → Phaedusa` dan `Balthilde → Balthalde`.

### P0 — Critical Token Revision Guard
- Multi-frame correction untuk `I`, `II`, `III`, `Level II`, `I've`, `I'll`, `I'm`.
- Late-correction dapat mengganti overlay/cache versi awal yang salah.

### P1 — Cache Hygiene Setelah Fix
- Pertahankan Stable Final Cache v2.
- Ringkas structured cache telemetry di UI.
- Per-model cache metrics.
- Migration/clear output cache yang telah menyimpan nama salah.

### P1 — Warmup dan Resource Control
- Real translation warmup.
- Name ROI minimum quality terpisah dari body downscale.
- Audit OCR downscale dan pipeline load.

---

## 12. Keputusan untuk Dokumentasi Proyek

Diagnosis ini harus masuk ke:
- Master Project Memory/Handoff versi berikutnya;
- Development Ledger;
- `KNOWN_ISSUES`;
- `NEXT_RECOMMENDATIONS`;
- changelog patch berikutnya;
- compile/test report setelah implementasi.

Tidak ada kode runtime yang diubah dalam audit ini. Patch baru sebaiknya baru dibuat setelah desain P0 di atas diterapkan secara terkontrol dan diuji dengan regression fixtures untuk:
- `Helen` vs `Helena`;
- `KSVK`;
- `Alya Kujou`;
- `Melanie/elanie`;
- `Balthilde`;
- `Phaetusa/Phaedusa`;
- `Level II`;
- `I Am`, `I Refuse`, `I've`, `I'll`.
