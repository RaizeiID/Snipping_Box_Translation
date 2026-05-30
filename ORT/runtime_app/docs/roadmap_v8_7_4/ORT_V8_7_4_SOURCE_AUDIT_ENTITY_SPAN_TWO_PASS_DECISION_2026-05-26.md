# ORT Translation v8.7.3 — Audit Folder Aktual dan Keputusan Hotfix v8.7.3.1
**Tanggal:** 26 Mei 2026  
**ZIP yang diaudit:** `ORT_Translation_v8_7_3.zip`  
**SHA-256 ZIP:** `36da4c81a828a828b53b78f4ae2cdfe89ecc262937c62ec9ada1bbd5832a2b2a`  
**Status:** Analisis/roadmap; tidak mengubah runtime pada tahap ini.  
**Keputusan pengguna:** gunakan **Opsi A — Entity diproses sebagai span terpisah** pada hotfix.

## 1. Kesimpulan Audit

| Masalah | Asal | Bukti source/data | Keputusan hotfix |
|---|---|---|---|
| `ORT_ENTITY_18` / `_ _ ORT _ ENTITY ...` tampil di terjemahan | Regresi baru v8.7.3 | `speaker_registry.py` membuat `__ORT_ENTITY_###__`; `translation_engine.py` mengirim proteksi kedua melewati IDN/QA; 1.109 final output tercemar | Ganti dengan span pipeline; residual guard dan fallback |
| Naturalized cache boot masih `version=v8_7_2` | Integrasi v8.7.3 tidak lengkap; setter lama menang | `v7_system_profile.py` menyetel v8.7.3, tetapi `model_strategy.py` masih hard-code `v8_7_2`; 2.316 naturalized cache keys semuanya `v8_7_2` | Perbaiki override; namespace/file cache baru; rotasi cache |
| Output placeholder sudah tersimpan cache | Efek lanjutan regresi v8.7.3 | 463 naturalized cached translations dan scoped cache v8.7.3 sudah tercemar | Jangan load/store output residual; migration/rotation report |
| Terjemahan terasa lambat saat story cepat | Campuran: perilaku lama + overhead baru | Auto menerjemahkan prefix sejak v8.4; v8.7.3 menambah entity pass/roster/QA/warmup | Latest-frame-wins, coalescing, light preview/full final |
| Two-pass OCR | Sudah ada sejak rancangan v8.7.2 dan tetap aktif | Body OCR paragraph; Name ROI terpisah; numeric dual-pass; scoped `I` recovery | Pertahankan, jangan OCR perhuruf global |

## 2. Akar Pasti Kebocoran Placeholder

### Source yang membuat placeholder

`app/identity/speaker_registry.py` baris 291–311:

```python
def protect_named_entities(text: str, game: str) -> ProtectedText:
    ...
    token = f"__ORT_ENTITY_{idx:03d}__"
    mapping[token] = name
    source = pattern.sub(token, source)

def restore_named_entities(text: str, protected: ProtectedText | None) -> str:
    ...
    out = out.replace(token, name)
```

Restoration hanya berhasil bila token masih persis sama.

### Source yang mengekspos token ke NLP/QA

`translation_engine.py` baris 296–339:

```python
entity_protection = protect_named_entities(translate_src, game_profile)
backend_raw = self._translate_offline(entity_protection.source)
backend_out = restore_named_entities(backend_raw, entity_protection)
...
post_entity_protection = protect_named_entities(out, game_profile)
out = post_entity_protection.source
out = bridge.post_translate_text(src, out, ...)
out = apply_idn_quality(src, out, ...)
out = restore_named_entities(out, post_entity_protection)
```

Tahap pertama berfungsi melindungi nama saat backend. Masalah muncul pada tahap kedua: output yang sudah direstore diproteksi kembali, lalu token internal dikirim melalui post-processing/IDN Quality/QA. Lapisan tersebut dapat mengubah token:

```text
__ORT_ENTITY_078__  →  _ _ ORT _ ENTITY _ 078 _ _
```

Setelah berubah, `str.replace()` exact tidak mampu merestore nama.

### Bukti dari file evaluasi aktual

`logs/idn_evaluation_v8_7_3.jsonl`:
- total row: **4.489**;
- placeholder pada `source_raw`: **0**;
- placeholder pada `source_normalized`: **0**;
- placeholder rusak pada `backend_output`: **1.109**;
- placeholder rusak pada `final_idn_output`: **1.109**.

Per model:

| Model | Final output tercemar |
|---|---:|
| IDN V1 | 105 |
| IDN V2 | 236 |
| IDN V3 | 239 |
| IDN V4 | 257 |
| IDN V5 | 272 |

Ini membuktikan placeholder bukan berasal dari OCR, melainkan pipeline translation/entity protection v8.7.3.

## 3. Desain Pilihan Pengguna: Entity Diproses sebagai Span Terpisah

Hotfix **tidak boleh** lagi membawa placeholder `ORT_ENTITY_*` melalui IDN Quality/QA.

### Alur baru yang direkomendasikan

```text
OCR / normalized source
→ identifikasi canonical entity
→ backend-safe protection internal (bila backend memerlukan)
→ backend translate
→ restore segera ke canonical display name
→ parse hasil menjadi:
     TextSpan("...hasil kalimat...")
     EntitySpan(canonical_id="phaetusa", display_name="Phaetusa")
     TextSpan("...")
→ naturalization/QA hanya memodifikasi TextSpan
→ compose final output dari span
→ residual-internal-token guard
→ overlay / cache / export
```

### Aturan penting

- `EntitySpan` adalah immutable; `Helen`, `Helena`, `Phaetusa`, `Balthilde`, dan `Alya Kujou` tidak masuk rewriting NLP.
- Jangan melakukan `post_entity_protection = protect_named_entities(out, ...)` dalam bentuk string placeholder lagi.
- Fallback wajib: bila output akhir mengandung `ORT_ENTITY`, `_ _ ORT`, atau sentinel internal apa pun, jangan tampilkan dan jangan cache hasil tersebut.
- Log baru:
  - `ENTITY_SPAN_PROTECTED`
  - `ENTITY_SPAN_RESTORED`
  - `ENTITY_RESIDUAL_BLOCKED`
  - `ENTITY_FALLBACK_USED`
  - `FINAL_OVERLAY_ENTITY_SAFE`

## 4. Akar Cache Version yang Salah

### Setting baru yang benar

`v7_system_profile.py` baris 375–386 sudah menyetel:

```python
"ORT_IDN_CACHE_VERSION": "v8_7_3_identity_guard",
"ORT_SCOPED_CACHE_VERSION": "v8_7_3_identity_guard",
```

### Setter lama yang menimpa

`model_strategy.py` baris 100–114 masih memuat:

```python
"ORT_IDN_CACHE_VERSION": "v8_7_2",
```

File `model_strategy.py` tidak tercantum pada `CHANGED_FILES_MANIFEST_V8_7_3.txt`, sehingga jalur lama tersebut tidak ikut diperbarui ketika namespace identity baru ditambahkan.

### Bukti cache folder aktual

`cache/naturalized_idn_cache.json`:
- total entries: **2.316**;
- seluruh key memakai prefix versi: **`v8_7_2`**;
- entries dengan translation placeholder rusak: **463**.

Scoped caches `*_v8_7_3_identity_guard.json` sudah ada, tetapi juga memiliki output placeholder rusak karena output final v8.7.3 tersimpan sebelum guard tersedia.

### Hotfix cache

- Ubah semua setter cache agar memakai namespace baru:
  ```text
  v8_7_3_1_entity_span_hotfix
  ```
- Gunakan file naturalized cache baru atau filter load berdasarkan namespace secara ketat.
- Backup/rotate cache lama; jangan memakainya sebagai HIT.
- Jangan STORE output dengan residual token.
- Buat report daftar cache yang dirotasi/diabaikan.

## 5. Asal Beban Performa

### Yang sudah ada sebelum v8.7.3

Auto Story memang telah menerjemahkan teks progresif sejak rancangan lama. Log boot menyatakan:

```text
v8.4 menerjemahkan teks bertahap mengikuti kemunculan dialog
```

Jadi pola translation per-prefix bukan sepenuhnya bug baru.

### Yang ditambah v8.7.3

- Entity protection sebelum backend.
- Entity protection kedua sebelum IDN/QA.
- Reference roster catalog besar.
- Pencocokan longest-first yang saat ini membaca registry/catalog dan membuat regex berulang.
- Warmup jalur terjemahan yang sekarang sekitar 1,2 detik.

### Microbenchmark source aktual

| Game | Jumlah protected terms | Waktu `protect_named_entities()` per pass |
|---|---:|---:|
| GFL2 | 83 | ±3,88 ms |
| WUWA | 61 | ±3,87 ms |
| GFL | 519 | ±109,88 ms |

Saat fungsi dipanggil dua kali per MISS, GFL berpotensi menambah >200 ms hanya dari entity matching.

### Optimasi hotfix

- Hapus entity pass string kedua melalui span pipeline.
- Cache registry/catalog di RAM.
- Precompile matcher hanya saat startup atau data berubah.
- Terapkan latest-frame-wins: prefix lama dibatalkan bila ada frame lebih lengkap.
- Pisahkan preview ringan dan final penuh.
- Tambahkan preset/policy `Auto Story Cepat / Tanpa Voice`.

## 6. Konfirmasi Two-Pass OCR

Ya, v8.7.3 tetap menerapkan pendekatan dua-pass/ROI, bukan OCR perhuruf global.

### Body OCR

`TITANMAIN.py` baris 1875–1881:

```python
out = reader.readtext(img_gray, detail=0, paragraph=True)
raw_text = " ".join(out).strip() if out else ""
result = self.gfl2_speaker_tracker.process(reader, img_gray, raw_text)
```

Body tetap dibaca sebagai kalimat/paragraf agar performa dan konteks terjaga.

### Name ROI pass terpisah

`app/ocr/gfl2_speaker_roi.py` baris 96–115:

```python
roi = img_gray[...]
roi = cv2.resize(...)
roi = CLAHE(...).apply(roi)
detections = reader.readtext(
    roi, detail=1, paragraph=False,
    allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789- "
)
```

Ini membaca blok teks nama pada ROI kecil secara terpisah. `paragraph=False` tidak sama dengan membaca huruf satu per satu.

### Recovery terbatas untuk huruf awal `I`

Baris 136–154 menjalankan pemeriksaan tambahan hanya bila body terlihat mulai dengan pola tertentu:

```text
am ...
refuse ...
m ...
have to ...
```

Tujuannya mencoba memulihkan:
```text
I am
I refuse
```

### Numeric dual-pass

`TITANMAIN.py` juga masih memiliki `_maybe_numeric_dual_pass(...)` untuk kasus angka tertentu.

### Keterbatasan saat ini

- Recovery huruf `I` bersifat sangat sempit.
- Ia belum otomatis menyelesaikan `Level II`, `I've`, `I'll`, atau semua variasi `I/l/II`.
- Untuk itu tetap diperlukan **Critical Token Revision Guard** yang memilih frame terbaik sebelum cache/final overlay, bukan OCR perhuruf global.

## 7. Klasifikasi Apakah Masalah Baru atau Lama

| Masalah | Baru di v8.7.3? | Penjelasan |
|---|---:|---|
| Placeholder `ORT_ENTITY_*` bocor | Ya | Muncul dari Named Entity Protection v8.7.3 dan pass kedua ke NLP |
| Cache naturalisasi masih version `v8_7_2` | Integrasi baru gagal karena kode lama tertinggal | Setter lama di `model_strategy.py` menimpa setting baru |
| Cache menyimpan placeholder rusak | Ya, akibat leak baru | Tidak mungkin terjadi sebelum token baru diperkenalkan |
| Per-prefix Argos pada Auto | Tidak | Sudah bagian Auto Story lama |
| Rasa lebih lambat di v8.7.3 | Sebagian baru | Per-prefix lama diperberat entity passes/warmup/catalog |
| Two-pass Name ROI | Sudah ada dari v8.7.2 dan dipertahankan | Bukan penyebab placeholder |
| Kesulitan `I/II` | Lama dan belum tuntas | Two-pass hanya scoped; perlu revision guard |

## 8. Prioritas Hotfix v8.7.3.1

| Prioritas | Implementasi |
|---|---|
| P0 | EntitySpan pipeline; hapus string post-placeholder melalui NLP/QA |
| P0 | Residual-placeholder guard + safe fallback |
| P0 | Namespace cache baru dan rotasi cache tercemar |
| P0 | Latest-frame-wins/coalescing untuk dialog progresif |
| P1 | Light preview / full final IDN processing |
| P1 | Precompiled entity matcher in-memory |
| P1 | Critical Token Revision Guard diperluas untuk `I/II/I've/I'll/Level II` |
| P1 | Debug export memuat event span/fallback/cache rotation |

## 9. Test Wajib Hotfix

| Test | Expected |
|---|---|
| `Colphne`, `Phaetusa`, `Balthilde`, `Helen`, `Helena`, `Alya Kujou` | Tidak ada output `ORT_ENTITY` |
| Output final mengandung residual internal token | Diblok; fallback tampil; tidak cache |
| Cache boot | Menunjukkan `v8_7_3_1_entity_span_hotfix` |
| Cache lama | Di-backup/diabaikan, bukan dipakai ulang |
| Story tanpa voice | Prefix lama tidak memenuhi queue; final lebih cepat |
| GFL dengan katalog besar | Entity matching tidak menambah >200 ms per MISS |
| OCR `Helen`/`Helena` | Tetap identitas berbeda |
| `Level II`, `I am`, `I've`, `I'll` | Frame koreksi final dapat mengganti preview salah |

## 10. Keputusan yang Dikunci

- Hotfix berikutnya memakai **Opsi A: EntitySpan pipeline**.
- Two-pass OCR tetap dipertahankan; tidak diganti OCR perhuruf global.
- Fitur UI/roster v8.7.3 tidak dibuang, tetapi correctness dan responsivitas diperbaiki lebih dahulu melalui v8.7.3.1.
