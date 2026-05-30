# TITANCORE V2 — Shortcuts & Model Guide (Update 6.4-IDN-1)

## Tujuan update ini
Menambah *shortcut runner* (CMD/PowerShell) untuk semua model yang sebelumnya belum ada, plus menambah varian ***_IDN** (naturalisasi Bahasa Indonesia) untuk V1–V4.

## Versi / Paket
- Pack: **TitanCore_V2 + IDN MultiModel**
- Versi: **6.4-IDN-1**
- Tanggal: **2026-01-05**


## Pembaruan global (semua model, bukan hanya *_IDN)
- Patch `_safe_save_json` di `TitanMainV1.py`, `TitanMainV2.py`, `TITANMAIN.py` untuk mencegah crash saat save cache.

## Pembaruan global yang diterapkan ke semua *_IDN (V1–V4)
1) **Indonesian Naturalizer (evolving)**  
   - File: `TitanIndonesianLocalizer.py`  
   - Menjadikan hasil terjemahan lebih natural untuk pembaca Indonesia (tidak kaku/aneh).
   - Belajar dari pemakaian (statistik) dan memunculkan aturan ke `titan_idn_auto_rules.json`.
   - Manual override: `titan_idn_rules.json`  
   ENV:
   - `TITAN_IDN_STYLE=neutral|formal|casual`
   - `TITAN_IDN_LOCALIZE=1/0`

2) **Game Name Classifier (roster-based)**  
   - File: `TitanGameNameClassifier.py`
   - Mengunci “nama-nama familiar” per game agar tidak nyasar cross-game.
   - Roster seed: `titan_game_rosters.json`

3) **Proteksi UNIQUE_TERMS**  
   - File: `TitanIDN_Shared.py`
   - Token ⟦UTx⟧ supaya istilah game tidak diubah oleh naturalizer.

4) **Fix crash save cache**  
   - Patch `_safe_save_json` (copy dict/list dulu) untuk mencegah:
     `dictionary changed size during iteration`

## Perubahan khusus V4_IDN
- **MS & PING dipisah** jadi 2 bingkai sejajar (tidak overlap).
- Router V4 “middle-ground”: online-first + fallback offline (latency rendah tapi tetap akurat).

## Daftar shortcut (runner)
> Semua runner ada versi `.cmd`. Beberapa juga ada `.ps1`.

### Utama
- `Run_TITANMAIN.cmd` — entry main
- `Run_MODE_DEBUG.cmd` — debug import semua core

### Model original
- `Run_TitanMainV1.cmd`
- `Run_TitanMainV2.cmd`
- `Run_TitanMainV3_OptionA_FRAMED.cmd`, `...B...`, `...C...`
- `Run_TitanMainV3Lite_OptionA_FRAMED.cmd`, `...B...`, `...C...`
- `Run_TitanMainV4.cmd` (original, full ENV)
- `Run_TitanMainV4_Quick.cmd` (pakai python PATH, ENV minimal)

### Model naturalisasi (IDN)
- `Run_TitanMainV1_IDN.cmd`
- `Run_TitanMainV2_IDN.cmd`
- `Run_TitanMainV3_IDN.cmd`  (default OptionC, override via `TITAN_V3_OPTION=A/B/C`)
- `Run_TitanMainV3Lite_IDN.cmd` (default OptionC)
- `Run_TitanMainV4_IDN.cmd`

## Catatan penting
- Runner `.cmd` memakai `python` dari PATH. Jika kamu pakai Python portable / path khusus, edit runner.
- Engine online (Libre/GAS/DEEPLX) pakai ENV; contoh ada di `Run_TitanMainV4.cmd`.
