# ORT Translation v8.9.2-R6

**Release:** Audio Native Crash Isolation Hotfix  
**Basis:** v8.9.2-R5  
**Tanggal:** 23 Juli 2026

## Bukti live yang ditangani

Mode Audio berhasil mencapai `MODEL_READY`, `LISTENING`, dan menghasilkan transkrip. Tepat setelah transkrip pertama, proses utama selesai dengan kode Windows `3221225477`, yaitu `0xC0000005` atau native access violation. Tidak ada event `displayed` maupun pesan `Audio sidecar berhenti`, sehingga kegagalan terjadi pada proses induk saat penerjemah native pertama kali dibuat, bukan pada model Whisper atau WASAPI.

## Perubahan

- ORTCore Fast V2/CTranslate2 dipindahkan dari thread penerjemahan dalam proses PyQt ke `audio_translation_sidecar.py`.
- Proses penerjemahan dimulai sebelum sidecar ASR agar inisialisasi native tidak menunggu transkrip pertama.
- Jalur primary memakai CT2 CPU INT8 dengan packed GEMM dinonaktifkan dan anggaran 1–2 thread.
- Satu transkrip aktif dan satu kandidat terbaru dipertahankan; kandidat pending lama dibuang.
- Generation guard tetap memblokir hasil yang selesai setelah dialog yang lebih baru diterima.
- Exit proses primary memindahkan kembali pekerjaan aktif ke slot pending dan memulai satu proses pemulihan.
- Proses pemulihan menetapkan `ORT_DISABLE_CT2=1` dan menggunakan Argos dalam proses terisolasi.
- Jika proses pemulihan juga jatuh, proses Audio utama tetap hidup dan menampilkan sumber sebagai fallback.
- Status dan telemetry baru mencatat `translation_process_state`, mode, exit code, access violation, dan restart count.
- `faulthandler` diaktifkan pada sidecar penerjemahan untuk membantu diagnosis kegagalan native berikutnya.

## Tidak diubah

- UI Guided/Expert.
- Eksklusivitas OCR dan Audio.
- Normal/VAD serta Speed/Normal/Accurate.
- Model ASR `tiny/base/small`, CPU INT8, dan cache lokal R5.
- Seluruh pipeline OCR dan overlay v8.9.2.
- Isolasi Suara tetap belum aktif.
