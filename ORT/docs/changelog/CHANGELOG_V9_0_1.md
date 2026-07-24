# ORT Translation v9.0.1

## Audio Lab Preload, Watchdog & Diagnostics

- Overlay Audio Lab tidak muncul selama ASR dan penerjemah masih dimuat.
- Capture WASAPI ditahan oleh start gate sampai kedua worker siap.
- Faster-Whisper menjalankan warmup nyata dengan mengonsumsi generator transkripsi.
- Revisi parsial Confirmed Prefix dikonsolidasikan sebelum dikirim ke penerjemah.
- Translation watchdog memulihkan sidecar yang hidup tetapi tidak merespons.
- Open Architecture Lab menyediakan Copy Log Lab dan panel log yang selalu mudah dibuka.
- Silero VAD dan WhisperLive tetap berstatus eksperimen dan tidak diaktifkan dalam jalur produksi v9.0.1.
