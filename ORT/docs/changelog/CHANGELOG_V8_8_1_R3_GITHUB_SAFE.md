# ORT Translation v8.8.1 R3 — GitHub Safe Upload Protection

## Fokus R3
R3 menambahkan proteksi agar folder runtime/cache/log/model besar tidak ikut terupload ke GitHub saat memakai VSCode.

## Perubahan
- Menambahkan `.gitignore` di root project.
- Menambahkan `ORT/.gitignore` untuk keamanan jika repo dibuka langsung dari folder ORT.
- Menambahkan `.gitattributes`.
- Memperbarui `EXPORT_GITHUB_SOURCE.bat` agar membuat ZIP source GitHub yang otomatis mengecualikan folder lokal/berat.
- Menambahkan `CHECK_GITHUB_READY.bat`.
- Menambahkan `UNTRACK_LOCAL_RUNTIME_FROM_GIT.bat`.
- Menambahkan panduan `ORT/docs/user_guide/GITHUB_UPLOAD_GUIDE_V8_8_1_R3.md`.
- Menambahkan contoh setting VSCode `.vscode/settings.example.json`.

## Yang tidak diubah
- OCR behavior.
- Auto/Freeze/Interval behavior.
- Translation engine.
- Scheduler.
- Overlay.
- Cache namespace.

R3 masih termasuk structural refactor/support tooling, bukan runtime behavior refactor.
