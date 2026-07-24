ORT Translation v8.9.2-R5 — PETUNJUK AUDIO MODEL COMPATIBILITY HOTFIX
======================================================================

BASIS WAJIB
-----------
Terapkan paket ini di atas ORT Translation v8.9.2-R4 Audio Model Recovery Hotfix.
R5 tidak mengganti tampilan Guided/Expert, aturan OCR/Audio, atau konfigurasi pengguna.

CARA MEMASANG
-------------
1. Tekan Stop, lalu tutup WebUI ORT.
2. Buat salinan cadangan folder ORT Translation v8.9.2-R4.
3. Ekstrak isi ZIP patch ke root folder ORT Translation.
4. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
5. Jalankan START_HERE.bat dan buka WebUI.

MEMULIHKAN MODEL TINY YANG SUDAH ADA
------------------------------------
1. Pilih Sumber: Audio · Uji CPU.
2. Pilih Profil Speed agar ORT memeriksa cache model tiny yang sama.
3. Tekan Siapkan Audio CPU satu kali.
4. Jika config.json, model.bin, tokenizer.json, dan vocabulary.* sudah ada,
   ORT tidak mengunduh model kembali dan langsung menguji pemuatan CPU INT8.
5. Tunggu hingga panel menampilkan model_ready = True.
6. Uji dahulu dengan File audio uji 5–20 detik, kemudian coba WASAPI.

PERILAKU BARU
-------------
- preprocessor_config.json bersifat opsional untuk model tiny/base/small resmi.
- Empat komponen inti tetap wajib: config.json, model.bin, tokenizer.json,
  dan satu vocabulary.* yang valid.
- Model tidak dinyatakan siap hanya berdasarkan nama atau marker; setup tetap
  membangun WhisperModel lokal sebelum melaporkan sukses.
- Setelah siap, start Audio tetap menggunakan local_files_only=True.
- Cache, model, log, dan konfigurasi pengguna tidak dihapus atau ditimpa.

VERIFIKASI CEPAT
----------------
- Header menampilkan ORT Translation v8.9.2-R5.
- Profil Speed menampilkan model_ready = True untuk cache tiny lengkap.
- Status tidak lagi menyebut preprocessor_config.json sebagai model_problem.
- Log setup mencatat MODEL_DOWNLOAD_READY cached=true, lalu MODEL_LOADING dan
  MODEL_READY offline=true.

UJI OPSIONAL
------------
Dari folder ORT\runtime_app, jalankan:

  python tools\v8_9_2_regression_test.py
  python tools\v8_9_2_r2_ui_regression_test.py
  python tools\v8_9_2_r3_audio_regression_test.py
  python tools\v8_9_2_r4_audio_model_recovery_test.py
  python tools\v8_9_2_r5_audio_model_compatibility_test.py

Kelima kelompok pengujian harus menampilkan PASS.

ROLLBACK
--------
Pulihkan salinan cadangan R4. Patch tidak menghapus model, cache, runtime Python,
log, data identitas, atau konfigurasi pengguna.
