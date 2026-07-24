# ORT Translation v7 Complete Folder

Ini adalah paket lengkap v7 berbasis v6.6 yang sudah digabung dengan refactor profil game, rekomendasi hardware, dan safe mode untuk game berat.

## Cara menjalankan

1. Ekstrak folder `ORT_Translation_v7`.
2. Jalankan `Start_ORT_Translation.bat`.
3. Pilih lokasi runtime seperti biasa.
4. Buka Dashboard WebUI.
5. Pilih `Nama Game`:
   - `Girls' Frontline 2 Exilium` untuk profil Balanced.
   - `Wuthering Waves` untuk profil Heavy/Safe Game.
   - `Custom / Game Lain` untuk profil netral.
6. Klik `Terapkan Rekomendasi Profil`, lalu `Start`.

## Perubahan sistem utama v7

- `model_registry.py` menjadi sumber utama daftar model.
- `launcher_backend.py` mengirim preset engine/mode/interval/OCR resolution dari WebUI ke runtime.
- `TITANMAIN.py` menghormati engine pilihan WebUI; tidak lagi memaksa AUTO_GPU saat boot.
- `v7_system_profile.py` mendeteksi hardware dan menyusun rekomendasi game/profile.
- WebUI memiliki game profile untuk GFL2, Wuthering Waves, dan Custom.
- Wuthering Waves otomatis diarahkan ke CPU + Lite/Fast + interval tinggi jika sistem terdeteksi berisiko overload.
- User tetap dapat memilih Normal Override.
- Live Log utuh selama sesi berjalan dan reset hanya saat Start sesi baru.
- AI Recap dipindahkan ke Dashboard dekat Live Log.
- Runtime & Tools tetap fokus pada runtime dan GPU tools.
- Candidate duplicate feedback dan confirmed log diperjelas.

## Rekomendasi untuk laptop Acer Predator Helios Neo PHN16-71, RAM 64GB, RTX 4050 6GB

- GFL2 Exilium: `ORTCore V2` / Hybrid / Interval / OCR 70%.
- Wuthering Waves: `ORTCore Lite V2` atau `ORTCore Fast V2` / CPU / Interval 450ms / OCR 55%.
- Jangan gunakan GPU OCR untuk Wuthering Waves kecuali VRAM longgar dan game terasa stabil.

## Catatan batas aman

Bagian berikut tetap tidak dirombak besar agar tidak merusak pengalaman runtime:

- UI box terjemahan utama.
- Indikator ping/ms/game/engine.
- Shortcut utama F1-F11/ESC.
- Struktur overlay utama.

Perombakan v7 berfokus pada WebUI, launcher, model registry, profil game, dan pengaturan runtime.
