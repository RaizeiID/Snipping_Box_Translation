# ORT Translation v8.7.5 — Audit Folder Runtime, Korelasi Downgrade OCR, Kandidat Nama, dan Ledger Roadmap v8.7.6
**Tanggal audit:** 27 Mei 2026  
**Basis audit:** ZIP runtime pengguna `ORT_Translation_v8_7_5.zip`, live log/video v8.7.5 yang dikirim sebelumnya, arsip source v8.7.2–v8.7.4 yang tersedia, serta memo/ledger lama proyek.  
**Status:** Hasil analisis dan rancangan kumulatif v8.7.6; belum merupakan patch runtime.

## 1. Kesimpulan Profesional

Audit folder v8.7.5 mengonfirmasi empat hal utama:

1. **Perbaikan correctness v8.7.5 benar-benar bekerja pada sisi EntitySpan dan exact-speaker.** Evaluation/cache aktif v8.7.5 tidak lagi mengandung marker internal `ORT_ENTITY`, `ORT_BKEND`, `ORT_BKED`, `ORT_BEND`, atau `_ _ ORT`; speaker resmi di luar seed lama seperti `Colphne`, `Groza`, `Mayling`, `Krolik`, `Nikketa`, dan `Ullrid` benar-benar terpilih pada event runtime.
2. **Tidak ditemukan perubahan source dari v8.7.2 ke v8.7.5 yang menurunkan Body OCR atau menurunkan preset OCR Lite/Lite IDN.** Tangga OCR rendah `40/45/50/55/60%` dan mekanisme cap Lite sudah ada sebelumnya; body OCR GFL2 tetap memakai `reader.readtext(... detail=0, paragraph=True)`.
3. **Ada keterkaitan nyata yang menjelaskan pengalaman downgrade:** v8.7.5 masih mengunci Lite/Lite IDN V1–V2 maksimal pada `40%/45%` sehingga user tidak dapat menyelamatkan kualitas melalui override normal; pada saat yang sama CT2 Fast/Lite sekarang gagal aktif dan jatuh ke Argos, sehingga OCR rendah kehilangan keterbacaan tanpa memperoleh manfaat backend cepat.
4. **Masih ada bug false-speaker di overlay final.** Name ROI exact baru aman, tetapi bila metadata ROI tidak terbawa pada frame antrian tertentu, parser teks fallback masih menganggap potongan seperti `DP-'5 an` sebagai speaker `DP`, serta menghasilkan label mencurigakan lain (`Name`, `TC`, `Hybrid`, `Scavenger Ugh`, `Kulich Woof`). Ini harus menjadi P0 v8.7.6.

## 2. Isi Folder v8.7.5 yang Diaudit

ZIP runtime aktual memuat:
- source runtime (`TITANMAIN.py`, `translation_engine.py`, `model_strategy.py`, `app/ocr/*`, `app/identity/*`);
- konfigurasi katalog roster;
- `speaker_registry_v2.json` aktif;
- log penuh/session events/evaluation v8.7.5;
- cache namespace v8.7.5 dan backup cache v8.7.4;
- dokumentasi master memory, ledger, changelog, test report, serta addendum audit sebelumnya.

Karena source, log, cache, dan dokumentasi berada di folder yang sama, audit dapat membandingkan apa yang direncanakan, apa yang diterapkan dalam kode, dan apa yang benar-benar terjadi saat gameplay.

## 3. Audit Source: Apakah v8.7.5 Menurunkan OCR di Bawah 50%?

### 3.1 Preset dan cap Lite/Lite IDN tidak berubah dari v8.7.2

Pada `model_strategy.py`, source v8.7.2 dan v8.7.5 sama-sama menggunakan preset:

```text
V1 = OCR 40%
V2 = OCR 45%
V3 = OCR 50%
V4 = OCR 55%
V5 = OCR 60%
```

Lebih penting, untuk keluarga Lite/Lite IDN terdapat logika:

```python
level_ocr_cap = {1: 40, 2: 45, 3: 50, 4: 55, 5: 60}.get(level, 45)
ocr = min(int(ocr), int(level_ocr_cap))
```

Dampaknya:
- Lite/Lite IDN V1 tidak dapat berjalan di atas 40% melalui override biasa;
- Lite/Lite IDN V2 tidak dapat berjalan di atas 45% melalui override biasa;
- adaptive rescue belum tersedia;
- model rendah tetap dipaksa berada pada ambang yang sekarang terbukti tidak aman untuk sejumlah scene GFL2.

### 3.2 Body OCR tidak diturunkan pada v8.7.5

`TITANMAIN.py` v8.7.2 dan v8.7.5 sama-sama membaca body GFL2 melalui:

```python
reader.readtext(img_gray, detail=0, paragraph=True)
```

v8.7.5 menambahkan exact-speaker, stale-overlay/internal-marker guard, telemetry, dan integrasi EntitySpan; tidak ditemukan perubahan source yang secara langsung membuat Body OCR 40/45% membaca resolusi lebih rendah daripada preset lama.

### 3.3 Name ROI pernah dibuat lebih sempit sejak v8.7.3

Dibanding v8.7.2, jalur Name ROI sejak v8.7.3/v8.7.5 menggunakan area lebih sempit dengan upscale/contrast lebih tinggi. Tujuannya benar: mengurangi body text masuk ke jalur nama. Konsekuensinya, label nama pada posisi/layout yang bergeser dapat menjadi lebih sensitif terhadap blur/resolusi rendah. Ini berkaitan dengan **pelabelan speaker**, bukan akar utama body dialog gibberish pada OCR 40–45%.

## 4. Bukti Riwayat: OCR 45% Pernah Menjadi Profil Layak Sebelum v8.7.5

Memo proyek sebelumnya memang menetapkan:
```text
Lite/Lite IDN V2 = OCR 45% recommended efficient-balanced
```

Lebih kuat lagi, ditemukan log lama **v8.4.4 Lite IDN V2 pada OCR 45%** yang benar-benar dijalankan pada GFL2. Log itu mencatat raw OCR yang masih cukup terbaca, misalnya:

```text
Voymastina Visual system and targeting assistance are Off
Voymastina need yoU. to be my eye
Raizei But the accuracy Will suffer
```

Pada sesi lama tersebut, runtime juga mencatat:
```text
Lite CT2 efficient engine active
engine=ct2_fast
```

Ini mendukung ingatan pengguna bahwa OCR 45% sebelumnya tidak selalu terasa rusak berat.

Namun, bukti ini belum dapat membuktikan regresi algoritma OCR secara ilmiah karena:
- scene dan crop lama berbeda dari rekaman v8.7.5;
- sesi lama memakai CT2 aktif sedangkan sesi v8.7.5 jatuh ke Argos;
- belum ada replay frame identik yang diproses di kedua versi.

### Status kesimpulan yang benar

| Klaim | Status |
|---|---|
| OCR 45% pernah digunakan dan dianggap recommended pada versi lama | Terbukti |
| Ada sesi lama OCR 45% dengan raw OCR cukup terbaca | Terbukti |
| v8.7.5 pada OCR 40–45% buruk pada video/log terbaru | Terbukti |
| Source v8.7.5 sengaja menurunkan preset/body OCR dibanding v8.7.2 | Tidak ditemukan |
| v8.7.5 pasti memiliki regresi OCR pada frame identik | Belum terbukti; wajib replay benchmark |

## 5. Faktor yang Berkaitan dengan Pengalaman Downgrade Saat Ini

### A. Cap OCR Lite/Lite IDN terlalu kaku
Cap level menjadikan V1/V2 terjebak di 40%/45%, walaupun pada scene tertentu user membutuhkan kualitas lebih tinggi. Ini adalah keterbatasan desain lama yang kini perlu diperbaiki.

### B. CT2/SPM gagal aktif pada sesi terbaru
Pada v8.7.5, Fast/Lite mencatat:
```text
Fast CT2 unavailable -> Argos fallback: Missing SPM files ... source.spm & target.spm
```

Akibatnya, mode rendah:
- tetap menerima OCR lebih kasar;
- tetapi tidak memperoleh backend translation cepat yang dahulu tampak pada sesi CT2 aktif.

### C. Scene/crop terbaru lebih menuntut
Sesi lama v8.4.4 OCR 45% menggunakan region lebar sekitar `1898 x 267`; sesi Lite IDN V2 v8.7.5 menggunakan region sekitar `1378 x 191`. Crop dan scene yang berbeda dapat memengaruhi keterbacaan raw OCR, sehingga replay identik wajib dilakukan sebelum menyatakan source regression.

### D. UI belum menyatakan runtime secara jujur
Contoh sebelumnya: Fast V1 override benar-benar berjalan pada 65%, tetapi note profil masih mengatakan OCR 40%. Untuk Lite, cap internal juga harus terlihat jelas agar user memahami bahwa override tinggi mungkin tidak benar-benar diterapkan.

## 6. Yang Berhasil pada Runtime v8.7.5

### 6.1 EntitySpan/cache aman pada data runtime yang diaudit
Audit:
- `logs/idn_evaluation_v8_7_5.jsonl`: 3.545 row;
- cache aktif namespace `v8_7_5_verified_exact_entity_safe`: lebih dari 5.000 entry dalam file cache sesi.

Tidak ditemukan marker internal pada evaluation atau cache aktif:
```text
ORT_ENTITY
ORT_BKEND
ORT_BKED
ORT_BEND
_ _ ORT
```

### 6.2 Exact-speaker katalog benar-benar bekerja
Katalog GFL2 berisi 69 nama resmi, dan runtime mengembalikan:
```text
verified_character_speaker_names(GFL2_EXILIUM) = 69
speaker_exact_names(GFL2_EXILIUM) = 70
```
Perbedaan satu nama berasal dari Commander user-configured `Alya Kujou`.

Nama resmi di luar protected seed yang benar-benar terpilih pada runtime v8.7.5:

| Nama | GFL2_SPEAKER_SELECTED | FINAL_OVERLAY berlabel |
|---|---:|---:|
| `Colphne` | 1.283 | 321 |
| `Groza` | 769 | 164 |
| `Krolik` | 187 | 23 |
| `Nikketa` | 178 | 76 |
| `Peri` | 66 | 110 |
| `Nemesis` | 48 | 13 |
| `Mayling` | 45 | 9 |
| `Sabrina` | 8 | 5 |
| `Voymastina` | 5 | 3 |
| `Ullrid` | 1 | 1 |

Ini membuktikan penambahan nama pada v8.7.5 sudah berdampak nyata.

## 7. Bug Baru yang Wajib Diperbaiki: False Speaker dari Fallback Parser

Walaupun Name ROI exact aman, audit `FINAL_OVERLAY` menemukan **31 label final mencurigakan** yang tidak berasal dari katalog speaker resmi:

| Label salah/mencurigakan | Jumlah |
|---|---:|
| `DP` | 18 |
| `Scavenger Ugh` | 3 |
| `Name` | 3 |
| `TC` | 2 |
| `Hybrid` | 2 |
| `Peri Ahh` | 1 |
| `Kulich Woof` | 1 |
| `Colphne Wow` | 1 |

### Akar source
Pada `TITANMAIN.py`, jika metadata `roi_speaker` ada maka speaker aman dipakai. Namun bila metadata tidak ada pada frame tertentu, runtime kembali menjalankan:

```python
split_speaker_and_dialog(raw_text)
```

Parser tersebut memakai regex umum yang mengizinkan tanda hubung sebagai delimiter:
```python
_RX_SPEAKER_COLON = re.compile(
    r"^\s*([A-Za-z][A-Za-z0-9_\-'\s]{1,32})\s*[:：\-]\s*(.+)$"
)
```

Akibatnya, OCR rusak seperti:
```text
DP-'5 an
```
dapat salah dipotong menjadi:
```text
speaker = DP
body    = '5 an
```

Ini menjelaskan kembalinya label `DP`, meskipun `DP-12` sebenarnya sudah dilindungi.

### Solusi P0 v8.7.6
Untuk profile GFL2:
- parser fallback hanya boleh memberi label speaker bila prefix exact cocok dengan `speaker_exact_names()` atau `approved_role_speaker`;
- nonaktifkan generic colon/hyphen speaker promotion untuk GFL2;
- jangan menganggap `-` sebagai delimiter speaker generik ketika nama canonical seperti `DP-12` mungkin sedang rusak;
- pastikan metadata Name ROI tetap terikat pada frame/job antrean yang sama;
- tambahkan event `GFL2_FALLBACK_SPEAKER_REJECTED` dan `FALSE_SPEAKER_BLOCKED`.

## 8. Status Registry Persisten Masih Tidak Konsisten

File `speaker_registry_v2.json` dalam ZIP masih memuat beberapa nama resmi seperti `Groza`, `Nemesis`, dan `Krolik` di `legacy_untrusted`, walaupun runtime dinamis sudah mengenal seluruh 69 nama dari reference catalog.

Artinya:
- runtime label exact bekerja karena membaca katalog secara dinamis;
- tetapi UI/data persisten user masih menyimpan status lama;
- migration `--apply` kemungkinan belum diterapkan pada folder yang kemudian dizip, atau sengaja belum menimpa data user.

### Solusi v8.7.6
Tampilkan banner di UI:
```text
Official GFL2 exact-speaker migration pending.
Backup dan terapkan migrasi aman agar daftar UI sesuai dengan runtime.
```
Sediakan tombol backup + apply yang eksplisit; jangan mengubah data user diam-diam.

## 9. Kandidat Nama dan Alias Berdasarkan Pola Kemunculan

Permintaan pengguna untuk menambah daftar karakter pada v8.7.6 perlu dibedakan menjadi tiga kategori.

### A. Nama Resmi Sudah Ada di Katalog — Jangan Ditambah Duplikat, Tandai sebagai Observed/Priority

Nama berikut sudah ada dalam 69 katalog GFL2 dan sudah terpilih sebagai speaker exact pada v8.7.5. Pada v8.7.6, tambahkan metadata `observed_recent_story` atau tampilan `Terlihat pada Uji Terbaru`, bukan membuat entry baru:

```text
Colphne
Groza
Krolik
Nikketa
Peri
Nemesis
Mayling
Sabrina
Voymastina
Ullrid
```

Tambahkan juga nama resmi yang sudah ada tetapi penting untuk fokus pengujian berikutnya:
```text
Zhaohui
Vector
Harpsy
```

### B. Alias OCR Berulang — Layak Masuk Review Alias Terbatas Name ROI

| Bentuk OCR | Kandidat canonical | Jumlah teramati | Kebijakan |
|---|---|---:|---|
| `Perl` | `Peri` | 615 | Review kuat; ROI-only setelah verifikasi frame |
| `Lentle` | `Lentine` | 509 | Review kuat; ROI-only |
| `Lentlne` | `Lentine` | 354 | Review kuat; ROI-only |
| `DP 12` | `DP-12` | 367 | Tambah sebagai normalisasi Name ROI aman |
| `0P-12` | `DP-12` | 123 | Review/ROI-only |
| `Suoml` | `Suomi` | 37 | Review/ROI-only |
| `Nemesls` | `Nemesis` | 35 | Review/ROI-only |
| `Sprlngfield` | `Springfield` | 27 | Review bila nama ada di katalog |
| `Krolk` | `Krolik` | 27 | Review/ROI-only |
| `Groze`, `9r0za` | `Groza` | 23 / 18 | Review sebelum aktivasi |
| `RSVK`, `KSK` | `KSVK` | 27 / 14 | Ambigu; review ketat |

Alias tidak boleh berlaku pada seluruh body/narasi; hanya pada Name ROI atau exact speaker-prefix yang terverifikasi.

### C. Candidate Role/Story Speaker — Jangan Auto-Add sebagai Karakter Resmi

Candidate berikut muncul di area nama tetapi belum layak dimasukkan sebagai karakter resmi tanpa validasi scene/kategori:

```text
Cllent
Kenny
David
Mrs Grace
Cocoon
Heli
Unfamiliar Worker
Scavenger
Another Unfamllllar
Hybrld-Type Boajum
Igla
```

Mereka dapat masuk panel `Pending Story/Role Candidate` untuk review manual.

### D. Jangan Auto-Add / Klasifikasi Dulu

`DKRIN` muncul sangat sering (1.842 kali) di raw Name ROI, tetapi belum boleh otomatis diperlakukan sebagai nama karakter. Polanya dapat berasal dari label objek/suit/UI/story term pada crop nama. v8.7.6 harus menyediakan snapshot/rejected-candidate evidence sebelum mengklasifikasikan sebagai special term, blacklist, role, atau false crop.

`Helene` juga tidak boleh langsung diarahkan ke `Helen` atau `Helena`, karena kedua canonical character harus tetap dibedakan.

## 10. Roadmap Wajib v8.7.6

### P0 — OCR Profile & Override Repair
- Jadikan OCR 50% minimum rekomendasi story GFL2.
- Ubah label V1/V2 rendah menjadi `Ultra Efficient / Diagnostic` atau `Requires Adaptive Rescue`.
- Lepaskan cap keras Lite/Lite IDN saat user memilih manual override; tampilkan risiko VRAM/latency, bukan diam-diam menurunkan kembali.
- Tambahkan `Adaptive OCR Readability Guard`: OCR awal 40/45 dapat di-rescue menjadi 50/55 bila corruption score tinggi.
- Pertahankan Name ROI quality floor terpisah.

### P0 — False Speaker Fallback Gate
- Untuk GFL2, fallback parser hanya boleh melabel exact official/trusted/approved role.
- Blok `DP`, `Name`, `TC`, `Hybrid`, `Scavenger Ugh`, dan false parser lain.
- Ikat ROI metadata pada request/frame yang sama agar tidak hilang di antrean.

### P0 — Runtime UI Truthfulness
Tampilkan:
```text
Preset OCR
User Requested OCR
Applied OCR
Runtime Rescue OCR
Cap/Rescue Reason
CT2/Argos Applied Backend
Modification Badge
```

### P0 — Replay Benchmark Lintas Versi
Gunakan video/frame identik untuk:
```text
v8.4.4 / v8.7.2 bila runtime tersedia
v8.7.5
v8.7.6 candidate
```
Nilai:
- CER/WER raw OCR;
- exact speaker label hit rate;
- false speaker rate;
- stale-overlay rate;
- latency;
- backend actually applied;
- cache safety.

### P1 — CT2/SPM Recovery atau Safe Fallback
- Perbaiki `source.spm`/`target.spm` agar Fast/Lite kembali benar-benar memakai CT2;
- bila CT2 tidak tersedia, jangan merekomendasikan OCR ultra rendah untuk story;
- profil fallback Argos boleh otomatis memakai floor OCR lebih aman.

### P1 — Character/Alias Review UI
- Tambahkan kolom `Observed in Recent Test`, jumlah teramati, sumber session, dan status `Official / Alias Candidate / Role Candidate / Rejected`.
- Sediakan approve alias ROI-only, promote official migration, dan reject candidate.

### P1 — Memo/Ledger Wajib
Setiap analisis/update berikutnya wajib menambahkan:
- file log/video yang diuji;
- temuan dan angka;
- keputusan yang diterapkan/belum diterapkan;
- alasan perubahan preset;
- source/path yang berubah;
- test result;
- known issues;
- rekomendasi update berikutnya.

## 11. Keputusan Mengenai Riwayat Pengguna

Permintaan pengguna mengenai memo proyek valid dan perlu dipertahankan. Audit kali ini menunjukkan kegunaannya:
- memo lama berhasil membuktikan desain resmi V2 OCR 45% sebagai `recommended efficient-balanced`;
- arsip log v8.4.4 berhasil memberikan bukti sesi lama OCR 45% yang cukup terbaca dan CT2 aktif;
- tanpa catatan tersebut, diagnosis hanya akan bergantung pada ingatan atau absence-of-complaint.

Mulai v8.7.6, riwayat pengujian model harus dicatat sebagai **test ledger terstruktur**, bukan hanya changelog fitur. Ledger perlu menyimpan model, OCR preset/requested/applied, backend actual, scene/video/log, accuracy observation, serta apakah hasil dianggap layak atau gagal.

## 12. Kesimpulan Akhir

v8.7.5 tidak menunjukkan source downgrade langsung pada Body OCR. Namun ada tiga keterkaitan nyata yang membuat user merasakan kualitas lebih buruk:
1. cap Lite/Lite IDN 40/45% tetap dipaksa dan tidak dapat diselamatkan manual;
2. CT2 yang dahulu aktif pada log lama kini fallback Argos, sehingga profil rendah kehilangan manfaat performanya;
3. scene/crop terbaru memperlihatkan bahwa 40/45% tidak cukup aman untuk story GFL2 saat ini.

Sementara itu, v8.7.5 berhasil memperbaiki exact speaker dan EntitySpan, tetapi masih memiliki P0 false-speaker fallback parser yang dapat kembali menghasilkan label seperti `DP`.

Arah v8.7.6:
```text
Adaptive OCR Readability + Manual Override yang benar
+ CT2/fallback policy
+ Exact-only fallback speaker gate
+ Observed character/alias review ledger
+ Replay benchmark lintas versi
+ dokumentasi/memo kumulatif wajib
```
