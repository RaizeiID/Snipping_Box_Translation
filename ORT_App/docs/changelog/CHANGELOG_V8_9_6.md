# ORT v8.9.6 — Real-Time Cloud Enforcement

Live Media real-time sekarang bersifat fail-closed pada startup. Ketika Azure tidak
siap, ORT menampilkan error dan tidak menjalankan Faster-Whisper lokal dengan label
Azure fallback. Local fallback tetap tersedia sesudah cloud session aktif dan kemudian
mengalami gangguan.

Log sesi yang sah harus memperlihatkan `effective_engine=azure`, `CLOUD_CONNECTED`,
`STREAMING`, serta callback `cloud_interim` dan `cloud_final`.
