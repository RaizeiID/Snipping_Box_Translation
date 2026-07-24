# ORT v9.0.4 — Cloud & Locked Provider Benchmark Lab

## Fokus rilis

v9.0.4 menambahkan eksperimen provider yang dapat dibandingkan tanpa membiarkan
resource controller mengganti model yang dipilih user secara diam-diam.

## Perubahan utama

- Model ASR Jepang dapat dipilih dan dikunci untuk seluruh sesi.
- Provider tersedia: Kotoba Bilingual, ReazonSpeech K2, SenseVoice-Small,
  Faster-Whisper Base, dan Faster-Whisper Small.
- Optimal hanya boleh memindahkan device untuk provider yang sama.
- Provider yang tidak tersedia memblokir Start dan menampilkan alasan setup.
- SenseVoice-Small diarahkan ke CPU; tidak mengonsumsi VRAM game.
- Kotoba CPU memakai single stream, beam 1, dan rolling window terbatas.
- Tombol setup provider memasang dependency/model yang dipilih.
- Provider Benchmark Lab membandingkan beberapa model dengan WAV yang sama.
- Penerjemah memahami sumber Inggris atau Jepang dan melaporkan bridge yang
  benar-benar digunakan.
- Mode delivery Offline, Online, dan Hybrid tersedia.
- Azure adalah live cloud adapter v9.0.4; Google/AWS tetap catalog-only.
- Tabel transparansi menunjukkan requested/effective provider, owner, backend,
  license, model path, device, delivery, dan fallback state.

## Batasan

- Model provider tidak disertakan dalam source ZIP/GitHub.
- Setup ReazonSpeech mengunduh model ke cache lokal Hugging Face.
- SenseVoice mengunduh model sherpa-onnx lokal.
- Cloud memerlukan konfigurasi kredensial lokal dan koneksi internet.
- Kualitas provider harus dinilai dengan klip referensi yang sama; RTF saja
  tidak menentukan akurasi.

## R2 — ReazonSpeech K2 CUDA setup

- Setup Reazon sekarang mengikuti pilihan Perangkat ASR: CPU, GPU, atau keduanya pada Hybrid.
- GPU memasang wheel sherpa-onnx CUDA resmi dan melakukan warm-up `device=cuda`, `precision=int8-fp32`.
- CPU dan CUDA memakai weight K2 yang sama; hanya runtime backend yang berbeda.
- Status GPU menolak build sherpa-onnx CPU agar hard lock tidak memberi status READY palsu.
