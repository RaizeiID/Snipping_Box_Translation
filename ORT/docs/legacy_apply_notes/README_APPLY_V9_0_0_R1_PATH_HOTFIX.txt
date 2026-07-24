ORT v9.0.0 R1 — Windows Project-Root Path Hotfix

Base required: ORT v9.0.0 patch already extracted.
Version remains: v9.0.0

Fixes:
- Removes the trailing-backslash quote parsing bug in ORT v9 Setup.bat.
- Normalizes orphan quote characters in migrate_v9_structure.py.
- Prevents migration-report logging from hiding the original exception.
- Updates v9 checksum expectations for the two corrected files.

Apply:
1. Close ORT/WebUI/Python processes.
2. Extract this ZIP into the project root and choose Replace.
3. Run ORT v9 Setup.bat again.
4. Run ORT\maintenance\VERIFY_ORT_V9_0_0.bat.
