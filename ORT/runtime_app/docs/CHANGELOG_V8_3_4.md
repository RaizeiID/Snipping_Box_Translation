## v8.3.4 - Fast Final Lock & Auto Preset UX Patch

Date: 2026-05-20  
Type: final v8.3 tuning / WebUI UX / Fast Lock  
Base: v8.3.3

### Summary
- Finalizes the v8.3 Fast optimization line before v8.4.
- Replaces manual "Save Default" with automatic per-model preset memory.
- Adds orange **• Modification** badge under the selected model when a custom default is active.
- Keeps only a red oval **Reset Default** action, visible only when the model has custom settings.
- Adds Fast Lock documentation so v8.4 can optimize Lite IDN/OCR/Diagnose without accidentally changing Fast behavior.
- Adds Fast lightweight post-processing guard to reduce rare latency spikes from heavyweight bridge post-process cores.

### Locked Fast behavior
- Fast V1 remains speed-first.
- Fast V2 remains balanced.
- Fast IDN remains Fast V2-like + lightweight Indonesian naturalizer.
- Fast CT2 path remains shared and must not fallback silently if model files are valid.

### Validation
- Changed Python files compile successfully with 0 syntax errors.
