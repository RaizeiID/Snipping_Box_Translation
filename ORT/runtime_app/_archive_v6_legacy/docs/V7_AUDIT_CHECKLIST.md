# V7 Audit Checklist

Checklist ini dibuat untuk memastikan 11 temuan utama dari audit v6.6 sudah masuk ke v7.

| No | Temuan v6.6 | Status v7 |
|---:|---|---|
| 1 | Engine WebUI diabaikan karena boot memaksa AUTO_GPU | Diperbaiki di `TITANMAIN.py` dan `launcher_backend.py` |
| 2 | Belum ada Heavy Game Safe Mode | Ditambahkan via `v7_system_profile.py` dan Dashboard |
| 3 | OCR resolution belum menjadi kontrol nyata | Ditambahkan slider WebUI dan env `ORT_OCR_RESOLUTION_PERCENT` |
| 4 | VRAM guard terlalu reaktif | Ditambahkan threshold profil, WUWA default CPU/Safe Game |
| 5 | Resource/throttle belum menyatu penuh | Preset v7 mengatur interval, queue, CPU threads, scan sleep; modul lama tetap tersedia |
| 6 | Wuthering Waves ada di data tapi tidak di WebUI | Ditambahkan sebagai pilihan game resmi |
| 7 | AI Recap salah tempat di Runtime & Tools | Dipindah ke Dashboard dekat Live Log |
| 8 | Confirmed log belum tampil di UI | Ditampilkan di tab Kandidat Baru |
| 9 | Duplicate feedback belum jelas | `add_items_with_feedback` dipakai untuk confirm/manual add |
| 10 | Wrapper model V5 Lv3/Lv4 mengarah ke target hilang | Semua wrapper V5 Lv diarahkan ke `TITANMAIN.py` |
| 11 | Registry model tidak jadi sumber utama | `model_registry.py` dipakai WebUI, launcher backend, dan terminal launcher |

## Catatan

Beberapa file Python lama tetap disertakan sebagai legacy/komponen eksperimen agar kompatibilitas tidak rusak. Jalur utama v7 adalah:

`Start_ORT_Translation.bat` → `webui.py` → `launcher_backend.py` → `model_registry.py` + `v7_system_profile.py` → `TITANMAIN.py`
