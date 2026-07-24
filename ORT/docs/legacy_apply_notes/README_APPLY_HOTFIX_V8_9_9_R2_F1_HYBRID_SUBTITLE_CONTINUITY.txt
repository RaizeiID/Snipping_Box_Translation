ORT Translation v8.9.9 R2 F1 — Hybrid Startup & Subtitle Continuity Fix

Basis wajib:
- ORT v8.9.9 R2 sudah diterapkan
- INSTALL_AUDIO_GPU_V8_9_9_R2.bat sebelumnya sudah lulus

Pemasangan:
1. Tutup WebUI, overlay, dan semua proses Python ORT.
2. Ekstrak ZIP ke root ORT dan pilih Replace/Timpa semua.
3. Jalankan VERIFY_ORT_V8_9_9_R2_F1.bat.
4. Buka kembali WebUI. Tidak perlu menginstal ulang paket CUDA apabila installer R2 sudah passed=true.
5. Uji Normal + Hybrid + Japanese terlebih dahulu, lalu Accurate bila diperlukan.

Log sukses Hybrid Japanese:
- requested_mode=hybrid
- effective_mode=hybrid
- CUDA_PREFLIGHT_PASSED
- MODEL_READY device=cuda

Perilaku subtitle:
- partial pertama tetap cepat
- revisi kecil digabung agar tidak berkedip
- tanda baca tunggal tidak ditampilkan
- subtitle terakhir tetap terlihat saat guard menahan output yang tidak terpercaya
