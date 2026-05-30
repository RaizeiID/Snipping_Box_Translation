from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent

@dataclass(frozen=True)
class ModelPreset:
    key: str
    title: str
    script: str
    family: str
    tier: str
    order: int
    summary: str
    details: str
    default_interval_ms: int = 220
    default_engine: str = "hybrid"
    default_mode: str = "auto"
    ocr_resolution_percent: int = 65
    env: Dict[str, str] | None = None

    @property
    def path(self) -> Path:
        return ROOT / self.script

    @property
    def exists(self) -> bool:
        return self.path.exists()

    def env_map(self) -> Dict[str, str]:
        base = {
            "TITAN_MODEL_PRESET": self.family,
            "TITAN_MODEL_LABEL": self.title,
            "ORT_MODEL_KEY": self.key,
            "ORT_MODEL_GROUP": self.tier,
            "ORT_MODEL_FAMILY": self.family,
            "ORT_MODEL_TIER": self.tier,
            "ORT_MODEL_ORDER": str(self.order),
            "ORT_V71_CORE_PIPELINE": "1",
            "ORT_RUNTIME_STRATEGY": "1",
            "ORT_OCR_RESOLUTION_PERCENT": str(self.ocr_resolution_percent),
        }
        if self.env:
            base.update({str(k): str(v) for k, v in self.env.items()})
        return base

GAME_PRESETS = {
    "GFL2_EXILIUM": {
        "label": "Girls' Frontline 2 Exilium",
        "theme": "gfl2",
        "summary": "Ringan/visual novel, cocok Balanced.",
        "env": {"TITAN_GAME_PROFILE": "GFL2_EXILIUM"},
    },
    "WUWA": {
        "label": "Wuthering Waves",
        "theme": "wuwa",
        "summary": "Game berat, disarankan Safe Game.",
        "env": {"TITAN_GAME_PROFILE": "WUWA", "TITAN_HEAVY_GAME_SAFE": "1"},
    },
    "CUSTOM": {
        "label": "Custom / Game Lain",
        "theme": "custom",
        "summary": "Profil umum.",
        "env": {"TITAN_GAME_PROFILE": "CUSTOM"},
    },
}

MODEL_PRESETS: List[ModelPreset] = [
    # NORMAL: V1 - V5 only, sesuai usulan v7.
    ModelPreset("v1", "ORTCore V1", "TITANMAIN.py", "V1", "normal", 10, "Ringan", "Model paling ringan untuk dialog sederhana dan perangkat terbatas.", 160, "hybrid", "auto", 65, {"TITAN_MODEL_WEIGHT": "light", "TITAN_NATURALIZE_MAX": "0"}),
    ModelPreset("v2", "ORTCore V2", "TITANMAIN.py", "V2", "normal", 20, "Balance", "Model medium/balanced untuk penggunaan umum.", 220, "hybrid", "auto", 70, {"TITAN_MODEL_WEIGHT": "medium", "TITAN_NATURALIZE_MAX": "0"}),
    ModelPreset("v3", "ORTCore V3", "TITANMAIN.py", "V3", "normal", 30, "Akurat", "Model paling berat di grup normal dengan akurasi lebih tinggi.", 300, "hybrid", "auto", 75, {"TITAN_MODEL_WEIGHT": "heavy", "TITAN_NATURALIZE_MAX": "0"}),
    ModelPreset("v4", "ORTCore V4", "TITANMAIN.py", "V4", "normal", 40, "Hybrid online/offline", "Model hybrid online + offline agar ringan tetapi tetap akurat bila koneksi tersedia.", 230, "hybrid", "auto", 70, {"TITAN_MODEL_WEIGHT": "hybrid", "TITAN_ONLINE_ASSIST": "1", "TITAN_NATURALIZE_MAX": "0"}),
    ModelPreset("v5", "ORTCore V5", "TITANMAIN.py", "V5", "normal", 50, "Naturalisasi presisi", "Model naturalisasi paling presisi dan mendalam.", 260, "hybrid", "auto", 75, {"TITAN_MODEL_WEIGHT": "naturalize_deep", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "5"}),

    # LITE: lebih ringan untuk game berat / sistem overload.
    ModelPreset("lite_v1", "ORTCore Lite V1", "TITANMAIN.py", "V1", "lite", 110, "Lite V1 Ultra Efficient / Diagnostic", "v8.7.6: OCR 40% hanya untuk ultra-speed/diagnostic; GFL2 story memakai Adaptive Readability Rescue bila teks rusak.", 260, "hybrid", "auto", 40, {"TITAN_MODEL_WEIGHT": "lite", "TITAN_LITE_MODE": "1", "TITAN_NATURALIZE_MAX": "0", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_LITE_EFFICIENT_PROFILE": "ultra", "ORT_LITE_PROFILE_IDENTITY": "v8.6_ultra"}),
    ModelPreset("lite_v2", "ORTCore Lite V2", "TITANMAIN.py", "V2", "lite", 120, "Lite V2 Efficient + Rescue", "v8.7.6: OCR 45% memerlukan Adaptive Readability Rescue untuk GFL2 story; gunakan V3 50% sebagai baseline.", 330, "hybrid", "auto", 45, {"TITAN_MODEL_WEIGHT": "lite_balance", "TITAN_LITE_MODE": "1", "TITAN_NATURALIZE_MAX": "0", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_LITE_EFFICIENT_PROFILE": "balanced", "ORT_LITE_PROFILE_IDENTITY": "v8.6_balanced"}),
    ModelPreset("lite_v3", "ORTCore Lite V3", "TITANMAIN.py", "V3", "lite", 130, "Lite V3 Story Baseline", "v8.7.6: OCR 50%, minimum rekomendasi baseline story GFL2 setelah audit video/log.", 390, "hybrid", "auto", 50, {"TITAN_MODEL_WEIGHT": "lite_accurate", "TITAN_LITE_MODE": "1", "TITAN_NATURALIZE_MAX": "0", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_LITE_EFFICIENT_PROFILE": "quality_safe", "ORT_LITE_PROFILE_IDENTITY": "v8.6_balanced_quality"}),
    ModelPreset("lite_v4", "ORTCore Lite V4", "TITANMAIN.py", "V4", "lite", 140, "Lite V4 Quality Safe", "v8.6: OCR 55%, hybrid quality-safe dengan guard GPU/online; bukan default game berat.", 430, "hybrid", "auto", 55, {"TITAN_MODEL_WEIGHT": "lite_hybrid", "TITAN_LITE_MODE": "1", "TITAN_ONLINE_ASSIST": "1", "TITAN_NATURALIZE_MAX": "0", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_LITE_EFFICIENT_PROFILE": "hybrid_safe", "ORT_LITE_PROFILE_IDENTITY": "v8.6_quality_safe"}),
    ModelPreset("lite_v5", "ORTCore Lite V5", "TITANMAIN.py", "V5", "lite", 150, "Lite V5 Quality", "v8.6: OCR 60%, kualitas OCR tertinggi di Lite; gunakan jika VRAM aman, bukan default heavy-game.", 480, "hybrid", "auto", 60, {"TITAN_MODEL_WEIGHT": "lite_natural", "TITAN_LITE_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "5", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_LITE_EFFICIENT_PROFILE": "quality", "ORT_LITE_PROFILE_IDENTITY": "v8.6_quality"}),

    # IDN: sama seperti normal tetapi naturalisasi Indonesia aktif.
    ModelPreset("idn_v1", "ORTCore IDN V1", "TITANMAIN.py", "V1", "idn", 210, "IDN ringan", "V1 dengan naturalisasi bahasa Indonesia dasar.", 190, "hybrid", "auto", 65, {"TITAN_MODEL_WEIGHT": "light", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "lite_light"}),
    ModelPreset("idn_v2", "ORTCore IDN V2", "TITANMAIN.py", "V2", "idn", 220, "IDN balance", "V2 dengan naturalisasi bahasa Indonesia yang lebih natural.", 240, "hybrid", "auto", 70, {"TITAN_MODEL_WEIGHT": "medium", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "2", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "balanced"}),
    ModelPreset("idn_v3", "ORTCore IDN V3", "TITANMAIN.py", "V3", "idn", 230, "IDN akurat", "V3 dengan akurasi tinggi dan naturalisasi lebih matang.", 330, "hybrid", "auto", 75, {"TITAN_MODEL_WEIGHT": "heavy", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "3", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "natural"}),
    ModelPreset("idn_v4", "ORTCore IDN V4", "TITANMAIN.py", "V4", "idn", 240, "IDN hybrid", "V4 online/offline dengan naturalisasi bahasa Indonesia.", 260, "hybrid", "auto", 70, {"TITAN_MODEL_WEIGHT": "hybrid", "TITAN_IDN_MODE": "1", "TITAN_ONLINE_ASSIST": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "4", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "natural"}),
    ModelPreset("idn_v5", "ORTCore IDN V5", "TITANMAIN.py", "V5", "idn", 250, "IDN naturalisasi presisi", "V5 naturalisasi Indonesia paling presisi dan mendalam.", 300, "hybrid", "auto", 75, {"TITAN_MODEL_WEIGHT": "naturalize_deep", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "5", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "quality"}),

    # LITE IDN: Lite + naturalisasi.
    ModelPreset("lite_idn_v1", "ORTCore Lite IDN V1", "TITANMAIN.py", "V1", "lite_idn", 310, "Lite IDN V1 Ultra Efficient / Diagnostic", "v8.7.6: OCR 40% hanya ultra-speed/diagnostic; rescue adaptif aktif untuk story GFL2.", 260, "hybrid", "auto", 40, {"TITAN_LITE_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "1", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "lite_light", "ORT_LITE_EFFICIENT_PROFILE": "ultra", "ORT_LITE_PROFILE_IDENTITY": "v8.6_ultra_idn", "ORT_LITE_WIDE_DIALOG_FILTER": "1", "ORT_OCR_NOISE_REJECT": "1"}),
    ModelPreset("lite_idn_v2", "ORTCore Lite IDN V2", "TITANMAIN.py", "V2", "lite_idn", 320, "Lite IDN V2 Efficient + Rescue", "v8.7.6: OCR 45% tidak lagi baseline GFL2 tanpa rescue; gunakan V3 50% untuk correctness ringan.", 330, "hybrid", "auto", 45, {"TITAN_LITE_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "2", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "lite_balanced", "ORT_LITE_EFFICIENT_PROFILE": "balanced", "ORT_LITE_PROFILE_IDENTITY": "v8.6_balanced_idn", "ORT_LITE_WIDE_DIALOG_FILTER": "1", "ORT_OCR_NOISE_REJECT": "1"}),
    ModelPreset("lite_idn_v3", "ORTCore Lite IDN V3", "TITANMAIN.py", "V3", "lite_idn", 330, "Lite IDN V3 Story Baseline", "v8.7.6: OCR 50%, minimum rekomendasi story GFL2 dengan IDN naturalization.", 390, "hybrid", "auto", 50, {"TITAN_LITE_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "3", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "balanced", "ORT_LITE_EFFICIENT_PROFILE": "quality_safe", "ORT_LITE_PROFILE_IDENTITY": "v8.6_balanced_quality_idn", "ORT_LITE_WIDE_DIALOG_FILTER": "1", "ORT_OCR_NOISE_REJECT": "1"}),
    ModelPreset("lite_idn_v4", "ORTCore Lite IDN V4", "TITANMAIN.py", "V4", "lite_idn", 340, "Lite IDN V4 Natural Hybrid", "v8.6: OCR 55%, IDN Natural + optional V4 Online Assist resmi; bukan default game berat.", 430, "hybrid", "auto", 55, {"TITAN_LITE_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_ONLINE_ASSIST": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "4", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "natural", "ORT_LITE_EFFICIENT_PROFILE": "hybrid_safe", "ORT_LITE_PROFILE_IDENTITY": "v8.6_quality_safe_idn", "ORT_LITE_WIDE_DIALOG_FILTER": "1", "ORT_OCR_NOISE_REJECT": "1"}),
    ModelPreset("lite_idn_v5", "ORTCore Lite IDN V5", "TITANMAIN.py", "V5", "lite_idn", 350, "Lite IDN V5 Quality", "v8.6: OCR 60%, IDN Quality paling rapi di Lite IDN; gunakan jika VRAM aman.", 480, "hybrid", "auto", 60, {"TITAN_LITE_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "5", "ORT_LITE_GPU_EFFICIENT": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "quality", "ORT_LITE_EFFICIENT_PROFILE": "quality", "ORT_LITE_PROFILE_IDENTITY": "v8.6_quality_idn", "ORT_LITE_WIDE_DIALOG_FILTER": "1", "ORT_OCR_NOISE_REJECT": "1"}),

    # FAST: cepat untuk dialog cepat.
    ModelPreset("fast_v1", "ORTCore Fast V1", "TITANMAIN.py", "FAST", "fast", 410, "Fast V1 ultra speed", "v8.4.3: Fast V1 retune. OCR 40%, latency minimum, CT2 Fast, postprocess minimal; akurasi dikorbankan demi respon tercepat.", 45, "hybrid", "auto", 40, {"TITAN_FAST_MODE": "1", "TITAN_MODEL_WEIGHT": "fast", "TITAN_NATURALIZE_MAX": "0", "ORT_FAST_PROFILE": "fast_v1_speed_first", "ORT_FAST_RETUNE_V843": "1"}),
    ModelPreset("fast_v2", "ORTCore Fast V2", "TITANMAIN.py", "FAST", "fast", 420, "Fast V2 low-latency balanced", "v8.4.3: Fast V2 retune. OCR 45%, latency rendah, cleanup tetap aktif, cocok sebagai fast balanced story.", 60, "hybrid", "auto", 45, {"TITAN_FAST_MODE": "1", "TITAN_MODEL_WEIGHT": "fast_balance", "TITAN_NATURALIZE_MAX": "0", "ORT_FAST_PROFILE": "fast_v2_balanced", "ORT_FAST_RETUNE_V843": "1"}),
    ModelPreset("fast_idn", "ORTCore Fast IDN", "TITANMAIN.py", "FAST", "fast", 430, "Fast IDN light naturalized", "v8.6: Fast IDN tetap basis Fast V2 + IDN fast_light; cepat dan tidak memakai quality layer berat.", 75, "hybrid", "auto", 50, {"TITAN_FAST_MODE": "1", "TITAN_IDN_MODE": "1", "TITAN_MODEL_WEIGHT": "fast_idn", "TITAN_NATURALIZE_MAX": "1", "ORT_V5_LEVEL": "2", "ORT_FAST_PROFILE": "fast_idn_naturalized", "ORT_IDN_NATURALIZER": "1", "ORT_IDN_QUALITY_LAYER": "1", "ORT_IDN_QUALITY_MODE": "fast_light", "ORT_FAST_LOCKED": "0", "ORT_FAST_RETUNE_V843": "1"}),
]

GROUP_LABELS = {
    "normal": "Normal V1–V5",
    "lite": "Lite untuk game berat",
    "idn": "IDN / naturalisasi",
    "lite_idn": "Lite IDN",
    "fast": "Fast dialog cepat",
}

INDEX: Dict[str, ModelPreset] = {m.key: m for m in MODEL_PRESETS}
TITLE_INDEX: Dict[str, ModelPreset] = {m.title: m for m in MODEL_PRESETS}

# Alias lama agar launcher lama/tombol lama tidak putus.
ALIASES = {
    "ORTCore V1 Lite": "ORTCore Lite V1",
    "ORTCore V2 Lite": "ORTCore Lite V2",
    "ORTCore V3 Lite": "ORTCore Lite V3",
    "ORTCore V4 Lite": "ORTCore Lite V4",
    "ORTCore V5 Lite": "ORTCore Lite V5",
    "ORTCore V1 IDN": "ORTCore IDN V1",
    "ORTCore V2 IDN": "ORTCore IDN V2",
    "ORTCore V3 IDN": "ORTCore IDN V3",
    "ORTCore V4 IDN": "ORTCore IDN V4",
    "ORTCore V5 IDN": "ORTCore IDN V5",
    "ORTCore V1 Lite IDN": "ORTCore Lite IDN V1",
    "ORTCore V2 Lite IDN": "ORTCore Lite IDN V2",
    "ORTCore V3 Lite IDN": "ORTCore Lite IDN V3",
    "ORTCore V4 Lite IDN": "ORTCore Lite IDN V4",
    "ORTCore V5 Lite IDN": "ORTCore Lite IDN V5",
    "ORTCore V5 Lv1": "ORTCore IDN V1",
    "ORTCore V5 Lv2": "ORTCore IDN V2",
    "ORTCore V5 Lv3": "ORTCore IDN V3",
    "ORTCore V5 Lv4": "ORTCore IDN V4",
    "ORTCore V5 Lv1 Lite": "ORTCore Lite IDN V1",
    "ORTCore V5 Lv2 Lite": "ORTCore Lite IDN V2",
    "ORTCore V5 Lv3 Lite": "ORTCore Lite IDN V3",
    "ORTCore V5 Lv4 Lite": "ORTCore Lite IDN V4",
}


def list_models(group: Optional[str] = None) -> List[ModelPreset]:
    items = sorted(MODEL_PRESETS, key=lambda x: x.order)
    if group:
        items = [m for m in items if m.tier == group]
    return items


def get_model(key: str) -> ModelPreset:
    return INDEX[key.lower()]


def available_model_choices(group: Optional[str] = None) -> List[str]:
    return [m.title for m in list_models(group)]


def group_choices() -> List[tuple[str, str]]:
    return [(label, key) for key, label in GROUP_LABELS.items()]


def choice_to_key(title: str) -> str:
    title = ALIASES.get(title, title)
    if title in TITLE_INDEX:
        return TITLE_INDEX[title].key
    raise KeyError(title)


def get_model_by_title(title: str) -> ModelPreset:
    return get_model(choice_to_key(title))


def model_script_for_title(title: str) -> str:
    return get_model_by_title(title).script
