# v8.7.9 → v8.8.1 Structure Map

v8.8.1 is a structural refactor. Runtime behavior is preserved through a compatibility folder.

## Main mapping

| v8.7.9 location | v8.8.1 location |
|---|---|
| Root runtime files (`webui.py`, `TITANMAIN.py`, `translation_engine.py`, etc.) | `ORT/runtime_app/` |
| `app/` | `ORT/runtime_app/app/` |
| `configs/` | `ORT/runtime_app/configs/` |
| `tools/` | `ORT/runtime_app/tools/` |
| `docs/` | `ORT/runtime_app/docs/` plus curated docs in `ORT/docs/` |
| `logs/` | cleaned runtime folder `ORT/runtime_app/logs/` |
| `cache/` | cleaned runtime folder `ORT/runtime_app/cache/` |
| `backups/` | cleaned runtime folder `ORT/runtime_app/backups/` |
| Root launchers | new root launchers: `START_HERE.bat`, `Start WebUI.bat`, `Start OCR.bat`, `Runtime.bat` |

## Why compatibility folder?

Many legacy modules still use relative imports and expect the runtime current working directory to contain config files and support folders. Moving every `.py` file into a fully modular source layout in one update would risk breaking import paths. v8.8.1 therefore cleans the user-facing project root first, while keeping the proven runtime structure intact inside `ORT/runtime_app/`.

## Next refactor stage

v8.8.2 should refactor behavior and policy: Auto Smooth, Freeze Ultra OCR, Interval Stable/Story-aware, Turn Transcript Accumulator, and Overlay Anti-Flicker.
