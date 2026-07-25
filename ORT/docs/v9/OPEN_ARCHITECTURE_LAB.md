# ORT Open Architecture Lab

The Lab is an isolated experimental architecture layer. It does not import or copy complete third-party applications into the production ORT pipeline.

## Layers

1. Source provider — OCR, WASAPI, multi-region OCR, or external text connector.
2. VAD provider — ORT RMS/VAD, Silero ONNX, or hybrid trigger/confirmation.
3. ASR provider — ORT Faster-Whisper, Japanese Specialist, or external worker adapter.
4. Streaming policy — ORT Rolling Turn Context, Confirmed Prefix, or Local Agreement.
5. Translation route — ORTCore, Japanese bridge, direct Japanese route, or external API.
6. Overlay provider — ORT Overlay.

## Safety boundary

Selecting a Lab preset only writes an experiment plan. It does not start a second hidden OCR/audio process and does not modify the Original pipeline configuration.

## Planned implementation order

1. Silero VAD adapter and model installer.
2. Confirmed-prefix integration with recorded/offline replay.
3. Per-turn queue and A/B metrics.
4. Direct Japanese transcript → Indonesian provider.
5. Multi-region OCR adapter.
6. External GPL connector bridge.

## v9.0.0 R2 — Executable Audio Lab & Developer Mode

Open Architecture Lab sekarang mempunyai dua sudut pandang yang konsisten:

- **Normal Mode** — preset, konfigurasi sesi, validasi, `Mulai Audio Lab`, `Stop Audio Lab`, dan status.
- **Developer Mode** — seluruh provider ID, lisensi, JSON plan, A/B comparison, agreement passes, log, dan diagnostik.

Preset `Japanese Live Lab · Recommended` adalah jalur eksperimen pertama yang dapat dijalankan langsung:

```text
ORT WASAPI Loopback
→ ORT RMS/VAD Native
→ ORT Japanese Specialist
→ Confirmed Prefix
→ Japanese → English → Indonesian
→ ORT Overlay
```

Lab menggunakan ProcessManager yang sama dengan pipeline produksi. Karena itu, ORT tetap mencegah Audio Original dan Audio Lab berjalan bersamaan.

Provider yang belum mempunyai executor nyata tetap ditandai dan diblokir sebelum sesi dimulai. Pemilihan provider di Developer Mode tidak dianggap aktif sampai validasi runtime lulus dan tombol `Mulai Audio Lab` ditekan.



## v9.0.1 — Preload, anti-stall, dan log Lab

- `Preload & Mulai Audio Lab` menjalankan model ASR dan penerjemah tanpa menampilkan overlay terlebih dahulu.
- Overlay hanya muncul setelah `LOCAL_REALTIME_READY` dan `TRANSLATOR_READY` sama-sama diterima.
- Capture WASAPI ditahan oleh start gate selama proses preload.
- Faster-Whisper dipanaskan dengan inferensi sintetis; generator hasil wajib dikonsumsi agar preload benar-benar mengeksekusi model.
- Revisi parsial dikonsolidasikan sebelum masuk ke penerjemah untuk mencegah antrean tertinggal.
- Translation watchdog memulai ulang sidecar yang hidup tetapi tidak merespons.
- Panel Lab memiliki `Copy Log Lab`; tekan Refresh Status Lab sebelum menyalin.
- Silero VAD dan WhisperLive tetap tidak diaktifkan sebagai runtime produksi pada rilis ini. Keduanya tetap provider eksperimen sampai installer, health check, dan uji Windows selesai.

## v9.0.2 — Adaptive Turn & Overlay Layout

Audio Lab kini menjalankan pemisahan dialog adaptif. Jeda singkat pada klausa yang belum selesai dipertahankan sebagai turn yang sama, sedangkan akhir kalimat, jeda panjang, dan batas monolog menghasilkan segmen subtitle baru. Bukti `NO_SPEECH` dari ASR dapat menutup turn walaupun musik latar membuat energy VAD tetap aktif.

Penerjemahan Indonesia tidak lagi menerjemahkan ulang seluruh paragraf pada setiap revisi. Klausa lama digunakan kembali dan hanya klausa atau tail baru yang diterjemahkan.

Pilihan `Model terjemahan ORT` dihapus dari Audio Lab. Daftar tersebut berasal dari registry model OCR dan tidak memilih model Japanese ASR. Audio Lab mengunci strategi internal `ORTCore Fast V2`, sedangkan ASR, streaming policy, translation route, dan overlay tetap berasal dari provider arsitektur.

Mode overlay:

- `adaptive`: ukuran mengikuti hasil subtitle.
- `fixed`: lebar/tinggi tetap berdasarkan monitor; drag dibatasi vertikal.
- `custom`: resize dan perpindahan bebas dengan pengaturan layout tambahan.

## v9.0.3 — Stability Recovery & Realtime Diagnostics

### Realtime Overlay Preview

Tombol `Preview` membuka overlay contoh tanpa menjalankan ASR atau penerjemah. Selama aktif tombol berubah menjadi `Stop Preview`. Mode, ukuran, font, opacity, sumber Inggris, dan alignment diperbarui realtime. Memulai Audio Lab otomatis menutup preview.

### Kebijakan resource

- `Efficient`: satu stream ASR ringan, konteks pendek, tanpa koreksi model kedua.
- `Normal`: satu model utama stabil; tidak melakukan dual-stream correction.
- `Optimal`: memeriksa headroom VRAM dan latency CUDA preflight. Sistem beralih ke CPU single-stream jika GPU tidak sehat.

### Realtime diagnostics

Log Lab diperbarui selama proses berjalan. Provider transparency menyebut komponen yang benar-benar aktif: WASAPI/PyAudioWPatch, Faster-Whisper/CTranslate2, Kotoba bila dipilih, OPUS-MT/CTranslate2, VAD native, dan CT2 recovery.

### Profil bahasa

- Daily / Media: Auto, English, Japanese, Chinese, Korean.
- GFL2 Exilium: Japanese dan Chinese.
- Girls' Frontline: Japanese.
- Wuthering Waves: English, Japanese, Chinese, Korean.

English menggunakan `transcribe`; bahasa Asia yang memerlukan bridge menggunakan route speech → English → Indonesian. Nilai bahasa dari profil sebelumnya tidak boleh bocor ke sesi baru.

### Recovery policy

v9.0.3 menggunakan latest-wins. Request terbaru menggantikan revisi lama yang belum diproses. Timeout pertama merestart CT2 low-pressure dan mempertahankan request terbaru. Argos tidak menjadi fallback otomatis.

## v9.0.4 — Cloud & Locked Provider Benchmark Lab

### Hard model lock

Audio Lab exposes an explicit Japanese ASR model selector. Once a session starts,
`requested_provider` and `effective_provider` must remain identical. Resource
policies may move the same provider between CPU and CUDA only when that provider
supports both devices. A missing or failed model blocks the session instead of
silently substituting Faster-Whisper Base.

Available provider candidates:

- Kotoba Whisper Bilingual — current Japanese-to-English bridge.
- ReazonSpeech K2 — Japanese transcription candidate for stable game/CPU use.
- SenseVoice-Small through sherpa-onnx — fast CPU multilingual candidate.
- Faster-Whisper Base and Small — diagnostic baselines.

Kotoba CPU uses one stream, beam size 1, and bounded rolling windows to avoid
minute-long queues. SenseVoice is routed to CPU in this release. Reazon and
Kotoba can use CPU or CUDA when their selected runtime is installed.

### Provider setup and benchmark

`Siapkan model yang dipilih` installs only the selected provider dependencies.
Provider Benchmark Lab runs the same WAV clip against multiple selected models
and reports ASR latency, real-time factor, transcript, device, and errors. It
does not decide accuracy automatically; the user compares every transcript with
the same reference dialogue.

### Source-aware translation

Kotoba and generic Whisper direct-translation providers produce an English
bridge. ReazonSpeech and SenseVoice produce Japanese text. Japanese transcripts
use an installed Japanese→Indonesian Argos route when available, otherwise a
Japanese→English Argos bridge followed by the existing CTranslate2 EN→ID engine.
Missing bridge packages are reported explicitly instead of pretending the
Japanese source was an Indonesian translation.

### Delivery modes

- Offline — locked local ASR and local translation.
- Online — Azure live cloud path.
- Hybrid — Azure primary plus the exact locked local provider as fallback.

Google Cloud and AWS are visible as benchmark/catalog candidates in v9.0.4, but
are blocked for live start until their streaming adapters and credential health
checks are implemented. Credentials remain outside source control.
