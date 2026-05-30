# ORT Translation v8.7.3 — Roadmap Addendum: Multi-Game Data Processing & UI Redesign
**Tanggal:** 26 Mei 2026  
**Status:** Tambahan roadmap kumulatif sebelum implementasi v8.7.3  
**Dasar:** Permintaan pengguna, audit ZIP aktual v8.7.2, serta roadmap Trusted Speaker Registry / Compound Speaker Entity.

## 1. Temuan Audit Halaman Aktual

Audit source aktual menemukan bahwa halaman `Pengolahan Data` belum sepenuhnya sesuai perkembangan proyek multi-game:

### Yang sudah ada
- Backend/data store telah memiliki bucket:
  - `GFL2_EXILIUM`
  - `WUWA`
  - `GFL`
  - `CUSTOM`
- Seed awal WUWA sudah tersimpan, terdiri dari nama seperti `Rover`, `Yangyang`, `Chixia`, `Jinhsi`, `Changli`, `Camellya`, `Carlotta`, `Phoebe`, `Brant`, `Cartethyia`, dan lainnya.
- Seed awal GFL sudah tersimpan, termasuk `Commander`, `Kalina`, `Dandelion`, `AK-12`, `AN-94`, `AK-15`, `M4A1`, `M4 SOPMOD II`, `ST AR-15`, `UMP45`, `HK416`, `Kryuger`, `Helian`, `Persica`, `William`, dan lainnya.
- Action pada Pengolahan Data sudah menerima nilai `game_dropdown` dari Dashboard sehingga penyimpanan backend dapat per game.

### Yang belum baik
- Tab `Pengolahan Data` tidak menampilkan selector game sendiri; user harus mengingat game yang dipilih di Dashboard.
- Layout selalu menampilkan kategori tetap:
  - Kandidat Baru
  - Daftar Nama
  - Daftar Kata Khusus
  - Original Name
  - Blacklist Kata
  - Pengaturan Pengolahan
- `Original Name` selalu ditampilkan meskipun relevansi utamanya adalah GFL2.
- Data nama masih ditempatkan dalam satu list `names`, belum dibedakan sebagai playable/character, NPC/role speaker, Commander/player name, alias, dan legacy/untrusted.
- Preview badge masih menampilkan contoh statis bernuansa GFL2 (`Groza`, `Commander`, `Project Eden`) meski game aktif WUWA atau GFL.
- Setting saat ini `auto_reset_candidates=False`, sehingga candidate sesi tidak otomatis dibersihkan.

## 2. Tujuan Redesign

Halaman baru harus:
1. Jelas bahwa data berlaku untuk game/profile aktif.
2. Menampilkan kategori yang berbeda sesuai kebutuhan game.
3. Mendukung UI sederhana bagi pengguna yang fokus menguji model.
4. Tetap memisahkan nama speaker dengan kata khusus dan blacklist.
5. Mendukung Compound Speaker Entity sehingga nama multi-kata tetap satu identitas.
6. Terintegrasi dengan Trusted Speaker Registry dan Named Entity Protection.
7. Tidak menimpa data pengguna lama tanpa backup/migration dry-run.

## 3. Nama Halaman Baru

Nama yang disarankan:

```text
Pengolahan Data & Identitas
```

Subjudul:

```text
Kelola nama karakter, speaker NPC yang disetujui, istilah khusus,
koreksi OCR, dan blacklist per game profile.
```

## 4. Header Halaman: Game Selector Sinkron dengan Dashboard

Tambahkan card paling atas:

```text
┌──────────────────────────────────────────────────────────────┐
│ Pengolahan Data & Identitas                                   │
│ Game Profile: [ GFL2: Exilium ▼ ]  Tampilan: [ Sederhana ▼ ]  │
│ Status: GFL2 profile • 14 nama terlindungi • 10 istilah       │
│         3 blacklist • 0 kandidat sesi                          │
│ Data di halaman ini hanya berlaku untuk game profile terpilih.│
└──────────────────────────────────────────────────────────────┘
```

### Aturan sinkronisasi
- Selector game di Pengolahan Data memakai key yang sama dengan Dashboard.
- Mengubah game di Dashboard memperbarui halaman Pengolahan Data.
- Mengubah game di Pengolahan Data memperbarui pilihan game Dashboard bila runtime belum berjalan.
- Jika runtime sedang berjalan, perubahan data profile tidak boleh diam-diam mengubah game runtime aktif; tampilkan pesan:
  ```text
  Data profile berubah untuk WUWA. Runtime saat ini tetap GFL2 sampai sesi berikutnya.
  ```

## 5. Dua Mode Tampilan

### 5.1 Tampilan Sederhana

Mode default yang direkomendasikan bagi pengguna.

Tujuan: user hanya perlu mengelola hal yang sering dibutuhkan tanpa menghadapi candidate/alias database kompleks.

#### Struktur

```text
[ Nama yang Dilindungi ]     [ Kata Khusus ]
- character/playable           - istilah/faksi/lokasi
- NPC/role approved             - tidak boleh menjadi speaker
- Commander/player name

[ Blacklist ]                [ Koreksi OCR / Alias ] (collapsed)
- tidak boleh speaker/term     - elanie → Melanie

[ Advanced: Kandidat Sesi & Cleanup ] (collapsed, default OFF)
```

#### Prinsip penggabungan

Pada mode sederhana, daftar berikut boleh digabung menjadi **Nama yang Dilindungi**:
- playable character;
- story character;
- Commander/player name;
- NPC/role speaker yang sudah disetujui.

Tetapi dua kategori berikut **tidak boleh digabung**:
- `Kata Khusus`, karena istilah bukan speaker;
- `Blacklist`, karena bersifat penolakan dan dapat bentrok bila digabung.

Contoh:
```text
Nama yang Dilindungi:
Alya Kujou, Helen, Helena, KSVK, Balthilde, Phaetusa, URNC Leader

Kata Khusus:
Project Eden, Lviv, Tacet Discord, Griffin & Kryuger

Blacklist:
Dontworry, Hereyes, GFsystem
```

### 5.2 Tampilan Normal / Detail

Mode bagi user yang ingin mengatur kategori secara lebih tepat.

UI menyesuaikan game yang aktif.

## 6. Struktur Normal/Detail Per Game

### 6.1 GFL2: Exilium

```text
GFL2: Exilium
├─ Commander / Player Name
│  └─ Alya Kujou
├─ Karakter / Doll Terlindungi
│  └─ Helen, Helena, KSVK, DP-12, Phaetusa, Balthilde, Melanie, ...
├─ NPC / Role Speaker Disetujui
│  └─ URNC Leader, Army Guard, Mysterious Figure
├─ Original Name / Identity Map
│  └─ Groza → OTs-14
│     Leva → UMP45
│     Alva → AN-94
│     Voymastina → AK-15
├─ Kata / Terminologi Khusus
│  └─ T-Doll, Project Eden, Lviv, Mangi Security, ...
├─ Blacklist Kata
├─ Koreksi OCR / Alias
└─ Advanced: Candidate & Legacy Cleanup
```

**Catatan:** `Original Name / Identity Map` tampil hanya pada GFL2 karena konteks cerita dapat merujuk identitas T-Doll dari GFL lama.

### 6.2 Wuthering Waves / WUWA

```text
Wuthering Waves
├─ Playable Resonator
│  └─ Rover, Yangyang, Chixia, Baizhi, Jinhsi, Changli, ...
├─ Story NPC / Approved Role Speaker
│  └─ NPC penting atau title speaker yang disetujui
├─ Terminologi / Lokasi / Faksi
│  └─ Resonator, Tacet Discord, Black Shores, Jinzhou, Huanglong, ...
├─ Blacklist Kata
├─ Koreksi OCR / Alias
└─ Advanced: Candidate & Legacy Cleanup
```

Tidak menampilkan `Original Name`.

Seed WUWA yang sudah ada diperlakukan sebagai **seed awal**, bukan klaim daftar roster lengkap/terbaru. Daftar dapat diperbarui melalui import/manual update pada pengembangan berikutnya.

### 6.3 Girls' Frontline / GFL

```text
Girls' Frontline
├─ Daftar T-Doll
│  └─ AK-12, AN-94, M4A1, ST AR-15, M4 SOPMOD II, UMP45, ...
├─ Karakter Penting
│  └─ Commander, Kalina, Kryuger, Helian, Persica, William, ...
├─ NPC / Role Speaker Disetujui (opsional)
│  └─ Elite Guard, Voice Male, atau role lain hanya jika manual approved
├─ Terminologi / Faksi
│  └─ T-Doll, DEFY, Paradeus, Sangvis Ferri, Griffin & Kryuger, ...
├─ Blacklist / Footer Noise
│  └─ GFsystem, gFn, ngf, nifn, credit/UI artifacts
├─ Koreksi OCR / Alias
└─ Advanced: Candidate & Legacy Cleanup
```

Tidak perlu menampilkan `Original Name` pada Basic UI GFL; alias/terminologi dapat tetap tersedia di bagian Advanced bila suatu saat dibutuhkan.

### 6.4 Custom

```text
Custom Game
├─ Nama yang Dilindungi
├─ Approved NPC / Role Speaker
├─ Kata Khusus
├─ Blacklist
├─ Koreksi OCR / Alias
└─ Import / Export Profile
```

## 7. Model Data Baru / Schema v2

Simpan data per game menggunakan kategori yang sesuai dengan speaker registry baru:

```json
{
  "GFL2_EXILIUM": {
    "display_name": "GFL2: Exilium",
    "simple_view": true,
    "protected_character": [
      {"canonical_id": "helen", "display_name": "Helen", "aliases": []},
      {"canonical_id": "helena", "display_name": "Helena", "aliases": []},
      {"canonical_id": "phaetusa", "display_name": "Phaetusa", "aliases": ["Phaedusa"]}
    ],
    "user_configured": [
      {"canonical_id": "commander_user", "display_name": "Alya Kujou", "role": "Commander"}
    ],
    "approved_role_speaker": [
      {"canonical_id": "urnc_leader", "display_name": "URNC Leader"}
    ],
    "reviewed_alias": [
      {"ocr_form": "elanie", "canonical_id": "melanie", "scope": "speaker_roi"}
    ],
    "special_terms": ["Project Eden", "Lviv"],
    "blacklist": ["Dontworry", "Hereyes"],
    "original_identity_map": {
      "Groza": "OTs-14",
      "Leva": "UMP45"
    },
    "pending_session_candidate": [],
    "legacy_untrusted": []
  }
}
```

### Backward-compatible migration

Fields lama:
```text
names
special_words
blacklist
original_names
```

harus dimigrasikan secara aman:
- buat backup file lama;
- tampilkan dry-run migration;
- nama yang sudah jelas/protected masuk `protected_character`;
- nama role/title tidak otomatis dipercaya, masuk review;
- false legacy NPC masuk `legacy_untrusted`;
- `special_words` menjadi `special_terms`;
- `original_names` menjadi `original_identity_map` hanya untuk game yang mendukung.

## 8. Compound Name / Longest-Match-First

Seluruh halaman baru dan runtime harus menganggap nama multi-kata sebagai satu entity atomik:

```text
Alya Kujou
URNC Leader
Army Guard
Mysterious Figure
Mysterious Picture
Descender Zero
M4 SOPMOD II
Griffin & Kryuger
Black Shores
```

### Aturan UI
- Chip daftar menampilkan frasa utuh.
- Edit/hapus bekerja pada entity utuh.
- Preview warna tidak menandai token internal secara terpisah.

### Aturan Runtime
- Matching mencoba frasa terpanjang terlebih dahulu.
- Jika speaker `Alya Kujou`, label orange tampil utuh.
- `Kujou` tidak boleh dianggap mention merah terpisah.
- `M4 SOPMOD II` tidak boleh dipecah sehingga `II` berubah makna atau warna.

## 9. Kata Khusus Harus Tetap Terpisah dari Nama

Permintaan pengguna tepat: mode sederhana tidak boleh menggabungkan `Daftar Kata Khusus` ke daftar nama.

### Alasannya
| Contoh | Bila digabung nama | Dampak |
|---|---|---|
| `Project Eden` | Dapat dianggap speaker | Label orange palsu |
| `Black Shores` | Dapat dianggap orang | Salah highlight/NER |
| `Tacet Discord` | Dapat dianggap NPC | Salah parsing |
| `Griffin & Kryuger` | Dapat salah dianggap speaker pada narasi | Kesalahan overlay |

### Desain warna/semantik
| Kategori | Fungsi Runtime | Warna/Label |
|---|---|---|
| Nama Speaker Dilindungi | Boleh menjadi speaker | Orange/kuning speaker |
| Kata Khusus | Protected translation/mention, bukan speaker | Warna term tersendiri |
| Blacklist | Ditolak sebagai nama/term | Badge warning/rejected |
| Pending Candidate | Review saja | Abu-abu, tidak live |

## 10. UI Kandidat dan Pengaturan yang Disederhanakan

### Basic Settings
```text
Tampilan default          : Sederhana
Reset kandidat saat Start : ON
Auto label kandidat baru  : OFF
Legacy NPC dipercaya      : OFF
Popup kandidat setelah Stop: OFF
```

### Advanced
- Candidate review.
- Import/export profile JSON.
- Legacy cleanup/migration.
- Alias editor.
- Color editor.
- Registry source/confidence.

Candidate tidak boleh memengaruhi overlay hingga disetujui.

## 11. Wireframe Konseptual

### Mode Sederhana

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Pengolahan Data & Identitas                                         │
│ Game: [ GFL2: Exilium ▼ ]    Tampilan: [ Sederhana ▼ ]              │
│ 16 Nama Dilindungi • 12 Kata Khusus • 8 Blacklist • 0 Kandidat      │
├─────────────────────────────────────────────────────────────────────┤
│ Nama yang Dilindungi                                                │
│ [Alya Kujou] [Helen] [Helena] [KSVK] [Phaetusa] [URNC Leader]      │
│ Input nama: [________________________] [Tambah] [Import]           │
├─────────────────────────────────────────────────────────────────────┤
│ Kata Khusus                                                         │
│ [Project Eden] [Lviv] [Mangi Security]                              │
│ Input term: [________________________] [Tambah]                     │
├─────────────────────────────────────────────────────────────────────┤
│ Blacklist Kata                                                      │
│ [Dontworry] [Hereyes] [GFsystem]                                    │
│ Input blacklist: [__________________] [Tambah]                      │
├─────────────────────────────────────────────────────────────────────┤
│ ▸ Koreksi OCR / Alias      ▸ Kandidat & Cleanup (Advanced)          │
└─────────────────────────────────────────────────────────────────────┘
```

### Mode Normal GFL2

```text
┌ Game: GFL2: Exilium ▼ ─ Tampilan: Normal ▼ ─ Sync Dashboard: ON ┐
│ Commander Name: [ Alya Kujou____________________ ] [Simpan]      │
│ Tabs: Karakter | NPC/Role | Original Identity | Kata Khusus       │
│       Blacklist | OCR Alias | Kandidat/Cleanup                    │
│ Preview label: [Helen/orange] [Project Eden/term] [Blocked/yellow]│
└────────────────────────────────────────────────────────────────────┘
```

## 12. Perubahan Source yang Dibutuhkan

| File/Area | Perubahan |
|---|---|
| `webui.py` | Header selector game, view-mode toggle, conditional sections, two-way dashboard sync, basic/normal UI |
| `data_processing_backend.py` | Schema v2 per game, entity operations, role approval, migration, import/export |
| `data_processing_settings.json` | `view_mode`, `auto_reset_candidates=True`, `auto_live_candidate_label=False`, `trust_legacy_npc=False` |
| `data_processing_store.json` | Migration-backed storage, tidak ditimpa paksa dalam patch |
| `app/ocr/gfl2_speaker_roi.py` | Ambil only trusted speaker registry |
| `TITANMAIN.py` | Overlay/entity matching longest-first |
| `translation_engine.py` | Named Entity Protection dari registry game aktif |
| `tools/npc_database_cleanup.py` | Migrasi legacy speaker ke untrusted/reviewed |
| `launcher_backend.py` | Profile sync/status diagnostics |
| Tests | UI schema/migration/multi-game/compound-name/no-auto-role tests |
| Dokumentasi | Master handoff, ledger, changelog, patch notes, test report |

## 13. Test Wajib

| Uji | Expected |
|---|---|
| Pilih WUWA di Pengolahan Data | Menampilkan kategori WUWA, tanpa Original Name |
| Pilih GFL2 | Menampilkan Original Identity dan Commander |
| Pilih GFL | Menampilkan T-Doll/Karakter Penting/NPC role opsional |
| Mode Sederhana | Nama speaker digabung; special terms dan blacklist tetap terpisah |
| `Alya Kujou` | Satu chip/entity dan satu label orange utuh |
| `URNC Leader` approved | Satu speaker entity utuh |
| `Army Guard` belum approved | Tidak live-label |
| `Helen`/`Helena` | Dua canonical berbeda, tidak cross-map |
| `M4 SOPMOD II` | Tidak pecah dan token `II` tetap aman |
| Start session | Pending candidate reset bila opsi ON |
| Legacy false names | Tidak menjadi speaker trusted |
| Migration | Membuat backup dan dry-run sebelum ubah data user |

## 14. Keputusan Akhir untuk v8.7.3

Halaman `Pengolahan Data` perlu dirombak menjadi `Pengolahan Data & Identitas` multi-game.

```text
Game selector terlihat dan sinkron dengan Dashboard.
Mode Sederhana menjadi default yang mudah digunakan.
Mode Normal memberi kategori sesuai game.
Nama multi-kata selalu satu entity.
Special terms dan blacklist tidak pernah digabung dengan nama.
Original Name hanya muncul ketika relevan, terutama GFL2.
Candidate/legacy learning menjadi Advanced dan tidak memengaruhi overlay secara otomatis.
```

Rancangan ini harus diimplementasikan bersama Trusted Speaker Registry, Compound Entity, Dual Helen/Helena Guard, Named Entity Protection, dan dokumentasi proyek terintegrasi pada patch v8.7.3.
