# ORT v9.0.5 Validation Report

Release: **Engineering Baseline & Resilient Provider Setup**  
Tanggal validasi: **25 Juli 2026**

## Hasil

- Update bersih dari paket ORT v9.0.4: **PASS**
- Repair ulang pada instalasi v9.0.5: **PASS**
- Project-root parser dengan trailing slash dan orphan quote: **PASS**
- Kompilasi 12 file Python yang diperbarui: **PASS**
- Payload SHA-256 (30 file): **PASS**
- Nested `DryRunError → WinError 10054` detection: **PASS**
- HTTP Range resume dari file `.part`: **PASS**
- Reazon direct static manifest tanpa snapshot dry-run: **PASS**
- Reazon local CPU/CUDA file validation: **PASS**
- Reazon local sherpa-onnx decode path: **PASS**
- WebUI callback audit: **PASS**
- Provider setup progress regression: **PASS**
- Audio realtime sidecar self-test: **PASS**
- Verifier v9.0.5 dan release checksum: **PASS**

## Batas pengujian internal

Lingkungan internal bukan Windows dengan WASAPI/CUDA aktif. Karena itu, pengunduhan model nyata dan inferensi Reazon pada GPU RTX tidak dijalankan. Jalur downloader, resume, status, adapter, dan kontrak runtime telah diuji secara deterministik; pengujian perangkat nyata dilakukan setelah patch diterapkan pada komputer ORT.
