# ORT v8.9.9 Safe Language Validation Report

Tanggal: 23 Juli 2026

## Temuan pengguna yang menjadi dasar

- Rolling partial sudah berjalan tanpa pause.
- Ketiga pengujian Jepang memuat Kotoba pada CUDA, tetapi inferensi pertama gagal karena `cublas64_12.dll`.
- Hybrid mengganti Kotoba dengan Faster-Whisper Base CPU, sehingga pengujian belum mengukur kualitas Kotoba.
- Base CPU menghasilkan token/nama berulang dan English bridge yang kadang tetap berisi Jepang.
- Smart Auto English bekerja jauh lebih baik.

## Perbaikan tervalidasi

- CUDA preflight terjadi sebelum streaming.
- Kegagalan Kotoba CUDA berpindah ke Kotoba CPU.
- Balanced Auto-Correct memerlukan empat observasi dominan dalam jendela sekitar delapan detik.
- Language lock mencegah global switch tetapi mempertahankan temporary code-switch.
- Repetition gate menolak token loop Jepang dan n-gram loop Inggris.
- Rolling partial pertama pada simulasi ucapan kontinu muncul pada audio 300 ms.
- Empat update partial terjadi sebelum final tanpa pause.

## Batas validasi

Pengujian deterministik tidak menggantikan Windows WASAPI, audio anime nyata, driver CUDA laptop pengguna, maupun pengukuran kualitas Kotoba pada dialog GFL2 sebenarnya.
