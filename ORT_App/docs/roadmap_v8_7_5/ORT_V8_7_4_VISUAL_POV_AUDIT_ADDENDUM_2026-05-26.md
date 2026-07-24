# ORT Translation v8.7.4 — Addendum Audit Visual POV Gameplay
**Tanggal:** 26 Mei 2026  
**Status:** Bukti visual tambahan untuk melengkapi audit log/ZIP runtime v8.7.4  
**Video dianalisis:**
- `2026-05-26 19-42-39.mkv` — berkorelasi dengan ORTCore Fast IDN / OCR 50%
- `2026-05-26 19-51-00.mkv` — berkorelasi dengan ORTCore Lite V5 / OCR 60%
- `2026-05-26 19-58-18.mkv` — berkorelasi dengan ORTCore Fast V1 / OCR 40%

## 1. Ringkasan Temuan Visual

Rekaman POV mengonfirmasi dua masalah yang sebelumnya ditemukan melalui source/log:

1. **Karakter valid terbaca di game/hasil OCR tetapi tidak diberi label speaker kuning/orange oleh overlay**, terutama `Zhaohui` dan `Vector`.
2. **Overlay dapat tertinggal melewati pergantian speaker**, sehingga hasil terjemahan speaker sebelumnya masih tampil ketika game sudah memperlihatkan speaker baru.

Rekaman juga menunjukkan mekanisme label berwarna masih bekerja untuk nama trusted, yaitu `Alya Kujou`, sehingga problem bukan kegagalan rendering warna global melainkan kombinasi **registry eligibility** dan **stale output/queue**.

## 2. Video Fast IDN — `2026-05-26 19-42-39.mkv`

### Korelasi runtime
Log sesi Fast IDN menunjukkan:
- `fast_idn`, OCR 50%;
- `responsive_story=0`;
- `latest_frame_wins=0`;
- Fast CT2 tidak tersedia dan runtime fallback ke `argos_offline`.

### Observasi visual

| Timestamp video | Tampilan game | Overlay ORT | Diagnosis |
|---:|---|---|---|
| ±180–184 detik | Speaker game `Vector` | Overlay memulai hasil dengan `Vector Diers ...`, tanpa label warna speaker terpisah | `Vector` terbaca sebagai body, bukan speaker label |
| ±186–188 detik | Speaker game sudah berubah ke `Harpsy` | Overlay masih menampilkan baris yang berawal `Vector ...` | Output tertinggal melewati pergantian speaker |

### Korelasi log
Pada rentang sekitar 19:45:37–19:45:42, queue meningkat dari sekitar 1.013 ms hingga 2.886 ms sebelum baris `Vector Diers ...` diproses. Ini menjelaskan secara teknis mengapa overlay visual masih menunjukkan hasil lama ketika dialog game sudah berpindah.

## 3. Video Lite V5 — `2026-05-26 19-51-00.mkv`

### Korelasi runtime
Log sesi Lite V5 menunjukkan:
- `lite_v5`, OCR 60%;
- `responsive_story=0`;
- `latest_frame_wins=0`;
- backend tetap `argos_offline`.

### Observasi visual

| Timestamp video | Tampilan game | Overlay ORT | Diagnosis |
|---:|---|---|---|
| ±101,7–104 detik | Speaker game `Zhaohui`, body `Alright, then. Talk...` | Overlay menampilkan `Zhaohui Baiklah ...` sebagai teks biasa, tanpa label kuning/orange | OCR/source mengenali nama, tetapi registry/label pipeline tidak memilih speaker |
| ±106–108 detik | Dialog beralih antara `Panicked Suspicious Man` dan `Zhaohui` | Overlay masih membawa terjemahan turn sebelumnya pada sebagian transisi | Stale overlay pada pergantian cepat |

### Korelasi log
Log sekitar 19:52:41–19:52:42 membaca:
```text
Zhaohui
Zhaohui Alright
Zhaohui Alright then
```
dengan tepat. Dengan demikian, kegagalan label `Zhaohui` pada video bukan akibat nama tidak pernah terbaca OCR, melainkan karena `Zhaohui` belum berada pada jalur speaker live yang diizinkan.

## 4. Video Fast V1 — `2026-05-26 19-58-18.mkv`

### Korelasi runtime
Log sesi Fast V1 menunjukkan:
- `fast_v1`, OCR hanya 40%;
- `responsive_story=0`;
- `latest_frame_wins=0`;
- Fast CT2 tidak tersedia, fallback Argos.

### Observasi visual

| Timestamp video | Tampilan game | Overlay ORT | Diagnosis |
|---:|---|---|---|
| ±120–157 detik | Scene berkaitan dengan `Zhaohui` | Overlay menampilkan gibberish, termasuk awal seperti `Zhohul ...` | OCR 40% terlalu rusak untuk baseline akurasi nama |
| ±176–191 detik | Speaker game `Alya Kujou` | Overlay menampilkan label kuning/orange `Alya Kujou` | Mekanisme label berfungsi untuk speaker trusted |
| ±194 detik | Speaker game sudah berubah menjadi `Zhaohui` | Overlay masih menampilkan label/hasil `Alya Kujou` dari turn sebelumnya | Stale output / speaker transition belum diinvalidate segera |
| ±197 detik | Dialog berubah ke narasi | Overlay baru berubah ke hasil berikutnya | Pembaruan overlay terlambat satu transisi |

### Makna
Video ini penting karena membuktikan dua hal sekaligus:
- warna label speaker bukan rusak secara global, karena `Alya Kujou` dapat berwarna benar;
- `Zhaohui` tidak diberi label dan pergantian speaker dapat tertinggal.

## 5. Hubungan dengan Audit Registry Sebelumnya

Temuan visual konsisten dengan audit source/data:
- `Alya Kujou` berada pada jalur speaker terpercaya, sehingga label warna tampil;
- `Zhaohui` hanya berada pada reference catalog, belum live-trusted;
- `Vector` berada pada `legacy_untrusted`, sehingga OCR dapat membaca nama tetapi overlay tidak menjadikannya speaker.

Dengan demikian, perbaikan yang tepat bukan mengaktifkan kembali seluruh NPC legacy, melainkan menambahkan tier aman:

```text
verified_character_speaker_exact
```

Tier ini mengizinkan seluruh karakter GFL2 terverifikasi menjadi speaker **hanya melalui exact Name ROI / exact prefix**, tanpa fuzzy bebas dan tanpa auto-learning narasi.

## 6. Solusi Wajib untuk Update Berikutnya

### Correctness Speaker
- Perbaiki migration agar membaca `reference_roster_catalog.entries[].display_name`.
- Promosikan karakter GFL2 terverifikasi seperti `Zhaohui`, `Vector`, `Colphne`, `Groza`, dan `Ullrid` ke `verified_character_speaker_exact`.
- Tambahkan telemetry `GFL2_NAME_ROI_REJECTED` agar dapat diketahui nama terbaca tetapi ditolak registry.

### Responsivitas Overlay
- Terapkan stale-overlay invalidation ketika speaker/name ROI berubah.
- Prioritaskan output speaker baru dibanding hasil queue dari turn lama.
- Gunakan `latest-frame-wins` dan coalescing pada Mode Responsif.
- Tambahkan event `OVERLAY_STALE_SPEAKER_DROPPED`.

### Baseline Pengujian
- Gunakan Lite V5 atau IDN V2/V3 untuk correctness speaker.
- Jangan memakai Fast V1 OCR 40% sebagai acuan akurasi nama; gunakan hanya untuk mengukur kecepatan ekstrem.
- Uji ulang scene yang sama pada Baseline dan Responsive setelah correctness diperbaiki.

## 7. Batasan Bukti Visual

Video yang diperiksa memberikan bukti langsung untuk:
- `Zhaohui`;
- `Vector`;
- `Alya Kujou`;
- stale overlay pada transition.

Video yang diperiksa belum memberikan bukti visual langsung yang cukup untuk:
- `Ullrid`;
- `Suomi`;
- `Colphne`;
- `Groza`;
- marker backend `ORT_BEND/BKED`.

Kesimpulan untuk nama-nama tersebut dan marker internal tetap bersandar pada structured logs, registry, cache, dan IDN evaluation yang telah diaudit sebelumnya.

## 8. Keputusan Roadmap

Bukti visual ini memperkuat prioritas patch berikutnya:

```text
Registry verified-character exact speaker
+ migration schema fix
+ full backend-safe EntitySpan
+ stale-overlay/speaker transition invalidation
+ baseline-versus-responsive A/B test
```
