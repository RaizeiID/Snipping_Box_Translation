ORT Translation v8.9.9 — Cara Memasang Patch

Basis wajib: instalasi ORT v8.9.8 lengkap.

1. Tutup WebUI, overlay, dan seluruh proses Python ORT.
2. Ekstrak ZIP patch ke folder ORT yang sama.
3. Pilih Replace/Timpa semua.
4. Jalankan VERIFY_ORT_V8_9_9.bat.
5. Bila Japanese Specialist belum tervalidasi, jalankan INSTALL_JAPANESE_SPECIALIST.bat.
6. Jalankan CHECK_AUDIO_GPU_V8_9_9.bat. Jika gagal, Hybrid tetap dapat memakai Kotoba CPU.
7. Buka ORT dan gunakan Auto-Correct Balanced.

Pengaturan awal anime Jepang:
- Live Media
- Local Live
- Japanese Specialist atau Smart Auto
- Auto-Correct Balanced
- Language Lock OFF
- Hybrid
- VAD
- Balanced/Instant sesuai kebutuhan

Log sukses failover:
- CUDA_PREFLIGHT
- HYBRID_FAILOVER preserve_model=kotoba-bilingual
- JAPANESE_SPECIALIST_CPU_LOADING
- JAPANESE_SPECIALIST_CPU_ACTIVE
- partial / displayed

File lama SETUP_JAPANESE_SPECIALIST_V8_9_8.bat hanya redirect kompatibilitas. Nama permanen baru adalah INSTALL_JAPANESE_SPECIALIST.bat; relokasi ke Plugin dilakukan pada v9.0.0.
