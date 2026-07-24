ORT Translation v8.9.4 — PETUNJUK CLOUD LIVE MEDIA STREAMING
================================================================

BASIS WAJIB
-----------
Pasang paket ini di atas ORT Translation v8.9.3.

CARA MEMASANG
-------------
1. Tekan Stop, lalu tutup WebUI ORT.
2. Ekstrak ZIP v8.9.4 ke folder utama instalasi ORT v8.9.3.
3. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
4. Jangan hapus folder runtime, model, cache, log, atau konfigurasi pengguna.
5. Jalankan WebUI dan pastikan header menampilkan v8.9.4.

SETUP PERTAMA — GFL2 DUB JEPANG
-------------------------------
1. Pilih sumber Audio.
2. Jenis penggunaan: Live Media.
3. Mesin Audio: Azure + Local Fallback.
4. Bahasa suara: Japanese.
5. Perangkat fallback lokal: Hybrid; profil Normal; pemrosesan VAD.
6. Tekan Siapkan Fallback Lokal Hybrid jika status lokal belum READY.
7. Buka panel Azure Speech, lalu tekan Siapkan Runtime Azure.
8. Buat resource Azure Speech pada akun Azure Anda. Salin region dan API key
   dari Azure Portal. Jangan mengirim API key melalui chat atau memasukkannya
   ke source code.
9. Masukkan region dan API key di WebUI lokal, lalu tekan Simpan & Uji Azure.
10. Pilih perangkat WASAPI tempat suara GFL2 benar-benar keluar.
11. Tekan Mulai Audio.

KONTRAK LIVE MEDIA
------------------
Audio sistem dikirim sebagai PCM mono 16-bit 16 kHz. Azure memberikan hasil
interim selama karakter masih berbicara. Overlay menampilkan teks sementara
berwarna biru muda, lalu menggantinya dengan hasil final berwarna putih.

Log normal:

requested_engine=azure_fallback | effective_engine=azure
usage=live_media
cloud_state=CLOUD_CONNECTED | connected=1
cloud_interim | result=... | cloud_ms=...
cloud_final | result=... | cloud_ms=...

FALLBACK
--------
Jika Azure terputus dan runtime lokal tervalidasi, ORT menutup jalur cloud,
memutar ulang rolling buffer enam detik terakhir, lalu melanjutkan sesi melalui
Whisper lokal:

CLOUD_LOCAL_FAILOVER | reason=... | replay=... | effective_engine=local_fallback

Fallback tidak berpindah-pindah kembali ke cloud pada sesi yang sama. Mulai sesi
baru untuk mencoba Azure lagi.

PRIVASI DAN BIAYA
-----------------
- Audio dikirim ke Microsoft Azure ketika mesin Azure aktif.
- Penggunaan Azure Speech dapat menimbulkan biaya berdasarkan akun/resource.
- API key disimpan melalui Windows Credential Manager.
- API key tidak ditulis ke ZIP, source, preferensi WebUI, status, atau log.
- Tombol Hapus Kredensial Azure menghapus key dari Credential Manager.

FILE UJI
--------
Azure menerima file uji WAV PCM 16-bit. Gunakan mesin Local untuk MP3, M4A,
MKV, MP4, atau format lain.

ROLLBACK
--------
Timpa kembali file v8.9.3 dari paket v8.9.3. Runtime cloud, credential, model,
cache, log, status, dan data pengguna tidak dihapus oleh rollback patch.

BATAS VALIDASI
--------------
Build otomatis memvalidasi callback interim/final dengan Azure SDK tiruan,
stream PCM, deduplikasi overlay, rolling replay, failover, keamanan credential,
325 modul Python, serta delapan kelompok regresi v8.9.2–v8.9.4. Efektivitas, biaya, latensi
internet, akurasi Jepang→Indonesia, dan kestabilan sesi GFL2 nyata harus diuji
pada laptop pengguna dengan akun Azure aktif.
