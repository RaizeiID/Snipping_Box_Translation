# ORT v8.9.6 Validation Report

Validated behaviors:

- Azure runtime yang hanya `ready` tetapi gagal network test tidak dipilih sebagai cloud.
- Azure yang lulus network test dipilih sebagai `effective=azure`.
- Launcher memiliki strict Live Media guard dan pesan `REALTIME BLOCKED`.
- v8.9.5 streaming regressions tetap lulus pada build v8.9.6.
- Semua file Python perubahan berhasil dikompilasi.

Validasi layanan nyata tetap membutuhkan Windows, WASAPI, credential Azure aktif,
dan audio media pengguna.
