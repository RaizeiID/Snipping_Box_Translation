# ORT v8.9.9 R2 GPU/CPU Realtime Validation Report

Tanggal: 2026-07-23

## Automated validation
- Python compilation: PASS
- Normal profile contract: PASS
- CUDA DLL directory discovery: PASS
- CPU Normal partial window cap: PASS
- CPU Normal final window cap: PASS
- Normal no-double-retry policy: PASS
- Final backpressure latest-two policy: PASS
- GPU installer/checker wiring: PASS
- NVIDIA dependency contract: PASS

## Environment limitation
Pengujian otomatis di lingkungan pembuatan paket tidak memiliki GPU NVIDIA Windows pengguna. Karena itu keberhasilan GPU aktual tidak diklaim di sini. Installer pada komputer pengguna melakukan dua inferensi nyata dan hanya menulis marker `ready=true` setelah keduanya berhasil.
