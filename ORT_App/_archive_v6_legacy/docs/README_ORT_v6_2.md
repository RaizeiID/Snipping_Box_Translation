# ORT Translation v6.2.1

Update ini membangun ulang launcher web di atas fondasi v5 dan menambahkan beberapa hal utama:

- rebranding UI dari TitanCore menjadi ORT / ORTCore
- pilihan penyimpanan runtime saat first start
- cleaner BAT yang menghapus project extract + runtime custom
- fondasi `ORTUnifiedUIBox.py` + `ort_ui_theme.json` sebagai sumber UI box bersama
- model registry baru dengan urutan V1 ringan, V2 seimbang, V3 berat-akurat, V4 hybrid, V5 naturalisasi berbasis level
- wrapper baru `ORTCore_V5_Lv1` sampai `ORTCore_V5_Lv4` beserta Lite

## Arti legacy Option A / B / C (V3 framed)

- Option A: badge **MS + PING** selalu tampil.
- Option B: badge **MS saja**.
- Option C: **MS selalu tampil**, **PING hanya muncul jika nilai valid sudah ada**.

## Cara pakai

1. Jalankan `Start_ORT_Translation_v6_2.bat`.
2. Saat pertama kali start, pilih lokasi runtime:
   - **1** = runtime disimpan di folder project
   - **2** = pilih folder custom lewat dialog Windows
3. Launcher akan membuat virtual environment di folder runtime yang dipilih lalu menginstal dependency dari `requirements_v6_2.txt`.
4. Buka model dari web UI.

## Catatan dependency

Error `ModuleNotFoundError: No module named 'cv2'` yang Anda alami sebelumnya disebabkan OpenCV belum terinstal. File `requirements_v6_2.txt` sekarang sudah menambahkan `opencv-python` agar bootstrap runtime dapat memasangnya ke folder storage yang dipilih.

## Tentang penyatuan UI box

File `ORTUnifiedUIBox.py` dan `ort_ui_theme.json` adalah pusat desain UI box. Fondasi ini sudah siap untuk dipanggil lintas model. Untuk benar-benar menjadikan semua renderer legacy 100 persen identik, masing-masing core lama perlu diarahkan ke adapter yang sama. Paket ini sudah menyiapkan fondasi, tema, dan helper agar patch integrasi itu bisa dilanjutkan tanpa mengubah ulang gaya UI di banyak file.
