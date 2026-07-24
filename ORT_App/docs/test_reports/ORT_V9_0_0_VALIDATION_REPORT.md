# ORT v9.0.0 Validation Report

Validation scope:

- Python compilation for Open Architecture modules and modified WebUI.
- Provider registry/preset integrity.
- Confirmed Prefix deterministic behavior.
- Root launcher compatibility with `ORT_App` and legacy `ORT/runtime_app`.
- Migration test on an isolated project copy.
- Source-light ZIP export test.
- Version/checksum verification.

Actual Windows junction creation, Gradio launch, and existing local runtime/model performance must be validated on the user's Windows installation after migration.
