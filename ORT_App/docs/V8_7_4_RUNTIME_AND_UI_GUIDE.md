# ORT Translation v8.7.4 — Runtime & UI Guide

## Mode runtime baru

- **Baseline Correctness**: jalur standar untuk memvalidasi EntitySpan, label speaker, dan hasil final.
- **Mode Responsif / Story Cepat (Tanpa Voice)**: checkbox runtime yang memprioritaskan dialog terbaru, mengurangi preview progresif usang, dan tetap mempertahankan Two-Pass Name ROI.
- **Diagnostic No-Name-ROI**: hanya uji A/B. Jangan digunakan sebagai konfigurasi normal karena label speaker dapat hilang/salah.

## Halaman identitas yang dipertahankan

`Pengolahan Data & Identitas` tetap memiliki `Tampilan Sederhana` tercentang default dan mode detail per game. Nama yang ditambah dari mode sederhana tampil orange/migratable pada mode detail. Mode ini berbeda dari checkbox Mode Responsif di Dashboard.

## Tahap tes yang disarankan

1. Baseline Correctness pada scene GFL2 yang memuat Helen, Helena, KSVK, Alya Kujou, Phaetusa/Balthilde.
2. Pastikan overlay tidak menampilkan `ORT_ENTITY` atau marker internal apa pun.
3. Ulangi scene dialog cepat tanpa voice dengan Mode Responsif.
4. Ekspor Debug Bundle dan bandingkan stage timing serta final-output integrity.
