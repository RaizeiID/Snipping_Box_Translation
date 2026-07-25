# ORT Translation v9.0.5

**Optic Recognition & Real-Time Translation**

ORT Translation adalah aplikasi penerjemah layar dan audio berbasis Windows yang dirancang untuk membantu menerjemahkan teks game, visual novel, video, film, dan media lain secara langsung ke Bahasa Indonesia.

ORT menyediakan dua jalur utama:

- **Mode OCR** untuk membaca teks dari area layar yang dipilih.
- **Mode Audio** untuk mendengarkan suara sistem, mengenali ucapan, lalu menerjemahkannya.
- **Open Architecture Lab** untuk menguji provider atau strategi baru tanpa mengganti pipeline produksi utama.

> **Status rilis:** ORT v9.0.5 — Engineering Baseline & Resilient Provider Setup  
> **Basis pembaruan:** ORT v9.0.4  
> **Platform utama:** Windows 10/11 64-bit

### Yang baru pada v9.0.5

- project root pada file BAT dinormalisasi tanpa trailing backslash/quote;
- setup model dipisahkan dari proses update aplikasi, sehingga gangguan jaringan tidak membatalkan update;
- ReazonSpeech K2 memakai manifest revision terkunci tanpa Hugging Face `dry_run`;
- unduhan file model mendukung `.part`, HTTP Range, retry berjenjang, cache-first, dan verifikasi ukuran/checksum;
- rantai exception diperiksa sampai root cause, termasuk `DryRunError → ConnectError → WinError 10054`;
- ReazonSpeech dimuat langsung dari model lokal dengan sherpa-onnx untuk CPU dan CUDA;
- verifier v9.0.5 menggunakan regression test perilaku dan menghasilkan manifest SHA-256 baru.

---

## Daftar Isi

- [Fitur Utama](#fitur-utama)
- [Cara Kerja](#cara-kerja)
- [Spesifikasi Perangkat](#spesifikasi-perangkat)
- [Kebutuhan Perangkat Lunak](#kebutuhan-perangkat-lunak)
- [Struktur Proyek](#struktur-proyek)
- [Instalasi dan Pembaruan](#instalasi-dan-pembaruan)
- [Cara Menggunakan Mode OCR](#cara-menggunakan-mode-ocr)
- [Cara Menggunakan Mode Audio](#cara-menggunakan-mode-audio)
- [Profil Performa](#profil-performa)
- [Verifikasi Instalasi](#verifikasi-instalasi)
- [Pemecahan Masalah](#pemecahan-masalah)
- [Privasi dan Data Lokal](#privasi-dan-data-lokal)
- [Catatan Pengembangan](#catatan-pengembangan)

---

## Fitur Utama

### Mode OCR

Mode OCR mengambil gambar dari area layar tertentu, membaca teks yang terlihat, lalu menerjemahkannya.

Fitur utamanya meliputi:

- pemilihan area layar atau *snipping box*;
- pengambilan layar berulang;
- OCR berbasis EasyOCR dan OpenCV;
- mode pembacaan Auto, Freeze, dan Interval;
- normalisasi teks dan penyaringan hasil OCR;
- penyimpanan konteks dialog;
- overlay terjemahan;
- dukungan penerjemahan offline;
- profil khusus untuk game dan dialog cerita.

Mode OCR cocok untuk:

- game dengan kotak dialog;
- visual novel;
- subtitle yang tertanam dalam video;
- manga atau gambar;
- antarmuka aplikasi;
- teks yang tidak dapat disalin secara langsung.

### Mode Audio

Mode Audio mengambil suara dari perangkat keluaran Windows melalui WASAPI loopback, mengenali ucapan, lalu mengirim hasilnya ke pipeline terjemahan.

Fitur utamanya meliputi:

- pengambilan suara sistem tanpa mikrofon eksternal;
- pengenalan ucapan lokal;
- mode CPU, GPU, dan Hybrid;
- pilihan Speed, Normal, dan Accurate;
- deteksi bahasa otomatis;
- dukungan bahasa Jepang;
- Japanese Specialist apabila model tersedia;
- rolling partial untuk menampilkan hasil sebelum dialog selesai;
- konteks dialog panjang;
- overlay subtitle Bahasa Indonesia;
- fallback CPU apabila jalur GPU gagal.

Mode Audio cocok untuk:

- game yang tidak memiliki teks dialog di layar;
- film dan anime;
- video;
- siaran langsung;
- percakapan atau media dengan suara yang jelas.

### Open Architecture Lab

Open Architecture Lab adalah area eksperimen terpisah untuk:

- source provider;
- VAD provider;
- ASR provider;
- streaming policy;
- translation route;
- overlay provider;
- perbandingan A/B antar-pipeline;
- Confirmed Prefix dan Local Agreement;
- adapter provider pihak ketiga.

Open Architecture Lab tidak mengganti pipeline OCR atau Audio utama secara diam-diam. Pipeline produksi ORT tetap menjadi baseline aktif.

---

## Cara Kerja

### Pipeline OCR

```text
Area layar
    ↓
Screen Capture
    ↓
Image Preprocessing
    ↓
EasyOCR
    ↓
Text Repair dan Stability Gate
    ↓
ORT Translation Pipeline
    ↓
Overlay Bahasa Indonesia
```

### Pipeline Audio

```text
Audio keluaran Windows
    ↓
WASAPI Loopback
    ↓
VAD / Segmentasi Ucapan
    ↓
ASR Lokal
    ↓
Language Routing
    ↓
ORT Translation Pipeline
    ↓
Overlay Subtitle Bahasa Indonesia
```

Kecepatan hasil dipengaruhi oleh panjang ucapan, model ASR, perangkat CPU/GPU, profil performa, kualitas audio, dan tingkat kesulitan bahasa sumber.

---

## Spesifikasi Perangkat

Angka berikut merupakan batas operasional yang disarankan berdasarkan struktur runtime ORT. Angka ini bukan sertifikasi resmi untuk seluruh kombinasi perangkat dan model.

### Minimum untuk Mode OCR

| Komponen | Minimum |
|---|---|
| Sistem operasi | Windows 10 64-bit |
| Prosesor | CPU x64 4-core modern |
| Contoh kelas CPU | Intel Core i3/i5 atau AMD Ryzen 3/5 setara |
| RAM | 8 GB |
| GPU | Tidak wajib; grafis terintegrasi dapat digunakan |
| Penyimpanan kosong | Sekitar 8–10 GB |
| Jenis penyimpanan | SSD sangat disarankan |
| Resolusi layar | 1366 × 768 |
| Internet | Tidak wajib setelah seluruh model tersedia |

Mode OCR dapat berjalan dengan CPU, tetapi proses OCR dan penerjemahan dapat menjadi lebih lambat pada laptop lama atau saat area tangkap terlalu besar.

### Minimum untuk Mode Audio CPU

| Komponen | Minimum |
|---|---|
| Sistem operasi | Windows 10/11 64-bit |
| Prosesor | CPU x64 minimal 6-core |
| Contoh kelas CPU | Intel Core i5 generasi menengah atau AMD Ryzen 5 setara |
| RAM | 12 GB |
| RAM yang disarankan | 16 GB |
| GPU | Tidak wajib |
| Penyimpanan kosong | Sekitar 15–20 GB |
| Audio | Perangkat keluaran Windows yang mendukung WASAPI loopback |
| Internet | Tidak wajib untuk jalur lokal setelah model tersedia |

Mode Audio CPU tetap dapat digunakan, tetapi subtitle parsial dan hasil final mungkin memiliki jeda lebih besar daripada jalur GPU. Gunakan profil **Speed** atau **Normal** untuk perangkat CPU-only.

### Minimum untuk Mode Audio GPU

| Komponen | Minimum |
|---|---|
| Sistem operasi | Windows 10/11 64-bit |
| Prosesor | CPU x64 4–6 core |
| RAM | 16 GB |
| GPU | NVIDIA yang kompatibel dengan CUDA |
| VRAM minimum | 4 GB untuk model ringan |
| VRAM yang disarankan | 6 GB atau lebih |
| Penyimpanan kosong | Sekitar 20–30 GB |
| Driver | NVIDIA Driver yang sesuai dengan runtime CUDA |
| Jenis penyimpanan | SSD atau NVMe |

GPU dengan VRAM 6 GB lebih sesuai untuk penggunaan model Small, jalur Hybrid, dan Japanese Specialist. Kapasitas 4 GB dapat digunakan untuk model ringan, tetapi berisiko mengalami keterbatasan VRAM pada konfigurasi berat.

### Perangkat yang Disarankan

Untuk penggunaan OCR dan Audio secara bersamaan:

| Komponen | Rekomendasi |
|---|---|
| Sistem operasi | Windows 11 64-bit |
| Prosesor | Intel Core i5/i7 atau AMD Ryzen 5/7, minimal 6 core |
| RAM | 16 GB |
| GPU | NVIDIA RTX dengan VRAM 6 GB atau lebih |
| Penyimpanan | SSD/NVMe dengan ruang kosong minimal 30 GB |
| Resolusi | 1920 × 1080 |
| Audio | Headphone/speaker sebagai perangkat output default Windows |

### Catatan Laptop

Pada laptop:

- gunakan mode daya **Best performance** ketika menjalankan Audio GPU;
- pastikan aplikasi memakai GPU NVIDIA, bukan iGPU;
- sambungkan charger;
- hindari menjalankan game berat, perekaman, dan model Accurate secara bersamaan apabila VRAM terbatas;
- perhatikan suhu CPU dan GPU.

---

## Kebutuhan Perangkat Lunak

### Wajib

- Windows 10 atau Windows 11 64-bit;
- Python 3 yang kompatibel dengan runtime ORT;
- Microsoft Visual C++ Runtime;
- driver audio Windows;
- model OCR dan terjemahan;
- runtime yang berada di folder `ORT_Runtime`.

### Komponen Dasar

Runtime dasar ORT menggunakan komponen seperti:

- PyQt5;
- Gradio;
- EasyOCR;
- OpenCV;
- MSS;
- NumPy;
- Argos Translate;
- Requests;
- psutil.

Torch, TorchVision, TorchAudio, CUDA, CTranslate2, model ASR, dan model terjemahan harus mengikuti konfigurasi runtime yang sesuai. Jangan memasang versi Torch secara acak ke environment yang sudah berjalan karena dapat menyebabkan konflik CPU/CUDA.

### GPU

Untuk Mode Audio GPU diperlukan:

- GPU NVIDIA;
- driver NVIDIA yang aktif;
- library CUDA/cuDNN yang sesuai;
- environment GPU ORT;
- model yang kompatibel dengan CTranslate2 atau backend yang digunakan.

GPU AMD dan Intel tidak menjadi target utama runtime CUDA ORT saat ini. Perangkat tersebut masih dapat memakai jalur CPU apabila tersedia.

---

## Struktur Proyek

```text
ORT_Translation/
├── START_HERE.bat
├── Start WebUI.bat
├── Start OCR.bat
├── Runtime.bat
├── ORT v9 Setup.bat
├── VERSION.txt
├── ORT_App/
├── ORT_Runtime/
└── ORT/
    ├── docs/
    ├── plugins/
    ├── logs/
    ├── cache/
    ├── status/
    ├── user_data/
    ├── maintenance/
    ├── exports/
    ├── release/
    └── config/
```

### Penjelasan Folder

| Folder | Fungsi |
|---|---|
| `ORT_App` | Source aplikasi dan aset kecil yang dibutuhkan |
| `ORT_Runtime` | Environment Python, CUDA, model, dependency, dan spool audio |
| `ORT/docs` | Dokumentasi, changelog, laporan pengujian, dan handoff |
| `ORT/plugins` | Metadata provider dan Open Architecture |
| `ORT/logs` | Log runtime dan diagnostik |
| `ORT/cache` | Cache lokal |
| `ORT/status` | Status proses dan marker runtime |
| `ORT/user_data` | Preferensi serta data pengguna lokal |
| `ORT/maintenance` | Verifier, exporter, installer, dan alat perawatan |
| `ORT/exports` | Hasil ekspor source ringan |
| `ORT/release` | Manifest dan checksum rilis |
| `ORT/config` | Template serta konfigurasi layout |

> `ORT_Runtime`, model, credential, log, cache, dan data pengguna tidak disertakan dalam repository GitHub.

---

## Instalasi dan Pembaruan

### Menggunakan Paket ORT Lengkap

1. Tutup WebUI, overlay, proses Audio, dan seluruh proses Python ORT.
2. Cadangkan folder proyek sebelum menerapkan pembaruan.
3. Ekstrak paket atau patch ke root proyek.
4. Jalankan:

```text
ORT v9 Setup.bat
```

5. Tunggu migrasi struktur selesai.
6. Jalankan verifier:

```text
ORT\maintenance\VERIFY_ORT_V9_0_5.bat
```

7. Jalankan aplikasi melalui:

```text
START_HERE.bat
```

atau:

```text
Start WebUI.bat
```

### Menggunakan Source dari GitHub

Repository GitHub berisi source aplikasi, dokumentasi, dan konfigurasi ringan. Repository tidak membawa:

- `ORT_Runtime`;
- environment Python;
- CUDA/cuDNN;
- model OCR;
- model ASR;
- model terjemahan;
- credential;
- log dan data pengguna.

Karena itu, hasil `git clone` belum menjadi instalasi lengkap yang langsung dapat digunakan.

Pengguna perlu menyiapkan runtime dan model yang kompatibel, atau menyalin folder `ORT_Runtime` dari instalasi ORT yang sudah berfungsi.

```powershell
git clone https://github.com/RaizeiID/Snipping_Box_Translation.git
cd Snipping_Box_Translation
```

Setelah runtime tersedia, jalankan `ORT v9 Setup.bat` dan verifier.

---

## Cara Menggunakan Mode OCR

1. Jalankan:

```text
START_HERE.bat
```

atau:

```text
Start OCR.bat
```

2. Buka Mode OCR.
3. Pilih bahasa sumber dan Bahasa Indonesia sebagai bahasa target.
4. Tentukan area layar yang berisi teks.
5. Pilih mode pembacaan:
   - **Auto** untuk pembacaan berulang;
   - **Freeze** untuk mempertahankan hasil sampai ada perubahan valid;
   - **Interval** untuk pembacaan berdasarkan jeda tertentu.
6. Pilih profil performa.
7. Jalankan OCR.
8. Pastikan overlay berada pada posisi yang tidak menutup teks asli.

### Tips OCR

- Ambil hanya area dialog, bukan seluruh layar.
- Hindari area dengan animasi, partikel, atau latar belakang yang terlalu ramai.
- Perbesar UI atau subtitle game apabila teks terlalu kecil.
- Gunakan resolusi asli game.
- Pastikan skala tampilan Windows tidak membuat area tangkap bergeser.
- Gunakan Freeze atau Interval untuk dialog cerita yang berubah perlahan.
- Gunakan Auto untuk UI atau subtitle yang berubah cepat.

---

## Cara Menggunakan Mode Audio

1. Jalankan:

```text
START_HERE.bat
```

atau:

```text
Start WebUI.bat
```

2. Pilih Mode Audio.
3. Pilih perangkat output/loopback Windows yang sedang digunakan oleh game atau video.
4. Pilih bahasa sumber:
   - English;
   - Japanese;
   - Chinese;
   - Korean;
   - Smart Auto;
   - Japanese Specialist, apabila tersedia.
5. Pilih device:
   - **CPU**;
   - **GPU**;
   - **Hybrid**.
6. Pilih profil:
   - **Speed**;
   - **Normal**;
   - **Accurate**.
7. Pilih pemrosesan suara yang tersedia:
   - **Normal** untuk semua suara;
   - **VAD** untuk memprioritaskan suara manusia;
   - **ANC** untuk penyaringan noise dengan kebutuhan resource lebih tinggi.
8. Jalankan Audio Translation.
9. Putar game atau video dan periksa indikator input audio.
10. Sesuaikan volume aplikasi agar suara dialog cukup jelas.

> Ketersediaan Normal, VAD, ANC, Japanese Specialist, dan provider lain bergantung pada runtime serta model yang terpasang.

### Tips Audio

- Pilih perangkat loopback yang sama dengan perangkat output aktif Windows.
- Gunakan VAD untuk dialog dengan musik latar yang kuat.
- Gunakan headphone untuk mencegah suara mikrofon kembali masuk.
- Gunakan Smart Auto jika bahasa sumber dapat berubah.
- Gunakan Japanese Specialist untuk konten Jepang apabila modelnya tersedia.
- Gunakan GPU atau Hybrid untuk dialog panjang dan pembaruan subtitle yang lebih cepat.
- Jangan mengharapkan hasil benar-benar tanpa jeda; ASR perlu mengumpulkan audio yang cukup sebelum membuat transkripsi stabil.

---

## Profil Performa

### Speed

Cocok untuk:

- CPU-only;
- subtitle cepat;
- percakapan pendek;
- perangkat dengan resource terbatas.

Karakteristik:

- model atau jendela lebih ringan;
- latency lebih rendah;
- kemungkinan koreksi lebih sedikit;
- akurasi dapat lebih rendah pada ucapan sulit.

### Normal

Cocok untuk penggunaan harian.

Karakteristik:

- keseimbangan kecepatan dan ketelitian;
- disarankan untuk game;
- cocok untuk CPU modern dan GPU entry-level;
- penggunaan resource sedang.

### Accurate

Cocok untuk:

- dialog cerita;
- film;
- ucapan panjang;
- evaluasi hasil.

Karakteristik:

- proses lebih berat;
- jendela audio dan konteks lebih besar;
- latency lebih tinggi;
- lebih disarankan pada GPU dengan VRAM cukup.

---

## Verifikasi Instalasi

Jalankan:

```text
ORT\maintenance\VERIFY_ORT_V9_0_5.bat
```

Verifier memeriksa:

- versi aplikasi;
- file root wajib;
- file aplikasi wajib;
- struktur migrasi;
- compile source Python;
- import Open Architecture;
- Confirmed Prefix;
- regression test;
- checksum rilis.

Hasil yang benar:

```json
{
  "passed": true,
  "version": "v9.0.5",
  "errors": [],
  "warnings": []
}
```

---

## Pemecahan Masalah

### OCR Tidak Membaca Teks

Periksa:

- area tangkap sudah benar;
- teks tidak terlalu kecil;
- warna teks cukup kontras;
- game tidak berjalan dalam mode yang menghalangi screen capture;
- skala Windows dan resolusi game;
- model OCR tersedia;
- log pada `ORT/logs`.

Coba kecilkan area OCR hanya pada kotak dialog.

### Hasil OCR Berulang atau Tidak Stabil

- gunakan Freeze;
- tingkatkan interval pembacaan;
- hindari area dengan animasi;
- gunakan area dialog yang lebih sempit;
- bersihkan cache hanya melalui alat maintenance yang sesuai.

### Audio Tidak Terdeteksi

Periksa:

- perangkat output Windows yang aktif;
- perangkat loopback yang dipilih;
- volume game/video;
- mode eksklusif audio;
- aplikasi tidak berpindah ke perangkat output lain;
- driver audio;
- izin akses perangkat.

Coba tutup dan buka kembali aplikasi setelah mengganti perangkat output Windows.

### Audio CPU Terlalu Lambat

- gunakan profil Speed atau Normal;
- gunakan model yang lebih kecil;
- tutup aplikasi berat;
- kurangi proses perekaman atau streaming;
- gunakan mode daya performa tinggi;
- gunakan GPU atau Hybrid apabila tersedia.

### GPU/CUDA Gagal

- perbarui driver NVIDIA;
- periksa environment GPU ORT;
- periksa library CUDA dan cuDNN;
- gunakan alat diagnostik GPU pada folder maintenance;
- pilih Hybrid agar ORT dapat turun ke CPU;
- jangan menandai GPU sebagai siap apabila inferensi nyata gagal.

### Bahasa Jepang Tidak Akurat

- pastikan bahasa tidak dipaksa ke English;
- pilih Japanese atau Smart Auto;
- gunakan Japanese Specialist apabila tersedia;
- gunakan Normal atau Accurate;
- pastikan suara dialog lebih dominan daripada musik;
- gunakan GPU untuk model specialist yang lebih berat.

### Subtitle Muncul Setelah Jeda

Hal ini dapat terjadi karena:

- ASR menunggu konteks ucapan;
- VAD belum mendeteksi akhir atau jeda;
- model berjalan lebih lambat daripada audio;
- profil Accurate memakai jendela lebih besar;
- antrean terjemahan sedang penuh.

Gunakan Speed atau Normal untuk memperpendek latency.

---

## Privasi dan Data Lokal

ORT dirancang untuk dapat menggunakan pipeline lokal.

Secara default, data seperti berikut disimpan secara lokal:

- log;
- cache;
- status runtime;
- preferensi;
- custom preset;
- data sesi;
- model;
- hasil diagnostik.

Provider cloud atau API eksternal hanya boleh digunakan setelah dikonfigurasi oleh pengguna. Jangan mengunggah:

- `.env`;
- credential;
- API key;
- `ORT_Runtime`;
- model;
- log pribadi;
- `ORT/user_data`;
- konfigurasi perangkat lokal.

---

## Ekspor Source Ringan

Jalankan:

```text
ORT\maintenance\EXPORT_ORT_SOURCE_LIGHT.bat
```

atau pilih menu ekspor pada:

```text
START_HERE.bat
```

Exporter mengecualikan:

- runtime;
- model;
- log;
- cache;
- status;
- data pengguna;
- credential;
- arsip lokal;
- file besar.

Hasil ekspor disimpan di:

```text
ORT/exports
```

---

## Catatan Pengembangan

### Pipeline Produksi

Pipeline OCR dan Audio asli tetap menjadi baseline produksi.

### Pipeline Eksperimen

Open Architecture Lab dapat digunakan untuk merencanakan dan menguji:

- adapter OCR;
- Silero VAD;
- provider ASR;
- Confirmed Prefix;
- Local Agreement;
- direct Japanese-to-Indonesian route;
- provider eksternal.

Eksperimen tidak boleh mengganti pipeline utama tanpa persetujuan dan pengujian eksplisit.

### Kontribusi

Sebelum membuat pull request:

1. buat branch baru;
2. jangan sertakan runtime, model, log, atau credential;
3. jalankan verifier;
4. jalankan `git diff --check`;
5. jelaskan perubahan dan hasil pengujian;
6. gunakan Draft Pull Request untuk perubahan besar.

---

## Batasan

- Akurasi OCR dipengaruhi font, ukuran, warna, efek visual, dan resolusi.
- Akurasi Audio dipengaruhi bahasa, aksen, musik, noise, model, dan perangkat.
- Terjemahan real-time tetap memiliki latency pemrosesan.
- Model specialist memerlukan storage, RAM, dan VRAM lebih besar.
- Source GitHub tidak menyertakan runtime lengkap.
- Hasil terjemahan otomatis tetap perlu diperiksa untuk penggunaan penting.

---

## Versi

```text
ORT Translation v9.0.5
Engineering Baseline & Resilient Provider Setup
```

Dokumentasi teknis lanjutan tersedia di:

```text
ORT/docs/README.md
ORT/docs/v9/
ORT_App/docs/
```
