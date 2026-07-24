ORT Translation v8.9.2-R6 — PETUNJUK AUDIO NATIVE CRASH ISOLATION HOTFIX
============================================================================

BASIS WAJIB
-----------
Pasang paket ini di atas ORT Translation v8.9.2-R5.

CARA MEMASANG
-------------
1. Tekan Stop dan tutup WebUI ORT.
2. Ekstrak ZIP R6 ke folder utama instalasi ORT v8.9.2-R5.
3. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
4. Jangan menghapus folder ORT_Runtime\audio_cpu\models.
5. Jalankan WebUI dan pastikan header menampilkan v8.9.2-R6.

UJI PERTAMA YANG DISARANKAN
---------------------------
1. Pilih Audio · Uji CPU.
2. Pilih VAD + Normal.
3. Pastikan Siapkan Audio CPU tetap menunjukkan model_ready = True.
4. Pilih WASAPI loopback Headphones (DAXA SL1) yang sebelumnya berhasil.
5. Tekan Mulai Audio dan putar dialog pendek.

URUTAN LOG NORMAL
-----------------
[AUDIO v8.9.2-R6] translation_state=TRANSLATOR_LOADING | mode=isolated_ct2
[AUDIO v8.9.2-R6] translation_state=TRANSLATOR_READY | mode=isolated_ct2
[AUDIO v8.9.2-R6] state=MODEL_READY
[AUDIO v8.9.2-R6] state=LISTENING
[AUDIO v8.9.2-R6] transcript | generation=1
[AUDIO v8.9.2-R6] displayed | generation=1

PEMULIHAN OTOMATIS
------------------
Jika proses ORTCore Fast V2 masih mengalami access violation, proses utama tidak
boleh ikut berhenti. Log akan menampilkan:

translation process exit 0xC0000005 (native access violation)
restarting with isolated Argos recovery
translation_state=TRANSLATOR_READY | mode=safe_argos

Transkrip aktif akan dikirim ulang satu kali. ASR, overlay, dan WebUI tetap hidup.
Mode aman dapat lebih lambat daripada CT2, tetapi mencegah sesi Audio terputus.

ROLLBACK
--------
Timpa kembali file R5 dari paket R5. Data model, cache, log, status, dan konfigurasi
pengguna tidak diubah oleh paket R6.

BATAS RILIS
-----------
- Isolasi Suara masih Belum aktif.
- Pengujian Windows nyata tetap diperlukan untuk memastikan modul native yang
  sebelumnya jatuh sudah terisolasi pada perangkat pengguna.
- Paket ini tidak mengubah perilaku OCR, pilihan model, profil Audio, atau tata
  letak Guided/Expert.
