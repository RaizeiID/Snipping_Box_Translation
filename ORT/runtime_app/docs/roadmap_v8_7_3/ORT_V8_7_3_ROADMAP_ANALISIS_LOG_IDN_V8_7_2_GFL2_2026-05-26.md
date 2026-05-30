# ORT Translation — Analisis Profesional Uji Semua Model IDN v8.7.2 pada GFL2
**Tanggal analisis:** 26 Mei 2026  
**Status:** Roadmap kumulatif untuk update berikutnya (calon v8.7.3), belum merupakan patch runtime.  
**Sumber:** Lima live log `ORTCore IDN V1` sampai `V5` setelah instalasi v8.7.2.

## 1. Kesimpulan Eksekutif

v8.7.2 berhasil mempertahankan beberapa fondasi baik dari versi sebelumnya:
- seluruh model IDN yang diuji berjalan dengan `mode=auto`, `scheduler=auto_story`;
- `legacy_vault=isolated` tetap aktif;
- warmup event dan alasan perubahan OCR resolution kini terlihat;
- cache tidak lagi 100% MISS: sudah ada `HIT_STABLE_FINAL` dan `DUPLICATE_OCR_SUPPRESSED`.

Namun, pengujian baru membuktikan bahwa **GFL2 Speaker ROI / Orange Label v2 belum menyelesaikan identifikasi karakter**. Beberapa nama sudah terbaca jelas oleh OCR berkali-kali tetapi tidak menjadi label karakter; satu nama (`Helen`) justru mengalami salah canonical menjadi `Helena` dan diduplikasi ke isi dialog. Ini adalah prioritas P0 untuk update berikutnya.

Masalah kualitas lain tetap penting:
- `KSVK` masih tidak pernah menjadi prefix speaker pada OCR log walaupun muncul dalam body;
- `Melanie` sering kehilangan huruf awal menjadi `elanie`;
- `Level II` kadang akhirnya terbaca benar oleh OCR, tetapi pengguna melihat hasil akhir `Level I`, menunjukkan masalah final-selection/commit/cache, bukan semata-mata OCR awal;
- seluruh translasi MISS tetap menggunakan `argos_offline`;
- warmup yang tercatat 14–23 ms belum memanaskan jalur penerjemahan nyata karena first-pipe latency masih dapat mencapai 17.291 ms;
- log live belum menampilkan output Bahasa Indonesia dari IDN Evaluation Export, sehingga akurasi akhir naturalisasi belum dapat dinilai.

---

## 2. Statistik Pipeline Seluruh Model IDN

| Model | PIPE total | MISS / Argos | HIT_STABLE_FINAL | DUPLICATE_SUPPRESSED | Median PIPE | Maksimum |
|---|---:|---:|---:|---:|---:|---:|
| IDN V1 | 652 | 647 | 4 | 1 | 364,5 ms | 2.740 ms |
| IDN V2 | 367 | 366 | 1 | 0 | 341 ms | 2.194 ms |
| IDN V3 | 678 | 676 | 2 | 0 | 355,5 ms | 17.291 ms |
| IDN V4 | 617 | 615 | 1 | 1 | 328 ms | 2.682 ms |
| IDN V5 | 367 | 365 | 2 | 0 | 384 ms | 2.011 ms |
| **Total** | **2.681** | **2.669** | **10** | **2** | **354 ms** | **17.291 ms** |

### Makna data cache

- Cache sudah menunjukkan kemajuan parsial: 10 `HIT_STABLE_FINAL` dan 2 `DUPLICATE_OCR_SUPPRESSED`, berbeda dari v8.7.1 yang seluruhnya MISS.
- Stable-final HIT masih hanya sekitar **0,37%** dari total PIPE; seluruh non-MISS sekitar **0,45%**.
- Live log tidak memuat event eksplisit `CACHE_STORE_STABLE_FINAL` atau `CACHE_SKIP_PROGRESSIVE`, sehingga belum dapat diketahui dialog mana yang disimpan, mengapa sebagian besar masih MISS, dan apakah progressive skip berjalan sesuai rancangan.
- Jumlah entry Naturalized IDN cache pada boot meningkat saat model berganti: `0 → 233 → 340 → 560 → 786`. Ini perlu diaudit: bila angka tersebut adalah cache lintas-model dan output final digunakan ulang antar level IDN, benchmark V1–V5 dapat tercemar. Bila hanya statistik global, UI/report harus mengatakannya dengan jelas.

### Applied backend

Semua PIPE `MISS` tetap memakai:

```text
engine=argos_offline
```

HIT memakai `naturalized_cache`; dua suppression memakai `current_dialog_memo`. IDN V4 belum terbukti menggunakan online/hybrid assist walaupun strategy startup menyebut `hybrid`.

---

## 3. Bukti Kegagalan Speaker Label / Orange Label

### 3.1 Ringkasan nama yang perlu dilindungi

| Nama canonical yang diperlukan | Bukti OCR dalam log | Masalah yang dilaporkan/terlihat | Keputusan roadmap |
|---|---:|---|---|
| `KSVK` | 16 occurrence di body; **0 sebagai prefix speaker** | Saat KSVK berdialog, label orange tidak tampil | Seed tetap dipertahankan; perbaiki Name ROI geometry/voting dan overlay telemetry |
| `Alya Kujou` | ±328 baris sebagai prefix OCR | Commander terbaca tetapi tidak dilabel karakter | Tambahkan protected speaker / configurable Commander Display Name |
| `Melanie` | 0 sebagai prefix; `elanie` menjadi prefix ±81 baris | Huruf awal `M` hilang | Seed `Melanie`; alias ROI `^elanie → Melanie` secara konteks-speaker |
| `Helen` | ±55 prefix murni; terjadi `Helena Helen ...` ±756 baris | Label salah `Helena`, body masih `Helen`, nama tampil ganda | Canonical display `Helen`; migrasi/blacklist contextual `Helena`; strip duplicate body prefix |
| `Balthilde` | 6 prefix OCR, 8 occurrence | Terbaca tetapi tidak dilabel | Seed/protected speaker `Balthilde`; `Bathilde` hanya alias review bila UI aktual membuktikan |
| `Phaetusa` | ±325 prefix OCR, 335 occurrence | Terbaca tetapi tidak dilabel; pengguna melihat varian `Phaedusa` | Seed/protected speaker `Phaetusa`; audit jalur overlay/IDN output untuk sumber `Phaedusa` |

**Catatan ejaan:** log membaca `Balthilde`, bukan `Bathilde`, dan membaca `Phaetusa`, bukan `Phaedusa`. Oleh karena itu, canonical aman berdasarkan bukti log adalah `Balthilde` dan `Phaetusa`. Varian lain hanya boleh menjadi alias OCR/review setelah divalidasi dengan screenshot UI asli atau output final terjemahan.

---

## 4. Diagnosis Per Nama

### 4.1 `KSVK`: Name ROI belum menangkap speaker

`KSVK` tetap muncul dalam body/narasi, misalnya bentuk possessive `KSVK's`, tetapi tidak pernah menjadi awalan OCR pada sesi IDN V2 yang memuat kisah karakter tersebut. Ini menjelaskan mengapa seed lama belum cukup untuk memunculkan label orange: canonical matcher tidak mendapat candidate dari Name ROI/prefix speaker.

**Solusi berikutnya:**
- log hasil Name ROI mentah pada setiap frame (`raw_name_roi`, confidence, bbox);
- tambahkan ROI calibration/preview UI khusus GFL2 agar user dapat melihat kotak nama yang dibaca;
- gunakan multi-scale name pass ringan hanya pada kotak nama;
- temporal hold hanya aktif setelah nama benar-benar terdeteksi, bukan menebak dari body;
- tambahkan regression frame/screenshot KSVK.

### 4.2 `Alya Kujou`: OCR berhasil, registry/overlay tidak menerima

`Alya Kujou` sering tampil di awal OCR sebagai pembicara, tetapi tidak menjadi label sesuai pengamatan pengguna. Karena ini adalah nama Commander yang dapat berbeda antarpemain, hard-code saja kurang ideal.

**Solusi berikutnya:**
- tambahkan field UI `Commander / Player Display Name`;
- nilai pengguna (`Alya Kujou`) menjadi protected speaker seed per profile GFL2;
- body prefix `Alya Kujou` harus dipisah dari dialog bila speaker berhasil dipilih;
- jangan belajar nama Commander dari narasi sembarang.

### 4.3 `Melanie` → `elanie`: kegagalan glyph awal pada Name ROI

Dalam log, `Melanie` muncul sebagai referensi di body, tetapi tidak pernah sebagai prefix pembicara; sebaliknya `elanie` muncul sebagai prefix sekitar 81 kali. Ini bukti kuat huruf awal `M` hilang pada pembacaan nama.

**Solusi berikutnya:**
- seed canonical `Melanie`;
- alias speaker-slot terbatas: `elanie`, `Melanle`, `Melan` → `Melanie`;
- lakukan start-of-name recovery pass untuk glyph pertama;
- jangan mengubah `elanie` global di body bila confidence/posisi tidak mendukung.

### 4.4 `Helen` → `Helena Helen`: regression overlay paling kritis

Log menunjukkan ratusan baris seperti:

```text
Helena Helen Based on the intel gathered so far...
Helena Helen But they weren't fast enough...
Helena Helen The explosion at Lviv...
```

Ini cocok dengan observasi pengguna: orange label menampilkan `Helena`, sedangkan isi dialog masih mengandung `Helen`. Dengan demikian, kesalahan terjadi sebelum/ketika final overlay dibentuk, bukan sekadar kesalahan terjemahan Argos.

**Solusi berikutnya:**
- canonical protected speaker ditetapkan sebagai `Helen`;
- `Helena` diperlakukan sebagai wrong-alias pada speaker slot untuk scene/profile ini, bukan koreksi global body;
- lakukan deduplication setelah speaker dipilih:
  ```text
  chosen_label=Helen + body_prefix=Helen → body tanpa prefix nama
  ```
- bila candidate label tidak identik dengan body prefix (`Helena` vs `Helen`), jangan commit label tanpa voting/confidence kuat;
- sediakan NPC migration/review untuk menghapus seed `Helena` salah bila telah tersimpan.

### 4.5 `Balthilde`: terbaca jelas tetapi tidak menjadi label

Log V4 memuat:

```text
Balthilde
Balthilde Thanks to Helen...
```

Jadi masalahnya bukan OCR gagal membaca seluruh nama, melainkan speaker registry/overlay tidak mengenal atau tidak mengizinkan nama tersebut.

**Solusi berikutnya:**
- canonical seed `Balthilde`;
- optional OCR alias `Balthild → Balthilde`;
- simpan `Bathilde` hanya sebagai alias pending confirmation bila user menyertakan screenshot UI yang memakai ejaan itu.

### 4.6 `Phaetusa`: terbaca ratusan kali tetapi tidak menjadi speaker orange

Log V5 memuat `Phaetusa` sebagai prefix sekitar 325 baris. Tidak ada `Phaedusa` dalam raw OCR log, sehingga varian `Phaedusa` yang pengguna lihat kemungkinan muncul pada jalur label/overlay atau output terjemahan yang belum tercatat di live log.

**Solusi berikutnya:**
- seed/protected speaker `Phaetusa`;
- alias OCR seperti `Phaet` hanya dipakai dengan temporal confirmation;
- tambahkan log `final_overlay_speaker` dan `final_idn_output`;
- jangan mengubah `Phaetusa` menjadi bentuk lain tanpa bukti UI.

---

## 5. Mengapa Speaker ROI v2 Tidak Cukup?

Kelima log menyatakan fitur aktif pada boot:

```text
GFL2 speaker_roi=1 | temporal_label_hold=1
```

Namun tidak ada event keberhasilan deteksi seperti `GFL2_SPEAKER_ROI` atau telemetry yang menunjukkan:
- hasil OCR khusus kotak nama;
- confidence;
- canonical match;
- alasan label dipilih/ditolak;
- speaker yang benar-benar diwarnai orange;
- body sesudah nama pembicara dipotong.

Tanpa telemetry tersebut, sistem dapat:
- gagal melabel nama yang sudah jelas terbaca (`Alya Kujou`, `Balthilde`, `Phaetusa`);
- tidak mendeteksi nama yang tidak pernah masuk prefix (`KSVK`);
- memilih alias salah (`Helena`) dan meninggalkan nama asli di body (`Helen`).

### Rancangan Speaker Identification / Overlay Integrity v3

Tambahkan pipeline berikut:

```text
Name ROI raw OCR
→ canonical candidate matcher
→ confidence + temporal vote
→ selected speaker label
→ body OCR
→ strip hanya prefix yang cocok dengan speaker/alias aman
→ final overlay speaker + final body
→ telemetry lengkap
```

Event/field log wajib:

```text
GFL2_NAME_ROI_RAW
GFL2_NAME_CANDIDATE
GFL2_NAME_SELECTED
GFL2_NAME_REJECTED
GFL2_BODY_PREFIX_STRIPPED
GFL2_SPEAKER_CONFLICT
FINAL_OVERLAY_SPEAKER
FINAL_OVERLAY_BODY
```

---

## 6. Huruf `I`, Apostrof, dan Angka Romawi: Masalah Bukan Hanya OCR

### Bukti Level II

Log V4 menunjukkan urutan OCR yang berubah:

```text
LevelIl
Level Il
Level II
```

Artinya, OCR akhirnya mampu membaca `Level II` dengan benar pada beberapa frame. Bila hasil overlay/terjemahan masih tampil `Level I`, maka kemungkinan jalur final commit/cache memakai pembacaan awal yang kurang lengkap dan tidak menggantinya dengan pembacaan akhir yang lebih baik.

### Bukti pronoun/contraction

Log juga menunjukkan pola seperti:

```text
Phaetusa Hehe~ II need to make some preparations
l'Ve been longing to return...
```

Ini menunjukkan ambiguitas `I/l/II` dan apostrof belum ditangani dengan aman.

### Perbaikan yang disarankan: Critical Token Revision Guard

Token tertentu harus dianggap kritis dan diberi kesempatan direvisi oleh frame berikutnya sebelum final overlay/cache:

```text
I
II / III / IV
I'm
I've
I'll
I'd
```

Aturan:
- untuk Roman numeral setelah kata seperti `Level`, tunggu voting/stability lebih tinggi;
- pembacaan `Level II` pada frame akhir harus boleh mengganti output lama `Level I` atau `Level Il`;
- untuk pronoun/contraction, gunakan konteks grammar + multi-frame voting;
- jangan melakukan replace global `I`/`II` karena dapat merusak angka dan nama.

---

## 7. Cache v8.7.2: Membaik, tetapi Belum Cukup Terukur

### Hasil aktual

| Status | Jumlah |
|---|---:|
| `MISS` | 2.669 |
| `HIT_STABLE_FINAL` | 10 |
| `DUPLICATE_OCR_SUPPRESSED` | 2 |
| **Total PIPE** | **2.681** |

Ini menunjukkan Stable Final Cache mulai bekerja, tetapi penggunaannya sangat rendah.

### Kekurangan observability

Tidak ditemukan baris eksplisit:

```text
CACHE_STORE_STABLE_FINAL
CACHE_SKIP_PROGRESSIVE
```

Akibatnya belum bisa ditentukan:
- kapan dialog final disimpan;
- berapa banyak progressive frames ditolak;
- mengapa dialog panjang yang stabil tetap MISS;
- apakah cache final lintas model tercampur.

### Risiko namespace cache

Cache entries saat boot terlihat meningkat saat model berganti:

```text
IDN V1: 0
IDN V2: 233
IDN V3: 340
IDN V4: 560
IDN V5: 786
```

Ini perlu diaudit. Jika hanya penghitung agregat, UI harus menjelaskannya. Jika cache final terpakai lintas model IDN, hasil naturalisasi V1/V2 dapat mengganggu evaluasi V4/V5.

### Roadmap cache berikutnya

- log `CACHE_STORE_STABLE_FINAL` dan `CACHE_SKIP_PROGRESSIVE`;
- tampilkan namespace/model pada setiap STORE/HIT;
- pastikan output final IDN scoped per model/quality layer;
- gunakan Critical Token Revision Guard sebelum cache final menyimpan teks dengan `Level II`, nama, atau pronoun yang masih ambigu.

---

## 8. Performa dan Backend

### Applied backend

Semua event `MISS` pada kelima log masih menggunakan:

```text
engine=argos_offline
```

IDN V4 yang berstrategi `hybrid` masih belum terbukti menggunakan online assist.

### Warmup belum efektif

Walaupun log menampilkan:

```text
IDN warmup complete | 14–23ms
```

first PIPE masih sangat tinggi:

| Model | First/Max spike penting |
|---|---:|
| V1 | 2.740 ms |
| V2 | 2.194 ms |
| V3 | 17.291 ms |
| V4 | 2.613 ms |
| V5 | 2.011 ms |

Ini menunjukkan warmup sekarang belum menyentuh jalur berat yang benar-benar dipakai saat translate pertama, kemungkinan resource NLP/backend masih lazy-loaded setelah dialog muncul.

### Dynamic OCR downscale

Terdapat **21 penurunan OCR resolution** ke 55% pada rangkaian uji ini:
- V1: 7 kali;
- V2: 2 kali;
- V3: 1 kali;
- V4: 7 kali;
- V5: 4 kali.

Sebagian dipicu `CPU/RAM warning`, sebagian `translate latency high`. Dengan speaker recognition yang masih gagal, menambah OCR pass berat secara global berisiko memperburuk latency/downscale.

### Roadmap performa

- prewarm harus menjalankan jalur translasi/NLP representatif, bukan hanya initializer ringan;
- pisahkan latency first-load dari live latency;
- ukur beban Name ROI pass;
- jangan menaikkan jumlah OCR pass seluruh body;
- applied backend/online assist V4 harus dilog secara eksplisit.

---

## 9. Masalah Evaluasi Terjemahan IDN

Walaupun boot menyatakan `idn_eval_export=1`, kelima live log yang diberikan hanya memiliki tiga baris `[TRANSLATION]` per sesi: cache active, engine initialized, dan warmup complete. Tidak ada pasangan:

```text
source_normalized
backend_output
final_idn_output
final_overlay_speaker
```

Karena itu, kesalahan yang pengguna lihat pada hasil terjemahan seperti `Phaedusa` atau hasil akhir `Level I` belum dapat ditelusuri titik asalnya hanya dari live log.

### Perbaikan berikutnya

- tampilkan lokasi file IDN Evaluation Export di WebUI;
- tambahkan tombol `Export IDN Evaluation Log`;
- sertakan final overlay speaker dan body ke export;
- bila export gagal dibuat, tampilkan warning pada live log.

---

## 10. Prioritas Update Berikutnya (Calon v8.7.3)

### P0 — GFL2 Speaker Identification / Orange Label Integrity v3
- Protected names: `KSVK`, `Alya Kujou`, `Melanie`, `Helen`, `Balthilde`, `Phaetusa`.
- Configurable `Commander Display Name` untuk `Alya Kujou`.
- Wrong-alias migration/guard `Helena → Helen` pada speaker slot saja.
- Speaker/body duplication stripping.
- ROI confidence, temporal vote, selected/rejected reason, final overlay telemetry.
- Screenshot-based regression fixtures untuk seluruh nama baru.

### P0 — Critical Token Revision Guard
- Multi-frame voting untuk `I`, `II`, `III`, `I'm`, `I've`, `I'll`.
- Late correction dapat mengganti final output yang sempat salah.
- Cache final menunggu token kritis stabil.
- Test scene `Level II`, `I Am`, `I Refuse`, `I've`, `I'll`.

### P1 — Cache Telemetry dan Isolation Audit
- Lengkapi STORE/SKIP/HIT/suppression telemetry.
- Tampilkan namespace model pada cache.
- Pastikan naturalized final cache tidak menyilang antar IDN level tanpa desain yang disengaja.

### P1 — Real Warmup / Resource Stabilization
- Warmup harus memanggil jalur translation/NLP nyata.
- Catat `cold_start`, `warmup`, dan `live` latency terpisah.
- Audit alasan 21 downscale OCR agar Name ROI tidak melemah saat dialog penting.

### P1 — IDN Output / Overlay Export
- Pastikan file evaluation benar-benar dibuat dan mudah diambil pengguna.
- Rekam raw OCR, normalized OCR, selected speaker, stripped body, backend output, final IDN output.
- Hanya setelah itu kualitas IDN V1–V5 dapat dinilai secara sah.

---

## 11. Keputusan yang Disimpan untuk Update Selanjutnya

1. Masalah label karakter bukan selesai pada v8.7.2; ia menjadi P0 berikutnya.
2. Canonical name baru yang harus dilindungi: `KSVK`, `Alya Kujou`, `Melanie`, `Helen`, `Balthilde`, `Phaetusa`.
3. `Helena Helen` adalah regression yang wajib diperbaiki, bukan ditoleransi sebagai OCR noise biasa.
4. `Balthilde` adalah ejaan yang dibuktikan log; `Bathilde` tetap alias review sampai UI aktual mengonfirmasi.
5. `Phaetusa` terbaca benar di raw OCR; `Phaedusa` harus ditelusuri pada final overlay/translation export.
6. Cache telah membaik sebagian, tetapi perlu telemetry dan isolasi model yang terukur.
7. Huruf `I` dan Roman numeral perlu final-correction policy, bukan hanya OCR pass tambahan.
8. Semua temuan ini wajib dimasukkan ke master handoff/development ledger dalam ZIP update berikutnya.
