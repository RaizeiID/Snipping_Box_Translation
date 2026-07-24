# ORT Translation v8.9.0 — Overlay Stability, OCR Repair & Runtime Hardening

Tanggal: 2026-06-03

## Fokus utama
v8.9.0 adalah stabilization update. Update ini tidak mengejar fitur baru besar, melainkan menutup masalah user-facing dari v8.8.9: overlay berkedip, source/English preview bocor, Prediction/Repair Text belum cukup luas, dan metode OCR low-level readability perlu diperluas secara aman.

## Perubahan utama

### 1. Stop English leak di overlay
- Raw source fallback tidak lagi ditampilkan di overlay user-facing secara default.
- Saat final Indonesia belum siap, overlay menampilkan preview Indonesia: `Menerjemahkan dialog baru…`.
- Raw source tetap tersedia di log/debug.
- Env override: `ORT_OVERLAY_ALLOW_ENGLISH_SOURCE=1` untuk debug.

### 2. Overlay stability hardening
- Legacy repaint-last-good dari v8.8.8-r2 diblokir default melalui `ORT_V890_ALLOW_LEGACY_REPAINT=0`.
- New-turn Indonesian preview dianggap meaningful sehingga bisa mengganti overlay lama.
- Mengurangi risiko dialog lama menimpa dialog baru.

### 3. Contextual OCR Repair v3
Menambahkan repair guarded untuk kata umum yang sering salah OCR:
- `Qur -> our`
- `healin9/healng/healln9 -> healing`
- `Ifnot -> If not`
- `ook at -> look at`
- `callyoU -> call you`
- `must'ye -> must've`
- `weve -> we've`
- `telljust -> tell just`

Repair ini deterministic dan token-bounded, bukan autocorrect bebas.

### 4. OCR Readability Enhancement v2
- Menambahkan CLAHE contrast ringan dan unsharp mask konservatif pada OCR profile <=55% secara default.
- Tidak menaikkan global OCR 40-50% ke 55/60%.
- Env:
  - `ORT_OCR_READABILITY_ENHANCE=1/0`
  - `ORT_OCR_READABILITY_ENHANCE_SCOPE=low/all`
  - `ORT_OCR_READABILITY_ENHANCE_MAX_PERCENT=55`

### 5. UI Filter v4
Menambah filter untuk menu/battle/progress yang bocor:
- Toysmith / Max Level / Commander Level
- Dammage/Damage Stats Confirm
- Clickanywhere to exit
- End Action
- Formation / Commission / Platoon
- Marionette Melee
- numeric slash stats seperti `3821/3821`

### 6. Entity registry v8.9.0
Menambahkan/menjaga entity baru dari log v8.8.9:
- `Littara`
- `Ullrid`
- `Phaetusa`
- `Sweeper`
- `Nyxie`

Alias seperti `UIlr -> Ullrid` dibuat guarded/Yellow agar tidak menjadi auto-hallucination global.

## Known issue tersisa
- v8.9.0 masih perlu live test untuk mengukur apakah final Indonesia sudah cukup dominan menggantikan preview.
- Jika waiting preview terlalu sering, tahap berikutnya perlu mempercepat quick-ID preview/final CT2, bukan mengembalikan raw English source.


## v8.9.0 UI Version Label Hotfix
- Memperbarui judul/header WebUI dari label lama ke `ORT Translation v8.9.0`.
- Memperbarui log WebUI, launcher state, Fast engine status, dan translation engine metadata agar tidak menampilkan `v8.8.8-r2` pada runtime user-facing.
- Menambahkan aturan validasi: setiap release wajib melakukan global version-label search sebelum ZIP final dibuat.
