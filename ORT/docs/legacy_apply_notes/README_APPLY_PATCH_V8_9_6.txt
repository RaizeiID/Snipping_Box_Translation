ORT Translation v8.9.6 — Real-Time Cloud Enforcement Update
============================================================

Basis pemasangan:
- Terapkan di atas ORT Translation v8.9.5 yang lengkap.
- Paket ini hanya membawa file yang berubah.

Masalah yang diperbaiki:
- Pada v8.9.5, pilihan Azure + Local Fallback dapat diam-diam berubah menjadi
  effective_engine=local_guard apabila Azure belum siap.
- Local guard memakai Faster-Whisper per segmen, sehingga hasil baru muncul setelah
  jeda/akhir ucapan dan terasa sama seperti versi lama.

Perilaku v8.9.6:
1. Live Media + Azure/Azure Fallback wajib lulus uji koneksi Azure saat Start.
2. Jika Azure belum siap atau tidak terhubung, sesi diblokir dengan penjelasan rinci.
3. ORT tidak lagi menyamarkan local_guard sebagai mode real-time.
4. Local fallback baru aktif setelah sesi cloud real-time sempat berjalan lalu gagal.
5. Mode Local tetap tersedia bila dipilih secara eksplisit, tetapi diberi label bahwa
   ia bekerja per segmen dan bukan subtitle video real-time.

Cara memasang:
1. Tutup WebUI dan seluruh proses ORT.
2. Ekstrak ZIP ini ke folder instalasi ORT v8.9.5.
3. Pilih Replace/Timpa untuk file yang sama.
4. Buka WebUI.
5. Pada Audio, tekan Siapkan Runtime Azure.
6. Simpan region dan API key melalui Simpan & Uji Azure.
7. Pastikan status menampilkan cloud_connected=True.
8. Pilih Live Media + Azure + Local Fallback dan mulai Audio.

Tanda sesi real-time benar-benar aktif pada log:
- effective_engine=azure
- cloud_ready=1
- CLOUD_CONNECTED
- STREAMING
- cloud_interim selama karakter masih berbicara
- cloud_final setelah frasa dikunci

Jika log masih menampilkan local_guard, cpu_guard, atau asr_state=TRANSCRIBING
berdurasi beberapa detik, sesi tersebut bukan jalur real-time cloud.
