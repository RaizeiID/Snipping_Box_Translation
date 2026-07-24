# ORT Translation v8.7.3 — Addendum Roadmap: Packaging Strategy & Verified Multi-Game Roster Catalog
**Tanggal:** 26 Mei 2026  
**Status:** Keputusan roadmap kumulatif sebelum implementasi v8.7.3  
**Game scope:** `GFL2_EXILIUM`, `GFL`, `WUWA`, `CUSTOM`

## 1. Keputusan Packaging v8.7.3

v8.7.3 tidak wajib dibuat sebagai full-project/folder baru. Aturan rilis yang tetap berlaku:
- full project terakhir adalah v8.7;
- update minor/iteratif berikutnya tetap dikirim sebagai **changed-files ZIP patch**;
- setiap ZIP patch wajib membawa master handoff, ledger, changelog, status implementasi, known issues, rekomendasi berikutnya, manifest, patch notes, serta test report terbaru di dalam struktur proyek yang sama.

Namun v8.7.3 bukan patch kecil biasa. Ia akan menyentuh:
- halaman `Pengolahan Data & Identitas`;
- schema data speaker multi-game;
- Trusted Speaker Registry;
- Compound Speaker Entity;
- Named Entity Protection;
- cache namespace/version bump dan cleanup kontaminasi;
- migration data user lama.

Karena itu, prosedur pemasangan yang aman:
1. Simpan folder v8.7.2 aktif sebagai backup.
2. Buat salinan lokal, misalnya:
   `ORT_Translation_v8_7_3_TEST`
3. Terapkan changed-files patch v8.7.3 ke folder salinan.
4. Jalankan dry-run migration dan periksa daftar perubahan data.
5. Uji GFL2/GFL/WUWA pada folder test.
6. Setelah lolos validasi, folder test dapat digunakan sebagai folder utama baru.

Full-project v8.7.3 hanya perlu dibuat bila pengguna secara eksplisit meminta build lengkap, atau bila setelah uji patch ternyata migration/source-state terlalu sulit dipastikan dengan overwrite changed-files.

## 2. Keputusan: Sistem Boleh Mengetahui Roster Tiga Game Secara Luas

Pengguna mengizinkan penambahan daftar nama karakter dari:
- Girls' Frontline (`GFL`);
- Girls' Frontline 2: Exilium (`GFL2_EXILIUM`);
- Wuthering Waves (`WUWA`).

Namun implementasi tidak boleh hanya mengandalkan ingatan AI. Daftar harus:
- dikumpulkan dari sumber yang diverifikasi saat implementasi;
- mencatat sumber, tanggal pengambilan, game version/server scope bila tersedia;
- dapat di-update/import di versi berikutnya;
- tidak secara otomatis mempercayai semua nama atau role sebagai speaker live dengan fuzzy matching bebas.

## 3. Sumber Acuan Roster Awal yang Sudah Diverifikasi

### Girls' Frontline
- IOP Wiki `T-Doll Index` menyatakan dirinya sebagai complete image list T-Dolls yang dicakup wiki.
- Halaman tersebut memuat ratusan T-Dolls, termasuk `DP-12`, `KSVK`, `M4 SOPMOD II`, `ST AR-15`, `UMP45`, `HK416`, `AK-12`, `AN-94`, dan lain-lain.

### Girls' Frontline 2: Exilium
- IOP Wiki `GFL2 Doll Index` menyatakan daftar lengkap Dolls yang dicakup wiki.
- Indeks saat audit telah memuat `Helen`, `Balthilde`, `Phaetusa`, `Dushevnaya`, `Daiyan`, `Klukai`, `Makiatto`, `Springfield`, dan banyak Doll lainnya.
- Sumber story/crew context membuktikan `Helen`, `Balthilde`, `Phaetusa` hadir bersama dalam konten Antiparallel.
- `Helena` harus dipertahankan sebagai canonical story character yang berbeda dari `Helen`, sesuai konfirmasi pengguna dan konteks cerita GFL2.

### Wuthering Waves
- Kuro Games merilis resonator baru melalui patch/version update, sehingga roster WUWA bersifat berkembang.
- Saat implementasi, daftar playable Resonator harus ditarik dari sumber official/current yang tersedia dan/atau roster index terawat, disimpan sebagai versioned seed, bukan diklaim lengkap selamanya tanpa refresh.

## 4. Jangan Memasukkan Semua Nama Langsung ke Jalur Label Orange

Masalah inti v8.7.2 adalah registry label orange terlalu mudah tercemar dan fuzzy matcher terlalu bebas. Jika seluruh roster besar GFL langsung dijadikan fuzzy candidate speaker aktif, collision akan meningkat.

Solusi yang benar adalah dua lapis data:

### 4.1 `reference_roster_catalog`
Berisi seluruh nama karakter terverifikasi yang diketahui sistem.

Dipakai untuk:
- pencarian/daftar UI;
- exact matching;
- Named Entity Protection agar nama tidak diubah backend;
- saran aktivasi;
- original identity map bila relevan.

Tidak otomatis dipakai untuk fuzzy live label seluruhnya.

### 4.2 `active_speaker_registry`
Berisi nama yang boleh menjadi label orange pada game/session aktif.

Kategori:
- `protected_character`;
- `user_configured` seperti Commander Name;
- `approved_role_speaker`;
- `reviewed_alias`.

Dipakai untuk:
- Name ROI label speaker;
- exact/alias-first speaker selection;
- temporal voting;
- final overlay.

Kategori lain:
- `pending_session_candidate`: saran sementara, tidak label live;
- `legacy_untrusted`: data lama tercemar, tidak label live.

## 5. Strategi Per Game

### 5.1 GFL2_EXILIUM
Import:
- verified Doll roster ke `reference_roster_catalog`;
- named story characters yang terverifikasi dan dapat muncul sebagai speaker;
- `original_identity_map` untuk identitas GFL lama bila relevan.

Protected awal wajib:
```text
Helen
Helena
KSVK
DP-12
Balthilde
Phaetusa
Melanie
Dushevnaya
Suomi
Lentine
Dandelion
Descender Zero
```

User-configured:
```text
Alya Kujou = Commander Display Name
```

Aturan penting:
- `Helen` dan `Helena` protected terpisah;
- tidak fuzzy cross-map;
- `DP-12` dapat berhubungan dengan `Helen` pada identity/history context, tetapi jangan menyamakan dialog speaker tanpa aturan cerita/konfigurasi yang eksplisit.

### 5.2 GFL
Import:
- seluruh T-Doll terverifikasi ke `reference_roster_catalog`;
- karakter story penting seperti `Commander`, `Kalina`, `Kryuger`, `Helian`, `Persica`, `William`;
- terminology/faction terpisah.

Karena roster GFL sangat besar:
- exact/longest-match-first aman digunakan;
- fuzzy alias hanya untuk active/reviewed set atau nama yang sedang tampil di story test;
- jangan membuat seluruh ratusan T-Doll menjadi fuzzy candidate bebas terhadap body OCR.

### 5.3 WUWA
Import:
- seluruh playable Resonator terverifikasi pada versi/sumber saat build sebagai `reference_roster_catalog`;
- named story NPC dapat ditambahkan jika sumber terverifikasi atau pengguna menyetujuinya;
- terminology/lokasi/faksi tetap terpisah dari speaker.

Tidak memiliki `Original Name` seperti GFL2.

Karena roster bertambah melalui update:
- simpan metadata `source_checked_at`;
- sediakan import/update roster di UI/patch berikutnya;
- label daftar sebagai seed pada versi tertentu, bukan “selamanya lengkap”.

### 5.4 Role Speaker / NPC Gelar
Role seperti:
```text
Army Guard
URNC Leader
Mysterious Figure
Voice Male
Elite Guard
```
tidak dimasukkan otomatis sebagai roster karakter terverifikasi kecuali memang ada sumber/dialog valid dan/atau disetujui pengguna.

Masuk sebagai:
```text
approved_role_speaker
```
setelah manual approval.

## 6. Compound Entity dan Nama Multi-Kata

Semua nama roster harus mendukung entity atomik dan longest-match-first:

```text
Alya Kujou
Descender Zero
M4 SOPMOD II
ST AR-15
Griffin & Kryuger
Black Shores
URNC Leader
```

Aturan:
- frasa penuh dicocokkan sebelum token parsial;
- nama speaker tidak dipecah menjadi beberapa warna/identitas;
- proper noun multi-kata dilindungi utuh dari backend;
- token `II` di `M4 SOPMOD II` atau `Level II` tidak boleh dirusak normalizer umum.

## 7. Data UI dan Import Manifest

Halaman `Pengolahan Data & Identitas` perlu menampilkan:
- Game Profile;
- Tampilan Sederhana/Normal;
- jumlah roster referensi;
- jumlah speaker aktif/protected;
- source roster dan tanggal pembaruan;
- tombol `Update/Import Roster`;
- tombol `Activate as Speaker`;
- tombol `Approve Role Speaker`;
- tombol `Clean Legacy NPC`.

Contoh metadata roster:
```json
{
  "game": "GFL2_EXILIUM",
  "catalog_version": "v8_7_3_seed_2026_05_26",
  "source_name": "IOP Wiki GFL2 Doll Index + validated project log additions",
  "source_checked_at": "2026-05-26",
  "reference_count": 0,
  "active_speaker_count": 0
}
```

## 8. Migration dan Keamanan

Pada v8.7.3:
- jangan overwrite file data user secara paksa;
- buat backup sebelum migration;
- tampilkan dry-run:
  - data masuk protected;
  - data masuk catalog reference;
  - data dipindah ke legacy_untrusted;
  - cache yang di-invalidasi;
- semua docs/memo harus ikut ZIP patch.

## 9. Test Wajib

| Uji | Expected |
|---|---|
| Patch diterapkan ke salinan v8.7.2 | Tidak merusak folder asli |
| Roster GFL2 import | Helen dan Helena terpisah; Phaetusa/Balthilde ada |
| Roster GFL import | T-Dolls tersedia sebagai reference catalog tanpa fuzzy body pollution |
| Roster WUWA import | Playable Resonators tersedia dan memiliki metadata sumber/tanggal |
| `Alya Kujou` | Satu compound speaker entity |
| `M4 SOPMOD II` | Tidak pecah atau salah pada token II |
| Unapproved `Army Guard` | Tidak otomatis label orange |
| Approved `URNC Leader` | Dapat label orange sebagai satu entity |
| Cache version bump | Output tercemar lama tidak dipakai ulang |
| Migration dry-run | Backup dan daftar perubahan tersedia |

## 10. Keputusan Akhir

Untuk v8.7.3:
- format rilis default tetap changed-files patch terintegrasi;
- pemasangan awal dilakukan ke clone/test folder baru karena perubahan schema besar;
- sistem akan ditambah katalog roster karakter yang luas dan terverifikasi untuk ketiga game;
- seluruh roster tidak langsung dijadikan fuzzy live speaker;
- speaker orange hanya berasal dari active/trusted registry;
- roster dan source metadata dapat diperbarui pada rilis mendatang.
