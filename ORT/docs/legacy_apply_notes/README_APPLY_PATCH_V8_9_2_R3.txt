ORT Translation v8.9.2-R3 — PETUNJUK PATCH AUDIO CPU FIRST-TEST
================================================================

BASIS WAJIB
-----------
Terapkan paket ini di atas ORT Translation v8.9.2-R2 yang sudah berfungsi.
Jangan terapkan langsung ke v8.9.1, v8.9.2 awal, atau versi lebih lama.

CARA MEMASANG
-------------
1. Tutup WebUI dan hentikan runtime OCR/Audio.
2. Buat salinan cadangan folder ORT Translation v8.9.2-R2.
3. Ekstrak isi ZIP patch ke root folder ORT Translation.
4. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
5. Jalankan START_HERE.bat, lalu buka WebUI.

SETUP AUDIO PERTAMA
-------------------
1. Pada Sumber terjemahan, pilih Audio · Uji CPU.
2. Pilih profil Normal dan tekan Siapkan Audio CPU.
3. Tunggu dependensi serta model base selesai diunduh. Internet diperlukan
   hanya untuk setup/model pertama atau saat memilih model profil lain.
4. Untuk uji paling sederhana, pilih File audio uji dan gunakan klip pendek
   5–20 detik yang berisi ucapan jelas.
5. Untuk suara game langsung, pilih Audio internal (WASAPI), pilih output
   yang sedang digunakan game, lalu tekan Mulai Audio.
6. Tekan Stop sebelum berpindah aplikasi atau mengganti konfigurasi besar.

PENGATURAN AWAL YANG DISARANKAN
-------------------------------
- Pemrosesan: VAD
- Profil: Normal (base / CPU INT8 / 4 thread)
- Bahasa suara: Deteksi otomatis
- Jika latensi masih tinggi: pilih Speed
- Jika nama/ucapan sulit dikenali: pilih Accurate

CATATAN PENTING
---------------
- OCR dan Audio tetap saling eksklusif.
- Isolasi Suara masih berstatus Belum aktif dan tidak dapat dipilih.
- WASAPI loopback langsung memerlukan Windows.
- File audio/video uji tidak memerlukan WASAPI.
- Audio memakai runtime terisolasi di runtime_root\audio_cpu agar dependensi
  OCR yang sudah ada tidak diubah.
- Model ASR tidak disertakan dalam ZIP patch dan diunduh saat setup pertama.

VERIFIKASI CEPAT
----------------
- Header menampilkan ORT Translation v8.9.2-R3.
- Sumber Audio menampilkan tombol Siapkan Audio CPU dan Mulai Audio.
- Memilih Audio menyembunyikan tombol Mulai OCR.
- Status Audio menunjukkan CPU INT8, profil, input, serta latensi terakhir.
- Uji file menampilkan teks yang didengar dan terjemahan pada overlay Audio.

UJI OPSIONAL
------------
Dari folder ORT\runtime_app, jalankan:

  python tools\v8_9_2_regression_test.py
  python tools\v8_9_2_r2_ui_regression_test.py
  python tools\v8_9_2_r3_audio_regression_test.py

Ketiganya harus menampilkan PASS.

ROLLBACK
--------
Pulihkan salinan cadangan v8.9.2-R2. Patch tidak menghapus model OCR, cache,
log, data identitas, atau konfigurasi pengguna. Folder runtime Audio yang
dibuat setelah setup berada di luar isi paket dan boleh dibiarkan.
