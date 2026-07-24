ORT Translation v8.9.9 R2 F2
Long-Turn Context & Japanese Accuracy Fix

BASIS WAJIB
- ORT v8.9.9 R2 F1 sudah terpasang.
- GPU installer R2 tidak perlu dijalankan ulang bila CUDA sudah passed=true.

CARA MEMASANG
1. Tutup WebUI, overlay, Audio ORT, dan seluruh proses Python ORT.
2. Ekstrak ZIP ini ke root instalasi ORT.
3. Pilih Replace/Timpa semua file.
4. Jalankan VERIFY_ORT_V8_9_9_R2_F2.bat.
5. Buka kembali WebUI.

PENGATURAN UJI YANG DISARANKAN
- Language: Japanese Specialist
- Profile: Normal
- Device: Hybrid
- Engine: Local Live
- Processing: VAD
- Auto-Correct: Off untuk uji bahasa tetap

LOG YANG DIHARAPKAN
- continuous_turn_context=true
- context_history_words=240
- metric name=continuous_turn_window_shift pada ucapan panjang
- displayed ... context_words=<bertambah> display_words=<maksimal profil>
- asr=cuda:kotoba-bilingual pada GPU

CATATAN
- Konteks internal dapat menyimpan hingga 240 kata.
- Overlay menerjemahkan jendela terbaru 56/72/92 kata agar latency tetap terkendali.
- Update ini tidak menjanjikan kesetaraan akurasi Jepang dengan English, tetapi memperbaiki segmentasi, pencarian Kotoba, dan kehilangan konteks panjang.
