# CHANGELOG — ORT Translation v8.9.9 R2 F2

## Long-Turn Context & Japanese Accuracy Fix

### Added
- `RollingTurnContext` dengan committed prefix dan replaceable live tail.
- Konteks internal maksimal 240 kata dengan display window profil: Speed 56, Normal 72, Accurate 92 kata.
- Telemetry `continuous_turn_window_shift`, `turn_context_words`, `turn_display_words`, dan `final_context_fallback`.

### Changed
- Batas 6–10 detik sekarang menjadi ukuran rolling audio window, bukan pemutus paksa dialog.
- Speed/Normal/Accurate memakai endpoint 460/620/760 ms untuk mempertahankan jeda singkat.
- Jendela GPU Jepang menjadi 5,5/7,5/10 detik untuk partial dan 8/12/16 detik untuk final.
- Kotoba GPU: Speed beam 1/2, Normal beam 2/3, Accurate beam 3/4 untuk partial/final.
- Threshold no-speech Japanese Specialist dilonggarkan menjadi 0,52 dan bridge Japanese guard menjadi 45% karakter Jepang.

### Fixed
- Terjemahan yang kembali pendek setiap rolling window walaupun karakter masih berbicara.
- Segment reset pada dialog panjang tanpa jeda.
- Final previous speaker yang dibuang ketika pembicara baru hanya sempat menghasilkan satu sampai tiga kata.
- Final kosong yang menghapus konteks partial berguna.
- Revisi ASR panjang yang ditempel sebagai kalimat duplikat alih-alih mengganti tail tidak stabil.

### Preserved
- Nomor versi tetap v8.9.9.
- GPU preflight, CUDA runtime R2, Hybrid fallback, dan subtitle continuity F1 tetap aktif.
- CPU Normal tetap memakai jendela inference 3,2 detik partial / 6 detik final; konteks panjang dibangun oleh assembler agar latency CPU tidak meningkat tajam.

# CHANGELOG — ORT Translation v8.9.9 R2 F1

## Hybrid Startup & Subtitle Continuity Fix

### Fixed
- Hybrid + Accurate + Japanese tidak lagi dipaksa ke CPU Guard hanya karena marker `validated_cuda_medium.json` belum ada. Marker Small hasil inferensi nyata dipakai sebagai baseline CUDA, lalu Kotoba melakukan preflight spesifik sebelum streaming.
- Runtime capture mengikuti GPU runtime ketika mode efektif GPU/Hybrid.
- Output `.` atau tanda baca tunggal tidak lagi masuk antrean penerjemah maupun menggantikan overlay.
- Pesan `[Terjemahan ditahan: ...]` tetap dicatat di log tetapi tidak menimpa subtitle terakhir yang berguna.
- Partial rolling yang hanya berubah sedikit digabung agar preview Inggris dan Indonesia lebih stabil.
- Spam `EMPTY,NO_SPEECH` dibatasi tanpa memperketat penerimaan dialog bermakna.

### Preserved
- Nomor versi tetap v8.9.9.
- GPU preflight nyata dan CPU fallback R2 tetap aktif.
- Partial pertama tetap dapat muncul segera; hotfix bukan final-only mode.

# CHANGELOG — ORT Translation v8.9.9 R2

## GPU Runtime
- Menambahkan installer/repair GPU mandiri untuk environment `ORT_Runtime/audio_gpu/.venv`.
- Menambahkan paket CUDA 12.4, cuBLAS 12, cuDNN 9, CUDA runtime, dan NVRTC pada environment GPU.
- Menambahkan CUDA DLL bootstrap dari paket `nvidia/*/bin`, CUDA Toolkit, atau cuDNN lokal.
- Mengganti pemeriksaan GPU semu dengan load model dan dua inferensi nyata.
- Marker `validated_cuda_small.json` hanya ditulis `ready=true` setelah inferensi nyata berhasil.
- CUDA preflight live memakai sinyal non-zero dan mencatat `warmup_ms` serta `steady_ms`.

## Normal Realtime Stability
- Normal CPU memakai Faster-Whisper Base INT8; Normal GPU memakai Small INT8-Float16.
- Beam dan best-of Normal diturunkan ke 1 untuk mengurangi waktu inferensi berulang.
- Jendela partial Normal dibatasi: sekitar 3,2 detik pada CPU dan 4 detik pada GPU.
- Jendela final Normal dibatasi sekitar 6 detik.
- Quality retry ganda hanya aktif pada Accurate/Quality.
- Antrean final Normal dibatasi dua segmen; saat backlog terjadi, segmen lama dilepas dan event `realtime_final_backpressure_drop` dicatat.

## Safety
- GPU tidak dialihkan diam-diam atau ditandai siap ketika DLL/inferensi gagal.
- CPU Guard tetap tersedia dan tidak membutuhkan paket CUDA.
- Model, environment, dan DLL NVIDIA tidak dimasukkan ke ZIP patch.

---

# ORT v8.9.9 R1 - Live Preview & CPU Dual-Stream Performance Hotfix

- Restored English/source preview by default (`ORT_AUDIO_SHOW_SOURCE=1`).
- Added `FAST_PREVIEW_MODEL_LOADING/READY` and `JAPANESE_DUAL_STREAM_ACTIVE`.
- Normal/Instant Japanese Specialist on CPU now uses fast provisional ASR for the live path instead of synchronously waiting 7-15 seconds for Kotoba.
- Accurate profile retains direct Kotoba CPU inference.
- Background specialist correction is opt-in only to avoid competing with the live CPU path.
- Added deterministic preview/performance regression and R1 verifier.

# ORT Translation v8.9.9 — Safe Language Auto-Correct & Japanese Reliability

## Added

- Language Watchdog asynchronous dengan mode Off, Conservative, Balanced, dan Aggressive.
- Code-switch guard, confidence/dominance confirmation, cooldown, hysteresis, dan manual language lock.
- CUDA preflight sebelum streaming agar kegagalan cuBLAS/cudNN diketahui sebelum dialog pertama.
- Repetition/hallucination gate untuk token loop, n-gram loop, lexical diversity rendah, rasio output tidak wajar, dan bridge non-English.
- Installer permanen `INSTALL_JAPANESE_SPECIALIST.bat` dengan tokenizer repair dan CPU offline model-load validation.

## Changed

- Failover Japanese Specialist mempertahankan model: Kotoba CUDA → Kotoba CPU.
- Metadata model, source language, task, bridge, dan specialist status disinkronkan setelah failover atau language switch.
- Language detection berjalan pada thread terpisah agar tidak menghambat rolling-partial ASR.
- Glosarium GFL2 menjadi post-ASR soft correction, bukan hard initial prompt pada setiap partial.
- Subtitle Indonesia menjadi konten utama; source/bridge disembunyikan default.
- Pipeline contract naik menjadi `rolling-partial-v2`.

## Fixed

- Status `JAPANESE_SPECIALIST_ACTIVE` yang tetap tampil setelah model sebenarnya berubah ke Base CPU.
- Anime Jepang yang menghasilkan repetition loop seperti nama karakter atau kata Katakana berulang.
- English bridge yang masih berisi dominan tulisan Jepang diteruskan ke EN→ID.
- Pilihan English yang salah untuk video Jepang tidak lagi langsung dipaksa ke Auto; Watchdog mengoreksi setelah bukti aman.
- Installer Kotoba yang sebelumnya melaporkan sukses sebelum tokenizer dan model-load benar-benar tervalidasi.

## Deferred to v9.0.0

- Relokasi installer ke folder `Plugin/`.
- Relokasi seluruh log ke folder root `Log/`.
- Perapihan penuh struktur root dan sinkronisasi source lengkap GitHub.

---

# ORT Translation v8.9.8 — Multilingual Instant & Japanese Specialist

## Added

- Source-aware language routing untuk English, Japanese, Chinese, Korean, dan Smart Auto.
- English bridge metadata: `requested_language`, `detected_language`, `source_language`, `bridge_language`, dan `asr_task`.
- Pilihan **Japanese Specialist · Kotoba bila tersedia**.
- Hot-switch Smart Auto ke model Kotoba setelah Japanese terdeteksi, bila model tersedia dan GPU aktif.
- `SETUP_JAPANESE_SPECIALIST_V8_9_8.bat` untuk mengunduh model Kotoba bilingual ke model root bersama.
- `CHECK_AUDIO_GPU_V8_9_8.bat` untuk memeriksa CTranslate2, CUDA device, `cublas64_12.dll`, dan `cudnn64_9.dll`.
- `VERIFY_ORT_V8_9_8.bat` dan regression test multilingual.

## Changed

- English memakai `language=en, task=transcribe`.
- Japanese dan bahasa non-Inggris memakai bahasa sumber yang benar dengan `task=translate`, menghasilkan English bridge sebelum EN→ID.
- Profil GFL2 yang masih menyimpan English otomatis diamankan menjadi Smart Auto agar anime Jepang tidak dipaksa sebagai English.
- Completed partial translation ditampilkan secara monoton per segment. Revisi ASR yang lebih baru tidak lagi membatalkan semua hasil Indonesia yang sudah selesai.
- Overlay/status mencatat bahasa sumber, bridge, task ASR, dan status Japanese Specialist.

## Fixed

- Anime Jepang yang sebelumnya menghasilkan pseudo-English karena `language=en`.
- Indonesian subtitle yang tertunda lama akibat global generation gate `stale translation blocked`.
- Smart Auto yang tidak mempunyai jalur untuk mengaktifkan Japanese Specialist setelah Japanese terdeteksi.

## Important runtime note

- GPU pengguna pada log v8.9.7 gagal karena `cublas64_12.dll` tidak tersedia, sehingga ORT turun ke CPU `base`. Patch tidak membawa DLL NVIDIA atau model weights.
- Japanese Specialist diprioritaskan pada GPU. CPU rolling-partial tetap tersedia sebagai fallback, tetapi tidak menjanjikan latensi setara GPU.

## Validation scope

- Pengujian deterministik memvalidasi continuous partial, routing English/Japanese/Auto/Specialist, CUDA failure fallback, engine resolution, serta wiring metadata dan queue policy.
- Pengujian internal tidak menggantikan validasi WASAPI Windows, CUDA nyata, audio anime asli, atau bobot Kotoba pada laptop pengguna.

---

# ORT Translation v8.9.7 — Continuous Rolling-Partial Real-Time Update

## Added

- Sidecar `audio_realtime_local_sidecar.py` untuk WASAPI rolling-partial ASR lokal.
- Subtitle parsial lokal yang diterjemahkan dan mengganti baris yang sama sebelum endpoint/final.
- Latest-only interim mailbox agar transkripsi lama tidak menumpuk ketika model lebih lambat dari audio.
- Version contract root/ORTCore/TitanCore dan pipeline contract `rolling-partial-v1`.
- `VERIFY_ORT_V8_9_7.bat` serta pengujian integrasi ucapan kontinu tanpa pause.

## Changed

- Live Media Local dan Azure fallback tanpa cloud sekarang memilih `local_live`, bukan `local_guard`.
- VAD/jeda hanya menyelesaikan final; transkripsi dan terjemahan parsial dimulai selama ucapan.
- Hybrid CUDA failure tetap berada pada jalur Local Live dan memuat CPU fallback tanpa kembali ke segment-final ASR.
- WebUI menjelaskan perbedaan Local Live, Azure, dan Azure + Local Live Fallback.

## Fixed

- Instalasi campuran seperti WebUI v8.9.5 dengan Audio v8.9.6 sekarang diblokir sebelum sesi dimulai.
- Live Media lokal tidak lagi bergantung pada segmen 1–8 detik untuk memulai terjemahan.
- Cloud yang belum siap tidak lagi memaksa pengguna kembali ke pipeline lama.

## Validation scope

- Pengujian internal deterministik memvalidasi capture-frame simulation → rolling ASR partial → translation display revisions → final commit selama empat detik ucapan tanpa jeda.
- Pengujian ini tidak menggantikan validasi Windows WASAPI, model Faster-Whisper nyata, Azure, atau CUDA pada laptop pengguna.

---

# ORT Translation v8.9.5 — Real-Time Video Translation Update

## Added

- Kebijakan Live Media `speed`, `normal`, dan `accurate` untuk endpoint, maksimum panjang frasa, stabilitas partial, drain final, interval overlay, dan frame audio.
- Japanese Specialist phrase list untuk nama/istilah GFL2 dalam bentuk Jepang dan kanonik.
- Telemetry `cloud_connect_ms`, `first_interim_ms`, `first_final_ms`, serta ringkasan sesi.
- Regresi perilaku untuk state ordering, delayed final, rolling-tail safety, subtitle coalescing, repeated speaker line, dan credential deletion failure.

## Changed

- PCM cloud dikirim per 20 ms. Status `STREAMING` baru diterbitkan setelah Azure mengonfirmasi sesi.
- Profil Speed/Instant menggunakan endpoint Jepang sekitar 280 ms dan partial threshold 1; Balanced sekitar 350 ms; Accurate sekitar 480 ms.
- Interim mengganti satu baris subtitle secara bertahap dan callback terlalu rapat digabung agar overlay tidak berkedip.
- Deduplikasi final menggunakan `result_id`; kalimat yang sama dari result/speaker lain tidak dihapus.
- File/Stop menutup push stream lebih dahulu lalu menunggu final callback sebelum recognizer dihentikan.
- Rolling buffer memotong dari sisi lama dan mempertahankan tail terbaru untuk payload berukuran besar.

## Fixed

- `STREAMING` tidak lagi dapat muncul sebelum `CLOUD_CONNECTED`.
- Kalimat terakhir tidak lagi mudah hilang ketika final Azure datang sesaat setelah EOF.
- Stale interim setelah final diblokir.
- Penghapusan credential tidak lagi melaporkan sukses ketika backend gagal atau environment key masih aktif.

## Preserved

- OCR, Audio Local CPU/GPU/Hybrid, Azure→Local one-way fallback, isolated translation recovery, model/cache, dan data pengguna.
- Patch tidak membawa API key, runtime, model, cache, log, status, spool, atau preferensi pengguna.

---

# ORT Translation v8.9.4 — Cloud Live Media Streaming Update

## Added

- `Live Media` satu arah dan `Conversation` sebagai jenis penggunaan yang terpisah.
- Mesin `Local`, `Azure`, serta `Azure + Local Fallback`.
- Azure Speech Translation kontinu melalui `PushAudioInputStream` PCM 16 kHz.
- Hasil `interim` dan `final` dengan penggantian overlay atomik serta deduplikasi.
- Runtime `audio_cloud/.venv`, setup SDK terisolasi, pemeriksaan koneksi, dan perangkat WASAPI.
- Penyimpanan API key melalui Windows Credential Manager.
- Rolling replay enam detik dan one-way failover Azure→Local.
- Telemetri cloud connection, result state, cloud latency, requested/effective engine, dan failover reason.
- Regresi Azure tiruan yang memvalidasi aliran PCM, callback interim/final, dan non-eksposur credential.

## Changed

- Azure Live Media menjadi jalur real-time; VAD tidak lagi menentukan kapan hasil interim boleh tampil.
- Quality rejection lokal dan `NO_MATCH` cloud tidak lagi menulis notifikasi ke overlay.
- Panel Audio membedakan mesin cloud dari perangkat CPU/GPU/Hybrid lokal.
- File uji Azure dibatasi pada WAV PCM 16-bit; format lain tetap tersedia melalui mesin Local.

## Preserved

- Seluruh kontrak Audio Tri-Mode v8.9.3.
- Isolasi penerjemah R6, pemulihan Argos, model recovery R4/R5, OCR, data pengguna, dan cache.
- Patch tidak membawa API key, runtime, model, cache, log, status, spool, atau preferensi pengguna.

---

# ORT Translation v8.9.3 — Audio Tri-Mode & Japanese Quality Update

## Added

- Mode CPU, GPU, dan Hybrid dengan kontrak requested/effective yang dapat diaudit pada UI, status, state, dan log.
- Runtime `audio_gpu/.venv` terpisah; cache model tetap dibagikan melalui `audio_cpu/models` agar model R6 tidak diunduh ulang.
- Pekerja capture/VAD dan ASR terpisah, ledger segmen disk, replay identitas yang sama, Hybrid failover GPU→CPU, satu GPU retry, dan circuit breaker dua kegagalan.
- CUDA doctor untuk device count, dukungan `int8_float16`, DLL CUDA Windows, dan cadangan VRAM.
- Model `small` untuk GPU Speed/Normal dan `medium` untuk GPU Accurate; CPU memakai `base`/`small` tanpa memeriksa CUDA.
- Quality gate untuk no-speech, log probability, compression ratio, pengulangan, kepadatan token, probabilitas bahasa, dan frasa halusinasi.
- Retry ASR satu kali dengan beam lebih tinggi, adaptive energy pre-gate, Silero VAD, speech padding, dan pre-roll.
- Glosarium Audio khusus GFL2 dan penerjemahan per klausa dengan kebijakan preserve-all-clauses.
- Regresi khusus tri-mode, strict GPU, CPU no-CUDA-probe, replay ledger, quality gate, glosarium, serta wiring full-stack.

## Changed

- GFL2 otomatis memakai bahasa masukan `ja` jika pilihan sebelumnya masih `auto`.
- Model `tiny` tidak lagi dipilih otomatis untuk profil dialog Jepang.
- GPU hanya mengerjakan ASR; ORTCore Fast V2/Argos tetap pada proses CPU terisolasi R6.
- Hybrid dapat mulai sebagai `cpu_guard` jika CUDA/VRAM belum siap, sedangkan GPU mode berhenti jelas tanpa fallback diam-diam.

## Preserved

- Pemisahan proses penerjemah dan pemulihan native crash R6.
- Model-file contract R5, cache recovery R4, eksklusivitas OCR/Audio, graceful stop, dan seluruh pipeline OCR.
- Tidak ada model, cache, log, status, atau konfigurasi pengguna di dalam changed-files patch.

---

# ORT Translation v8.9.2-R6 — Audio Native Crash Isolation Hotfix

## Fixed

- Windows exit `3221225477 / 0xC0000005` setelah transkrip Audio pertama tidak lagi dapat menjatuhkan proses overlay utama.
- ORTCore Fast V2/CTranslate2 kini dibuat dan dijalankan di proses penerjemahan khusus, bukan di thread latar PyQt.
- Penerjemah dimuat sebelum ASR mulai menerima dialog sehingga masalah native muncul sebagai status pemulihan, bukan sesi Audio yang mendadak selesai.
- Packed GEMM dinonaktifkan hanya pada proses Audio Translation sebagai jalur stabilitas CPU Windows.
- Proses penerjemahan yang berhenti mengembalikan pekerjaan aktif ke slot latest-only dan memulai ulang satu kali menggunakan Argos tanpa CT2.
- Jika proses pemulihan juga berhenti, ASR dan overlay tetap hidup serta menampilkan sumber terakhir sebagai fallback.
- Telemetri mencatat tahap penerjemah, mode proses, kode keluar, deteksi access violation, dan jumlah restart.

## Preserved

- Model `tiny`, `base`, dan `small` R5 tetap dapat dimuat tanpa `preprocessor_config.json`.
- Pemulihan cache R4, WASAPI/file test, Normal/VAD, serta Speed/Normal/Accurate.
- Tampilan Guided/Expert, eksklusivitas OCR/Audio, dan seluruh stabilisasi OCR v8.9.2.
- Isolasi Suara tetap belum aktif.

---

# ORT Translation v8.9.2-R5 — Audio Model Compatibility Hotfix

## Fixed

- `preprocessor_config.json` tidak lagi diperlakukan sebagai berkas wajib untuk model resmi `tiny`, `base`, dan `small` yang memang tidak menyediakannya.
- Cache dengan empat komponen inti sekarang langsung masuk ke uji pemuatan model, tanpa tiga percobaan unduhan yang mustahil selesai.
- Validasi tetap menolak model yang kehilangan `config.json`, `model.bin`, `tokenizer.json`, atau `vocabulary.*`.
- Setup yang lolos tetap memuat `WhisperModel` dengan CPU INT8 dan `local_files_only=True` sebelum menyatakan Audio siap.

## Preserved

- Pemulihan cache, retry, dan penguncian setup dari R4.
- Tampilan Guided/Expert, WASAPI/file test, Normal/VAD, serta Speed/Normal/Accurate.
- Eksklusivitas OCR/Audio dan seluruh stabilisasi OCR v8.9.2.
- Isolasi Suara tetap belum aktif.

---

# ORT Translation v8.9.2-R4 — Audio Model Recovery Hotfix

## Fixed

- Snapshot `faster-whisper` yang hanya memiliki `model.bin` tidak lagi dianggap siap.
- Cache terputus sekarang dilanjutkan melalui setup lokal dengan retry; setelah kegagalan pertama transfer beralih ke satu pekerja tanpa menghapus unduhan sebelumnya.
- Runtime Audio memuat model dari folder lokal tervalidasi dan tidak menghubungi Hub ketika tombol Mulai Audio ditekan.
- Marker setup lama tidak dapat melewati validasi berkas model.
- UI membedakan dependensi Audio siap dari model ASR lengkap.
- Setup model kedua ditolak selama satu setup masih aktif agar cache tidak ditulis bersamaan.

## Preserved

- Tampilan Guided & Expert R2.
- WASAPI/file test, Normal/VAD, serta Speed/Normal/Accurate dari R3.
- Eksklusivitas OCR/Audio dan seluruh stabilisasi OCR v8.9.2.
- Isolasi Suara tetap belum aktif.

---

# ORT Translation v8.9.2-R3 — Audio CPU First-Test

## Added

- Runtime Audio terpisah dengan `faster-whisper` CPU INT8.
- Penangkapan audio internal Windows melalui WASAPI loopback.
- Jalur file audio/video untuk uji pertama tanpa menangkap suara sistem.
- Pemrosesan Normal/VAD dan profil Speed/Normal/Accurate.
- Overlay Audio mandiri, status runtime, telemetry, dan diagnostic setup.
- Regression test Audio CPU untuk segmentasi, deduplikasi, protokol sidecar, isolasi runtime, eksklusivitas sumber, dan generation guard.

## Stability & CPU efficiency

- OCR dan Audio tidak pernah diluncurkan bersamaan oleh Process Manager.
- Dependensi ASR dipasang ke `audio_cpu/.venv`, bukan runtime OCR utama.
- Antrean ASR dibatasi dua segmen dan membuang pekerjaan tertua ketika tertinggal.
- Antrean terjemahan dibatasi satu hasil terbaru; hasil generasi lama tidak dapat commit.
- Model ASR dibatasi pada tiny/base/small, CPU INT8, satu worker, dan 3/4/6 thread sesuai profil.
- Overlay lama dipertahankan sampai hasil baru siap.

## Preserved

- Tampilan Guided & Expert v8.9.2-R2.
- Seluruh stabilisasi OCR/overlay v8.9.2.
- Mode Buffer tetap OFF secara default.
- Isolasi Suara belum dapat dipilih pada uji pertama.

---

# ORT Translation v8.9.2-R2 — Guided & Expert UI Refresh

## Added

- Pemilih sumber terjemahan OCR/Audio di bagian utama.
- Preview Audio yang menjelaskan status backend serta rancangan Normal, VAD, Isolasi Suara, Speed, Normal, dan Accurate.
- Workspace Expert dengan kontrol lanjutan dan monitoring teknis yang tersusun dalam satu area.
- Status kesiapan sumber, hierarki tiga langkah, transisi panel, dan layout responsif.
- Regression test khusus kontrak UI dan eksklusivitas sumber.

## Changed

- Dashboard utama menjadi tab `Mulai` dengan alur yang lebih mudah dipahami.
- Basic/Terpandu menyembunyikan detail teknis; Expert menampilkan seluruh kontrol profesional.
- Label ambigu `Mode Pengaturan` diganti menjadi `Konfigurasi`; mode runtime menjadi `Strategi capture`.
- Live Log dan AI Recap dipindahkan ke accordion.
- Memilih preview Audio menghentikan OCR aktif, menyembunyikan workspace OCR, dan tidak menyediakan tombol start palsu.

## Preserved

- Seluruh stabilisasi OCR/overlay v8.9.2.
- Mode Buffer tetap OFF secara default.
- Audio runtime belum disertakan; implementasi ini hanya membuat keberadaan dan status roadmap Audio mudah ditemukan.

---

# ORT Translation v8.9.2 — OCR & Overlay Transactional Stability

## Added

- Text-aware ROI Change Gate untuk menahan OCR pada area teks yang tidak berubah.
- Turn/generation state bersama antara worker OCR dan worker terjemahan.
- Progressive-frame queue coalescing agar hanya kandidat terbaru yang menunggu diproses.
- Stale-result guard pada tahap sebelum terjemahan, setelah terjemahan, dan sebelum commit.
- Atomic overlay swap, explicit clear dengan debounce, dan single-final lock per turn.
- Canonical cross-process JSONL writer dengan lock dan append atomik.
- Telemetry baru untuk gate, turn, generation, stale drop, atomic swap, explicit clear, dan multi-final prevention.
- Sumber versi tunggal `build_info.py`.

## Changed

- Auto mengaktifkan Text ROI Change Gate; static probe default 15 detik dan perubahan teks tetap memicu OCR segera.
- `FINAL_OVERLAY` hanya dicatat setelah payload benar-benar lolos commit gate.
- Pergantian dialog tidak lagi dicatat sebagai clear dan tidak mengosongkan overlay.
- Placeholder/ID preview tetap nonaktif secara bawaan.
- Mode Buffer tetap OFF secara bawaan.

## Preserved

- Prediction Guard, UI/Dialog Filter, OCR repair, entity registry, CT2 routing, Helen/Helena separation, dan Sweeper/entity label behavior v8.9.1.
- Tidak ada Mode Audio pada rilis ini.

---

# ORT Translation v8.8.8 R2 — Entity Label & Mode Policy Activation Hotfix

## Fixed
- Fixed Prediction Guard false positive spam where ambiguous aliases like `Hell -> Heli` were logged/blocked even when the OCR text did not contain that alias.
- Exact entity prefixes now become speaker/entity labels: `Raizei`, `Darture`, `Poludnitsa`, `Anfiya Sharapova`, `Mangi Security Team Leader`, `Shadow Figure`, and `Shadowy Figure`.
- Added visible confidence badge support on speaker labels.
- Merged registry names/terms into runtime NPC/unique-term memory at boot.
- Activated Mode Policy telemetry for Auto/Interval/Freeze.
- Connected Interval Fast-Skip Safety into held-dialogue emergency path.
- Added `Poludnitsa` to registry.
- Preserved separate `Heli`, `Helen`, and `Helena`.

## Still Not Stable
This is a hotfix to make v8.8.8 roadmap behavior visible and active. Long-session testing is still required before stable.


# ORT Translation v8.8.8-r2 — Offline Replay Benchmark, Registry Expansion & Interval Safety

## Added
- Offline Replay Benchmark tool for text logs.
- Long Session Analyzer report generator.
- Mode Policy Manager foundation for Auto/Interval/Freeze separation.
- Interval Fast-Skip Safety foundation.
- Expanded GFL2 entity registry based on v8.8.7 recordings without logs.
- Heli, Helen, and Helena kept as separate entities.
- Anfiya Sharapova added as review/Yellow relation candidate for Colphne.
- Shadow Figure / Shadowy Figure added as masked speaker labels.
- Mangi Security Team Leader retained as exact story speaker/NPC display label.
- Tlazo retained as unique term/review Yellow, not NPC global.

## Preserved
- v8.8.6 low-OCR 40% improvements.
- v8.8.7 Name/Term Prediction Guard and Dialogue Safety.
- Mode Buffer remains optional/default OFF.

## Notes
- Offline Replay Benchmark extracts general failure patterns; it must not be used to memorize old story lines.


# ORT Translation v8.8.8-r2 — Name/Term Prediction Guard & Dialogue Safety

## Added
- Name/Term Prediction Guard with Green/Yellow/Red confidence labels.
- General Name/Term Ambiguity Guard for all names/terms, not only Helen/Helena.
- Commander Profile Resolver: Raizei is main Commander.
- Mangi Security Team Leader exact speaker/NPC display label.
- Tlazo retained as unique term/review Yellow, not NPC global.
- UI/Loading/Battle Text Filter v2 before translation/cache.
- Dialogue Timeout Safety / Emergency Commit.
- Stale Last-Good Limit v2.
- Prediction review configs and telemetry.

## Preserved
- v8.8.6 low-OCR gains for OCR 40% / Lite IDN / Fast V1.
- Mode Buffer remains default OFF unless user enables it.
- Temporal OCR Consensus remains final-lane only and must not block preview.


# CHANGELOG — ORT Translation v8.8.5

## v8.8.5 — Turn Finalizer & OCR Churn Rescue

### Added
- Turn Finalizer: each dialogue turn now tries to produce one final-complete render before the turn is considered finished.
- OCR Churn Rescue for low-OCR profiles (40–45%) using lightweight source repair, churn detection, and corrupted-frame hold.
- Bad Cache Shield: fuzzy/naturalized cache is downgraded from final when the OCR source is heavily corrupted.
- Source Longer Must Win: valid longer source can override `MIN_VISIBLE`, duplicate, and similar suppression.
- Hard repaint last-good overlay to avoid blank/stale boxes during held dialogue.
- Extra recording telemetry: `turn_finalizer_forced`, `bad_cache_shielded`, `ocr_churn_rescued`, `source_suppressed_ratio`, and `new_turn_ratio`.

### Changed
- Auto remains responsive, but valid complete source now has priority over anti-flicker suppression.
- New-turn commit is less aggressive; short/noisy turn-id churn keeps/repaints the last good overlay.
- Low-OCR profiles remain testable and supported as entry-level stress targets instead of being treated as unusable.
- OCR repair is conservative and deterministic; it does not increase global OCR percentage and does not call a heavy model.

### Not changed intentionally
- No new model dependency.
- No global OCR increase for Lite/Fast profiles.
- No Argos story fallback re-enabled when CT2 is available.
- No full rewrite of `TITANMAIN.py`; refactoring remains incremental.

### Next validation target
- Test Lite V1, Lite IDN V1, Lite IDN V2, Normal V1/IDN V2 in Auto and Interval.
- Check whether `final_complete_ratio` increases, `source_longer_but_suppressed` decreases, and blank overlay disappears.
- Use v8.8.8-r2 only after comparing long-session logs.

# CHANGELOG — ORT Translation v8.8.5

## v8.8.5 — GFL2 Recording Stability & Overlay Commit Gate
- Added CT2 Path Resolver so root `models/ct2_opus_mt_en_id` is found without manual junction.
- Added render-level Overlay Commit Gate to reduce flicker without delaying OCR/translation.
- Added normalized render signature to suppress visually-identical cache/preview updates.
- New turn clearing in Auto now keeps last good overlay until a meaningful new payload is ready.
- Speaker-only fragments are suppressed in Auto/Recording.
- Added lightweight recording telemetry for long GFL2 sessions.


## v8.8.2 — Runtime Behavior Refactor

- Added mode-specific runtime policy for Auto, Freeze, and Interval.
- Added Auto Smooth coalescing to reduce overlay flicker from low-OCR progressive text.
- Added Freeze OCR Override so Freeze can use high/100% OCR for screenshot-like accuracy.
- Added Interval Stable/Story-aware policy for manual story reading and VA-assisted story timing.
- Added Turn Transcript Accumulator / best-source-per-turn to avoid 20–90% partial dialog output.
- Added No-Downgrade Source Rule so shorter/noisier OCR frames do not replace a better full sentence.
- Added Speaker Prefix Sanitizer v3 for duplicated labels such as Phaetusa(?) in body text.
- Preserved v8.8.2 GitHub-safe layout and local runtime grouping.

# CHANGELOG — ORT Translation v8.8.2

## v8.8.2 — Project Structure Refactor & GitHub-Ready Layout

### Added
- Root launcher `START_HERE.bat` with simple menu.
- Root launcher `Start WebUI.bat`.
- Root launcher `Start OCR.bat`.
- Root launcher `Runtime.bat`.
- Clean `README.md`, `VERSION.txt`, `CHANGELOG.md`, and `.gitignore`.
- Outer folders under `ORT/` for docs, user_data, logs, cache, backups, and debug bundles.
- Migration map: `ORT/docs/migration/V8_7_9_TO_V8_8_1_STRUCTURE_MAP.md`.
- Structural validation report: `ORT/docs/test_reports/ORT_V8_8_1_STRUCTURE_VALIDATION_REPORT.md`.
- Current master continuity handoff in `ORT/docs/handoff/` and runtime docs.

### Changed
- Runtime is now placed under `ORT/runtime_app/` and launched through compatibility launchers.
- Display/version labels updated to v8.8.2 where relevant.
- Historical logs/cache/backups are not included in the clean v8.8.2 package.

### Not changed intentionally
- OCR behavior.
- Auto/Freeze/Interval runtime policy.
- Translation model behavior.
- v8.7.9 cache namespace `v8_7_9_responsive_turn_safe_ct2`.

### Next target
- v8.8.2: Auto Smooth, Freeze Ultra OCR, Interval Stable/Story-aware, Turn Transcript Accumulator, Overlay Anti-Flicker, and mode-specific runtime policy.


## v8.8.2 R2 — Local Runtime Grouping

- Menambahkan `ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD/` sebagai satu lokasi untuk file/folder lokal besar yang mudah dikecualikan saat ZIP/GitHub.
- Menambahkan `EXPORT_GITHUB_SOURCE.bat` dan `ORT/tools/packaging/export_github_source.py` untuk membuat ZIP source bersih.
- Memperbarui `.gitignore`, README, dan migration guide.
- Tidak mengubah perilaku OCR, translation, Auto/Freeze/Interval, atau scheduler.


# ORT Translation v8.8.8-r2 — Mandatory Final Commit, Temporal OCR Consensus, Mode Buffer

## Fokus
v8.8.8-r2 adalah stabilization patch di atas v8.8.5. Targetnya mengurangi masalah hasil terjemahan tidak full, overlay stale, cache terlalu percaya OCR rusak, dan low-OCR churn tanpa membuat Auto Story terasa lamban.

## Perubahan utama
- Mandatory Final Commit v2: setiap turn punya deadline final agar preview tidak menjadi output terakhir.
- Temporal OCR Consensus final-lane only: consensus dari beberapa OCR frame terakhir tidak memblokir preview.
- Mode Buffer: checkbox eksperimental default OFF di bawah `Pilih Model`, dengan tooltip dan tombol `?`.
- Low-OCR Visual Rescue planner: mendeteksi frame OCR 40–45% yang tampak muddy/noisy dan menandainya untuk final-lane rescue/cache guard.
- Bad Cache Shield v2: lebih ketat pada cache final jika corruption score tinggi.
- Stale Overlay Limit telemetry: repaint last-good tetap ada, tetapi dipantau agar tidak menyembunyikan final miss.

## Prinsip performa
Preview tetap cepat. Consensus, buffer, dan final completeness bekerja di final lane atau hanya saat Mode Buffer ON.
