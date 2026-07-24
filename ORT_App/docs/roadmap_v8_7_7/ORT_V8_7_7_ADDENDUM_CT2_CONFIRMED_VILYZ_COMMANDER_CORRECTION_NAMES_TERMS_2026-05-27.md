# ORT Translation v8.7.7 — Addendum Koreksi CT2, Commander Name, Nama dan Terms
**Tanggal:** 27 Mei 2026  
**Status:** Keputusan roadmap terkunci untuk update v8.7.7; dokumen ini tidak mengubah runtime v8.7.6.

## 1. CT2: Diagnosis Kini Terkonfirmasi oleh Uji PowerShell Pengguna

Pengguna memeriksa folder model CT2 yang benar:

```text
D:\AI TRANSLATOR\ORT_Translation_v8_7\models\ct2_opus_mt_en_id
```

dan kelima file wajib telah tersedia:

```text
config.json               True
model.bin                 True
shared_vocabulary.json    True
source.spm                True
target.spm                True
```

Sebelum koreksi environment, PowerShell menunjukkan konflik path:

```text
TITAN_CT2_EN_ID_DIR = D:\AI TRANSLATOR\TitanCore V2 (5)\models\ct2_opus_mt_en_id
TITAN_SPM_EN_ID_DIR = D:\AI TRANSLATOR\TitanCORE V2\models\opus_mt_en_id_raw
```

Ini mengonfirmasi bahwa fallback Argos bukan disebabkan model CT2/SPM tidak ada di instalasi ORT, tetapi karena runtime masih mendapat environment lama yang menunjuk folder TitanCORE lama.

### Langkah verifikasi manual yang perlu diselesaikan

Empat user environment variable berikut harus menunjuk folder CT2 ORT yang sama:

```text
TITAN_CT2_EN_ID_DIR
TITAN_SPM_EN_ID_DIR
ORT_FAST_CT2_MODEL_DIR
ORT_LITE_CT2_MODEL_DIR
```

Setelah persistent variable disetel, buka PowerShell baru, cek nilainya, jalankan `test_ct2_en_id.py`, lalu pastikan boot log aplikasi berubah menjadi:

```text
Lite CT2 efficient engine active
Fast CT2 engine active
```

dan tidak lagi:

```text
Fast CT2 unavailable -> Argos fallback
```

### Perbaikan permanen v8.7.7

- `launcher_backend.py` harus overwrite seluruh path model/SPM dari folder valid hasil FastModelManager, termasuk `TITAN_SPM_EN_ID_DIR`.
- `translation_engine.py` harus mengirim `spm_dir_en_id=str(model_dir)` secara eksplisit.
- UI Runtime & Tools harus menyediakan `Repair / Rebind CT2 Model & SPM Path`.
- Diagnostic report harus menunjukkan `model_dir_used` dan `spm_dir_used` serta memberi error bila berbeda.

## 2. Koreksi Penting: `Vilyz` Bukan NPC/Character Bawaan

Pengguna mengonfirmasi bahwa `Vilyz` adalah **nama Commander pada akun lain**, bukan nama karakter resmi atau NPC global yang harus dimasukkan ke roster.

### Kebijakan final

`Vilyz` tidak boleh masuk:

```text
reference_roster_catalog official GFL2
verified_story_character_speaker_exact global
approved_named_npc_speaker bawaan
alias auto-live global
```

`Vilyz` hanya boleh digunakan sebagai:

```text
commander_profile_name / user_configured_commander
```

yang aktif per akun/profile saat pengguna memilih atau mengetikkannya. Aturannya exact-only, sama seperti mekanisme Commander Name `Alya Kujou`.

## 3. Official GFL2 yang Tidak Ditambah Duplikat, tetapi Diberi Metadata Observed

Nama berikut sudah termasuk official roster/exact speaker. v8.7.7 harus memperbarui metadata `observed_recent_story_v8_7_6` dan prioritas retest, bukan membuat entri baru.

| Nama | Selected pada v8.7.6 |
|---|---:|
| Phaetusa | 2.132 |
| DP-12 | 1.715 |
| KSVK | 1.042 |
| Lentine | 750 |
| Helen | 744 |
| Lenna | 696 |
| Mayling | 363 |
| Helena | 196 |
| Groza | 174 |
| Colphne | 136 |
| Melanie | 98 |
| Krolik | 84 |
| Ullrid | 82 |
| Nemesis | 56 |
| Dushevnaya | 23 |

Fokus retest tambahan yang sudah official:

```text
Zhaohui
Vector
Harpsy
```

## 4. Pending NPC / Role Speaker: Review Manual, Bukan Auto-Live

| Kandidat | Bukti kemunculan | Kebijakan |
|---|---:|---|
| Inspector | 248 | Pending role exact-only setelah konfirmasi visual |
| Warrant Officer Vladimir (`Warrant Offlcer Vlad`) | 177 | Pending named-role; konfirmasi frame |
| Client / Cllent | 127+ | Pending generic role; jangan auto-live |
| Unfamiliar Worker | 42 | Pending role |
| Another Unfamiliar ... | 17 | Pending; canonical belum pasti |
| UMP9 / UMPO | 52 / 45 | Perlu verifikasi konteks identitas/story |

## 5. Alias OCR untuk Review ROI-Only

Alias ini hanya boleh berlaku pada Name ROI atau speaker-prefix tervalidasi, tidak untuk body dialog.

| OCR | Canonical | Hit |
|---|---|---:|
| Lentlne | Lentine | 1.162 |
| Lentle | Lentine | 263 |
| DP 12 | DP-12 | 445 |
| D-12 | DP-12 | 302 |
| 0p12 | DP-12 | 233 |
| 0P-12 | DP-12 | 105 |
| KVK | KSVK | 145 |
| KSUK | KSVK | 99 |
| KSV | KSVK | 34 |
| Krolk | Krolik | 55 |
| Mayllng | Mayling | 41 |
| 6r0za | Groza | 30 |
| 9r0za | Groza | 28 |
| Gr0za | Groza | 10 |
| Nemeslis | Nemesis | 8 |
| Lenne / Lemna | Lenna | 6 / 2 |

Aturan tetap:

```text
Helene tidak boleh auto-map ke Helen maupun Helena.
```

## 6. Special Terms GFL2 yang Harus Ditambahkan pada v8.7.7

Term berikut masuk sebagai istilah/lokasi/organisasi terlindungi, **bukan speaker**:

| Term | Fungsi |
|---|---|
| URNC | Organisasi/faksi |
| Conglomerate | Organisasi/faksi |
| Green Zone | Zona/lokasi |
| Yellow Zone | Zona/lokasi |
| Odesa | Lokasi |
| ELID / ELIDs | Istilah lore |
| ODE-01 | Identifier/lokasi dengan angka-hyphen |
| Griffin / Griffin & Kryuger | Organisasi |

Term yang sudah ada dan harus dipertahankan:

```text
Lviv
Mangi Security
Neural Cloud
T-Doll
Nyto
Project Eden
```

Kandidat lore yang tetap review-only sebelum diaktifkan:

```text
Elmo
Cocoon
Boajum
Varjager / Varjagers
ODE-01 Central Station
```

## 7. Kata Hallucination Bukan Lore Game

Kata berikut tidak boleh dimasukkan ke `special_terms` GFL2:

```text
nabi
Quran / Alquran
Mekah
Luth
Syuaib
malaikat
kafir
mukmin
Al-masyâriq
```

Kata-kata tersebut hanya digunakan sebagai indikator **Universal Semantic Faithfulness Gate** ketika tidak didukung oleh source dialog.

## 8. Implementasi Wajib v8.7.7

1. CT2/SPM path rebind permanen dan diagnostic repair.
2. Universal Semantic Faithfulness Gate dan semantic cache rotation.
3. Dialogue Completeness / Stable Commit Gate.
4. IDN quality lock/hysteresis.
5. Official observed metadata update tanpa duplikat roster.
6. Pending role/NPC review panel dan alias ROI-only review.
7. Special terms GFL2 baru sesuai tabel di atas.
8. `Vilyz` hanya sebagai Commander Name opsional per akun, bukan roster/NPC global.
