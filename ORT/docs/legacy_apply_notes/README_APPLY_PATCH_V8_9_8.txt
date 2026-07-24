ORT Translation v8.9.8 — Cara menerapkan patch
================================================

Basis wajib:
- ORT v8.9.7 lengkap dan sudah dapat menjalankan Local Live.

Langkah:
1. Tutup WebUI, overlay, dan semua proses Python ORT.
2. Ekstrak isi ZIP patch ke folder instalasi ORT.
3. Pilih Replace/Timpa semua file.
4. Jalankan VERIFY_ORT_V8_9_8.bat.
5. Jalankan CHECK_AUDIO_GPU_V8_9_8.bat.
6. Bila ingin akurasi Jepang terbaik, jalankan SETUP_JAPANESE_SPECIALIST_V8_9_8.bat.
7. Buka WebUI dan pilih:
   - Film Inggris: Smart Auto atau English.
   - Anime/game Jepang: Japanese Specialist atau Japanese.
   - Profil: Speed untuk latensi terendah; Normal untuk keseimbangan.

Log yang diharapkan untuk Jepang:
- requested_language=ja / ja_specialist / auto
- source_lang=ja
- bridge=en
- task=translate
- LANGUAGE_LOCKED detected_language=ja (Smart Auto)
- JAPANESE_SPECIALIST_ACTIVE (jika model dan GPU siap)
- displayed muncul selama partial, bukan hanya final

Log yang tidak boleh terjadi pada anime Jepang:
- language=en tanpa language guard
- rangkaian stale translation blocked

Catatan:
- Teks sumber yang terlihat dalam box dapat berupa English bridge. Ini disengaja agar mesin EN→ID ORTCore tetap cepat.
- Bobot Kotoba dan DLL NVIDIA tidak dibundel dalam patch.
- Latensi nol tidak mungkin; targetnya adalah pembaruan subtitle selama ucapan, dengan hasil Indonesia mengikuti setiap hasil partial yang selesai.
