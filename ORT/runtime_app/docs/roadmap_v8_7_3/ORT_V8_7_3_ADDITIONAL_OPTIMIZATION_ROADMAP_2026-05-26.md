# ORT Translation v8.7.3 — Tambahan Roadmap Optimasi Arsitektur dan Validasi
**Tanggal:** 26 Mei 2026  
**Status:** Tambahan roadmap kumulatif; wajib digabung dengan Source Audit Root-Cause Report dan Helen/Helena Dual Canonical Identity Guard pada patch berikutnya.  
**Tujuan:** memastikan v8.7.3 memperbaiki akar sistem, bukan hanya menambah daftar nama.

## A. Dasar Rekomendasi

Tambahan roadmap ini didasarkan pada temuan yang sudah terverifikasi:
- raw OCR/log berulang menampilkan `Helena Helen ...`, sedangkan `Helen` dan `Helena` kini telah dikonfirmasi sebagai dua karakter valid yang harus dibedakan;
- audit source menemukan Name ROI/legacy-NPC/fuzzy canonical dapat salah memilih identitas dan metadata ROI tidak menjadi sumber overlay yang otoritatif;
- structured events menunjukkan `KSVK` pernah terdeteksi internal tetapi tidak sampai menjadi label orange;
- IDN Evaluation Export menunjukkan nama benar seperti `Phaetusa`/`Balthilde` dapat berubah setelah backend menjadi `Phaedusa`/`Balthalde`;
- stable-final cache bekerja sebagian, tetapi cache harus di-invalidasi setelah fix identitas/named entity agar output salah tidak dipakai ulang;
- OCR pernah berkembang dari varian salah menuju `Level II` yang benar, sehingga final commit harus mengizinkan koreksi frame akhir.

## B. Prioritas P0 — Perubahan Arsitektur yang Wajib

### 1. Dialogue Frame Transaction / Trace ID

Setiap dialog/frame harus membawa identitas tunggal dari capture hingga overlay:

```text
dialog_id
frame_id
raw_name_roi
raw_body_ocr
canonical_speaker_candidate
selected_speaker
normalized_source
cache_decision
backend_output
final_idn_output
final_overlay_speaker
final_overlay_body
```

**Tujuan:**
- memastikan hasil ROI `KSVK` tidak hilang saat melewati scheduler/queue;
- dapat mengetahui tepat di tahap mana `Helen` menjadi `Helena`;
- dapat mengaitkan output salah backend dengan source yang benar;
- menjadikan debug dan laporan sesi dapat diaudit.

### 2. Trusted Speaker Registry Bertingkat

Name ROI tidak boleh lagi mempercayai seluruh `npc_database.json` legacy.

Buat tingkat kepercayaan:

| Tingkat | Isi | Boleh menjadi label orange otomatis? |
|---|---|---|
| `protected_canonical` | Nama resmi tervalidasi | Ya |
| `user_configured` | Commander display name, mis. `Alya Kujou` | Ya |
| `reviewed_learned` | Nama baru yang sudah disetujui user | Ya |
| `quarantine` | Kandidat dari OCR/learning | Tidak |
| `legacy_untrusted` | Data lama/false speaker | Tidak |

Protected canonical awal GFL2:

```text
DP-12
KSVK
Helen
Helena
Melanie
Balthilde
Phaetusa
Dushevnaya
Suomi
Lentine
Descender Zero
Dandelion
```

`Alya Kujou` dimasukkan sebagai `user_configured Commander Display Name`.

### 3. Speaker Identity Conflict Guard

Aturan identity:
- exact match menang mutlak;
- alias terverifikasi menang setelah exact;
- fuzzy baru dipakai bila tidak ada canonical conflict;
- pasangan canonical dekat `Helen` dan `Helena` tidak boleh saling fuzzy-map;
- speaker final berasal dari Name ROI/temporal vote yang tervalidasi, bukan dari body.

Jangan lagi menyuntikkan selected speaker ke depan raw body. Kirim metadata speaker terpisah ke overlay.

### 4. Named Entity Round-Trip Protection

Sebelum backend translation, lindungi nama/istilah penting sebagai placeholder; setelah backend dan IDN Quality Layer, pulihkan ejaan canonical.

Contoh protected names:

```text
Helen
Helena
Phaetusa
Balthilde
Alya Kujou
KSVK
DP-12
Dushevnaya
Suomi
```

**Target:**
- menghentikan `Phaetusa → Phaedusa`;
- menghentikan `Balthilde → Balthalde`;
- mempertahankan `Helen` dan `Helena` terpisah.

### 5. Cache Schema Versioning & Contamination Cleanup

Setelah speaker/NER normalizer diubah:
- bump versi cache namespace;
- invalidasi/migrasi cache yang memuat output tercemar:
  - `Helena Helen ...`;
  - `Phaedusa`;
  - `Balthalde`;
  - token kritis final yang salah.
- jangan menghapus canonical `Helena` yang benar.

## C. Prioritas P0 — Critical Text Integrity

### 6. Critical Token Revision Guard

Token berikut tidak boleh final-store terlalu dini:

```text
I
II
III
IV
I'm
I've
I'll
I'd
DP-12
Helen
Helena
```

Aturan:
- bila frame akhir memberi pembacaan lebih lengkap (`Level II`) daripada preview awal (`Level I`/`Level Il`), final output dan cache harus direvisi;
- untuk `I`/contraction, gunakan multi-frame voting dan context rule terbatas;
- token critical yang masih berkonflik menunda `CACHE_STORE_STABLE_FINAL`.

## D. Prioritas P1 — UI, OCR, dan Pengujian

### 7. GFL2 ROI Calibration & Debug UI

Tambahkan pada WebUI:
- preview kotak Name ROI dan Body ROI;
- adjustment posisi/ukuran ROI per resolusi/UI scale;
- badge selected speaker + confidence + source (`ROI exact`, `alias`, `temporal hold`);
- tombol koreksi speaker aktif;
- field `Commander / Player Display Name`.

Koreksi manual user masuk ke `reviewed_learned`/`user_configured`, bukan auto-learning liar.

### 8. OCR Quality Budget Terpisah

- Body OCR boleh turun resolusi karena pressure/latency.
- Name ROI harus memiliki kualitas minimum yang lebih stabil karena teksnya kecil dan menentukan identitas.
- Jangan menambah OCR karakter-per-karakter untuk seluruh body.
- Tambahkan log saat Name ROI tetap high-quality sementara body downscale.

### 9. Offline Replay Regression Harness

Simpan frame/screenshot masalah sebagai test fixture:

```text
KSVK speaker dialog
Alya Kujou commander dialog
Melanie / elanie
Helen dialog
Helena dialog
Balthilde dialog
Phaetusa / Phaedusa
Level II
I am
I refuse
I've
I'll
```

Setiap test memiliki expected:
- selected speaker;
- body setelah prefix stripping;
- protected names output;
- critical tokens;
- cache/store decision.

Patch tidak boleh dirilis bila fixture inti gagal.

### 10. Session Debug Bundle / One-Click Export

WebUI sebaiknya menyediakan tombol ekspor ZIP berisi:
- live log;
- structured events;
- `idn_evaluation*.jsonl`;
- status applied engine;
- cache summary per model;
- speaker conflicts;
- ROI snapshot opsional;
- konfigurasi model/profile/crop yang digunakan.

**Tujuan:** pengguna cukup mengirim satu paket evaluasi lengkap setelah tes.

### 11. True Pipeline Warmup

Warmup v8.7.2 belum merepresentasikan translasi pertama yang nyata. Pada v8.7.3:
- lakukan warmup OCR ROI + backend Argos/engine applied + IDN layer;
- pisahkan `cold_start_ms`, `warmup_ms`, dan `live_latency_ms`;
- jangan menganggap model lambat hanya karena cold start;
- jangan menambah pass global berat ketika OCR sering didownscale.

## E. Urutan Implementasi yang Disarankan

| Tahap | Implementasi | Alasan |
|---|---|---|
| 1 | Trusted Speaker Registry + Dual Helen/Helena Guard | Menghentikan label salah paling merusak |
| 2 | Metadata speaker otoritatif + frame transaction | Memastikan ROI benar sampai overlay |
| 3 | Named Entity Protection | Menghentikan nama benar rusak oleh backend |
| 4 | Cache version bump/cleanup | Mencegah output lama salah muncul ulang |
| 5 | Critical Token Revision Guard | Menangani `I`/`II`/contractions secara aman |
| 6 | ROI Calibration UI + Commander field | Membuat perbaikan dapat disesuaikan user |
| 7 | Debug Bundle + Replay Harness | Membuat validasi versi berikutnya lebih cepat dan terpercaya |
| 8 | True warmup/resource tuning | Optimasi performa setelah correctness stabil |

## F. Hal yang Tidak Disarankan untuk v8.7.3

- Jangan menghapus `Helena` atau mengganti seluruh `Helena → Helen`.
- Jangan mempercayai seluruh database NPC legacy sebagai speaker valid.
- Jangan mengubah OCR seluruh body menjadi perhuruf.
- Jangan menilai model IDN terbaik sebelum output final/source yang sama dibandingkan.
- Jangan menaikkan beban OCR global saat body masih sering downscale.
- Jangan mempertahankan cache lama tanpa version bump setelah perbaikan identitas/named entity.

## G. Dokumentasi dan Validasi Wajib pada Rilis

Patch v8.7.3 harus menyertakan di ZIP yang sama:
- master project memory/handoff terbaru;
- development ledger/workflow;
- changelog/version history;
- implementation status/known issues/next recommendations;
- manifest dan patch notes;
- compile/test report;
- daftar cache invalidation/migration;
- hasil replay regression tests.

## H. Keputusan Akhir Tambahan Roadmap

v8.7.3 harus berorientasi pada **integritas identitas dan traceability**:

```text
Nama benar dibaca
→ nama benar dipilih sebagai speaker
→ nama benar dilindungi dari backend
→ body tidak menggandakan speaker
→ cache menyimpan output yang benar
→ log membuktikan setiap keputusan
```

Setelah fondasi ini lolos uji GFL2, barulah optimasi naturalisasi IDN/model ranking dan perluasan fitur lain aman dilakukan.
