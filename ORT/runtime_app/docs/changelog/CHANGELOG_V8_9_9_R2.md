# ORT v8.9.9 R2 — GPU Runtime & Normal Realtime Stability

## Root cause
Mode Hybrid sebelumnya berhenti pada `cpu_guard` karena CTranslate2 tidak dapat menemukan `cublas64_12.dll`. Pemeriksaan lama juga belum cukup untuk membuktikan inferensi GPU benar-benar dapat berjalan. Di CPU, jendela audio dan retry dapat membuat kerja menumpuk saat dialog panjang.

## Implementation
- CUDA DLL bootstrap sebelum import Faster-Whisper/CTranslate2.
- Installer NVIDIA runtime lokal pada Audio GPU venv.
- Real two-pass GPU inference validation.
- Validation marker compatible dengan `audio_runtime_backend.py`.
- Normal CPU Base INT8 dan Normal GPU Small INT8-Float16.
- Bounded inference windows, bounded final queue, no Normal double retry.

## Non-goals
- Tidak mengubah model Japanese Specialist.
- Tidak mengunduh model ke GitHub.
- Tidak mengklaim GPU aktif ketika driver atau DLL belum kompatibel.
