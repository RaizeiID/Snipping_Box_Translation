# ORT v8.9.2 Validation Report

Tanggal validasi: 22 Juli 2026  
Basis: runtime ORT v8.9.1  
Lingkungan validasi: Linux, Python 3.12

## Hasil

| Pemeriksaan | Hasil |
|---|---|
| Kompilasi seluruh modul Python runtime | PASS |
| Regression aktif v8.9.1 | PASS |
| Regression khusus v8.9.2 | PASS |
| Text ROI gate: first/change/confirm/static | PASS |
| Turn dan generation stale-token rejection | PASS |
| Atomic swap dan satu final per turn | PASS |
| JSONL multiprocess: 4 worker × 80 event | PASS — 320/320 valid dan unik |
| Overlay patch pada salinan bersih v8.9.1 | PASS — versi dan 23 file selektif terpasang |
| Integritas ZIP dan checksum | PASS — 24 entri file, seluruh checksum valid |

Regression historis yang kompatibel lulus 15 skrip. Empat skrip v8.7.2–v8.7.5 tidak dapat dijalankan karena OpenCV/GUI Windows tidak tersedia di lingkungan ini. Test v8.8.7 dan v8.9.0 membawa kontrak lama yang sudah sengaja digantikan oleh v8.9.1: speaker/body separation dan silent pending tanpa placeholder.

## Batas validasi

GUI penuh, EasyOCR live, hook keyboard, display PyQt5, dan capture khusus Windows tidak dijalankan di lingkungan Linux ini. Karena itu smoke test langsung pada Windows tetap diperlukan setelah pemasangan, khususnya profil Auto CPU/GPU dan pergantian scene/dialog.

## Kriteria pemeriksaan live

- Tidak ada overlay kosong saat dialog berganti.
- Tidak ada hasil dialog lama muncul setelah dialog baru.
- Tidak ada placeholder atau ID internal pada overlay.
- Satu turn hanya menghasilkan satu event `FINAL_OVERLAY`.
- Clear hanya terjadi saat dialog/scene benar-benar hilang.
- JSONL sesi dapat diparse seluruhnya tanpa baris rusak.
- Frame statis menghasilkan `OCR_CHANGE_GATE_SKIPPED` dan panggilan OCR berkurang.
