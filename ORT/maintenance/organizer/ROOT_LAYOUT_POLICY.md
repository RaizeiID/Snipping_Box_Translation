# ORT Root Layout Policy

Root ORT hanya digunakan untuk komponen aktif dan launcher utama.

## Tetap berada di root

- VERSION.txt
- README.md
- START_HERE.bat
- Start WebUI.bat
- Start OCR.bat
- Runtime.bat
- ORT v9 Setup.bat
- ORT_App/
- ORT_Runtime/
- ORT/
- models/
- .git* dan .vscode/

## Lokasi artefak versi

- Laporan versi: ORT/release/<version>/reports/
- Manifest/checksum: ORT/release/<version>/manifests/
- Patch lama: ORT/archive/version_updates/<timestamp>/patch_files/
- Paket update: ORT/archive/version_updates/<timestamp>/patch_packages/
- Diagnostic manual: ORT/debug_bundles/manual/<timestamp>/
- Receipt dan rollback: ORT/maintenance/organizer/

## Aturan

1. Update versi harus menulis source aktif langsung ke ORT_App.
2. Runtime dan model hanya berada di ORT_Runtime atau models.
3. Patch/applicator tidak boleh menjadi dependency runtime.
4. Launcher root tidak boleh mengarah ke folder patch atau backup.
5. Folder ORT/backups tidak dihapus otomatis.
