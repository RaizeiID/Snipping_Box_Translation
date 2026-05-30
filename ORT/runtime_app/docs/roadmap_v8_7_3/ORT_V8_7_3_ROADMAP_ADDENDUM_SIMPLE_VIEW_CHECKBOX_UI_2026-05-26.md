# ORT Translation v8.7.3 — Roadmap Addendum: Checkbox UI untuk Tampilan Sederhana / Normal
**Tanggal:** 26 Mei 2026  
**Status:** Tambahan roadmap kumulatif sebelum implementasi v8.7.3  
**Halaman target:** `Pengolahan Data & Identitas`

## 1. Keputusan UI

Kontrol pergantian tampilan halaman tidak dibuat sebagai dropdown tambahan. Gunakan satu checkbox/switch:

```text
☑ Tampilan Sederhana
```

Perilaku:
- kondisi default pada first run/profile baru: **tercentang**;
- tercentang: halaman memakai UI Sederhana;
- tidak tercentang: halaman membuka UI Normal/Detail sesuai `Game Profile`;
- selector game tetap berupa dropdown tersendiri;
- checkbox hanya mengubah tampilan dan organisasi menu, tidak mengubah runtime game atau isi registry secara otomatis.

## 2. Rancangan Header Halaman

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Pengolahan Data & Identitas                                         │
│ Game Profile : [ GFL2: Exilium ▼ ]                                  │
│ ☑ Tampilan Sederhana                              Status: Sederhana │
│                                                                     │
│ 16 Nama Dilindungi • 12 Kata Khusus • 8 Blacklist • 0 Kandidat      │
│ Data tersimpan hanya berlaku untuk game profile terpilih.           │
└─────────────────────────────────────────────────────────────────────┘
```

Ketika di-uncheck:

```text
│ ☐ Tampilan Sederhana                         Status: Normal / Detail│
```

Label status diperlukan agar user langsung memahami perubahan tampilan tanpa menebak arti checkbox.

## 3. Mode Sederhana Saat Checkbox Tercentang

```text
☑ Tampilan Sederhana

Nama yang Dilindungi
- karakter resmi/playable/T-Doll yang aktif
- Commander / Player Name
- approved NPC/role speaker

Kata Khusus
- istilah/lokasi/faksi; tidak boleh dianggap speaker

Blacklist
- noise dan kata yang dilarang menjadi speaker/term

▸ Koreksi OCR / Alias             [collapsed]
▸ Kandidat & Cleanup              [Advanced, collapsed]
```

Prinsip:
- nama karakter dan NPC/role yang sudah disetujui boleh digabung karena sama-sama merupakan speaker valid;
- `Kata Khusus` tidak boleh digabung ke nama;
- `Blacklist` tidak boleh digabung ke nama atau kata khusus.

## 4. Mode Normal/Detail Saat Checkbox Tidak Tercentang

### GFL2_EXILIUM

```text
☐ Tampilan Sederhana — Normal / Detail

Commander / Player Name
Karakter / Doll Terlindungi
Approved NPC / Role Speaker
Original Name / Identity Map
Kata / Terminologi Khusus
Blacklist
OCR Alias & Cleanup
Candidate / Legacy Migration       [Advanced]
```

### WUWA

```text
Playable Resonator
Story NPC / Approved Role Speaker
Terminologi / Lokasi / Faksi
Blacklist
OCR Alias & Cleanup
Candidate / Legacy Migration       [Advanced]
```

Tidak menampilkan `Original Name`.

### GFL

```text
T-Doll
Karakter Penting / Griffin & Allies
Karakter Faksi Cerita
  ├─ Paradeus                       [priority/expanded]
  └─ Sangvis Ferri                  [additional/collapsed]
Approved NPC / Role Speaker
Terminologi / Faksi
Blacklist / Footer Noise
OCR Alias & Cleanup
Candidate / Legacy Migration       [Advanced]
```

### CUSTOM

```text
Nama yang Dilindungi
Approved NPC / Role Speaker
Kata Khusus
Blacklist
OCR Alias & Cleanup
Import / Export Profile
```

## 5. Penyimpanan Preferensi

Setting baru:

```json
{
  "simple_view_enabled": true
}
```

Aturan:
- bila setting belum ada, default dibuat `true`;
- setelah user mengubah ke Normal (`false`), pilihan tersebut disimpan;
- perpindahan game tidak mereset checkbox;
- membuka ulang aplikasi mempertahankan preferensi terakhir;
- patch/migration tidak boleh menimpa preferensi user yang sudah ada.

Rekomendasi: preferensi ini bersifat global untuk UI, bukan per-game, agar pengalaman tetap sederhana dan konsisten.

## 6. Keamanan Saat Berpindah Mode

Perpindahan UI tidak boleh:
- menghapus nama yang sudah diinput;
- menggabungkan kategori data secara permanen tanpa migrasi;
- memindahkan kata khusus menjadi nama;
- mengubah game runtime ketika proses sedang berjalan;
- menyimpan input yang belum dikonfirmasi secara diam-diam.

Bila ada input yang belum disimpan saat checkbox diubah, UI harus:
- menyimpan draf lokal dengan aman; atau
- menampilkan konfirmasi sebelum mengganti tampilan.

## 7. Hubungan dengan Compound Speaker Entity

Pada kedua mode, nama multi-kata tetap satu entity utuh:

```text
Alya Kujou
URNC Leader
Army Guard
Mysterious Figure
Descender Zero
M4 SOPMOD II
```

Mode Sederhana hanya menyederhanakan tampilan kategori; ia tidak boleh menyederhanakan entity menjadi token terpisah.

## 8. Target Perubahan Source

| File/Area | Kebutuhan |
|---|---|
| `webui.py` | Checkbox, badge status, conditional layout, preserve form/input |
| `data_processing_settings.json` | Tambah `simple_view_enabled`, default aman |
| `data_processing_backend.py` | UI mode membaca schema sama tanpa mengubah data otomatis |
| Migration tool | Tambahkan setting hanya jika belum ada |
| Tests | Checkbox default, persistence, per-game sections, no data-loss |
| Dokumentasi | Changelog, handoff, ledger, patch notes, UI guide |

## 9. Regression Test Wajib

| Uji | Expected |
|---|---|
| Instalasi/profile baru | `Tampilan Sederhana` tercentang |
| User uncheck checkbox | Mode Normal/Detail terbuka |
| Pilih GFL2 dalam Normal | Original Identity tampil |
| Pilih WUWA dalam Normal | Original Identity tidak tampil |
| Pilih GFL dalam Normal | Paradeus/Sangvis section tampil |
| Kembali ke Sederhana | Nama valid digabung tampilan; terms dan blacklist tetap terpisah |
| Pindah game | Status checkbox tetap |
| Restart aplikasi | Pilihan terakhir dipertahankan |
| Runtime aktif | Toggle tampilan tidak mengganti runtime game |
| Ada input belum tersimpan | Tidak hilang diam-diam |

## 10. Keputusan Final

Pada v8.7.3, kontrol tampilan halaman `Pengolahan Data & Identitas` menggunakan satu checkbox:

```text
☑ Tampilan Sederhana  = Mode Sederhana (default)
☐ Tampilan Sederhana  = Mode Normal / Detail
```

Desain ini mengurangi beban pilihan pada user, membuat game selector tetap fokus untuk memilih profile, dan menjaga halaman lebih praktis untuk aktivitas utama pengguna: pengujian model dan koreksi data penting.
