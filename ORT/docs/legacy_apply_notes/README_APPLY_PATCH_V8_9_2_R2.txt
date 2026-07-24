ORT Translation v8.9.2-R2 — PETUNJUK PEMASANGAN PATCH UI
=========================================================

BASIS WAJIB
-----------
Pasang patch ini di atas folder ORT Translation v8.9.2 yang sudah berfungsi.
Jangan terapkan langsung ke v8.9.1 atau versi yang lebih lama.

CARA MEMASANG
-------------
1. Tutup WebUI dan hentikan runtime OCR.
2. Buat salinan cadangan folder ORT Translation v8.9.2.
3. Ekstrak isi ZIP patch ke root folder ORT Translation.
4. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
5. Jalankan START_HERE.bat, lalu buka WebUI.

VERIFIKASI CEPAT
----------------
- Header WebUI menampilkan ORT Translation v8.9.2-R2.
- Tab pertama bernama Mulai.
- Bagian Sumber terjemahan menampilkan OCR · Siap dan Audio · Preview.
- Basic/Terpandu menampilkan alur ringkas.
- Expert membuka model, capture, engine, interval, resolusi, policy, runtime,
  hardware, dan diagnostic.
- Saat Audio dipilih, tombol Mulai OCR menghilang dan muncul status bahwa
  backend Audio belum tersedia.

BATAS MODE AUDIO
----------------
Audio pada v8.9.2-R2 adalah preview UI, bukan runtime ASR. Patch ini tidak
menyertakan WASAPI loopback, VAD, Whisper/faster-whisper, atau Isolasi Suara.
Memilih Audio akan menghentikan OCR aktif agar kedua sumber tetap eksklusif.

UJI OPSIONAL
------------
Dari folder ORT\runtime_app, jalankan:

  python tools\v8_9_2_regression_test.py
  python tools\v8_9_2_r2_ui_regression_test.py

Keduanya harus menampilkan PASS.

ROLLBACK
--------
Pulihkan file dari salinan cadangan v8.9.2. Patch tidak menghapus model,
cache, log, data identitas, atau konfigurasi pengguna.
