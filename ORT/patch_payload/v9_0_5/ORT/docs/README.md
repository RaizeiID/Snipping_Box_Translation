# ORT Translation v9.0.5

**Release:** Engineering Baseline & Resilient Provider Setup
**Base:** ORT v8.9.9 R2 F2
**Migration model:** original OCR/audio pipeline preserved; Open Architecture Lab isolated.

## Install / update

1. Close WebUI, overlay, audio processes, and every ORT Python process.
2. Extract this changed-files patch over the existing project.
3. Run `ORT v9 Setup.bat` once.
4. The setup moves `ORT/runtime_app` to the surface folder `ORT_App` and organizes generated/local files.
5. Start the program through `START_HERE.bat` or `Start WebUI.bat`.

## Clean root layout

After migration, the project root contains only daily launchers and the version marker:

```text
ORT_Translation/
├── START_HERE.bat
├── Start WebUI.bat
├── Start OCR.bat
├── Runtime.bat
├── ORT v9 Setup.bat
├── VERSION.txt
├── ORT_App/                 # Application source and required small assets
├── ORT_Runtime/             # Python environments, CUDA packages, models, spool (>1 GB possible)
└── ORT/                     # Lightweight support area
    ├── docs/
    ├── plugins/
    ├── logs/
    ├── cache/
    ├── status/
    ├── user_data/
    ├── maintenance/
    ├── exports/
    ├── release/
    └── config/
```

`ORT_Runtime` must not be included when sharing source or uploading a ZIP for review.

## Open Architecture Lab

The new WebUI tab provides an isolated architecture workspace with:

- provider registry and availability checks;
- ORT Native / Adapted Open Source / External Connector labels;
- provider license information;
- Original Audio/OCR baselines;
- Japanese Accuracy, Long Dialogue, and OCR Research presets;
- Confirmed Prefix / Local Agreement deterministic demo;
- A/B architecture comparison;
- custom preset storage and JSON export.

The Lab does **not** silently replace the production pipeline. The original OCR/audio pipeline remains the active baseline.

## Open-source integration policy

- MIT/permissive components are integrated through clean ORT adapters.
- GPL applications such as Textractor or LunaTranslator remain external processes and communicate through clipboard, pipe, localhost, or WebSocket adapters.
- Models, dependencies, and third-party runtime files remain in `ORT_Runtime`.
- Attribution and provider metadata are stored under `ORT/plugins/open_architecture`.

## Share a lightweight source package

Run:

```text
START_HERE.bat → Export source ringan untuk dibagikan
```

or:

```text
ORT\maintenance\EXPORT_ORT_SOURCE_LIGHT.bat
```

The exporter excludes runtime environments, models, logs, cache, status, user data, credentials, archives, and files larger than 25 MB. The ZIP is written to `ORT/exports`.

## Verification

Run:

```text
ORT\maintenance\VERIFY_ORT_V9_0_5.bat
```

The verifier checks version consistency, source compilation, Open Architecture imports, confirmed-prefix behavior, migration state, and package checksums.
