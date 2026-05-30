from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict

HEAVY_GAMES = {"WUWA", "WUTHERING_WAVES"}
GFL_GAMES = {"GFL", "GIRLS_FRONTLINE", "GFL1"}

def _is_lite_group(group: str, model_key: str = "") -> bool:
    s = f"{group} {model_key}".lower()
    return "lite" in s

def is_heavy_game(game: str) -> bool:
    return (game or "").upper() in HEAVY_GAMES

def resolve_profile(game: str, model_key: str = "", group: str = "normal", settings_mode: str = "recommended", requested_engine: str = "hybrid", requested_interval_ms: int | None = None, requested_ocr: int | None = None) -> Dict[str, Any]:
    heavy = is_heavy_game(game)
    lite = _is_lite_group(group, model_key)
    manual = (settings_mode or "recommended").lower() in {"manual", "normal"}
    out: Dict[str, Any] = {
        "version": "v8.7", "game": game, "model_key": model_key, "group": group,
        "settings_mode": "manual" if manual else "recommended", "heavy_game": heavy,
        "reason": [],
    }
    if manual:
        engine = requested_engine or "hybrid"
        if heavy and lite:
            engine = "hybrid" if engine in {"auto", "", "gpu", "hybrid"} else engine
            out["reason"].append("Mode manual: Lite/Lite IDN pada game berat memakai GPU Efficient bila VRAM aman, CPU fallback hanya jika kritis.")
        else:
            if engine in {"auto", ""}: engine = "hybrid"
            out["reason"].append("Mode manual: user bebas mengatur; model non-Lite default Hybrid/GPU priority.")
        out.update({"engine": engine, "mode": "auto", "ocr": int(requested_ocr or (55 if heavy and lite else 70)), "interval_ms": int(requested_interval_ms or (520 if heavy and lite else 200)), "safe_mode": heavy and lite})
        return out
    # Recommended mode
    if str(game or "").upper() in GFL_GAMES:
        out.update({"engine": "hybrid", "mode": "auto", "ocr": 55, "interval_ms": 240, "safe_mode": False, "recommended_model_group": "lite_idn", "recommended_model_key": "lite_idn_v3", "layout": "GFL_DIALOG_STANDARD", "footer_mask": True})
        out["reason"].append("Recommended Mode v8.7: GFL memakai compact-dialog resolver, Name/Body ROI, footer GFsystem mask, dan Lite IDN V3 balanced quality.")
    elif heavy:
        out.update({"engine": "hybrid", "mode": "auto", "ocr": 52, "interval_ms": 520, "safe_mode": True, "recommended_model_group": "lite_idn", "recommended_model_key": "lite_idn_v2"})
        out["reason"].append("Recommended Mode v8.4: game berat memakai Lite IDN V2 + GPU Efficient; CPU fallback hanya bila VRAM kritis.")
    else:
        out.update({"engine": "hybrid", "mode": "auto", "ocr": 70, "interval_ms": 200, "safe_mode": False, "recommended_model_group": "idn", "recommended_model_key": "idn_v2"})
        out["reason"].append("Recommended Mode: game ringan/visual novel, Hybrid + IDN V2 balanced.")
    return out

def resolve_profile_text(game: str, model_key: str = "", group: str = "normal", settings_mode: str = "recommended", requested_engine: str = "hybrid") -> str:
    p = resolve_profile(game, model_key, group, settings_mode, requested_engine)
    lines = ["Profile Resolver v8.7", "====================", f"Game: {p.get('game')}", f"Mode Pengaturan: {p.get('settings_mode')}", f"Heavy game: {p.get('heavy_game')}", f"Engine: {p.get('engine')}", f"OCR: {p.get('ocr')}%", f"Interval: {p.get('interval_ms')} ms", f"Safe Mode: {p.get('safe_mode')}", "", "Alasan:"]
    lines += ["- " + r for r in p.get("reason", [])]
    return "\n".join(lines)
