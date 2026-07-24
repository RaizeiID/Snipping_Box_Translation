ORT Translation v8.9.7 — Continuous Rolling-Partial Real-Time Update
====================================================================

Basis pemasangan:
- Terapkan di atas ORT Translation v8.9.6 yang lengkap.
- Paket ini hanya membawa file yang berubah.

Masalah yang diperbaiki:
- Log pengujian sebelumnya memperlihatkan WebUI v8.9.5 tetapi proses Audio v8.9.6.
- Azure tidak aktif (cloud_ready=0), sehingga program kembali ke local_guard.
- Local guard baru mentranskripsikan sesudah segmen 1–8 detik selesai.
- GPU gagal karena cublas64_12.dll tidak tersedia lalu pipeline lama berpindah ke CPU.

Perilaku v8.9.7:
1. Live Media Local menggunakan rolling-partial ASR, bukan segment-final ASR.
2. Audio masuk per 20 ms dan snapshot ucapan aktif diproses berulang.
3. Subtitle parsial diterjemahkan selama pembicara masih berbicara.
4. Jeda/VAD hanya mengunci final, bukan memulai terjemahan.
5. Azure fallback yang belum tersambung memilih Local Live, bukan local_guard.
6. Jika CUDA/cuBLAS gagal, Hybrid berpindah ke CPU tetapi tetap rolling-partial.
7. Versi WebUI, Audio, ORTCore, dan TitanCore wajib sama sebelum Audio dapat dimulai.

Cara memasang:
1. Tutup WebUI, overlay, dan semua proses Audio ORT.
2. Pastikan tidak ada jendela ORT lama yang masih terbuka.
3. Ekstrak ZIP patch ke folder instalasi ORT v8.9.6 yang sama.
4. Pilih Replace/Timpa untuk seluruh file yang sama.
5. Jalankan VERIFY_ORT_V8_9_7.bat.
6. Jangan mulai Audio sebelum hasil pemeriksaan menunjukkan "passed": true.
7. Buka kembali WebUI dari folder yang sama.

Pengaturan uji awal:
- Jenis penggunaan: Live Media
- Mesin: Local Live
- Profil: Speed/Instant
- Mode: Hybrid
- Input: Loopback
- Bahasa Spider-Man: English
- Bahasa GFL2: Japanese, jangan Auto

Tanda pipeline baru aktif:
- [WEBUI v8.9.7]
- [AUDIO v8.9.7]
- effective_engine=local_live atau effective_engine=azure
- local_live_state=STREAMING
- beberapa baris "partial" muncul sebelum "transcript" final
- audio_state=LOCAL_REALTIME_INTERIM selama karakter masih berbicara

Tanda instalasi/pipeline masih salah:
- WEBUI dan AUDIO menampilkan versi berbeda
- effective_engine=local_guard
- transkripsi utama hanya menunjukkan seconds=8.0
- tidak ada event partial sebelum final

Catatan GPU:
- Log sebelumnya menunjukkan cublas64_12.dll tidak tersedia.
- v8.9.7 akan melanjutkan Local Live melalui CPU agar tidak kembali ke segmen lama.
- GPU baru benar-benar digunakan setelah runtime CUDA/cuBLAS yang sesuai tersedia.

Batas pengujian paket:
- Pengujian internal memakai audio sintetis dan recognizer deterministik untuk membuktikan alur event tanpa pause.
- Uji Windows WASAPI, model nyata, kualitas terjemahan, dan latensi perangkat tetap dilakukan pada laptop pengguna.
