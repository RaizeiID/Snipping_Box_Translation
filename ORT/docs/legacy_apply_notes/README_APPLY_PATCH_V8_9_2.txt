ORT Translation v8.9.2 — PETUNJUK PEMASANGAN PATCH SELEKTIF
=============================================================

PENTING
-------
Patch ini hanya untuk basis runtime ORT v8.9.1. Jangan pasang langsung pada
source GitHub v8.8.1 atau versi yang lebih lama.

ZIP ini sengaja hanya berisi file yang baru atau diperbarui. Model, cache,
log sesi, status runtime, konfigurasi pribadi, dan file lain yang tidak berubah
tidak disertakan.

CARA MEMASANG
-------------
1. Tutup WebUI dan runtime ORT sepenuhnya.
2. Buat salinan cadangan folder ORT v8.9.1 yang sedang dipakai.
3. Ekstrak ZIP patch ke folder sementara.
4. Buka folder ORT_Translation_v8_9_2_CHANGED_FILES_PATCH hasil ekstraksi.
5. Salin seluruh isinya ke root proyek ORT v8.9.1, yaitu folder yang berisi
   START_HERE.bat, README.md, VERSION.txt, dan folder ORT.
6. Pilih Merge/Replace bila Windows meminta konfirmasi. Jangan menghapus folder
   proyek lama; cukup timpa file yang ada dan tambahkan file baru dari patch.

VALIDASI SETELAH PEMASANGAN
---------------------------
Jalankan dengan Python runtime ORT:

  ORT\runtime_app\tools\v8_9_2_regression_test.py

Hasil yang benar:

  v8.9.2 regression PASS

Kemudian jalankan Start WebUI.bat dan periksa log awal:

  [WEBUI v8.9.2]
  text_roi_gate=1:15000ms       (profil Auto)
  turn_state=1
  atomic_overlay=1

Saat runtime sudah berjalan, telemetry periodik harus memakai label:

  [REC v8.9.2]

ROLLBACK
--------
Tutup ORT, lalu pulihkan file dari salinan cadangan v8.9.1. Patch ini tidak
menyertakan dan tidak menimpa model, log, cache, atau konfigurasi pengguna.

RUANG LINGKUP RILIS
-------------------
v8.9.2 berfokus pada stabilisasi OCR dan overlay: Text-aware ROI Change Gate,
coalescing progressive text, turn_id/generation_id, stale-result guard,
atomic overlay swap, explicit clear, satu final per turn, dan JSONL writer aman.

Mode Audio, VAD, Isolasi Suara, serta profil Speed/Normal/Accurate belum masuk
ke rilis ini dan tetap direncanakan untuk tahapan setelah stabilisasi OCR.
