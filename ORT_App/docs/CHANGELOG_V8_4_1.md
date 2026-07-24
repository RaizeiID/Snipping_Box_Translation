# ORT Translation v8.4.1 — WebUI Startup Fix

## Summary
Hotfix after v8.4 full package.

## Fixed
- Fixed a Gradio button binding error in `webui.py` that prevented the WebUI from starting:
  `event_trigger() got multiple values for argument 'outputs'`.
- The NPC cleanup button now calls only `npc_cleanup_text` and outputs to the v8 diagnostics box.
- Updated launcher console labels to v8.4.1.

## Not changed
- Fast V1/V2/Fast IDN lock remains unchanged.
- Lite IDN GPU Efficient design remains unchanged.
- Diagnose & Repair Center features remain unchanged except the WebUI can now start.
