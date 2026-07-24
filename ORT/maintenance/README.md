# ORT Maintenance

Daily users should start ORT from the project root. This folder contains verification, source export, repair, and legacy maintenance tools so the root remains clean.

- `VERIFY_ORT_V9_0_0.bat` validates the source and structure.
- `EXPORT_ORT_SOURCE_LIGHT.bat` creates a shareable source ZIP without runtime/models/logs/cache.
- `legacy_v8/` is created by the migration script for old patch installers and verifiers.
