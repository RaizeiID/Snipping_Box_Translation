ORT Translation v8.9.3 — PETUNJUK AUDIO TRI-MODE & JAPANESE QUALITY UPDATE
================================================================================

BASIS WAJIB
-----------
Pasang paket ini di atas ORT Translation v8.9.2-R6.

CARA MEMASANG
-------------
1. Tekan Stop, lalu tutup WebUI ORT.
2. Ekstrak ZIP v8.9.3 ke folder utama instalasi ORT v8.9.2-R6.
3. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
4. Jangan hapus ORT_Runtime\audio_cpu\models, audio_cpu\.venv, atau data pengguna.
5. Jalankan WebUI dan pastikan header menampilkan v8.9.3.

UJI PERTAMA YANG DISARANKAN — RTX 4050 6 GB + GFL2 DUB JEPANG
----------------------------------------------------------------
1. Pilih sumber Audio · CPU/GPU/Hybrid.
2. Pilih Hybrid, profil Normal, VAD, dan game GFL2_EXILIUM.
3. Bahasa akan menjadi Japanese (`ja`) ketika pilihan lama masih Auto.
4. Tekan Siapkan Audio Hybrid. Setup akan mempertahankan cache R6 dan menyiapkan
   runtime GPU terpisah. Model `small` mungkin perlu diunduh satu kali.
5. Pilih WASAPI loopback yang sebelumnya berhasil, lalu tekan Mulai Audio.

PERAN MODE
----------
- CPU: ASR CPU INT8; tidak memeriksa CUDA dan tidak memakai VRAM.
- GPU: ASR CUDA INT8-FP16; berhenti jelas jika CUDA/VRAM belum siap, tanpa fallback.
- Hybrid: ASR GPU utama + CPU fallback. Segmen aktif diputar ulang pada CPU jika
  pekerja GPU OOM/crash, lalu GPU dicoba sekali lagi. Kegagalan GPU kedua membuka
  circuit breaker dan mengunci sisa sesi pada CPU. Terjemahan ORTCore tetap CPU.

LOG NORMAL HYBRID
-----------------
requested_mode=hybrid | effective_mode=hybrid
asr=small:cuda:int8_float16
translator=ct2_fast:cpu:int8
[AUDIO v8.9.3] transcript | segment=...
[AUDIO v8.9.3] displayed | generation=...

LOG CPU GUARD / FAILOVER
------------------------
requested_mode=hybrid | effective_mode=cpu_guard
reason=GPU_RUNTIME_OR_MODEL_NOT_READY

atau, jika GPU gagal di tengah sesi:

HYBRID_FAILOVER | reason=CUDA_OUT_OF_MEMORY | replay_generation=seg-... | from=gpu | to=cpu
effective_mode=cpu_fallback

PERSYARATAN GPU
---------------
Runtime faster-whisper/CTranslate2 GPU memerlukan GPU NVIDIA kompatibel, driver
yang sesuai, library CUDA 12/cuBLAS, dan cuDNN 9. Tombol setup memeriksa dukungan
CUDA `int8_float16`; runtime OCR/YOLO yang bisa memakai GPU tidak otomatis berarti
runtime Audio GPU sudah lengkap.

ROLLBACK
--------
Timpa kembali file R6 dari paket R6. Model, cache, log, status, dan konfigurasi
pengguna tidak diubah atau dihapus oleh paket v8.9.3.

BATAS VALIDASI
--------------
Regresi otomatis memvalidasi kontrak tiga mode, strict GPU, CPU tanpa probe CUDA,
replay Hybrid, quality gate, isolasi penerjemah, dan pemasangan ZIP. Uji CUDA,
WASAPI, VRAM ketika GFL2 aktif, serta kualitas dialog nyata tetap harus dilakukan
di perangkat Windows/NVIDIA pengguna.
