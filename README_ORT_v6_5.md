# ORT Translation v6.5

Perubahan utama:
- satu file start utama: `Start_ORT_Translation.bat`
- satu file cleaner utama: `Clean_ORT_Translation.bat`
- opsi runtime custom mendeteksi folder runtime lama dan memakai ulang `.venv` bila requirements masih sama
- popup loading saat Start di WebUI
- catatan user di halaman Runtime & Tools
- GPU Doctor untuk menjelaskan apakah CUDA benar-benar terdeteksi
- indikator engine di preview box memakai garis siku: CPU biru, GPU hijau, AUTO/HYBRID merah

## Catatan GPU
Jika saat menekan F9 Anda hanya melihat CPU dan AUTO, biasanya berarti `torch.cuda.is_available()` bernilai false.
Itu tidak selalu berarti proyek ini tidak mendukung GPU. Umumnya penyebabnya salah satu dari:
- driver NVIDIA / CUDA runtime tidak cocok
- build torch yang aktif tidak sesuai
- environment runtime custom masih memakai dependency lama

Buka tab **Runtime & Tools** untuk melihat ringkasan GPU Doctor.
