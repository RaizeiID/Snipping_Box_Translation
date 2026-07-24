# ORT v8.9.8 Multilingual Instant Validation Report

## Temuan dari log lapangan

- Sesi anime berjalan dengan `language=en` sehingga Japanese dipaksa menjadi pseudo-English.
- CUDA gagal memuat `cublas64_12.dll`, lalu sistem turun ke CPU model `base`.
- Banyak hasil Indonesia tertahan oleh global newest-generation gate meskipun partial translation sebelumnya sudah selesai.

## Perbaikan

- Source-aware routing dan Smart Auto language lock.
- Whisper translation bridge untuk bahasa non-Inggris.
- Optional Kotoba bilingual Japanese Specialist.
- Per-segment monotonic translation display.
- GPU doctor dan model setup utility.

## Pengujian deterministik

- Continuous speech menghasilkan beberapa partial sebelum final tanpa pause.
- English: `language=en`, `task=transcribe`.
- Japanese: `language=ja`, `task=translate`, `bridge=en`.
- Smart Auto: `language=None`, `task=translate`, lalu lock Japanese.
- Kotoba bilingual: `language=en`, `task=translate` untuk Japanese speech→English text.
- Simulasi CUDA DLL failure tetap beralih ke CPU rolling-partial.

## Batas validasi

Lingkungan build tidak memiliki Windows WASAPI, NVIDIA driver pengguna, model Kotoba yang diunduh, atau audio anime asli. Karena itu, hasil akurasi dan latensi perangkat nyata harus divalidasi pada laptop pengguna.
