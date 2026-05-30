# ORT Translation v8.7.3 — Roadmap Addendum: Simplified NPC/Role Speaker & Compound Name Integrity
**Tanggal:** 26 Mei 2026  
**Status:** Tambahan roadmap kumulatif sebelum implementasi v8.7.3  
**Dasar:** Diskusi pengguna, audit source aktual v8.7.2, log GFL2 IDN v8.7.2, serta roadmap speaker/NER sebelumnya.

## 1. Latar Belakang

Pengguna awalnya menginginkan sistem dapat mengenali pembicara non-karakter bernama seperti:
- `Army Guard`
- `The Mysterious`
- `URNC Leader`
- label role/title/alias serupa

Niat awalnya baik: bila game menampilkan speaker anonim atau gelar, overlay tetap dapat menunjukkan siapa yang berbicara. Namun pada penggunaan nyata, sistem sering:
- gagal mengenali role speaker yang benar;
- mencatat kata/frasa narasi sebagai kandidat nama;
- membawa false speaker lama ke Name ROI/overlay;
- menyulitkan pengujian karena pengguna fokus pada model dan jarang membuka pengaturan review kandidat.

Selain itu, nama multi-kata seperti `Alya Kujou` berisiko dipisah sebagai dua entity, sehingga satu token dapat dipakai sebagai label speaker dan token lainnya dianggap mention atau karakter lain.

## 2. Temuan Source Aktual

### 2.1 Candidate UI dan label salah adalah dua jalur berbeda

`data_processing_backend.py` saat ini:
- mengambil kandidat dari baris `[OCR]`;
- menyimpannya ke `runtime_candidates.json`;
- baru memasukkan kandidat menjadi `names`/`special_words` setelah user menekan tombol konfirmasi.

Jadi fitur `Kandidat Baru` sendiri bukan penyebab utama label orange salah secara otomatis.

Namun:
- `data_processing_settings.json` saat ini memiliki `auto_reset_candidates=False`;
- kandidat session tidak otomatis reset setiap Start sesuai perilaku yang pengguna ingat/inginkan.

### 2.2 Akar label acak yang lebih berbahaya

Jalur `GFL2SpeakerTracker` pada `TITANMAIN.py` menggunakan:

```python
GFL2SpeakerTracker(NPC_DATABASE.get("known", []))
```

Padahal `npc_database.json` telah berisi legacy false names seperti:

```text
Dontworry
Her
Asimple
Noticing
DP
Dp
Griffin's
Hereyes
Tillthe
```

Akibatnya, kata acak yang dulu pernah tersimpan dapat dipakai sebagai label speaker tepercaya pada Name ROI.

## 3. Keputusan Desain: Jangan Hapus Semua Role Speaker, Hapus Otomatisasi Berbahaya

Menghapus seluruh dukungan role/title speaker tidak ideal karena label seperti `URNC Leader` atau `Army Guard` dapat benar-benar merupakan nama pembicara yang ditampilkan game.

Keputusan yang disarankan:

```text
Dukungan role speaker tetap ada,
tetapi tidak boleh dipelajari atau dilabel otomatis dari OCR mentah.
```

### Perilaku default baru

| Jenis teks | Perlakuan default |
|---|---|
| Karakter resmi/protected | Boleh menjadi label orange otomatis |
| Commander name yang diisi pengguna | Boleh menjadi label orange otomatis |
| Role speaker yang sudah disetujui (`URNC Leader`) | Boleh menjadi label orange otomatis |
| Frasa title-like baru dari OCR (`Army Guard`, `The Mysterious`) | Tidak tampil sebagai label sampai user menyetujui |
| Kata biasa/narasi | Tidak disimpan dan tidak menjadi speaker |
| Legacy NPC tercemar | Masuk `legacy_untrusted`, tidak boleh dipakai Name ROI |

## 4. Registry Baru yang Sederhana

Buat data speaker menjadi beberapa kelas jelas:

| Kelas | Isi | Persistensi | Dipakai label orange? |
|---|---|---|---|
| `protected_character` | Nama karakter resmi: `Helen`, `Helena`, `KSVK`, `Phaetusa` | Permanen per game | Ya |
| `user_configured` | Nama Commander: `Alya Kujou` | Permanen per pengguna/game | Ya |
| `approved_role_speaker` | `URNC Leader`, `Army Guard`, `Mysterious Figure` setelah disetujui | Permanen per game | Ya |
| `reviewed_alias` | OCR alias yang sudah divalidasi: `elanie → Melanie` | Permanen dan terikat canonical | Ya, setelah canonicalized |
| `pending_session_candidate` | Kandidat OCR baru yang belum disetujui | Session-only, reset saat Start | Tidak |
| `legacy_untrusted` | Data lama/false speaker | Tersimpan hanya untuk cleanup/audit | Tidak |

## 5. Mode UI yang Disederhanakan

Karena pengguna lebih sering fokus pada pengujian model daripada membuka pengaturan, pengolahan nama harus lebih sederhana.

### Tab Basic yang disarankan

Tampilkan hanya:

1. **Commander / Player Name**
   ```text
   Alya Kujou
   ```

2. **Karakter Resmi yang Dilindungi**
   - daftar protected canonical;
   - tombol tambah/hapus manual;
   - nama valid default proyek.

3. **Role Speaker yang Disetujui**
   - tambah manual `URNC Leader`, `Army Guard`, dll.;
   - hapus manual bila tidak diperlukan.

4. **Tombol Koreksi Speaker Aktif**
   - saat overlay salah, user dapat memilih nama benar dengan satu aksi;
   - koreksi masuk `reviewed_alias`/`approved_role_speaker`, bukan learning liar.

### Tab Advanced yang disembunyikan secara default

- review kandidat otomatis;
- candidate frequency;
- blacklist;
- legacy cleanup;
- alias details;
- warna kategori.

### Pengaturan default

```text
Automatic Candidate Discovery for Live Label = OFF
Show Candidate Review Popup = OFF
Pending Candidate Auto Reset on Session Start = ON
Use Legacy NPC as Trusted Speaker = OFF
```

## 6. Compound Speaker Entity: Nama Dua/Tiga Kata Harus Atomik

Nama speaker tidak boleh diproses per-token. Ia harus diproses sebagai frasa utuh.

### Contoh entity atomik

```text
Alya Kujou
Mysterious Picture
URNC Leader
Army Guard
Descender Zero
M4 SOPMOD II
```

### Struktur data yang disarankan

```json
{
  "canonical_id": "commander_alya_kujou",
  "display_name": "Alya Kujou",
  "entity_type": "user_configured",
  "aliases": [],
  "tokens": ["Alya", "Kujou"],
  "allow_speaker_label": true,
  "allow_body_highlight": true
}
```

### Longest-Match-First

Matcher wajib mencoba frasa terpanjang lebih dahulu:

```text
Alya Kujou  sebelum  Alya  atau  Kujou
URNC Leader sebelum  URNC  atau  Leader
Descender Zero sebelum Descender
```

### Dampak pada warna dan overlay

Jika speaker aktif adalah `Alya Kujou`:

```text
OCR body: Alya Kujou How much do you know?
```

hasil akhir:

```text
Label orange: Alya Kujou
Body putih   : How much do you know?
```

Tidak boleh terjadi:

```text
Label orange: Alya
Body merah   : Kujou How much do you know?
```

atau:

```text
Label orange: Alya Kujou
Body merah   : Kujou ...
```

## 7. Role Speaker: Opsi yang Aman

### Contoh role speaker valid

```text
URNC Leader
Army Guard
Enemy Soldier
Mysterious Figure
```

### Cara masuk registry

| Cara | Status |
|---|---|
| User menambah manual | Langsung `approved_role_speaker` |
| Sistem mendeteksi berulang dari Name ROI | Hanya menjadi pending candidate |
| User menekan Approve pada candidate | Menjadi `approved_role_speaker` |
| Sistem menebak dari body/narasi | Dilarang |

### Perilaku session-only

Bila candidate discovery Advanced diaktifkan:
- kandidat disimpan hanya untuk sesi berjalan;
- otomatis reset ketika sesi baru dimulai;
- tidak memengaruhi label overlay;
- dapat dipromosikan manual bila benar.

## 8. Hubungan dengan Helen/Helena dan Nama Baru

Desain ini wajib digabungkan dengan:
- Dual Canonical Identity Guard `Helen`/`Helena`;
- protected characters: `KSVK`, `Melanie`, `Balthilde`, `Phaetusa`;
- Commander Display Name `Alya Kujou`;
- Named Entity Protection dari backend translation.

Compound name dan canonical identity tidak boleh bertentangan:
- `Helen` dan `Helena` adalah dua entity canonical berbeda;
- `Alya Kujou` adalah satu entity, bukan dua token nama;
- role speaker dua kata juga satu entity.

## 9. Migration dan Cleanup

Pada update v8.7.3:
- pindahkan false legacy NPC dari jalur trusted menjadi `legacy_untrusted`;
- jangan menghapus data otomatis tanpa dry-run/backup;
- sediakan tombol:
  - `Review & Clean Legacy NPC`;
  - `Promote to Character`;
  - `Promote to Role Speaker`;
  - `Blacklist as Non-Speaker`.

False entries yang telah terlihat dan layak masuk daftar review:

```text
Dontworry
Her
Asimple
Noticing
DP
Dp
Griffin's
Hereyes
Tillthe
Sensing
```

## 10. Regression Tests Wajib

| Uji | Expected |
|---|---|
| `Alya Kujou` sebagai speaker | Label utuh `Alya Kujou`, tidak terpecah |
| Body menyebut `Alya Kujou` tetapi speaker lain | Tidak mengganti speaker aktif |
| `URNC Leader` approved | Label utuh sebagai satu role speaker |
| `Army Guard` belum approved | Tidak menjadi label otomatis |
| `Mysterious Picture` protected/approved | Frasa utuh, tidak dipotong |
| `Helen` | Tetap `Helen`, tidak cross-map ke `Helena` |
| `Helena` | Tetap `Helena`, tidak cross-map ke `Helen` |
| `elanie` di Name ROI | Menjadi `Melanie` hanya melalui verified alias |
| Legacy `Dontworry` | Tidak boleh menjadi label speaker |
| Start sesi baru | Pending candidates reset otomatis |

## 11. Keputusan Final Roadmap

Untuk v8.7.3:

```text
Jangan menghapus dukungan speaker gelar/alias sepenuhnya.
Nonaktifkan auto-promotion dan auto-label role/title candidate secara default.
Gunakan approved role registry yang sederhana dan manual.
Pisahkan legacy NPC dari trusted speaker.
Perlakukan seluruh nama multi-kata sebagai satu entity atomik dengan longest-match-first.
Sederhanakan UI agar user dapat menambah Commander/Character/Role speaker tanpa harus mengelola candidate kompleks.
```

Dokumen ini harus dimasukkan ke master project memory/handoff, development ledger, known issues, next recommendations, dan ZIP patch terintegrasi saat v8.7.3 diimplementasikan.
