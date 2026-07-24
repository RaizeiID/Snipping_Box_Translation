# ORT v8.9.1 Test Report

## Tes yang dijalankan
- `python -m py_compile` pada modul yang berubah.
- `python tools/v8_9_1_regression_test.py`
- `python tools/v8_8_9_regression_test.py`
- ZIP integrity test untuk changed-files patch dan full project.

## Hasil
- Compile changed modules: PASS
- v8.9.1 hotfix regression: PASS
- v8.8.9 regression: PASS
- ZIP integrity: PASS

## Coverage test v8.9.1
- `Sweeper` exact speaker resolves Green.
- `Klukai` exact speaker resolves.
- Launcher default registry tidak lagi menunjuk v8.8.8-r2.
- English source preview default disilence, bukan ditampilkan sebagai placeholder.
- UI leakage dari log v8.9.0 (`Coading Resources`, `Marionette Repalr`, mixed-script garbage) diblok.
- OCR repair umum tetap aktif (`Qur`, `healin9`, `Ifnot`, `callyoU`, `must'ye`, `weve`).

## Known limitation
- Hotfix ini tidak mengubah model translation. Jika final IDN masih terlambat pada dialog sangat panjang, overlay akan menunggu/silent pending daripada menampilkan English/placeholder.
