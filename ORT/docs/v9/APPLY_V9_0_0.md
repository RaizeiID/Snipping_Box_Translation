# Apply ORT v9.0.0

Base required: ORT v8.9.9 R2 F2.

1. Close every ORT process.
2. Extract the changed-files patch into the existing project root and replace files.
3. Run `ORT v9 Setup.bat`.
4. Let the migration move `ORT/runtime_app` to `ORT_App` and organize root artifacts.
5. Run `ORT/maintenance/VERIFY_ORT_V9_0_0.bat`.
6. Start with `START_HERE.bat`.

Do not delete `ORT_Runtime`; it contains the existing environments, CUDA packages, and downloaded models.
