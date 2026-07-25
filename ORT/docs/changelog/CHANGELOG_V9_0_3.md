# ORT v9.0.3 — Stability Recovery & Realtime Diagnostics

## Fokus rilis

v9.0.3 memulihkan stabilitas Audio Lab setelah pengujian v9.0.2 menunjukkan dual-stream CPU, watchdog agresif, tekanan VRAM Hybrid, false-speech akibat musik, dan status/log yang terlambat terlihat.

## Perubahan utama

- Watchdog CT2 memakai latest-wins dan restart low-pressure; satu request lambat tidak langsung memindahkan sesi ke Argos.
- Argos recovery dinonaktifkan secara default dan hanya tersedia sebagai pemulihan eksplisit.
- Dual-stream ASR dinonaktifkan secara default pada Efficient, Normal, dan Optimal.
- Kebijakan resource baru:
  - Efficient: single-stream ringan, konteks pendek.
  - Normal: konfigurasi stabil tetap.
  - Optimal: guard VRAM dan latency preflight; otomatis beralih ke CPU single-stream bila GPU tidak sehat.
- False-speech cooldown mencegah musik/efek suara membuat segmen kosong berulang.
- Profil Daily / Media memisahkan English transcribe dari Japanese translate.
- Daftar bahasa mengikuti profil game: GFL2, GFL, Wuthering Waves, Daily / Media, dan Custom.
- Log Architecture Lab diperbarui realtime melalui timer UI.
- Transparansi provider menampilkan provider efektif, device, resource policy, dan recovery mode.
- Preview box realtime: tombol Preview berubah menjadi Stop Preview; perubahan layout diterapkan tanpa menutup box.
- Audio Lab otomatis menghentikan Preview sebelum memulai runtime.

## Ditunda ke v9.0.4

Cloud & Provider Benchmark Lab, termasuk Offline/Online/Hybrid cloud, Azure/Google/AWS adapters, dan benchmark kandidat open-source tambahan, sengaja dipisahkan agar v9.0.3 hanya memulihkan fondasi lokal.
