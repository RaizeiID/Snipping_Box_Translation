# ORT v9.0.5 — Engineering Baseline & Resilient Provider Setup

Tanggal rilis: 25 Juli 2026

## Perbaikan utama

- Memperbaiki project-root quoting pada file BAT untuk path Windows yang mengandung spasi dan trailing backslash.
- Memisahkan pemasangan update aplikasi dari setup/download provider. Kegagalan internet tidak lagi membatalkan pembaruan ORT.
- Mengganti jalur ReazonSpeech K2 dari Hugging Face snapshot `dry_run` menjadi manifest file langsung pada revision terkunci.
- Menambahkan resume `.part` berbasis HTTP Range, cache reuse, retry bertahap, timeout panjang, validasi ukuran, dan SHA-256 untuk model utama.
- Membaca seluruh exception chain agar `DryRunError → ConnectError → WinError 10054` dikenali sebagai gangguan jaringan sementara.
- Menyimpan laporan error provider ke `ORT_Runtime/provider_setup_status/last_error_<provider>_<device>.log` tanpa memenuhi UI dengan traceback.
- Memuat ReazonSpeech langsung dari file ONNX lokal melalui `sherpa_onnx.OfflineRecognizer.from_transducer`.
- Memperbaiki decode Reazon lokal agar menggunakan `create_stream`, `accept_waveform`, dan `decode_stream`.
- Menyamakan identitas versi pada launcher, BuildInfo, Open Architecture payload, README, dan project layout.
- Menambahkan verifier dan regression test v9.0.5 berbasis perilaku.

## Kompatibilitas

- Entry point `setup_v9_0_4_audio_providers.py` tetap dipertahankan agar shortcut dan recovery lama tetap bekerja.
- Entry point produksi baru adalah `setup_v9_0_5_audio_providers.py`.
- Runtime, model, cache, konfigurasi pengguna, dan log tidak dihapus oleh updater.

## Catatan pengujian

Pengujian otomatis mencakup:

- kompilasi source yang berubah;
- nested network exception detection;
- HTTP Range resume dari file `.part`;
- direct Reazon manifest tanpa snapshot dry-run;
- local CPU/CUDA model-path validation;
- WebUI callback audit;
- provider setup progress regression;
- audio realtime sidecar self-test;
- checksum payload setelah instalasi.
