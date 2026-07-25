# ORT v9.0.5 R1 Validation Report

## Masalah yang diperbaiki

Log pengguna menunjukkan WebUI masih menjalankan source v9.0.4 dan warmup lama memanggil `reazonspeech.k2.asr.load_model()`. Runtime probe lama hanya menguji import, sehingga package `sherpa_onnx` yang tidak mengekspor `OfflineRecognizer` tetap dianggap siap.

## Perubahan

- Paket ZIP dibuat tanpa folder pembungkus yang membingungkan.
- Updater mendeteksi project root saat patch diekstrak langsung maupun berada satu tingkat di bawah root.
- Runtime probe memeriksa `OfflineRecognizer.from_transducer`.
- Fallback ke `sherpa_onnx.offline_recognizer.OfflineRecognizer`.
- Top-level compatibility alias untuk ReazonSpeech.
- Warmup lokal dan adapter produksi memakai helper yang sama.
- Reinstall CPU dikunci ke `sherpa-onnx==1.13.4` bila API benar-benar rusak.
- Model cache dan file ONNX yang sudah selesai tidak dihapus.
- `__pycache__` source setup/adapter dibersihkan saat pemasangan.

## Pengujian internal

- Kompilasi seluruh Python payload: PASS.
- Submodule compatibility alias: PASS.
- Top-level API path: PASS.
- Direct manifest dan resumable download regression: PASS.
- Nested WinError 10054 retry regression: PASS.
- Project-root detection direct/parent: PASS.
- Install simulation dari v9.0.4: PASS.
- Verifier v9.0.5 R1: PASS.

Pengujian native Windows terhadap wheel CPU/CUDA dan inferensi ONNX tetap perlu dilakukan pada komputer pengguna.
