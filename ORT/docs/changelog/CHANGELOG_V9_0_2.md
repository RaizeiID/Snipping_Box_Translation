# ORT Translation v9.0.2

## Adaptive Dialogue Segmentation & Overlay Layout

Rilis ini memperbaiki Audio Lab lokal untuk media Jepang berdasarkan log pengujian nyata v9.0.1.

### Perubahan utama

- **Smart Dialogue Boundary** membedakan jeda singkat, jeda panjang, akhir kalimat, dan monolog panjang.
- Segmentasi dapat menutup turn berdasarkan bukti semantik ASR meskipun musik latar membuat RMS/VAD terus dianggap aktif.
- Subtitle otomatis melakukan rollover pada monolog panjang agar konteks lama tidak terus menumpuk.
- Carry-over audio antar-window diperkecil agar kata lama tidak berulang pada segmen baru.
- Penerjemah EN→ID memakai **incremental clause translation**: klausa yang sudah diterjemahkan dipakai kembali dan hanya bagian baru yang dikirim ke backend.
- Resolver model CTranslate2 diperbarui untuk layout v9 (`ORT_App` dan `ORT_Runtime`).
- Pilihan **Model terjemahan ORT** dihapus dari Audio Lab karena daftar itu berasal dari model/preset OCR dan membingungkan pemilihan Japanese ASR.
- Audio Lab sekarang mengunci strategi internal ke `ORTCore Fast V2`; provider ASR tetap ditentukan oleh arsitektur Lab.
- Mode overlay baru:
  - **Adaptif** — ukuran mengikuti teks.
  - **Fix** — ukuran tetap mengikuti monitor dan hanya dapat digeser vertikal.
  - **Custom** — ukuran, posisi, font, opacity, alignment, dan preview sumber dapat diatur user.
- Verifier v9.0.2 memakai UTF-8 agar log CJK atau karakter replacement tidak menyebabkan `UnicodeEncodeError` di Windows.

### Batasan

- Kecepatan terbaik EN→ID tetap memerlukan model CT2 EN→ID yang valid. Bila model tidak ditemukan, sistem memakai Argos sebagai fallback dan latensi dapat lebih tinggi.
- Pengujian sintetis tidak menggantikan validasi WASAPI, Kotoba, CUDA, dan anime nyata pada perangkat user.
