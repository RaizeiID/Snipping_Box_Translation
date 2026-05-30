# ORT Translation — Analisis Uji Semua Model IDN v8.7.3 & Roadmap Hotfix v8.7.3.1
**Tanggal analisis:** 26 Mei 2026  
**Game/Profile:** GFL2_EXILIUM  
**Log diuji:** IDN V1, V2, V3, V4, V5 setelah patch v8.7.3  
**Status:** Analisis dan roadmap kumulatif; belum mengubah runtime.

## 1. Kesimpulan Eksekutif

v8.7.3 memperkenalkan perbaikan identitas dan proteksi nama, tetapi hasil uji menemukan regresi P0: placeholder internal Named Entity Protection dapat tampil di hasil terjemahan sebagai `ORT_ENTITY_18` atau bentuk rusak serupa. Live log tidak mencetak token lengkap, namun merekam keluaran `out=_ _ ORT...` dan `HALLUCINATION_DETECTED` berulang saat OCR membaca `Colphne`, sesuai gejala placeholder yang terlihat pada overlay.

Selain itu, pengalaman pengguna bahwa proses terjemahan terasa lebih berat harus ditangani, terutama untuk story tanpa voice. Statistik live tidak membuktikan bahwa seluruh median lebih buruk dibanding tes sebelumnya, tetapi menunjukkan pola yang merusak responsivitas: hampir setiap prefix dialog yang tumbuh masih memanggil backend Argos; 95,6% PIPE adalah MISS, dengan cukup banyak tail latency >500 ms. Story tanpa voice dapat berganti dialog sebelum output final berhasil mengejar teks.

Rekomendasi rilis: buat hotfix `v8.7.3.1` yang fokus pada:
1. menghapus kebocoran placeholder internal;
2. memaksa namespace/cache versi baru dan membersihkan output tercemar;
3. mengurangi translasi berulang pada progressive prefix;
4. mengoptimalkan matcher roster/entity agar tidak menjadi beban besar, khususnya pada GFL.

## 2. Statistik Lima Log IDN v8.7.3

| Model | PIPE | MISS | HIT Stable Final | Duplicate Suppressed | Median | P90 | P95 | Maksimum | Warmup |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| IDN V1 | 812 | 773 | 27 | 12 | 206 ms | 359 ms | 415 ms | 1.295 ms | 1.228 ms |
| IDN V2 | 1.323 | 1.246 | 49 | 28 | 205 ms | 390 ms | 477 ms | 3.755 ms | 1.270 ms |
| IDN V3 | 909 | 867 | 29 | 13 | 228 ms | 407 ms | 462 ms | 929 ms | 1.244 ms |
| IDN V4 | 533 | 513 | 12 | 8 | 286 ms | 429 ms | 482 ms | 1.099 ms | 1.249 ms |
| IDN V5 | 923 | 905 | 7 | 11 | 231 ms | 344 ms | 394 ms | 951 ms | 1.261 ms |
| **Total** | **4.500** | **4.304** | **124** | **72** | **221 ms** | **384 ms** | **450 ms** | **3.755 ms** | — |

Tambahan statistik:
- `MISS`: 95,64% dari seluruh PIPE.
- Non-MISS (`HIT_STABLE_FINAL` + `DUPLICATE_OCR_SUPPRESSED`): 196 event atau 4,36%.
- PIPE >= 500 ms: 133 event (2,96%).
- PIPE >= 1.000 ms: 3 event.
- Seluruh MISS tetap memakai `engine=argos_offline`; V4 belum membuktikan online/hybrid assist aktif.

## 3. Regresi P0: Kebocoran `ORT_ENTITY_*`

### 3.1 Bukti pada log

String lengkap `ORT_ENTITY_18` tidak tertulis di lima live log, tetapi terdapat bukti padanan terpotong:
- IDN V3: 7 event `HALLUCINATION_DETECTED` dengan `src=Colphne` dan `out=_ _ ORT...`.
- IDN V5: 4 event sejenis dengan `src=Colphne`, plus satu rejection lain pada kalimat naratif.

Ini cocok dengan observasi pengguna bahwa overlay menampilkan `ORT_ENTITY_18`.

### 3.2 Akar source code

Pada `app/identity/speaker_registry.py`, nama terproteksi diganti token:

```python
token = f"__ORT_ENTITY_{idx:03d}__"
source = pattern.sub(token, source)
```

Restoration hanya menerima token yang masih sama persis:

```python
out = out.replace(token, name)
```

Di `translation_engine.py`, proteksi berjalan dua tahap:
1. sebelum backend Argos;
2. setelah backend dipulihkan, output kembali diproteksi lalu dikirim melalui `runtime_bridge.post_translate_text()` dan IDN Quality Layer.

Akibatnya, placeholder kedua melewati modul syntax/tone/terminology/quality/validation. Bila modul mengubah token seperti:

```text
__ORT_ENTITY_018__ → _ _ ORT ENTITY 018 ...
```

restore exact tidak lagi menemukan token, sehingga placeholder bocor ke overlay.

### 3.3 Mengapa kasus terlihat pada `Colphne`

`Colphne` sudah berada dalam reference roster/protected terms GFL2. Ketika hanya nama tersebut tampil sebagai dialog speaker pendek, isi yang diproses hampir seluruhnya adalah placeholder. Output internal kemudian mudah terlihat sebagai `ORT_ENTITY_*` bila restoration gagal.

## 4. Solusi P0 untuk Placeholder Leak

### Hotfix wajib
1. Jangan mengirim string literal yang menyerupai kata `ORT_ENTITY` ke post-processing/naturalization layer.
2. Gunakan salah satu desain aman:
   - **span-preserving pipeline**: naturalization hanya mengolah segmen non-entity; nama dipasang kembali secara struktural;
   - atau opaque sentinel non-linguistik yang diperlakukan immutable oleh semua layer.
3. Tambahkan `Residual Placeholder Guard` tepat sebelum:
   - overlay;
   - cache STORE;
   - IDN evaluation export.
4. Bila output masih mengandung:
   ```text
   ORT_ENTITY
   _ _ ORT
   malformed entity token
   ```
   maka:
   - jangan tampilkan hasil tersebut;
   - jangan simpan ke cache;
   - gunakan fallback output terakhir yang sudah dipulihkan atau backend output sebelum layer yang merusak token;
   - log event `ENTITY_RESTORE_FAILED_FALLBACK`.
5. Tambahkan regression test:
   - `Colphne`
   - `Phaetusa`
   - `Balthilde`
   - `Helen`
   - `Helena`
   - `Alya Kujou`
   - kalimat yang memuat dua nama sekaligus.

## 5. Masalah Cache: Runtime Masih Menyatakan `version=v8_7_2`

Seluruh log startup v8.7.3 mencatat Naturalized IDN cache masih memakai:

```text
version=v8_7_2
```

Entry cache juga terus meningkat:
- V1: 915;
- V2: 1.135;
- V3: 1.500;
- V4: 1.774;
- V5: 1.967.

Ini bertentangan dengan tujuan v8.7.3 yang seharusnya memakai namespace baru setelah perbaikan identity guard. Ada dua kemungkinan yang perlu diverifikasi melalui folder runtime aktual:
- cache lama menyimpan metadata versi dan tetap dimuat meskipun source meminta versi baru;
- nilai environment/startup yang dipakai runtime masih mengarah ke cache lama.

### Hotfix cache wajib
- paksa filename/namespace cache baru, bukan sekadar nilai parameter internal;
- tolak load cache bila metadata versi tidak cocok;
- rotasi cache v8.7.2 menjadi backup, jangan langsung hapus;
- jangan STORE output yang memuat placeholder residual;
- laporkan cache version/namespace yang benar di UI.

## 6. Mengapa Terjemahan Terasa Lebih Berat?

### 6.1 Progressive prefix masih diterjemahkan satu demi satu

Log menunjukkan satu dialog berkembang melalui banyak OCR prefix, dan masing-masing masuk backend sebagai MISS. Contoh pola:

```text
DP-12 ruffles KSVK'sh
DP-12 ruffles KSVK's hair
DP-12 ruffles KSVK's hair, then gently
DP-12 ruffles KSVK's hair, then gently squeezes her ha...
```

Setiap pertambahan memanggil Argos kembali. Pada story bersuara, dialog bertahan cukup lama sehingga pengguna masih dapat membaca hasil akhir. Pada story tanpa voice atau pergantian cepat, sistem dapat tertinggal sebelum dialog berpindah.

### 6.2 Post-processing dan entity protection ditambahkan pada setiap MISS

v8.7.3 memproses entity protection sebelum backend dan kembali sesudah backend untuk melindungi nama selama naturalization. Untuk GFL2, overhead matcher sendiri relatif kecil, tetapi tetap dilakukan ribuan kali; ditambah QA/IDN layer dan Argos untuk hampir seluruh prefix.

### 6.3 Risiko lebih berat ketika profile GFL dipakai

Microbenchmark source patch menunjukkan biaya `protect_named_entities()` saat ini:
- GFL2: ±2,8 ms per pass untuk sekitar 75 terms;
- WUWA: ±2,6 ms per pass untuk sekitar 54 terms;
- GFL: ±102 ms per pass untuk sekitar 515 terms.

Karena proteksi saat ini dapat dipanggil dua kali per MISS, GFL berisiko menambah >200 ms hanya dari matching entity bila tidak dioptimalkan sebelum profile itu diuji.

### 6.4 Warmup menjadi lebih nyata dan lebih berat

Warmup v8.7.3 berada sekitar 1,2 detik per model. Ini merupakan biaya startup, bukan penyebab utama lag setiap baris, tetapi perlu ditampilkan sebagai tahap loading sebelum capture berjalan agar tidak terasa sebagai dialog pertama yang tertunda.

## 7. Solusi Optimasi Responsivitas

### P0 — Latest-Frame-Wins untuk Auto Story
Untuk satu `dialog_id` yang sedang mengetik:
- batalkan request translation prefix lama yang belum tampil bila sudah ada OCR yang lebih lengkap;
- jangan membiarkan queue menerjemahkan teks yang telah usang;
- prioritaskan frame final/stabil.

### P0 — Progressive Preview Throttle
Mode Auto dapat memakai dua jalur:
- preview cepat: diterjemahkan terbatas, misalnya setelah perubahan panjang yang berarti atau interval minimum;
- stable final: diproses lengkap dengan Named Entity, IDN Quality, QA, dan cache.

Untuk story cepat tanpa voice, sediakan opsi/preset:
```text
Auto Story Cepat / Tanpa Voice
```
yang mengutamakan latest-frame dan final translation daripada menerjemahkan setiap efek typing.

### P1 — Light Preview, Full Final
- Jangan jalankan seluruh post-processing berat pada setiap prefix.
- Jalankan naturalization/QA/Named Entity restore lengkap pada final/stabil.
- Preview cukup memakai jalur ringan dan tidak di-cache permanen.

### P1 — Precompiled Entity Matcher
Saat Start atau ketika registry berubah:
- muat roster/registry sekali ke RAM;
- compile matcher sekali per game;
- gunakan trie/Aho-Corasick atau compiled alternation longest-first;
- jangan membaca JSON dan mengompilasi ratusan regex setiap translation call.

Ini wajib sebelum menguji GFL dengan katalog 509 nama.

## 8. Temuan Identitas Lanjutan

### Perbaikan yang tampak membaik pada raw log
Lima live log baru tidak lagi memperlihatkan:
- pola `Helena Helen`;
- `Phaedusa`;
- `Balthalde`.

Raw OCR juga membaca:
- `Helen` sebagai prefix dialog berulang pada V3;
- `Phaetusa` sebagai prefix ratusan kali pada V4/V5;
- `Alya Kujou` sebagai prefix pada V3/V5.

Ini tanda baik untuk input/identity guard, tetapi belum membuktikan output overlay final aman karena placeholder leak sekarang menjadi blocker utama.

### Masalah yang masih perlu debug bundle
- `KSVK` masih lebih sering muncul sebagai mention/body daripada prefix pada live OCR V2.
- Final label orange tidak dapat dinilai lengkap hanya dari live log.
- Setelah hotfix, kirim debug bundle/structured events/IDN evaluation untuk memverifikasi overlay.

## 9. Prioritas Hotfix v8.7.3.1

| Prioritas | Perubahan |
|---|---|
| P0 | Hilangkan placeholder leak dan tambahkan residual guard/fallback |
| P0 | Paksa cache namespace v8.7.3.1 baru; rotate cache lama |
| P0 | Latest-frame-wins + progressive request coalescing |
| P1 | Jalur preview ringan; full IDN/QA hanya pada stable-final |
| P1 | Precompiled entity matcher per game; wajib sebelum tes GFL |
| P1 | Debug bundle menyertakan final overlay, restore failure, cache namespace |
| P1 | Pastikan V4 melaporkan applied backend jujur; saat ini masih Argos Offline |

## 10. Test Wajib Sebelum Hotfix Dirilis

| Uji | Expected |
|---|---|
| Dialog `Colphne` | Tidak pernah tampil `ORT_ENTITY_*` atau `_ _ ORT...` |
| Dialog `Phaetusa` / `Balthilde` | Nama terlindungi dan tidak bocor placeholder |
| `Helen` dan `Helena` | Tetap terpisah; tidak ada duplikasi |
| Output residual placeholder | Diblok sebelum overlay dan cache |
| Cache startup | Menunjukkan namespace hotfix baru, bukan `v8_7_2` |
| Story cepat tanpa voice | Prefix stale dibuang; final output tampil lebih cepat |
| GFL catalog besar | Matcher tidak menambah latency ratusan ms per PIPE |
| V1–V5 | Median/tail/quality dicatat per scene yang sama |

## 11. Keputusan Roadmap

Bug `ORT_ENTITY_*` adalah regresi baru yang merusak hasil tampil dan harus ditangani lebih dahulu sebagai hotfix. Pengembangan fitur tambahan tetap disimpan, tetapi jangan dilanjutkan sebelum:
1. placeholder internal tidak pernah tampil;
2. cache versi identitas benar-benar terisolasi;
3. pipeline Auto lebih responsif untuk story tanpa voice;
4. tes ulang identitas speaker dan output final dilakukan melalui debug bundle lengkap.
