# ORT Translation v8.9.9 R2 F2 — Long-Turn Context & Japanese Accuracy Fix

Hotfix ini tetap memakai nomor versi **v8.9.9** dan dipasang setelah v8.9.9 R2 F1.

Perubahan utama:
- Dialog panjang tidak lagi dipaksa menjadi segmen baru setiap 6–10 detik. Audio memakai rolling window terbatas, tetapi satu `segment_id` dipertahankan sampai jeda yang benar-benar cukup.
- `RollingTurnContext` menyimpan hingga 240 kata konteks internal dan menampilkan jendela terbaru 56/72/92 kata sesuai profil Speed/Normal/Accurate.
- Hipotesis ASR yang berubah tidak ditempel mentah. Tail yang belum stabil diganti, sedangkan bagian yang keluar melalui overlap dikomit sebagai konteks.
- Kotoba GPU Normal memakai beam 2 untuk partial dan beam 3 untuk final; Accurate memakai beam 3/4. Ini meningkatkan ketelitian Jepang dengan latensi yang masih cocok untuk GPU realtime.
- Endpoint diperpanjang agar jeda pendek antarfrasa atau pergantian pembicara cepat tidak langsung memutus konteks.
- Final kosong dapat memakai konteks partial terakhir agar kalimat berguna tidak hilang.
- Final pembicara sebelumnya masih boleh tampil selama 1,8 detik bila pembicara baru belum menghasilkan setidaknya empat kata.
- Log `displayed` sekarang mencatat `context_words` dan `display_words`.

Jalankan `VERIFY_ORT_V8_9_9_R2_F2.bat` setelah menimpa file.

---

# ORT Translation v8.9.9 R2 F1 — Hybrid Startup & Subtitle Continuity Fix

Hotfix ini tetap menggunakan nomor versi **v8.9.9** dan dipasang di atas v8.9.9 R2.

Perubahan utama:
- Hybrid Japanese/Accurate dapat memakai baseline CUDA Small yang sudah divalidasi, lalu Kotoba menjalankan preflight modelnya sendiri.
- Partial bermakna pertama tetap tampil segera.
- Revisi kecil digabung sekitar 0,46 detik pada Normal dan 0,58 detik pada Accurate agar subtitle tidak berkedip atau terpotong per kata.
- Tanda baca tunggal, hasil kosong, dan pesan guard tidak menggantikan subtitle terakhir.
- Quality reject EMPTY/NO_SPEECH dibatasi frekuensinya di log.
- CPU fallback tetap aktif apabila preflight model GPU gagal.

Jalankan `VERIFY_ORT_V8_9_9_R2_F1.bat` setelah menimpa file.

---

# ORT Translation v8.9.9 R2 — GPU Runtime & Normal Realtime Stability

R2 adalah hotfix di atas v8.9.9 R1. Fokusnya adalah membuat mode GPU benar-benar menggunakan CUDA setelah inferensi nyata lulus, sekaligus menjaga profil **Normal** tetap responsif saat hanya CPU yang tersedia.

## Perubahan utama

- Installer `INSTALL_AUDIO_GPU_V8_9_9_R2.bat` membuat atau memperbaiki environment Audio GPU.
- CUDA 12, cuBLAS 12, cuDNN 9, dan CUDA runtime dipasang di environment GPU ORT, bukan ke source ZIP.
- Jalur DLL NVIDIA diaktifkan sebelum CTranslate2/Faster-Whisper diimpor.
- GPU baru dianggap siap setelah dua inferensi nyata pada model Faster-Whisper Small berhasil.
- Profil Normal menggunakan `small:cuda:int8_float16` pada GPU dan `base:cpu:int8` pada CPU/CPU Guard.
- Partial Normal dibatasi pada jendela audio terbaru agar antrean tidak terus membesar.
- Quality retry ganda dinonaktifkan pada Normal; retry kualitas penuh hanya tersedia pada Accurate.
- Antrean final dibatasi dan memprioritaskan segmen terbaru saat perangkat tertinggal.

## Cara menerapkan

1. Tutup seluruh WebUI, overlay, dan proses Audio ORT.
2. Timpa patch R2 ke instalasi v8.9.9 R1.
3. Jalankan `VERIFY_ORT_V8_9_9_R2.bat`.
4. Jalankan `INSTALL_AUDIO_GPU_V8_9_9_R2.bat`. Paket NVIDIA dapat berukuran lebih dari 1 GB.
5. Jalankan `CHECK_AUDIO_GPU_V8_9_9.bat`.
6. Buka kembali WebUI dan pilih **Normal + Hybrid** atau **Normal + GPU**.

GPU yang lulus akan menghasilkan `effective_mode=hybrid` atau `effective_mode=gpu`, diikuti `CUDA_PREFLIGHT_PASSED`. Jika driver atau runtime GPU belum kompatibel, ORT mempertahankan CPU Normal tanpa menandai GPU sebagai siap.

---

# ORT Translation v8.9.9 R1

**Hotfix:** Live Preview & CPU Dual-Stream Performance  
**Base required:** ORT v8.9.9

## R1 changes

- Preview English/source is visible by default for English, Japanese bridge, and other audio routes.
- Japanese Specialist on CPU no longer blocks the live overlay with a 7-15 second Kotoba pass in Normal/Instant.
- Normal/Instant uses a fast provisional multilingual preview and immediate Indonesian translation.
- Accurate keeps the direct Kotoba path for users who prefer quality over latency.
- Optional background Kotoba correction is disabled by default to prevent CPU contention. It can be enabled with `ORT_AUDIO_BACKGROUND_SPECIALIST_CORRECTION=1`.
- Azure status `credential_set=False` still means cloud translation is not active; Local Live remains the effective engine.

# ORT Translation v8.9.9

**Jenis rilis:** Safe Language Auto-Correct & Japanese Specialist Reliability  
**Basis pembaruan:** ORT Translation v8.9.8 lengkap  
**Mode awal yang disarankan:** Live Media · Local Live · Balanced · Smart Auto/Japanese Specialist

v8.9.9 memperbaiki hasil pengujian v8.9.8 ketika Kotoba sempat dimuat di GPU, tetapi inferensi pertama gagal karena `cublas64_12.dll` lalu sistem menggantinya dengan Faster-Whisper Base CPU. Sekarang model dipertahankan saat failover:

```text
Kotoba CUDA
→ CUDA preflight gagal
→ Kotoba CPU
→ rolling partial tetap berjalan
```

## Safe Language Auto-Correct

Mode default **Balanced** mengamati bahasa melalui Language Watchdog ringan yang berjalan terpisah dari ASR utama. Pergantian global membutuhkan bukti dominan sekitar delapan detik. Dialog asing pendek diproses sebagai `TEMPORARY_CODE_SWITCH` tanpa mengganti bahasa utama sesi.

Pilihan WebUI:

- Off
- Conservative · 12 detik
- Balanced · 8 detik · rekomendasi
- Aggressive · 5 detik
- Kunci bahasa utama; code-switch sementara tetap dapat dideteksi

## Japanese Specialist

Gunakan installer baru yang tidak terikat versi:

```text
INSTALL_JAPANESE_SPECIALIST.bat
```

Installer sekarang:

1. melanjutkan unduhan Kotoba yang terputus;
2. memeriksa file repository resmi;
3. menyalin `tokenizer.json` dari model Whisper lokal atau mengunduh hanya tokenizer;
4. memuat model Kotoba CPU secara offline;
5. baru melaporkan `passed=true` setelah model benar-benar dapat digunakan.

File lama `SETUP_JAPANESE_SPECIALIST_V8_9_8.bat` menjadi redirect kompatibilitas dan akan dihapus saat struktur Plugin v9.0.0 diterapkan.

## Perlindungan halusinasi

Output berulang seperti `チーズ` puluhan kali, frasa yang sama terus-menerus, rasio output tidak wajar, dan Japanese bridge yang gagal menjadi English diblokir sebelum diterjemahkan atau ditampilkan. Glosarium GFL2 tidak lagi dipakai sebagai prompt keras pada setiap snapshot; koreksi istilah dilakukan secara lunak setelah ASR.

## Tampilan overlay

Subtitle Indonesia menjadi tampilan utama. Teks sumber/English bridge disembunyikan secara default, tetapi tetap dicatat pada log untuk diagnosis.

## Pemeriksaan

```text
VERIFY_ORT_V8_9_9.bat
CHECK_AUDIO_GPU_V8_9_9.bat
```

Untuk memasang patch, baca `README_APPLY_PATCH_V8_9_9.txt`.

---



## v8.8.8 R2

Hotfix for v8.8.8 roadmap activation: fixes Prediction Guard false positives, activates exact entity labels/visible confidence badges, merges registry into runtime memory, activates mode policy telemetry, and connects Interval Fast-Skip Safety.


## v8.8.8-r2

Offline Replay Benchmark, Long Session Analyzer, registry expansion from v8.8.7 recording, and mode policy refactor foundation. Preserves low-OCR 40% gains while preparing Auto/Interval/Freeze separation.


## v8.8.8-r2

Name/Term Prediction Guard & Dialogue Safety. Adds guarded prediction/repair text, UI text filtering, emergency commit, and safer speaker/term handling while preserving v8.8.6 low-OCR improvements.

# ORT Translation v8.8.2

**Release type:** Full project folder / structural refactor  
**Focus:** folder cleanup, launcher UX, GitHub-ready layout, and compatibility bridge.  
**Runtime behavior:** based on v8.7.9 Responsive Faithfulness & Turn-Safe Overlay. OCR/translation behavior is intentionally not refactored yet; that is planned for v8.8.2.

## v8.8.5 Recording Candidate

v8.8.5 adds GFL2 recording stability features: CT2 path resolver, overlay commit gate, render signature dedupe, minimum visible time, and lightweight recording telemetry. For long GFL2 story recording, start with Normal V1 / Auto / OCR 65% and confirm the log shows CT2 active.


## Cara menjalankan

Untuk pengguna biasa, buka:

```text
START_HERE.bat
```

Pilihan utama:

1. **Buka WebUI / App Manager** — membuka dashboard ORT.
2. **Jalankan OCR Overlay** — memakai runtime terakhir yang sudah dikonfigurasi.
3. **Setup / pilih Runtime Python** — digunakan pertama kali atau saat runtime pindah folder.
4. **Buka folder logs** — melihat log runtime terbaru.
5. **Buka README** — membuka panduan ini.

## Struktur baru

```text
ORT_Translation_v8_8_1/
├── START_HERE.bat
├── Start WebUI.bat
├── Start OCR.bat
├── Runtime.bat
├── README.md
├── CHANGELOG.md
├── VERSION.txt
├── .gitignore
└── ORT/
    ├── runtime_app/        # Runtime aktual v8.8.2, kompatibel dengan struktur lama
    ├── docs/               # Dokumentasi, handoff, roadmap, migration map
    ├── user_data/          # Placeholder data aktif pengguna untuk struktur masa depan
    ├── logs/               # Placeholder log eksternal
    ├── cache/              # Placeholder cache eksternal
    ├── backups/            # Placeholder backup eksternal
    └── debug_bundles/      # Placeholder debug bundle eksternal
```

## Kenapa masih ada `ORT/runtime_app/`?

v8.8.2 adalah **structural refactor tahap aman**. File runtime lama tetap dipertahankan utuh di `ORT/runtime_app/` agar import/path lama tidak rusak. Root folder sudah bersih dan launcher baru mengarahkan pengguna ke runtime yang benar.

Refactor perilaku seperti Auto Smooth, Freeze OCR 100%, Interval Stable, Dialogue State Machine, dan Overlay Anti-Flicker ditargetkan untuk **v8.8.2** setelah struktur v8.8.2 stabil.

## Catatan GitHub

Paket lokal ini masih dapat menyertakan runtime/config kecil agar tetap mudah dipakai. Untuk upload GitHub publik, gunakan `.gitignore` yang sudah disediakan agar cache, logs, backup, debug bundle, runtime Python, dan data aktif tidak ikut terunggah.

## Update dari v8.7.9

- Root folder dibuat bersih.
- Launcher pengguna dipusatkan di root.
- Runtime lama dipindahkan ke folder terstruktur `ORT/runtime_app/`.
- Dokumentasi/handoff proyek disalin ke `ORT/docs/handoff/`.
- File generated lama seperti logs/cache/backups dibersihkan dari paket v8.8.2.
- Struktur awal GitHub-ready disiapkan.


## v8.8.2 R2 - Folder lokal besar dibuat satu tempat

Jika di laptop Anda ada folder/file besar seperti runtime Python, model, cache lokal, hasil log besar, backup, atau file web/runtime lokal yang tidak ingin ikut saat membuat ZIP/GitHub, kumpulkan semuanya di:

```text
ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/
```

Folder ini sengaja dibuat sebagai area lokal yang mudah dikecualikan. Saat Anda membuat ZIP manual untuk GitHub, cukup jangan centang folder tersebut. Untuk export source yang lebih aman, gunakan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Catatan: `ORT/runtime_app/` tetap berisi runtime aplikasi yang diperlukan oleh launcher agar program tetap berjalan. Folder `_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD` ditujukan untuk file besar/lokal seperti environment, model, cache, backup, log besar, dan export pribadi yang tidak perlu dibagikan.


---

## GitHub Safe Upload

v8.8.2 R3 menyertakan perlindungan agar folder runtime/cache/log/model besar tidak ikut terupload ke GitHub.

File penting:
- `.gitignore`
- `ORT/.gitignore`
- `.gitattributes`
- `EXPORT_GITHUB_SOURCE.bat`
- `CHECK_GITHUB_READY.bat`
- `UNTRACK_LOCAL_RUNTIME_FROM_GIT.bat`
- `ORT/docs/user_guide/GITHUB_UPLOAD_GUIDE_V8_8_1_R3.md`

Untuk upload paling aman, jalankan:

```text
EXPORT_GITHUB_SOURCE.bat
```

Lalu upload ZIP `ORT_GITHUB_SOURCE_EXPORT.zip` ke GitHub atau gunakan Git dari root folder project.



## v8.8.2 Runtime Behavior Refactor

Update ini menambahkan Auto Smooth, Freeze OCR Override, Interval Stable/Story-aware, Turn Transcript Accumulator, No-Downgrade Source Rule, Anti-Flicker Overlay Buffer, dan Speaker Prefix Sanitizer v3.


## v8.8.8-r2 — Mandatory Final Commit & Mode Buffer

Adds final-lane Temporal OCR Consensus, experimental `Mode Buffer`, Mandatory Final Commit v2, Low-OCR Visual Rescue planner, and Bad Cache Shield v2.
