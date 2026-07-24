# ORT Translation v8.9.2-R3

**Release:** Audio CPU First-Test  
**Required base:** v8.9.2-R2

## Runtime Audio

- Audio internal Windows melalui WASAPI loopback.
- File audio/video sebagai jalur uji awal.
- `faster-whisper` multilingual pada CPU INT8.
- Profil Speed/tiny, Normal/base, dan Accurate/small.
- Pemrosesan Normal dan VAD.
- Hasil ASR diterjemahkan ke English lalu memakai jalur CT2/Argos English→Indonesian yang sudah dimiliki ORT.

## Stability

- OCR dan Audio saling eksklusif pada UI dan Process Manager.
- ASR berjalan dalam virtual environment terisolasi.
- Antrean ASR dan terjemahan dibatasi agar backlog tidak membuat subtitle terlambat.
- Setiap hasil membawa generation identity; hasil lama tidak dapat menimpa dialog terbaru.
- Overlay menerapkan swap setelah terjemahan siap dan mempertahankan hasil terakhir selama pemrosesan.
- Status, event, error, model, thread, dan latensi Audio dicatat melalui jalur runtime yang ada.

## UI

Tampilan Guided & Expert v8.9.2-R2 dipertahankan. Workspace Audio yang sebelumnya preview kini menyediakan input, perangkat, bahasa, pemrosesan, profil, setup, diagnostic, dan tombol start yang nyata.

## Deferred

Isolasi Suara/source separation belum diaktifkan. Kontrolnya tetap diberi label `Belum aktif` sampai pemisahan BGM/SFX memiliki model, benchmark, dan fallback yang aman.
