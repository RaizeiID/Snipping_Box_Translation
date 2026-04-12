# ORT v6.5 GPU Patch

Patch ini hanya berisi file yang berubah/baru untuk v6.5.

## Isi patch
- `webui.py`
- `launcher_backend.py`
- `gpu_runtime.py`

## Cara pakai
1. Buka folder proyek `ORT_Translation_v6_5` Anda.
2. Ekstrak isi patch ini ke folder tersebut.
3. Pilih **overwrite / replace** bila diminta.
4. Jalankan lagi `Start_ORT_Translation.bat`.

## Perubahan
- GPU Doctor sekarang mendeteksi `nvidia-smi`, nama GPU, dan driver NVIDIA.
- Ada tombol **Install / Repair GPU (Torch CUDA)** di tab **Runtime & Tools**.
- Jika runtime masih memakai `torch +cpu`, tombol ini akan mencoba mengganti ke build CUDA (`cu121`) di `.venv` runtime aktif.
- Setelah proses selesai, GPU Doctor bisa di-refresh langsung dari WebUI.

## Catatan
- Fitur repair GPU ini ditujukan untuk GPU NVIDIA.
- Pastikan driver NVIDIA sudah terpasang di Windows.
- Jika runtime custom lama dipakai, patch ini tetap bekerja pada `.venv` di folder runtime tersebut.
