# ORT v8.9.2-R3 Audio CPU Validation Report

Tanggal validasi: 2026-07-23

## Hasil

| Pemeriksaan | Hasil |
|---|---|
| Kompilasi sumber Python (311 modul) | PASS |
| Regression v8.9.1 | PASS |
| Regression inti v8.9.2 | PASS |
| Kontrak Guided/Expert UI R2 | PASS |
| Regression Audio CPU R3 | PASS |
| Segmentasi Normal dan VAD sintetis | PASS |
| PCM stereo→mono dan resampling | PASS |
| Dedup/overlap transcript | PASS |
| Protokol JSON-line sidecar | PASS |
| Queue bounds dan generation guard | PASS |
| Eksklusivitas OCR/Audio | PASS |
| Runtime dependency isolation | PASS |

## Kontrak yang diverifikasi

- ASR memakai `device=cpu`, `compute_type=int8`, satu worker, dan budget thread terbatas.
- Profil Speed/Normal/Accurate memetakan ke tiny/base/small.
- Antrean ASR maksimum dua; antrean terjemahan maksimum satu/latest-wins.
- Audio tidak memakai OCR dan pergantian sumber meminta runtime lama berhenti.
- Overlay tidak dikosongkan atau diganti placeholder ketika terjemahan baru masih berjalan.
- Isolasi Suara tidak dapat dipilih pada build first-test.
- Dependensi Audio dikunci versi dan dipasang di runtime terpisah.

## Batas validasi lingkungan

Lingkungan validasi paket ini adalah Linux tanpa PyQt/Gradio/faster-whisper/PyAudioWPatch aktif. Karena itu, GUI Windows dan tangkapan WASAPI langsung tidak dijalankan di sini. Jalur tersebut diverifikasi melalui kompilasi, kontrak API, probe sidecar, state/lifecycle, dan regression test; uji perangkat Windows nyata tetap diperlukan pada pemasangan pertama.

Model ASR sengaja tidak disertakan di patch. Setup pertama mengunduh model sesuai profil yang dipilih.
