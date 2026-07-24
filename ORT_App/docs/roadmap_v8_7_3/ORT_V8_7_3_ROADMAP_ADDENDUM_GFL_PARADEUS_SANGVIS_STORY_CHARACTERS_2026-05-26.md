# ORT Translation v8.7.3 — Roadmap Addendum: GFL Story-Faction Characters (Paradeus & Sangvis Ferri)
**Tanggal:** 26 Mei 2026  
**Status:** Tambahan roadmap kumulatif sebelum implementasi v8.7.3  
**Game Profile:** `GFL` / Girls' Frontline  
**Digabung dengan:** Multi-Game Data Processing UI, Verified Roster Catalog, Trusted Speaker Registry, Compound Speaker Entity, dan Project Memory/Handoff.

## 1. Keputusan Desain

Profile GFL memerlukan bagian khusus untuk **karakter faksi cerita penting**, terutama:
- `Paradeus`
- `Sangvis Ferri`

Bagian ini diperlukan karena karakter bernama dari kedua faksi dapat berbicara dalam story dan perlu dikenali sebagai identitas, bukan dianggap kata biasa.

Namun, sistem **tidak perlu mengimpor semua nama enemy/unit generik sebagai speaker**. Daftar enemy yang luas akan meningkatkan risiko salah label, sementara tujuan utama overlay adalah mengenali pembicara bernama atau role speaker yang benar-benar disetujui.

## 2. Landasan Struktur Data

Sumber implementasi saat build wajib diverifikasi dan dicatat di manifest:
- daftar karakter cerita berdasarkan faksi/tim dipakai untuk `reference_roster_catalog`;
- halaman faksi Paradeus dan Sangvis Ferri dipakai untuk klasifikasi/metadata;
- Enemy Index tidak otomatis dijadikan daftar label speaker aktif.

Pemisahan data:

| Data | Fungsi | Label orange otomatis? |
|---|---|---|
| Karakter bernama penting Paradeus/Sangvis Ferri terverifikasi | Reference roster dan Named Entity Protection | Hanya bila diaktifkan/protected |
| Nama faksi `Paradeus`, `Sangvis Ferri` | Terminologi/Faksi | Tidak |
| Unit/enemy generik | Tidak diimpor default sebagai speaker | Tidak |
| Role yang benar-benar muncul sebagai pembicara | Manual approved role speaker | Ya setelah approval |

## 3. Prioritas Berdasarkan Workflow Pengguna

Pengguna menyatakan bahwa pada progres/story yang sedang dimainkan, fokus saat ini lebih banyak berkaitan dengan Paradeus dan William daripada Sangvis Ferri.

Rancangan UI boleh mengikuti prioritas penggunaan tersebut:
- subbagian `Paradeus` tampil lebih dahulu atau expanded secara default;
- `Sangvis Ferri` tersedia sebagai bagian tambahan/collapsed;
- tidak mengklaim bahwa urutan ini berlaku universal untuk seluruh chapter/story GFL.

## 4. Struktur Mode Normal/Detail GFL yang Direvisi

```text
Girls' Frontline / GFL
├─ T-Doll
│  └─ AK-12, AN-94, M4A1, ST AR-15, M4 SOPMOD II, UMP45, HK416, ...
│
├─ Karakter Penting / Griffin & Allies
│  └─ Commander, Kalina, Kryuger, Helian, Persica, William*, ...
│
├─ Karakter Faksi Cerita
│  ├─ Paradeus                         [Expanded / Priority]
│  │  └─ Named story characters yang diverifikasi/diaktifkan
│  └─ Sangvis Ferri                    [Collapsed / Additional]
│     └─ Named story characters yang diverifikasi/diaktifkan
│
├─ NPC / Role Speaker Disetujui        [Optional]
│  └─ Elite Guard, Voice Male, Army Guard hanya jika manual-approved
│
├─ Terminologi / Faksi
│  └─ Paradeus, Sangvis Ferri, Griffin & Kryuger, DEFY, Neural Cloud, ...
│
├─ Blacklist / Footer Noise
│  └─ GFsystem, gFn, ngf, nifn, UI/credit artifacts
│
├─ Koreksi OCR / Alias
└─ Advanced: Candidate, Legacy Cleanup, Import/Export
```

`William` dapat tampil dalam kelompok cerita/faksi yang sesuai dengan desain data final; UI sebaiknya mendukung metadata faksi/peran tanpa menggandakan satu identity sebagai dua speaker.

## 5. Struktur Mode Sederhana GFL

Dalam mode sederhana, pengguna tidak perlu melihat pembagian faksi yang rumit.

```text
GFL — Tampilan Sederhana
├─ Nama yang Dilindungi
│  └─ T-Doll aktif + karakter penting + karakter faksi yang diaktifkan
├─ Kata Khusus
│  └─ Faksi/istilah/lokasi; bukan speaker
├─ Blacklist / Footer Noise
├─ Koreksi OCR / Alias            [Collapsed]
└─ Kandidat & Cleanup             [Advanced, default OFF]
```

Contoh isi `Nama yang Dilindungi` dapat berisi nama aktif dari:
- T-Doll;
- Commander/Kalina/karakter penting;
- karakter Paradeus atau Sangvis Ferri yang ingin dikenali sebagai speaker.

Pemisahan faksi tetap tersimpan dalam metadata, walaupun mode sederhana menampilkannya sebagai satu daftar speaker terlindungi.

## 6. Spoiler-Aware Roster Design

Karakter faksi cerita dapat menjadi spoiler, khususnya untuk pemain baru. Karena pengguna juga ingin sistem berguna bagi pemain baru, UI perlu menyediakan kontrol spoiler.

### Opsi UI yang disarankan

```text
[ ] Tampilkan / Import Karakter Cerita Lanjutan (mengandung spoiler)
```

Perilaku:
- default OFF pada instalasi baru atau profile bersih;
- bila OFF, hanya karakter/term yang sudah diaktifkan pengguna yang terlihat;
- bila ON, daftar faksi cerita terverifikasi dapat dimuat/ditampilkan untuk memudahkan OCR;
- user berpengalaman dapat mengaktifkan roster lengkap untuk kebutuhan story lanjut.

### Peringatan UI

```text
Daftar karakter Paradeus/Sangvis Ferri dapat mengandung spoiler cerita.
Aktifkan hanya bila Anda ingin sistem mengenali nama cerita lanjutan.
```

## 7. Jangan Buat Kategori Enemy Unit sebagai Speaker Default

Pengguna menyatakan sempat mempertimbangkan memasukkan nama enemy, tetapi menilai tidak terlalu diperlukan. Keputusan yang disarankan:

```text
Tidak membuat daftar Enemy Unit sebagai kategori speaker default.
```

Alasan:
- enemy generik sering bukan pembicara;
- nama unit dapat muncul dalam narasi atau gameplay, bukan dialog;
- menambah daftar luas berisiko memperbesar collision OCR/label;
- Named Entity Protection untuk istilah tertentu dapat ditambahkan bila diperlukan tanpa membuatnya speaker.

Bila suatu generic role benar-benar muncul sebagai label pembicara, gunakan:
```text
Approved NPC / Role Speaker
```
setelah user menambah atau menyetujuinya secara manual.

## 8. Data Model Tambahan

Tambahkan metadata faksi pada `reference_roster_catalog` dan `active_speaker_registry`.

Contoh:

```json
{
  "canonical_id": "gfl_story_character_example",
  "display_name": "Example Character",
  "entity_type": "story_character",
  "game": "GFL",
  "faction": "Paradeus",
  "spoiler_level": "advanced_story",
  "allow_speaker_label": false,
  "active_as_speaker": false,
  "source_checked_at": "2026-05-26"
}
```

Setelah diaktifkan:

```json
{
  "canonical_id": "gfl_story_character_example",
  "active_as_speaker": true,
  "registry_tier": "protected_character"
}
```

Untuk nama faksi sebagai istilah:

```json
{
  "display_name": "Paradeus",
  "entity_type": "special_term",
  "allow_speaker_label": false
}
```

## 9. Hubungan dengan Compound Speaker Entity

Bila karakter atau role speaker faksi memiliki nama lebih dari satu kata, runtime wajib memakai longest-match-first.

Contoh:
```text
URNC Leader
Mysterious Figure
Army Guard
```

Aturan:
- frasa utuh adalah satu speaker entity;
- token internal tidak boleh berwarna atau dilabel terpisah;
- role speaker hanya aktif setelah manual approval.

## 10. Migration dan Import

Saat v8.7.3 diimplementasikan:
- data GFL lama tidak ditimpa langsung;
- buat backup/dry-run;
- imported faction roster masuk `reference_roster_catalog`;
- active speaker lama valid dipertahankan;
- false legacy speakers dipindah ke `legacy_untrusted`;
- tidak ada auto-activation seluruh karakter faksi tanpa pilihan atau kebijakan protected yang eksplisit.

## 11. Test Wajib

| Pengujian | Expected Result |
|---|---|
| Pilih GFL mode Normal | Tab `Karakter Faksi Cerita` tampil |
| Paradeus tab | Dapat expanded/pinned sebagai prioritas pengguna |
| Sangvis Ferri tab | Tersedia sebagai additional/collapsed |
| Spoiler option OFF | Roster cerita lanjutan tidak diekspos otomatis |
| Spoiler option ON | Catalog faksi dapat ditampilkan/import |
| Nama faksi `Paradeus` dalam dialog | Diproteksi sebagai term, bukan label speaker |
| Named Paradeus character aktif | Dapat label speaker melalui trusted registry |
| Named Sangvis character aktif | Dapat label speaker melalui trusted registry |
| Generic enemy tidak approved | Tidak menjadi label orange |
| Role speaker approved | Dilabel sebagai compound entity utuh |
| Mode Sederhana | Nama aktif faksi masuk `Nama yang Dilindungi`, terms/blacklist tetap terpisah |

## 12. Keputusan Final

Pada v8.7.3, halaman `Pengolahan Data & Identitas` untuk GFL harus menambahkan:

```text
Karakter Faksi Cerita
├─ Paradeus       (prioritas/expanded sesuai workflow pengguna)
└─ Sangvis Ferri  (tambahan/collapsed)
```

Dengan prinsip:
- hanya karakter bernama penting yang dimasukkan sebagai catalog/active speaker;
- nama faksi berada di Kata Khusus, bukan speaker;
- daftar enemy/unit generik tidak menjadi kategori speaker default;
- role speaker tetap manual-approved;
- opsi spoiler disediakan;
- mode sederhana tetap ringkas dan mudah digunakan.
