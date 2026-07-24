from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.open_architecture.lab import architecture_apply_preset, architecture_compare_presets, confirmed_prefix_demo
from app.open_architecture.pipeline import presets, validate_selections
from build_info import APP_VERSION_TAG, PROJECT_LAYOUT_SCHEMA_VERSION


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.0"
    assert PROJECT_LAYOUT_SCHEMA_VERSION == 9
    ids = {item.preset_id for item in presets()}
    assert {"original_audio", "original_ocr", "japanese_accuracy_lab", "long_dialogue_lab"}.issubset(ids)
    for item in presets():
        valid, errors = validate_selections(item.selections())
        assert valid, (item.preset_id, errors)
        payload = architecture_apply_preset(item.preset_id)
        assert len(payload) == 10
        parsed = json.loads(payload[8])
        assert parsed["production_pipeline_untouched"] is True
    comparison = architecture_compare_presets("original_audio", "japanese_safe_bridge")
    assert "Confirmed Prefix" in comparison
    table, raw = confirmed_prefix_demo("Thank you\nThank you for waiting\nThank you for waiting, gentlemen.", 2)
    rows = json.loads(raw)
    assert rows[-1]["confirmed"] == "Thank you for waiting, gentlemen."
    assert "<table" in table
    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    assert 'with gr.Tab("Open Architecture Lab")' in webui
    assert "ort original tetap utuh" in webui.lower()
    print("ORT v9.0.0 Open Architecture/Layout regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
