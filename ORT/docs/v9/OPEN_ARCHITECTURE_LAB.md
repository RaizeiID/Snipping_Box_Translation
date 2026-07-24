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
