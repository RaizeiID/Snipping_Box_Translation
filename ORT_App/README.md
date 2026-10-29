# Source Aplikasi ORT Translation

ORT_App memuat source aplikasi OCR/Audio, launcher internal, konfigurasi bawaan, alat pemeriksaan, dan aset popup Tutorial.

Untuk mengunduh dan memasang dari GitHub, mulai dari [Tutorial Pemasangan pada README utama](../README.md#tutorial-pemasangan).

## Launcher untuk pengguna

Jalankan dari folder utama proyek:

- `Instalation First.bat`: pemasangan awal runtime/dependensi.
- `Start WebUI.bat`: membuka WebUI pada pemakaian berikutnya.
- `Repair Struktur ORT.bat`: migrasi/perbaikan struktur dan verifikasi.

Jangan memindahkan ORT_App dari launcher utama. Runtime Python berada di ORT_Runtime atau lokasi kustom yang dipilih saat setup.

## Panduan penggunaan

[Panduan Basic](../README.md#tutorial-penggunaan-basic) menjelaskan pemilihan sumber, bahasa tulisan, area dialog, dan pemakaian overlay. [Panduan Live Log](../README.md#melihat-dan-menyalin-log-dialog) menjelaskan pencatatan dialog dan penyalinannya. Tutorial popup di WebUI mengikuti tingkat tampilan yang aktif.

## Bagian source

- `webui.py`: antarmuka web dan callback pengguna.
- `launcher_backend.py`: pengaturan sesi dan peluncuran runtime.
- `TITANMAIN.py`: tangkapan layar, OCR, dan overlay.
- `app/ocr/`: adapter provider, pembacaan/layout, dan kontrak konfigurasi OCR.
- `app/runtime/`: pengaturan resource, guard, dan pengendalian sesi.
- `app/ui/tutorial.py` dan `assets/tutorial/`: popup panduan dan screenshot lokal.
- `translation_engine.py`: jalur terjemahan bersama.
- `tools/`: verifier, exporter, dan pengujian.

File runtime/preferensi dan hasil belajar pengguna dibuat lokal. Model besar dan environment Python tidak disertakan dalam repository source.
