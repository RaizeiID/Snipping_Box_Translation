ORT Translation v8.9.2-R4 — PETUNJUK AUDIO MODEL RECOVERY HOTFIX
=================================================================

BASIS WAJIB
-----------
Terapkan paket ini di atas ORT Translation v8.9.2-R3 Audio CPU First-Test.
R4 tidak mengganti tampilan Guided/Expert atau aturan OCR/Audio.

CARA MEMASANG
-------------
1. Tekan Stop, lalu tutup WebUI ORT.
2. Buat salinan cadangan folder ORT Translation v8.9.2-R3.
3. Ekstrak isi ZIP patch ke root folder ORT Translation.
4. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
5. Jalankan START_HERE.bat dan buka WebUI.

MEMULIHKAN CACHE MODEL R3 YANG TERPUTUS
---------------------------------------
1. Pilih Sumber: Audio · Uji CPU.
2. Tetap gunakan Profil Normal untuk melanjutkan model base yang sudah dimulai.
3. Pastikan internet aktif, lalu tekan Siapkan Audio CPU.
4. ORT akan mencoba maksimal tiga kali dan beralih ke transfer satu-per-satu
   setelah kegagalan pertama. Berkas/cache yang sudah ada dipakai
   kembali; model.bin yang telah selesai tidak sengaja dianggap sebagai model
   lengkap dan tidak perlu dihapus manual.
5. Tunggu hingga panel menampilkan model_ready = True.
6. Uji dahulu dengan File audio uji 5–20 detik, kemudian coba WASAPI.

PERILAKU BARU
-------------
- Model wajib memiliki config.json, model.bin, preprocessor_config.json,
  tokenizer.json, dan vocabulary.* yang valid.
- Tombol Mulai Audio ditolak dengan alasan jelas jika salah satu berkas belum
  lengkap.
- Setelah model siap, runtime memuat folder lokal secara offline dan tidak
  mencoba menghubungi Hugging Face lagi pada setiap start.
- Menekan Siapkan Audio CPU ulang tidak memasang kembali dependensi yang sudah
  sehat.
- Kegagalan jaringan tidak menghapus cache atau konfigurasi pengguna.

JIKA WINERROR 10054 MASIH MUNCUL
--------------------------------
1. Jangan hapus folder audio_cpu atau model.bin.
2. Tunggu beberapa menit lalu tekan Siapkan Audio CPU sekali lagi.
3. Pastikan firewall, antivirus, DNS filter, VPN/proxy, atau jaringan kampus
   tidak memutus akses HTTPS ke huggingface.co dan layanan file modelnya.
4. Coba jaringan lain/hotspot hanya untuk menyelesaikan setup model pertama.
5. Setelah model_ready = True, koneksi tidak dibutuhkan lagi untuk memuat model.

VERIFIKASI CEPAT
----------------
- Header menampilkan ORT Translation v8.9.2-R4.
- Cache parsial ditampilkan sebagai Unduhan model belum lengkap.
- Status menyebutkan nama berkas yang masih hilang/tidak valid.
- Setup yang berhasil menampilkan model_ready = True.
- Start Audio berikutnya mencatat MODEL_READY dengan offline=true.

UJI OPSIONAL
------------
Dari folder ORT\runtime_app, jalankan:

  python tools\v8_9_2_regression_test.py
  python tools\v8_9_2_r2_ui_regression_test.py
  python tools\v8_9_2_r3_audio_regression_test.py
  python tools\v8_9_2_r4_audio_model_recovery_test.py

Keempatnya harus menampilkan PASS.

ROLLBACK
--------
Pulihkan salinan cadangan R3. Patch tidak menghapus model, cache, runtime Python,
log, data identitas, atau konfigurasi pengguna.
