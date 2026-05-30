# ORT Translation v7 Patch

Update v7 berfokus pada profil game, deteksi spesifikasi laptop, rekomendasi model, dan mode hemat resource untuk game berat.

## Perubahan utama

- Dashboard v7 dengan profil game terpisah untuk GFL2 Exilium, Wuthering Waves, dan Custom.
- Deteksi spesifikasi laptop sederhana melalui `nvidia-smi`, `wmic`, dan `psutil` bila tersedia.
- Rekomendasi otomatis model/mode/engine/interval/OCR resolution berdasarkan game dan risiko hardware.
- Grup model baru:
  - Normal V1–V5
  - Lite V1–V5
  - IDN V1–V5
  - Lite IDN V1–V5
  - Fast V1/Fast V2/Fast IDN
- Wuthering Waves diarahkan ke Safe Game saat VRAM/RAM berpotensi berat.
- User tetap bisa memaksa Normal Override dari Dashboard.
- `TITANMAIN.py` sekarang menghormati pilihan engine dari WebUI dan tidak memaksa AUTO_GPU saat boot.
- OCR resolution dapat dikontrol dari Dashboard.
- Live Log tidak dipangkas selama sesi berjalan; reset terjadi saat Start sesi baru.
- AI Recap dipindahkan ke Dashboard dekat Live Log.
- Runtime & Tools tetap fokus untuk runtime dan GPU.
- Confirmed candidate log tampil di Kandidat Baru.
- Duplicate feedback memakai `add_items_with_feedback`.
- Wrapper `ORTCore_V5_Lv*.py` diarahkan kembali ke `TITANMAIN.py` agar tidak gagal karena target lama hilang.

## Catatan aman

Patch ini tidak dimaksudkan untuk merombak UI box terjemahan utama atau indikator ping/ms/game/engine. Perubahan difokuskan pada WebUI, launcher, registry model, dan preset runtime.


## Paket lengkap

Untuk v7 ini juga tersedia `README_V7_FULL.md` dan `V7_AUDIT_CHECKLIST.md`. Paket complete folder menyertakan semua file project, bukan hanya file yang berubah.
