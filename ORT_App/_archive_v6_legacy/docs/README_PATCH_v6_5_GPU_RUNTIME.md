# ORT v6.5 GPU + Runtime Patch

Patch ini berisi perubahan berikut:
- Tombol **Install / Repair GPU (Torch CUDA)** kini membaca runtime aktif dari `runtime_paths.json` dan runtime custom `RUNTIME`.
- GPU Doctor kini menampilkan `runtime_python`, status `nvidia-smi`, nama GPU, dan versi driver.
- Installer GPU mencoba memasang build CUDA resmi PyTorch `torch==2.5.1 torchvision==0.20.1 torchaudio==2.5.1 --index-url https://download.pytorch.org/whl/cu121`.
- `Start_ORT_Translation.bat` kini menambah **opsi 3** untuk memakai runtime terakhir yang sudah tersedia.

## Cara pakai
1. Ekstrak patch ini ke folder `ORT_Translation_v6_5` Anda.
2. Pilih **overwrite** semua file.
3. Jalankan lagi `Start_ORT_Translation.bat`.
4. Bila runtime lama valid, Anda bisa pilih opsi **3**.
5. Di tab **Runtime & Tools**, gunakan tombol **Install / Repair GPU (Torch CUDA)** lalu refresh GPU Doctor.

## Catatan
- Installer GPU ini ditujukan untuk GPU NVIDIA dan membutuhkan `nvidia-smi`/driver yang terpasang.
- Jika driver belum cocok, instalasi torch CUDA bisa selesai tetapi `cuda_available` masih `False`.
