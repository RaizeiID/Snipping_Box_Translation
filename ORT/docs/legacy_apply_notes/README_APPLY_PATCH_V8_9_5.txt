ORT Translation v8.9.5 — Real-Time Video Translation Update
============================================================

BASIS WAJIB
-----------
Terapkan patch ini di atas instalasi ORT Translation v8.9.4 yang LENGKAP.
Paket ini hanya berisi file baru/berubah dan bukan full project.

CARA MEMASANG
-------------
1. Tutup WebUI, OCR, dan Audio ORT.
2. Backup folder ORT Translation aktif.
3. Ekstrak ZIP patch ke root instalasi ORT v8.9.4.
4. Pilih Replace/Timpa ketika Windows meminta konfirmasi.
5. Jalankan START_HERE.bat atau Start WebUI.bat.
6. Pada Audio pilih:
   - Jenis penggunaan: Live Media
   - Mesin: Azure + Local Fallback
   - Bahasa: Japanese untuk GFL2
   - Respons subtitle: Instant untuk latensi minimum atau Balanced untuk rekomendasi awal
7. Jalankan Siapkan Runtime Azure kembali agar dependency requirement terbaru diverifikasi.

HASIL YANG DIHARAPKAN
---------------------
- Subtitle mulai diperbarui ketika karakter masih berbicara.
- Overlay memakai satu baris sementara, kemudian menguncinya sebagai final.
- Program tidak menunggu potongan 4,8 detik.
- Status berurutan CONNECTING → CLOUD_CONNECTED → STREAMING.
- Kalimat terakhir tetap keluar setelah EOF/Stop.
- Dialog sama dari karakter/result berbeda tidak dihapus sebagai duplikat.

CATATAN PENGUJIAN
-----------------
Mulai dengan GFL2 Jepang dan satu cuplikan film Inggris yang sama seperti pengujian v8.9.4.
Simpan Live Log. Perhatikan nilai cloud_connect_ms, first_interim_ms, first_final_ms,
segmentation_silence_ms, segmentation_maximum_ms, interim_count, dan final_count.

KEAMANAN
--------
API key tidak disertakan. API key keyring dapat dihapus dari UI. Jika key berasal dari
ORT_AZURE_SPEECH_KEY environment, aplikasi akan menjelaskan bahwa key tersebut masih aktif
dan harus dihapus dari Environment Variables Windows secara manual.

BATASAN
-------
Cara kerja dibuat menyerupai penerjemah video langsung pada HP, tetapi tidak menyalin mesin
privat Xiaomi/Google/Samsung. Efektivitas nyata tetap bergantung pada Azure, internet,
kualitas audio, bahasa sumber, glosarium, dan adegan yang diuji.
