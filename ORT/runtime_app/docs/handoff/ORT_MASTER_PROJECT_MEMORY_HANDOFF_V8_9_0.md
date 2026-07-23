# ORT Translation / ORTCore — Master Handoff v8.9.0

Tanggal: 2026-06-03

## Status v8.9.0
v8.9.0 adalah stabilization milestone di atas v8.8.9. Tujuan utamanya bukan menambah fitur baru, tetapi memperbaiki masalah user-facing yang masih mengganggu: flicker overlay, English/source OCR leak, Prediction/Repair Text yang belum luas, UI leakage, dan kebutuhan OCR readability rendah yang aman untuk model lain.

## Keputusan penting
1. OCR level 40-50% yang sudah membaik tidak boleh dirusak.
2. Readability enhancement boleh diperluas ke model lain, tetapi defaultnya budgeted/light dan aktif terutama untuk OCR <=55%.
3. Source English tidak boleh tampil di overlay utama user secara default.
4. Prediction/Repair Text harus memeriksa semua token, tetapi hanya memperbaiki token yang lolos guard/kamus/registry/confusion map.
5. Legacy repaint_last_good tidak boleh lagi menjadi jalur default karena menyebabkan stale/flicker.

## Implementasi kunci
- `app/translation/ocr_text_repair.py`: Contextual OCR Repair v3.
- `app/runtime/overlay_language_guard.py`: mencegah English source leak di overlay.
- `TITANMAIN.py`: integrasi repair, ID-only source fallback, readability enhancement ringan, legacy repaint blocker.
- `app/runtime/ui_dialog_filter.py`: UI Filter v4.
- `configs/gfl2_entity_registry_v8_9_0.json`: registry entity/alias baru.
- `tools/v8_9_0_regression_test.py`: regression test baru.

## Entity baru/retained dari log v8.8.9
- Littara
- Ullrid
- Phaetusa
- Sweeper
- Nyxie
- Raizei
- Balthilde/Bathilde alias family
- Kenny

## Repair examples yang harus dipertahankan
- Qur -> our
- healin9/healng/healln9 -> healing
- Ifnot -> If not
- ook at -> look at
- callyoU -> call you
- must'ye -> must've
- weve -> we've
- telljust -> tell just

## Catatan untuk update berikutnya
Jika v8.9.0 masih terlalu sering menampilkan `Menerjemahkan dialog baru…`, jangan kembali menampilkan English source. Solusi berikutnya adalah mempercepat quick Indonesian preview atau memperbaiki final CT2 replacement.
