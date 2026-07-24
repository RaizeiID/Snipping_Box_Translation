# ORT v8.9.0 Stability Test Report

## Scope
Static/unit regression terhadap patch v8.9.0 di atas v8.8.9.

## Validated cases
- Entity registry v8.9.0: Littara, Ullrid, Phaetusa, Sweeper, Nyxie, Kenny, Raizei.
- Ullrid alias repair: `UIlr -> Ullrid` dengan confidence label.
- Contextual OCR repair: `Qur`, `healin9`, `Ifnot`, `ook at`, `callyoU`, `must'ye`, `weve`.
- Overlay language guard: English source/trusted preview tidak tampil di overlay user-facing.
- UI filter v4: Toysmith, Max Level, Dammage Stats Confirm, Clickanywhere to exit, End Action, Formation/Platoon.
- Overlay commit gate: Indonesian new-turn preview mengganti stale overlay.
- Low-OCR readability guard: low OCR 45% dapat meminta rescue ke safe floor tanpa menaikkan default global.

## Result
PASS.

## Live test checklist
- Pastikan overlay tidak lagi menampilkan teks Inggris saat final belum siap.
- Pastikan flicker berkurang ketika dialog diklik cepat di Auto/Interval.
- Pastikan Prediction/Repair Text menulis event `[REPAIR v8.9.0]` pada kata rusak.
- Pastikan UI/battle text lebih banyak masuk `[FILTER]` dan tidak diterjemahkan.
- Pastikan OCR 40-50% tetap terbaca jelas dan tidak lebih berat secara signifikan.
