# ORT v8.9.2-R6 Audio Native Crash Isolation Validation Report

## Target

Mencegah Windows exit `3221225477 / 0xC0000005` setelah transkrip pertama menutup Mode Audio, sambil mempertahankan UI, profil, pengaturan, dan pipeline OCR yang ada.

## Diagnosis berbasis log

- ASR model `base` berhasil dimuat secara lokal pada CPU INT8.
- WASAPI DAXA SL1 berhasil masuk keadaan `LISTENING`.
- Beberapa segmen berhasil ditranskripsi, termasuk hasil non-kosong.
- Proses selesai tepat setelah event transcript dan sebelum event display.
- Tidak ada pesan sidecar ASR berhenti sebelum WebUI melaporkan proses utama selesai.
- Kode desimal `3221225477` setara dengan `0xC0000005`.

Kesimpulan kerja: pemicu berada pada batas inisialisasi/eksekusi pertama ORTCore Fast V2/CTranslate2 di thread penerjemahan proses PyQt. Karena kesalahan native tidak dapat ditangkap oleh `try/except`, batas isolasi proses diperlukan.

## Validasi otomatis

- Release identity R6: PASS.
- Parent tidak mengimpor atau membuat TranslationEngine native: PASS.
- Translation sidecar stdin/stdout JSON protocol: PASS.
- Primary CT2 process preload sebelum ASR start: PASS.
- Packed GEMM disabled khusus Audio Translation: PASS.
- Signed/unsigned `0xC0000005` normalization: PASS.
- Simulasi process crash dan restart safe Argos: PASS.
- Replay transcript aktif dengan generation identity: PASS.
- Latest-only pending dan single in-flight contract: PASS.
- Stale result guard: PASS.
- R5 model compatibility regression: PASS.
- R4 model recovery regression: PASS.
- R3 Audio CPU regression: PASS.
- R2 Guided/Expert UI regression: PASS.
- v8.9.2 core regression: PASS.

## Batas validasi

Container pengujian bukan Windows dan tidak memiliki perangkat WASAPI pengguna. Karena itu, pengujian memastikan isolasi, protokol, recovery, dan regresi secara deterministik; verifikasi akhir bahwa fault native spesifik perangkat tidak lagi memutus sesi harus dilakukan pada instalasi Windows pengguna.
