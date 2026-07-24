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


## R3 — Reazon Japanese Bridge & Preview Repair

- Install Argos JA→EN and EN→ID inside the active Audio CPU/GPU runtime.
- Functionally verify both translation pairs during provider setup.
- Warm the JA→EN bridge before opening the capture gate.
- Route Reazon/SenseVoice as Japanese transcription → English preview → CT2 Indonesian.
- Send `bridge_text` to the overlay as Preview EN instead of displaying Japanese under an English label.
- Fail fast when the active Audio runtime has no Japanese bridge instead of silently timing out.
- Retain R2 ReazonSpeech CUDA setup and hard provider lock.

## R4 — Provider Setup Progress & Device Status UI

- Setup target must be selected explicitly on every run: CPU, GPU, or CPU + GPU.
- Model download reports total bytes, downloaded bytes, GB, percentage, file, phase, and active device in realtime.
- Provider setup output is streamed to a dedicated download/setup log instead of appearing only after the process finishes.
- Copy Log is hidden while the provider setup log is empty and appears automatically after setup starts.
- Check Model Status validates CPU and GPU separately using persistent manifests, actual model files, runtime probes, CUDA wheel type, and Japanese bridge readiness.
- CPU/GPU readiness is rendered as long oval pills: green READY, red NOT INSTALLED, yellow UNVERIFIED, or gray UNSUPPORTED.
- Reazon, Kotoba, Faster-Whisper, and SenseVoice setup persist model size/file manifests so partial downloads are not reported as READY.
- Windows setup output is forced to UTF-8 and inline Python source is hidden from command echo, fixing the `cp1252` UnicodeEncodeError seen during the Japanese Argos functional test.
