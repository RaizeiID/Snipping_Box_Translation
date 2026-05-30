from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
PREFS_PATH = ROOT / "webui_prefs.json"
_HARDWARE_CACHE: HardwareSnapshot | None = None  # type: ignore[name-defined]
_HARDWARE_CACHE_TS = 0.0
_HARDWARE_CACHE_TTL_SEC = float(os.environ.get("ORT_HARDWARE_CACHE_TTL_SEC", "45"))

GAME_PROFILES: Dict[str, Dict[str, Any]] = {
    "GFL": {
        "label": "Girls' Frontline (GFL)",
        "short": "GFL",
        "risk": "LOW",
        "page_title": "Profil Khusus Girls' Frontline",
        "description": "Kotak dialog GFL lebih kecil dari GFL2 dan memiliki footer GFsystem di kanan bawah. v8.7 memakai Name/Body ROI, footer mask, scene guard, dan cache bersih khusus GFL.",
        "recommended_model_group": "lite_idn",
        "recommended_model": "ORTCore Lite IDN V3",
        "recommended_mode": "auto",
        "recommended_engine": "hybrid",
        "recommended_interval_ms": 240,
        "recommended_ocr_resolution": 55,
        "queue_max": 18,
        "cpu_threads": 3,
        "vram_low_gb": 1.3,
        "vram_recover_gb": 2.1,
        "scan_sleep_gpu_ms": 32,
        "scan_sleep_cpu_ms": 72,
        "cas_detect_width": 1040,
        "performance_policy": "gfl_dialogue",
        "note": "v8.7: gunakan profil GFL agar footer GFsystem dimask sebelum OCR, nama pembicara hanya diambil dari ROI/roster yang aman, dan cache tidak terpecah oleh token gFn/ngf/nifn.",
    },
    "GFL2_EXILIUM": {
        "label": "Girls' Frontline 2 Exilium",
        "short": "GFL2",
        "risk": "LOW",
        "page_title": "Profil GFL2 Exilium",
        "description": "Game ringan/menengah dengan pola dialog visual-novel. v8.2 memakai Story/Dialog scheduler agar teks yang masih mengetik tidak diterjemahkan berulang.",
        "recommended_model_group": "fast",
        "recommended_model": "ORTCore Fast V2",
        "recommended_mode": "auto",
        "recommended_engine": "hybrid",
        "recommended_interval_ms": 105,
        "recommended_ocr_resolution": 60,
        "queue_max": 72,
        "cpu_threads": 6,
        "vram_low_gb": 1.0,
        "vram_recover_gb": 1.8,
        "scan_sleep_gpu_ms": 22,
        "scan_sleep_cpu_ms": 55,
        "cas_detect_width": 1280,
        "performance_policy": "balanced",
        "note": "v8.2: rekomendasi utama GFL2 adalah Fast V2 + Interval/Freeze Otomatis. Jika Fast CT2 belum aktif, WebUI akan memberi warning karena fallback Argos tetap lebih lambat.",
    },
    "WUWA": {
        "label": "Wuthering Waves",
        "short": "WUWA",
        "risk": "HIGH",
        "page_title": "Profil Wuthering Waves",
        "description": "Game berat/open-world. ORT disarankan berjalan hemat resource agar GPU/VRAM tetap diprioritaskan untuk game.",
        "recommended_model_group": "lite",
        "recommended_model": "ORTCore Lite V2",
        "recommended_mode": "auto",
        "recommended_engine": "cpu",
        "recommended_interval_ms": 450,
        "recommended_ocr_resolution": 55,
        "queue_max": 18,
        "cpu_threads": 4,
        "vram_low_gb": 2.4,
        "vram_recover_gb": 3.4,
        "scan_sleep_gpu_ms": 90,
        "scan_sleep_cpu_ms": 160,
        "cas_detect_width": 960,
        "performance_policy": "safe_game",
        "note": "Untuk RTX 4050 6GB atau laptop yang game-nya berat, gunakan CPU + Lite/Fast agar VRAM game tidak direbut OCR.",
    },
    "CUSTOM": {
        "label": "Custom / Game Lain",
        "short": "CUSTOM",
        "risk": "MEDIUM",
        "page_title": "Profil Custom",
        "description": "Profil umum untuk game lain. Mulai dari Balanced lalu turunkan ke Safe Game jika FPS turun/stutter.",
        "recommended_model_group": "normal",
        "recommended_model": "ORTCore V2",
        "recommended_mode": "auto",
        "recommended_engine": "hybrid",
        "recommended_interval_ms": 240,
        "recommended_ocr_resolution": 65,
        "queue_max": 50,
        "cpu_threads": 6,
        "vram_low_gb": 1.5,
        "vram_recover_gb": 2.4,
        "scan_sleep_gpu_ms": 45,
        "scan_sleep_cpu_ms": 95,
        "cas_detect_width": 1120,
        "performance_policy": "balanced",
        "note": "Profil netral. Sesuaikan interval dan OCR resolution dari Dashboard.",
    },
}

@dataclass
class HardwareSnapshot:
    os_name: str
    cpu_name: str
    cpu_cores_logical: int
    ram_gb: float
    gpu_name: str
    gpu_vram_gb: float
    nvidia_driver: str
    risk_summary: str


def _run(cmd: List[str], timeout: float = 2.5) -> str:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return out.strip()
    except Exception:
        return ""


def _ram_gb() -> float:
    try:
        import psutil  # type: ignore
        return round(psutil.virtual_memory().total / (1024 ** 3), 1)
    except Exception:
        pass
    if os.name == "nt":
        out = _run(["wmic", "computersystem", "get", "TotalPhysicalMemory", "/value"])
        m = re.search(r"TotalPhysicalMemory=(\d+)", out)
        if m:
            return round(int(m.group(1)) / (1024 ** 3), 1)
    return 0.0


def _cpu_name() -> str:
    name = platform.processor() or platform.machine() or "Unknown CPU"
    if os.name == "nt":
        out = _run(["wmic", "cpu", "get", "Name", "/value"])
        m = re.search(r"Name=(.+)", out)
        if m:
            name = m.group(1).strip()
    return name or "Unknown CPU"


def _gpu_from_nvidia_smi() -> tuple[str, float, str]:
    out = _run(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"], timeout=2.5)
    if out:
        line = out.splitlines()[0]
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 2:
            name = parts[0]
            try:
                vram = round(float(parts[1]) / 1024.0, 1)
            except Exception:
                vram = 0.0
            driver = parts[2] if len(parts) >= 3 else ""
            return name, vram, driver
    return "", 0.0, ""


def _gpu_from_wmic() -> tuple[str, float, str]:
    if os.name != "nt":
        return "", 0.0, ""
    out = _run(["wmic", "path", "win32_VideoController", "get", "Name,AdapterRAM,DriverVersion", "/format:csv"], timeout=3.0)
    best_name, best_vram, best_driver = "", 0.0, ""
    for line in out.splitlines():
        if not line.strip() or line.lower().startswith("node,") is False:
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 4:
            continue
        adapter_ram = parts[1]
        driver = parts[2]
        name = parts[3]
        try:
            vram = round(float(adapter_ram) / (1024 ** 3), 1)
        except Exception:
            vram = 0.0
        if "nvidia" in name.lower() or vram > best_vram:
            best_name, best_vram, best_driver = name, vram, driver
    return best_name, best_vram, best_driver


def _detect_hardware_uncached() -> HardwareSnapshot:
    gpu_name, gpu_vram, driver = _gpu_from_nvidia_smi()
    if not gpu_name:
        gpu_name, gpu_vram, driver = _gpu_from_wmic()
    ram = _ram_gb()
    cpu_logical = os.cpu_count() or 0
    risk = "NORMAL"
    if gpu_vram and gpu_vram <= 6.2:
        risk = "VRAM 6GB: gunakan Safe Game untuk game berat."
    if ram and ram < 16:
        risk = "RAM rendah: gunakan Lite/Fast dan CPU."
    if not gpu_name:
        risk = "GPU tidak terdeteksi dari sistem: default CPU/Hybrid aman."
    return HardwareSnapshot(
        os_name=f"{platform.system()} {platform.release()}".strip(),
        cpu_name=_cpu_name(),
        cpu_cores_logical=cpu_logical,
        ram_gb=ram,
        gpu_name=gpu_name or "Unknown GPU",
        gpu_vram_gb=gpu_vram,
        nvidia_driver=driver or "-",
        risk_summary=risk,
    )


def detect_hardware(force: bool = False) -> HardwareSnapshot:
    # v8.2: cache hardware detection so every dropdown/radio change does not call nvidia-smi/wmic repeatedly.
    global _HARDWARE_CACHE, _HARDWARE_CACHE_TS
    now = time.time()
    if (not force) and _HARDWARE_CACHE is not None and (now - _HARDWARE_CACHE_TS) <= _HARDWARE_CACHE_TTL_SEC:
        return _HARDWARE_CACHE
    _HARDWARE_CACHE = _detect_hardware_uncached()
    _HARDWARE_CACHE_TS = now
    return _HARDWARE_CACHE


def refresh_hardware() -> HardwareSnapshot:
    return detect_hardware(force=True)

def hardware_summary_text(snapshot: Optional[HardwareSnapshot] = None) -> str:
    hw = snapshot or detect_hardware()
    return "\n".join([
        f"OS = {hw.os_name}",
        f"CPU = {hw.cpu_name}",
        f"Logical cores = {hw.cpu_cores_logical}",
        f"RAM = {hw.ram_gb or '?'} GB",
        f"GPU = {hw.gpu_name}",
        f"GPU VRAM = {hw.gpu_vram_gb or '?'} GB",
        f"NVIDIA driver = {hw.nvidia_driver}",
        f"Risk = {hw.risk_summary}",
    ])


def get_game_profile(game: str) -> Dict[str, Any]:
    key = (game or "GFL2_EXILIUM").upper()
    return dict(GAME_PROFILES.get(key, GAME_PROFILES["CUSTOM"]))


def _heavy_hardware_risk(game: str, hw: HardwareSnapshot) -> bool:
    key = (game or "").upper()
    if key == "WUWA":
        if hw.gpu_vram_gb and hw.gpu_vram_gb <= 6.5:
            return True
        if hw.ram_gb and hw.ram_gb < 32:
            return True
    return False


def recommend_settings(game: str, hw: Optional[HardwareSnapshot] = None, allow_normal: bool = False) -> Dict[str, Any]:
    hw = hw or detect_hardware()
    profile = get_game_profile(game)
    rec = dict(profile)
    heavy_risk = _heavy_hardware_risk(game, hw)
    if heavy_risk and not allow_normal:
        rec.update({
            "recommended_model_group": "lite",
            "recommended_model": "ORTCore Lite V2",
            "recommended_engine": "cpu",
            "recommended_mode": "auto",
            "recommended_interval_ms": max(int(profile.get("recommended_interval_ms", 350)), 450),
            "recommended_ocr_resolution": min(int(profile.get("recommended_ocr_resolution", 60)), 55),
            "performance_policy": "safe_game",
            "queue_max": min(int(profile.get("queue_max", 24)), 18),
            "cpu_threads": min(int(profile.get("cpu_threads", 4)), 4),
            "note": profile.get("note", "") + " Sistem mendeteksi potensi beban tinggi, maka rekomendasi diarahkan ke Safe Game.",
        })
    elif allow_normal:
        # User tetap boleh memilih normal walau game berat. Beri preset normal yang masih masuk akal.
        rec.update({
            "recommended_model_group": "normal",
            "recommended_model": "ORTCore V2",
            "recommended_engine": "hybrid",
            "recommended_mode": "auto",
            "recommended_interval_ms": 240 if (game or "").upper() == "WUWA" else int(rec.get("recommended_interval_ms", 220)),
            "recommended_ocr_resolution": 65 if (game or "").upper() == "WUWA" else int(rec.get("recommended_ocr_resolution", 65)),
            "queue_max": 40 if (game or "").upper() == "WUWA" else int(rec.get("queue_max", 50)),
            "cpu_threads": 6,
            "performance_policy": "normal_forced",
            "note": "User memilih Normal Override. Program tetap mengirim batas aman, tetapi OCR dapat lebih berat.",
        })
    return rec


def recommendation_text(game: str, allow_normal: bool = False) -> str:
    hw = detect_hardware()
    rec = recommend_settings(game, hw, allow_normal=allow_normal)
    return "\n".join([
        f"Game = {rec['label']} ({game})",
        f"Policy = {rec['performance_policy']}",
        f"Rekomendasi model = {rec['recommended_model']}",
        f"Rekomendasi mode = {rec['recommended_mode']}",
        f"Rekomendasi engine = {rec['recommended_engine']}",
        f"Interval = {rec['recommended_interval_ms']} ms",
        f"OCR resolution = {rec['recommended_ocr_resolution']}%",
        f"Queue max = {rec['queue_max']}",
        f"CPU threads ORT = {rec['cpu_threads']}",
        f"VRAM guard = low {rec['vram_low_gb']} GB / recover {rec['vram_recover_gb']} GB",
        f"Catatan = {rec['note']}",
        "",
        hardware_summary_text(hw),
    ])


def env_from_settings(game: str, model_key: str = "", policy_override: str = "auto", ocr_resolution: Optional[int] = None) -> Dict[str, str]:
    policy = str(policy_override or "auto").lower()
    allow_normal = policy in {"normal", "normal_forced", "force_normal"}
    rec = recommend_settings(game, allow_normal=allow_normal)
    if policy == "safe_game":
        rec.update({
            "performance_policy": "safe_game",
            "recommended_engine": "cpu",
            "recommended_mode": "auto",
            "recommended_interval_ms": max(int(rec.get("recommended_interval_ms", 300)), 420),
            "recommended_ocr_resolution": min(int(rec.get("recommended_ocr_resolution", 65)), 60),
            "queue_max": min(int(rec.get("queue_max", 30)), 20),
            "cpu_threads": min(int(rec.get("cpu_threads", 6)), 4),
            "scan_sleep_gpu_ms": max(int(rec.get("scan_sleep_gpu_ms", 45)), 90),
            "scan_sleep_cpu_ms": max(int(rec.get("scan_sleep_cpu_ms", 95)), 150),
        })
    elif policy == "balanced":
        rec.update({
            "performance_policy": "balanced",
            "queue_max": min(max(int(rec.get("queue_max", 50)), 40), 80),
            "cpu_threads": min(max(int(rec.get("cpu_threads", 6)), 6), 8),
        })
    if ocr_resolution is not None:
        try:
            rec["recommended_ocr_resolution"] = int(ocr_resolution)
        except Exception:
            pass
    game_key = str((game or "").upper())
    gfl_active = game_key in {"GFL", "GIRLS_FRONTLINE", "GFL1"}
    gfl2_active = game_key in {"GFL2", "GFL2_EXILIUM"}
    env = {
        "ORT_V7_ENABLED": "1",
        "ORT_V71_CORE_PIPELINE": "1",
        "ORT_RUNTIME_STRATEGY": "1",
        "ORT_GAME_PROFILE": str((game or "GFL2_EXILIUM").upper()),
        "ORT_PERFORMANCE_POLICY": str(rec.get("performance_policy", "balanced")),
        "ORT_MODEL_KEY": str(model_key or ""),
        "ORT_MODEL_GROUP": str(rec.get("recommended_model_group", "normal")),
        "ORT_OCR_RESOLUTION_PERCENT": str(int(rec.get("recommended_ocr_resolution", 65))),
        "TITAN_QUEUE_MAX": str(int(rec.get("queue_max", 50))),
        "TITAN_CPU_THREADS": str(int(rec.get("cpu_threads", 6))),
        "TITAN_VRAM_LOW_GB": str(float(rec.get("vram_low_gb", 1.5))),
        "TITAN_VRAM_RECOVER_GB": str(float(rec.get("vram_recover_gb", 2.4))),
        "TITAN_SCAN_SLEEP_GPU_MS": str(int(rec.get("scan_sleep_gpu_ms", 45))),
        "TITAN_SCAN_SLEEP_CPU_MS": str(int(rec.get("scan_sleep_cpu_ms", 95))),
        "TITAN_CAS_FAST_DETECT_W": str(int(rec.get("cas_detect_width", 1120))),
        "TITAN_HEAVY_GAME_SAFE": "1" if str(rec.get("performance_policy")) in {"safe_game", "potato"} else "0",
        # v8.7 GFL1 contract: compact dialogue layout + fixed GFsystem/footer protection.
        "ORT_GFL_LAYOUT": "1" if gfl_active else "0",
        "ORT_GFL_FOOTER_MASK": "1" if gfl_active else "0",
        "ORT_GFL_DIALOG_PRESENCE_GUARD": "1" if gfl_active else "0",
        "ORT_GFL_SPEAKER_ROI": "1" if gfl_active else "0",
        "ORT_GFL_ARTIFACT_FILTER": "1" if gfl_active else "0",
        "ORT_GFL_CACHE_NORMALIZED": "1" if gfl_active else "0",
        "ORT_GFL_CACHE_STABLE_ONLY": "1" if gfl_active else "0",
        "ORT_SPEAKER_GATE_STRICTNESS": "strict" if gfl_active else os.environ.get("ORT_SPEAKER_GATE_STRICTNESS", "normal"),
        "ORT_LEARNING_QUARANTINE_SPEAKER_HITS": "3" if (gfl_active or gfl2_active) else os.environ.get("ORT_LEARNING_QUARANTINE_SPEAKER_HITS", "2"),
        # v8.7.1: GFL2 uses seeded speaker prefixes/quarantine instead of learning narrative first words.
        "ORT_GFL2_SPEAKER_GATE": "1" if gfl2_active else "0",
        # v8.7.6: GFL2 reads its speaker label through trusted registry metadata; body OCR stays paragraph-based.
        "ORT_GFL2_SPEAKER_ROI": "1" if gfl2_active else "0",
        "ORT_GFL2_TEXT_REPAIR_V2": "1" if gfl2_active else "0",
        "ORT_TRUSTED_SPEAKER_REGISTRY_V2": "1",
        "ORT_NAMED_ENTITY_PROTECTION": "1",
        "ORT_IDN_CACHE_VERSION": "v8_7_8_faithfulness_v2_strict_ct2_safe",
        "ORT_SCOPED_CACHE_VERSION": "v8_7_8_faithfulness_v2_strict_ct2_safe",
        "ORT_ADAPTIVE_READABILITY_GUARD": "1" if ("lite" in str(model_key).lower() or "fast" in str(model_key).lower()) else "0",
        "ORT_OCR_STORY_MIN_PERCENT": "50",
        "ORT_NAME_ROI_MIN_PERCENT": "50",
        "ORT_GFL2_EXACT_FALLBACK_ONLY": "1",
        "ORT_CRITICAL_TOKEN_GUARD": "1",
        "ORT_STABLE_FINAL_CACHE_V2": "1",
        "ORT_CURRENT_DIALOG_MEMO": "1",
        "ORT_IDN_EVAL_EXPORT": "1",
        "ORT_IDN_WARMUP": "1",
        # v8.7.1: do not reuse the contaminated legacy vault during clean validation sessions.
        "ORT_ENABLE_LEGACY_VAULT": os.environ.get("ORT_ENABLE_LEGACY_VAULT", "0"),
        # v8.7.1: reduce cache pollution from short progressive typing prefixes.
        "ORT_CACHE_PROGRESSIVE_GUARD": "1" if (gfl_active or gfl2_active) else os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD", "0"),
    }
    return env


def game_choices() -> List[tuple[str, str]]:
    return [(v["label"], k) for k, v in GAME_PROFILES.items()]


def profile_html(game: str, allow_normal: bool = False) -> str:
    rec = recommend_settings(game, allow_normal=allow_normal)
    risk_color = "#22c55e"
    if rec.get("risk") == "HIGH" or rec.get("performance_policy") == "safe_game":
        risk_color = "#f59e0b"
    if rec.get("performance_policy") == "normal_forced":
        risk_color = "#ef4444"
    return f"""
    <div class='card'>
      <h3 style='margin:0 0 8px 0'>{rec.get('page_title','Profil Game')}</h3>
      <p style='color:#dbeafe;margin:0 0 12px 0'>{rec.get('description','')}</p>
      <div style='display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px'>
        <div><b>Policy</b><br><span style='color:{risk_color};font-weight:800'>{rec.get('performance_policy')}</span></div>
        <div><b>Model</b><br>{rec.get('recommended_model')}</div>
        <div><b>Engine</b><br>{rec.get('recommended_engine')}</div>
        <div><b>Interval</b><br>{rec.get('recommended_interval_ms')} ms</div>
        <div><b>OCR Resolution</b><br>{rec.get('recommended_ocr_resolution')}%</div>
        <div><b>Queue</b><br>{rec.get('queue_max')}</div>
      </div>
      <p style='color:#fde68a;margin:12px 0 0 0'>{rec.get('note','')}</p>
    </div>
    """


def save_v7_prefs(extra: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    try:
        if PREFS_PATH.exists():
            data = json.loads(PREFS_PATH.read_text(encoding="utf-8-sig"))
    except Exception:
        data = {}
    data.update(extra or {})
    PREFS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data
