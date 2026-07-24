ORT Translation v8.9.9 R2 — GPU Runtime & Normal Realtime Stability

Basis pemasangan:
- ORT v8.9.9
- Hotfix v8.9.9 R1 sudah diterapkan

Langkah:
1. Tutup WebUI, overlay, dan semua proses Python ORT.
2. Ekstrak ZIP R2 ke root ORT dan pilih Replace/Timpa semua.
3. Jalankan VERIFY_ORT_V8_9_9_R2.bat.
4. Jalankan INSTALL_AUDIO_GPU_V8_9_9_R2.bat.
5. Setelah installer lulus, jalankan CHECK_AUDIO_GPU_V8_9_9.bat.
6. Tutup dan buka kembali WebUI.
7. Uji Normal + Hybrid terlebih dahulu.

Hasil GPU sukses:
- passed=true
- validated_cuda_small.json ready=true
- effective_mode=hybrid atau gpu
- CUDA_PREFLIGHT_PASSED
- MODEL_READY device=cuda compute_type=int8_float16

Hasil CPU Normal:
- effective_mode=cpu atau cpu_guard
- model=base
- device=cpu
- compute_type=int8
- partial diperbarui tanpa quality retry ganda

Catatan:
- Paket CUDA/cuBLAS/cuDNN dapat mengunduh lebih dari 1 GB.
- Driver NVIDIA yang kompatibel tetap diperlukan.
- Patch tidak menyertakan model, environment, DLL, log, atau credential.
