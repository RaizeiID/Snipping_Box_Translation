from __future__ import annotations
from typing import Dict, Any

def evaluate_safe_mode(game: str, engine: str, model_group: str, vram_gb: float | None = None, settings_mode: str = "recommended") -> Dict[str, Any]:
    heavy = (game or "").upper() in {"WUWA", "WUTHERING_WAVES"}
    lite = "lite" in (model_group or "").lower()
    warnings = []
    if heavy and engine.lower() in {"gpu", "hybrid"} and not lite:
        warnings.append("Game berat memakai GPU/Hybrid pada model non-Lite. Pastikan VRAM cukup; rekomendasi default CPU/Lite.")
    if heavy and lite and engine.lower() in {"gpu", "hybrid"}:
        warnings.append("v8.4: Lite/Lite IDN boleh memakai GPU Efficient pada game berat; pastikan VRAM guard aktif.")
    if vram_gb is not None and vram_gb <= 6 and heavy and engine.lower() != "cpu" and not lite:
        warnings.append("VRAM <= 6GB terdeteksi; model non-Lite sebaiknya CPU/Safe untuk Wuthering Waves.")
    return {"heavy_game": heavy, "safe": not warnings, "warnings": warnings}
