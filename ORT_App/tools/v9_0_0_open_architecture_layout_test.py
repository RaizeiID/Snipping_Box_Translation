from __future__ import annotations

import json
import sys
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.open_architecture.lab import architecture_apply_preset, architecture_compare_presets, confirmed_prefix_demo
from app.open_architecture.pipeline import presets, validate_selections
from app.open_architecture.executor import architecture_runtime_validation
from app.open_architecture.streaming.confirmed_prefix import ConfirmedPrefixEngine
from build_info import APP_VERSION_TAG, PROJECT_LAYOUT_SCHEMA_VERSION


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.4"
    assert PROJECT_LAYOUT_SCHEMA_VERSION == 9
    ids = {item.preset_id for item in presets()}
    assert {"original_audio", "original_ocr", "japanese_live_lab", "japanese_accuracy_lab", "long_dialogue_lab"}.issubset(ids)
    for item in presets():
        valid, errors = validate_selections(item.selections())
        assert valid, (item.preset_id, errors)
        payload = architecture_apply_preset(item.preset_id)
        assert len(payload) == 10
        parsed = json.loads(payload[8])
        assert parsed["production_pipeline_untouched"] is True
    comparison = architecture_compare_presets("original_audio", "japanese_safe_bridge")
    assert "Confirmed Prefix" in comparison
    runtime_preset = next(item for item in presets() if item.preset_id == "japanese_live_lab")
    runtime_report = architecture_runtime_validation(
        **runtime_preset.selections(),
        language="ja_specialist",
        agreement_passes=2,
    )
    assert runtime_report.ready, runtime_report.errors
    cjk_engine = ConfirmedPrefixEngine(agreement_passes=2)
    first = cjk_engine.update("私たちは", final=False)
    second = cjk_engine.update("私たちはここを", final=False)
    final = cjk_engine.update("私たちはここを離れる", final=True)
    assert first["display"] == "私たちは"
    assert second["confirmed"] == "私たちは"
    assert final["display"] == "私たちはここを離れる"
    table, raw = confirmed_prefix_demo("Thank you\nThank you for waiting\nThank you for waiting, gentlemen.", 2)
    rows = json.loads(raw)
    assert rows[-1]["confirmed"] == "Thank you for waiting, gentlemen."
    assert "<table" in table
    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    assert 'with gr.Tab("Open Architecture Lab")' in webui
    assert "preload & mulai audio lab" in webui.lower()
    assert "copy log lab" in webui.lower()
    assert "developer workspace" in webui.lower()
    assert '("Developer", "developer")' in webui
    print("ORT v9.0.4 Open Architecture/Layout regression: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
