import html
import json
import os
import subprocess
import threading
import time
from pathlib import Path
from typing import Optional

from data_processing_backend import record_runtime_line, get_candidates, load_settings, clear_candidates
from gpu_runtime import gpu_summary_text, install_or_repair_gpu
from model_registry import get_model_by_title, model_script_for_title
from v7_system_profile import env_from_settings, recommendation_text
from model_strategy import build_strategy, write_strategy_status
from fast_model_manager import FastModelManager, fast_engine_status_text
from session_log_manager import start_session, current_session, close_session
from graceful_shutdown import clear_stop_request, request_stop, stop_file_from_env, write_shutdown_status
from status_manager import read_status, cleanup_legacy_status_files
from fast_model_manager import prepare_fast_engine_folder, fast_engine_test_text
from runtime_dependency_checker import dependency_report_text
from online_assist_config import online_assist_status_text, test_online_assist, save_online_config_text, online_assist_config_values, apply_online_config_to_env
from benchmark_session_report import analyze_session
from app.runtime.settings_manager import reset_settings
from app.runtime.app_state import save_state, load_state
from app.strategies.profile_resolver import resolve_profile_text
from app.diagnostics.conflict_detector import detect_conflicts_text
from app.diagnostics.gpu_cuda_diagnostic import gpu_cuda_diagnostic_text
from app.runtime.lite_gpu_guard import apply_lite_gpu_env, write_lite_gpu_status, lite_gpu_status_text
from app.diagnostics.diagnose_repair_center import diagnose_text as diagnose_repair_center_text
from build_info import APP_DISPLAY_NAME, APP_VERSION_TAG, RELEASE_NAME
from audio_runtime_backend import (
    audio_device_choices,
    audio_model_ready,
    audio_model_status,
    audio_runtime_paths,
    audio_runtime_summary_text,
    probe_audio_runtime,
    resolve_effective_audio_mode,
    setup_audio_runtime,
)
from audio_cloud_backend import (
    cloud_config_values,
    cloud_device_choices,
    cloud_runtime_paths,
    cloud_runtime_summary_text,
    clear_cloud_credentials,
    probe_cloud_runtime,
    resolve_audio_delivery,
    save_cloud_config,
    setup_cloud_runtime,
)
from app.audio.cloud_streaming import (
    normalize_audio_engine,
    normalize_audio_usage,
    normalize_source_locale,
    resolve_live_media_policy,
)
from app.audio.profiles import get_audio_profile
from app.audio.runtime_modes import normalize_audio_mode, resolve_audio_plan

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_CFG = BASE_DIR / "runtime_paths.json"
PREFS_PATH = BASE_DIR / "webui_prefs.json"
try:
    cleanup_legacy_status_files(BASE_DIR)
except Exception:
    pass




def runtime_version_contract() -> dict:
    root = BASE_DIR.parent.parent
    expected = str(APP_VERSION_TAG).strip()
    paths = {
        "root": root / "VERSION.txt",
        "ortcore": BASE_DIR / "ORTCORE_VERSION.txt",
        "titancore": BASE_DIR / "TITANCORE_VERSION.txt",
    }
    values = {}
    errors = []
    for key, path in paths.items():
        try:
            values[key] = path.read_text(encoding="utf-8-sig").strip()
        except Exception as exc:
            values[key] = ""
            errors.append(f"{key}: {exc}")
    mismatches = {key: value for key, value in values.items() if value != expected}
    return {
        "ready": not errors and not mismatches,
        "expected": expected,
        "values": values,
        "mismatches": mismatches,
        "errors": errors,
    }

def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")



def _validated_cuda_baseline_ready(resolution: dict, *, model: str = "small") -> bool:
    """Trust a recent real-inference CUDA marker as a baseline for Hybrid.

    The active ASR model still performs its own CUDA preflight before streaming.
    This prevents Accurate + Japanese Specialist from being forced to CPU merely
    because the profile's generic model marker (for example medium) is absent.
    """
    try:
        runtime = resolution.get("runtime") or {}
        gpu = runtime.get("gpu") or {}
        if not gpu.get("ready"):
            return False
        paths = audio_runtime_paths(BASE_DIR)
        marker = paths["gpu_root"] / f"validated_cuda_{model}.json"
        data = _load_json(marker, {})
        validated_at = float(data.get("validated_at", 0.0) or 0.0)
        marker_fresh = validated_at > 0 and (time.time() - validated_at) <= 30 * 24 * 3600
        return bool(
            data.get("ready")
            and data.get("model") == model
            and data.get("device") == "cuda"
            and data.get("compute_type") == "int8_float16"
            and marker_fresh
        )
    except Exception:
        return False


def get_runtime_config():
    cfg = _load_json(RUNTIME_CFG, {})
    runtime_root = cfg.get("runtime_root") or str(BASE_DIR / "_runtime")
    project_root = cfg.get("project_root") or str(BASE_DIR)
    runtime_python = str(Path(runtime_root) / ".venv" / "Scripts" / "python.exe")
    valid = Path(runtime_python).exists()
    storage_mode = "custom" if Path(runtime_root).resolve() != (BASE_DIR / "_runtime").resolve() else "local"
    return {
        "project_root": project_root,
        "runtime_root": runtime_root,
        "runtime_python": runtime_python if valid else "-",
        "storage_mode": storage_mode,
        "last_runtime_valid": valid,
    }


def runtime_summary_text():
    cfg = get_runtime_config()
    return "\n".join([
        f"project_root = {cfg['project_root']}",
        f"runtime_root = {cfg['runtime_root']}",
        f"runtime_python = {cfg['runtime_python']}",
        f"storage_mode = {cfg['storage_mode']}",
        f"last_runtime_valid = {str(cfg['last_runtime_valid'])}",
    ])




def diagnostic_text():
    sections = [
        ("strategy", "MODEL STRATEGY"),
        ("runtime_health", "RUNTIME HEALTH"),
        ("runtime_actions", "RUNTIME ACTION APPLIER"),
        ("core_bridge", "CORE BRIDGE"),
        ("core_profile", "CORE PROFILE MANAGER"),
        ("cache", "SCOPED CACHE"),
        ("fast_engine", "FAST ENGINE"),
        ("lite_gpu_guard", "LITE GPU GUARD"),
        ("online_assist", "ONLINE ASSIST"),
        ("translation_engine", "TRANSLATION ENGINE"),
        ("shutdown", "GRACEFUL SHUTDOWN"),
        ("session_log", "SESSION LOG"),
        ("benchmark", "BENCHMARK"),
    ]
    lines = [f"{APP_DISPLAY_NAME} Diagnostic Dashboard", f"release = {RELEASE_NAME}", f"status_dir = {BASE_DIR / 'status'}"]
    for key, title in sections:
        data = read_status(key, BASE_DIR, {"missing": True})
        lines.append("")
        lines.append(f"[{title}]")
        if data.get("missing"):
            lines.append(f"status/{key}.json belum tersedia; tekan Start/Refresh/Benchmark untuk membuat status runtime.")
            continue
        if key == "strategy":
            lines.extend(str(data.get("summary", "")).splitlines()[:14])
        elif key == "runtime_health":
            for k in ["status", "cpu_percent", "ram_percent", "vram_free_gb", "vram_total_gb", "queue_size", "queue_max", "avg_ocr_ms", "avg_translate_ms", "recommended_sleep_ms", "recommended_ocr_resolution", "force_cpu", "reason"]:
                lines.append(f"{k} = {data.get(k, '-')}")
        elif key == "runtime_actions":
            for k in ["status", "ocr_resolution_percent", "force_cpu", "disable_online", "temporary_fast_mode", "extra_sleep_ms", "should_reload_cpu", "should_restore_engine", "reason"]:
                lines.append(f"{k} = {data.get(k, '-')}")
        elif key == "core_bridge":
            lines.append(data.get("summary", "Core status"))
            lines.append(f"active = {data.get('active_count', '?')} | parked = {data.get('parked_count', '?')} | failed = {data.get('failed_count', '?')}")
            lines.append(f"strategy = {data.get('strategy', '-')}")
            lines.append(f"core_profile = {data.get('core_profile', '-')}")
        elif key == "core_profile":
            lines.append(f"profile = {data.get('profile', '-')}")
            lines.append(f"target_active = {data.get('active_count_target', '-')}")
            names = data.get('active_core_names', [])[:12]
            lines.append("active_sample = " + ", ".join(names))
        else:
            for k, v in list(data.items())[:14]:
                if isinstance(v, (str, int, float, bool)):
                    lines.append(f"{k} = {v}")
    return "\n".join(lines)



def core_summary_text():
    data = read_status("core_bridge", BASE_DIR, {"missing": True})
    if data.get("missing"):
        return "Core Bridge belum berjalan. Status akan muncul setelah Start."
    try:
        lines = [
            data.get("summary", "Core Bridge status"),
            f"active = {data.get('active_count', '?')}",
            f"parked = {data.get('parked_count', '?')}",
            f"failed = {data.get('failed_count', '?')}",
            "",
            "FAILED/PARKED penting:",
        ]
        cores = data.get("cores", {}) or {}
        shown = 0
        for name, info in cores.items():
            st = info.get("status")
            if st in {"FAILED", "PARKED"}:
                lines.append(f"- {name}: {st} | {info.get('reason','')}")
                shown += 1
            if shown >= 18:
                lines.append("- ...lihat status/core_bridge.json untuk daftar lengkap")
                break
        if shown == 0:
            lines.append("- Tidak ada core gagal/parked yang perlu dicatat.")
        return "\n".join(lines)
    except Exception as e:
        return f"Gagal membaca status/core_bridge.json: {e}"


def fast_setup_text():
    try:
        return prepare_fast_engine_folder(BASE_DIR)
    except Exception as exc:
        return f"Fast setup helper gagal: {exc}"


def online_status_text():
    try:
        return online_assist_status_text(BASE_DIR)
    except Exception as exc:
        return f"Online Assist status gagal: {exc}"


def online_test_text():
    try:
        return test_online_assist(BASE_DIR)
    except Exception as exc:
        return f"Online Assist test gagal: {exc}"


def online_config_values():
    return online_assist_config_values(BASE_DIR)


def save_online_config_from_ui(enabled, provider, endpoint, api_key, timeout):
    try:
        return save_online_config_text(bool(enabled), str(provider or "libretranslate"), str(endpoint or ""), str(api_key or ""), float(timeout or 1.2), BASE_DIR)
    except Exception as exc:
        return f"Gagal menyimpan Online Assist config: {exc}"


def dependency_check_text():
    try:
        return dependency_report_text(BASE_DIR)
    except Exception as exc:
        return f"Dependency check gagal: {exc}"


def fast_engine_test_report():
    try:
        return fast_engine_test_text(BASE_DIR)
    except Exception as exc:
        return f"Fast Engine test gagal: {exc}"

def fast_engine_rebind_report():
    """Bind CT2 model and SentencePiece folders to one validated path for this WebUI runtime."""
    try:
        mgr = FastModelManager(BASE_DIR)
        data = mgr.status()
        model_dir = str(data.get("model_dir") or mgr.model_dir)
        required = ["config.json", "model.bin", "shared_vocabulary.json", "source.spm", "target.spm"]
        missing = [name for name in required if not (Path(model_dir) / name).exists()]
        if missing:
            return "Repair / Rebind CT2 gagal: file belum lengkap pada model_dir. Missing: " + ", ".join(missing)
        for key in ["TITAN_CT2_EN_ID_DIR", "TITAN_SPM_EN_ID_DIR", "ORT_FAST_CT2_MODEL_DIR", "ORT_LITE_CT2_MODEL_DIR"]:
            os.environ[key] = model_dir
        os.environ["ORT_CT2_PATH_REBIND"] = "1"
        test = mgr.quick_translation_test("Hello")
        return "\n".join([
            f"Repair / Rebind CT2 Model & SPM Path {APP_VERSION_TAG}",
            "==========================================",
            f"model_dir_used = {model_dir}",
            f"spm_dir_used   = {model_dir}",
            f"path_conflict  = False",
            f"quick_test_ok  = {bool(test.get('ok'))}",
            f"output         = {test.get('output') or '-'}",
            "Child runtime launch will overwrite CT2/SPM env to this validated path.",
        ])
    except Exception as exc:
        return f"Repair / Rebind CT2 gagal: {type(exc).__name__}: {exc}"


def analyze_last_session_text():
    try:
        data = analyze_session(base_dir=BASE_DIR)
        if not data.get("ok"):
            return "Analyze Last Session: belum ada session JSONL. Jalankan ORT lalu Stop terlebih dahulu."
        lines = ["Analyze Last Session v8.7", "========================", f"Log: {data.get('path','-')}", f"Avg OCR: {data.get('avg_ocr_ms')} ms | p95: {data.get('p95_ocr_ms')} ms", f"Avg Translate: {data.get('avg_translation_ms')} ms | p95: {data.get('p95_translation_ms')} ms", f"Cache hit rate: {data.get('cache_hit_rate')}", f"Runtime pressure: {data.get('runtime_pressure_events')}", f"GFL footer artifacts: {data.get('gfl_footer_artifact_events', 0)} | credit/non-dialog: {data.get('gfl_credit_text_events', 0)}", f"GFL suppressed text/frame: {data.get('gfl_non_dialog_skips', 0)} / {data.get('gfl_frame_skips', 0)}", "", "Rekomendasi:"]
        lines += ["- " + x for x in data.get("recommendations", [])]
        return "\n".join(lines)
    except Exception as exc:
        return f"Analyze Last Session gagal: {exc}"


def reset_settings_text(scope="all"):
    try:
        return reset_settings(scope=scope, base_dir=BASE_DIR, backup=True)
    except Exception as exc:
        return f"Reset settings gagal: {exc}"


def reset_live_log_text():
    try:
        MANAGER.clear_log()
        return ""
    except Exception:
        return ""


def profile_resolver_text(game="GFL2_EXILIUM", model_key="", group="normal", settings_mode="recommended", engine="hybrid"):
    try:
        return resolve_profile_text(game, model_key, group, settings_mode, engine)
    except Exception as exc:
        return f"Profile Resolver gagal: {exc}"


def conflict_detector_text():
    try:
        return detect_conflicts_text(BASE_DIR)
    except Exception as exc:
        return f"Conflict Detector gagal: {exc}"


def gpu_cuda_text():
    try:
        return gpu_cuda_diagnostic_text(BASE_DIR)
    except Exception as exc:
        return f"GPU/CUDA diagnostic gagal: {exc}"


def lite_gpu_guard_text():
    try:
        return lite_gpu_status_text(BASE_DIR)
    except Exception as exc:
        return f"Lite GPU Guard status gagal: {exc}"

def diagnose_repair_text():
    try:
        return diagnose_repair_center_text(BASE_DIR, export=False)
    except Exception as exc:
        return f"Diagnose & Repair Center gagal: {exc}"

def export_diagnostic_report_text():
    try:
        return diagnose_repair_center_text(BASE_DIR, export=True)
    except Exception as exc:
        return f"Export diagnostic report gagal: {exc}"

def npc_cleanup_text():
    try:
        from tools.npc_database_cleanup import cleanup
        return cleanup(BASE_DIR)
    except Exception as exc:
        return f"NPC cleanup gagal: {exc}"


def load_prefs():
    default = {
        "model": "ORTCore Lite IDN V3",
        "model_group": "lite_idn",
        "game": "GFL",
        "mode": "auto",
        "engine": "hybrid",
        "interval_ms": 240,
        "ocr_resolution": 55,
        "performance_policy": "auto",
        "normal_override": False,
        "settings_mode": "recommended",
        "ui_mode": "recommended",
        "translation_source": "ocr",
        "audio_input_mode": "loopback",
        "audio_device_index": "-1",
        "audio_language": "auto",
        "audio_processing": "vad",
        "audio_profile": "normal",
        "audio_mode": "hybrid",
        "audio_usage": "live_media",
        "audio_engine": "azure_fallback",
        "responsive_story_mode": False,
        "diagnostic_profile": "baseline",
        "mode_buffer_enabled": False,
    }
    data = _load_json(PREFS_PATH, default)
    # v8.7.1 migration: only upgrade the untouched shipped v8.7 first-run GFL preset.
    # Manual Interval/Freeze preferences remain user-controlled.
    if (str(data.get("game", "")).upper() == "GFL"
            and data.get("model") == "ORTCore Lite IDN V3"
            and str(data.get("settings_mode", "recommended")).lower() == "recommended"
            and str(data.get("mode", "")).lower() == "interval"
            and int(data.get("interval_ms", 0) or 0) == 240
            and int(data.get("ocr_resolution", 0) or 0) == 55):
        data["mode"] = "auto"
        try:
            _save_json(PREFS_PATH, data)
        except Exception:
            pass
    return data


def save_prefs(model, game, mode, engine, interval_ms, model_group=None, ocr_resolution=None, performance_policy=None, normal_override=None, settings_mode=None, ui_mode=None, responsive_story_mode=None, diagnostic_profile=None, mode_buffer_enabled=None, translation_source=None, audio_input_mode=None, audio_device_index=None, audio_language=None, audio_processing=None, audio_profile=None, audio_mode=None, audio_usage=None, audio_engine=None):
    data = load_prefs()
    data.update({
        "model": model,
        "game": game,
        "mode": mode,
        "engine": engine,
        "interval_ms": int(interval_ms),
    })
    if model_group:
        data["model_group"] = model_group
    if ocr_resolution is not None:
        data["ocr_resolution"] = int(ocr_resolution)
    if performance_policy is not None:
        data["performance_policy"] = str(performance_policy)
    if normal_override is not None:
        data["normal_override"] = bool(normal_override)
    if settings_mode is not None:
        data["settings_mode"] = str(settings_mode or "recommended")
    if ui_mode is not None:
        data["ui_mode"] = str(ui_mode or "recommended")
    if responsive_story_mode is not None:
        data["responsive_story_mode"] = bool(responsive_story_mode)
    if diagnostic_profile is not None:
        data["diagnostic_profile"] = str(diagnostic_profile or "baseline")
    if mode_buffer_enabled is not None:
        data["mode_buffer_enabled"] = bool(mode_buffer_enabled)
    if translation_source is not None:
        data["translation_source"] = str(translation_source or "ocr")
    if audio_input_mode is not None:
        data["audio_input_mode"] = str(audio_input_mode or "loopback")
    if audio_device_index is not None:
        data["audio_device_index"] = str(audio_device_index)
    if audio_language is not None:
        data["audio_language"] = str(audio_language or "auto")
    if audio_processing is not None:
        data["audio_processing"] = str(audio_processing or "vad")
    if audio_profile is not None:
        data["audio_profile"] = str(audio_profile or "normal")
    if audio_mode is not None:
        data["audio_mode"] = normalize_audio_mode(audio_mode)
    if audio_usage is not None:
        data["audio_usage"] = normalize_audio_usage(audio_usage)
    if audio_engine is not None:
        data["audio_engine"] = normalize_audio_engine(audio_engine)
    _save_json(PREFS_PATH, data)
    try:
        save_state({"version": APP_VERSION_TAG, "model": model, "game": game, "mode": mode, "engine": engine, "requested_engine": engine, "requested_mode": mode, "requested_interval_ms": int(interval_ms), "interval_ms": int(interval_ms), "requested_ocr_resolution": data.get("ocr_resolution"), "ocr_resolution": data.get("ocr_resolution"), "settings_mode": data.get("settings_mode", "recommended"), "translation_source": data.get("translation_source", "ocr"), "audio_input_mode": data.get("audio_input_mode", "loopback"), "audio_device_index": data.get("audio_device_index", "-1"), "audio_language": data.get("audio_language", "auto"), "audio_processing": data.get("audio_processing", "vad"), "audio_profile": data.get("audio_profile", "normal"), "audio_requested_mode": data.get("audio_mode", "hybrid"), "audio_usage": data.get("audio_usage", "live_media"), "audio_engine_requested": data.get("audio_engine", "azure_fallback"), "responsive_story_mode": bool(data.get("responsive_story_mode", False)), "diagnostic_profile": str(data.get("diagnostic_profile", "baseline")), "mode_buffer_enabled": bool(data.get("mode_buffer_enabled", False))}, BASE_DIR)
    except Exception:
        pass
    return data


# v7: daftar model tidak lagi diulang manual di launcher.
# Sumber utama ada di model_registry.py, dengan alias lama tetap ditangani di sana.
def _resolve_model(model_title: str):
    try:
        return get_model_by_title(model_title)
    except Exception:
        return get_model_by_title("ORTCore V2")



def _fast_profile_modifier(preset_key: str, mode: str = "auto") -> dict:
    """v8.4: Fast model identity layer.

    The selected mode keeps its global meaning. Fast V1/V2/Fast IDN only tune latency,
    stability, cleanup, cache aggressiveness, and IDN post-processing on top of that mode.
    """
    key = str(preset_key or "").lower()
    mode_l = str(mode or "auto").lower()
    if key == "fast_v1":
        return {
            "profile": "fast_v1_speed_first",
            "label": "Fast V1 v8.7 ultra speed: OCR 40%, latency minimum, akurasi/polish minimal.",
            "max_wait_auto": "120",
            "max_wait_interval": "150",
            "progressive_min": "45",
            "duplicate_hold": "240" if mode_l == "auto" else "360",
            "stable_repeats": "1",
            "quick_punct": "1",
            "preprocess": "fast",
            "fuzzy_aggressive": "1",
            "speaker_strictness": "normal",
            "idn_naturalizer": "0",
            "postprocess": "minimal",
            "skip_bridge_postprocess": "1",
        }
    if key == "fast_idn":
        return {
            "profile": "fast_idn_naturalized",
            "label": "Fast IDN v8.7: OCR 50%, basis Fast V2 + IDN fast_light.",
            "max_wait_auto": "240",
            "max_wait_interval": "310",
            "progressive_min": "90",
            "duplicate_hold": "460" if mode_l == "auto" else "620",
            "stable_repeats": "1",
            "quick_punct": "1",
            "preprocess": "balanced_idn",
            "fuzzy_aggressive": "1",
            "speaker_strictness": "strict",
            "idn_naturalizer": "1",
            "postprocess": "idn_polish",
            "skip_bridge_postprocess": "1",
        }
    if key == "fast_v2":
        return {
            "profile": "fast_v2_balanced",
            "label": "Fast V2 v8.7 low-latency balanced: OCR 45%, cleanup tetap aktif.",
            "max_wait_auto": "180",
            "max_wait_interval": "240",
            "progressive_min": "70",
            "duplicate_hold": "360" if mode_l == "auto" else "520",
            "stable_repeats": "1",
            "quick_punct": "1",
            "preprocess": "balanced",
            "fuzzy_aggressive": "1",
            "speaker_strictness": "strict",
            "idn_naturalizer": "0",
            "postprocess": "balanced",
            "skip_bridge_postprocess": "1",
        }
    return {
        "profile": "fast_generic",
        "label": "Fast generic profile.",
        "max_wait_auto": "260",
        "max_wait_interval": "320",
        "progressive_min": "120",
        "duplicate_hold": "520" if mode_l == "auto" else "700",
        "stable_repeats": "1",
        "quick_punct": "1",
        "preprocess": "balanced",
        "fuzzy_aggressive": "1",
        "speaker_strictness": "normal",
        "idn_naturalizer": "0",
        "postprocess": "minimal",
    }


def _lite_profile_modifier(preset_key: str, mode: str = "auto") -> dict:
    """v8.6 Lite/Lite IDN efficiency layer.

    Wide GFL2 dialog boxes are allowed; the profile lowers latency and enables
    noise filtering rather than forcing users to snip a too-small region.
    """
    key = str(preset_key or "").lower()
    if not key.startswith("lite"):
        return {}
    level = 2
    for n in (5, 4, 3, 2, 1):
        if f"v{n}" in key:
            level = n
            break
    idn = "idn" in key
    table = {
        1: dict(max_auto="240", max_interval="280", progressive="105", duplicate="520", voice="700", stable="1"),
        2: dict(max_auto="300", max_interval="350", progressive="125", duplicate="640", voice="850", stable="1"),
        3: dict(max_auto="360", max_interval="420", progressive="145", duplicate="760", voice="950", stable="1"),
        4: dict(max_auto="400", max_interval="460", progressive="155", duplicate="850", voice="1050", stable="1"),
        5: dict(max_auto="440", max_interval="500", progressive="165", duplicate="900", voice="1100", stable="1"),
    }
    prof = table.get(level, table[2]).copy()
    prof["profile"] = f"lite_idn_v{level}_efficient" if idn else f"lite_v{level}_efficient"
    ocr_label = {1: "OCR 40% diagnostic + rescue", 2: "OCR 45% efficient + rescue", 3: "OCR 50% story baseline", 4: "OCR 55% quality safe", 5: "OCR 60% quality"}.get(level, "OCR balanced")
    prof["label"] = (("Lite IDN" if idn else "Lite") + f" V{level} v8.7 profile · {ocr_label}")
    prof["idn_naturalizer"] = "0"  # IDN Quality Layer handles Lite IDN lightly in runtime_bridge.
    return prof

def _dialog_scheduler_env(mode: str, preset_key: str = "", game: str = "", responsive_story: bool = False) -> dict:
    """Map user-facing modes to scheduler behavior.

    v8.4 keeps Freeze/Interval/Auto as global semantics and layers Fast V1/V2/IDN
    as profile modifiers rather than redefining the modes.
    """
    mode_l = str(mode or "auto").lower()
    key = str(preset_key or "").lower()
    game_u = str(game or "").upper()
    fast = key.startswith("fast")
    lite = key.startswith("lite")
    prof = _fast_profile_modifier(key, mode_l) if fast else (_lite_profile_modifier(key, mode_l) if lite else {})
    env = {
        "ORT_STORY_DIALOGUE_SCHEDULER": "1",
        "ORT_IMAGE_HASH_GATE": "1",
        "ORT_TEXT_ROI_CHANGE_GATE": "1",
        "ORT_TEXT_ROI_CHANGE_THRESHOLD": "0.018",
        "ORT_TEXT_ROI_MIN_RUN_GAP_MS": "90",
        "ORT_TEXT_ROI_CONFIRM_DELAY_MS": "450",
        "ORT_PROGRESSIVE_QUEUE_COALESCE": "1",
        "ORT_TURN_STATE_MACHINE": "1",
        "ORT_DIALOG_CLEAR_MISSES": "2",
        "ORT_DIALOG_CLEAR_MIN_MS": "550",
        "ORT_TRANSACTIONAL_OVERLAY": "1",
        "ORT_FUZZY_CACHE_KEY": "1",
        "ORT_SPEAKER_GATE_V2": "1",
        "ORT_NUMERIC_DUAL_PASS": "1",
        "ORT_NUMERIC_ROI_ONLY": "1",
        "ORT_ALLOW_FORCE_CPU": "0",
        "ORT_FAST_PROFILE": prof.get("profile", "standard"),
        "ORT_FAST_PROFILE_LABEL": prof.get("label", "Standard model profile"),
        "ORT_FAST_PREPROCESS_PROFILE": prof.get("preprocess", "standard"),
        "ORT_FUZZY_CACHE_AGGRESSIVE": prof.get("fuzzy_aggressive", "0"),
        "ORT_SPEAKER_GATE_STRICTNESS": prof.get("speaker_strictness", "normal"),
        "ORT_IDN_NATURALIZER": prof.get("idn_naturalizer", "0"),
        "ORT_FAST_POSTPROCESS_PROFILE": prof.get("postprocess", "standard"),
        "ORT_FAST_SKIP_HEAVY_BRIDGE_POST": prof.get("skip_bridge_postprocess", "0"),
        "ORT_LITE_WIDE_DIALOG_FILTER": "1" if lite else "0",
        "ORT_OCR_NOISE_REJECT": "1" if lite else "0",
        "ORT_LITE_ADAPTIVE_OCR": "1" if lite else "0",
        "ORT_STABLE_FINAL_CACHE_V2": "1",
        "ORT_CURRENT_DIALOG_MEMO": "1",
        "ORT_IDN_EVAL_EXPORT": "1" if "idn" in key else "0",
        "ORT_IDN_WARMUP": "1" if "idn" in key else "0",
        "ORT_RESPONSIVE_STORY_MODE": "1" if (responsive_story or game_u == "GFL2_EXILIUM") else "0",
        "ORT_LATEST_FRAME_WINS": "1" if (responsive_story or game_u == "GFL2_EXILIUM") else "0",
        "ORT_RESPONSIVE_LIGHT_PREVIEW": "1" if (responsive_story or game_u == "GFL2_EXILIUM") else "0",
        "ORT_RESPONSIVE_SKIP_BRIDGE_PREVIEW": "1" if (responsive_story or game_u == "GFL2_EXILIUM") else "0",
        "ORT_ENTITY_SPAN_PIPELINE": "1",
        "ORT_SPEAKER_TRANSITION_GUARD": "1",
        "ORT_GFL2_EXACT_FALLBACK_ONLY": "1",
        "ORT_SEMANTIC_FAITHFULNESS_GATE": "1",
        "ORT_DIALOGUE_COMPLETENESS_GATE": "1",
        "ORT_CT2_PATH_REBIND": "1",
        "ORT_ADAPTIVE_READABILITY_GUARD": "1" if (lite or fast) else "0",
        "ORT_OCR_STORY_MIN_PERCENT": "50",
        "ORT_NAME_ROI_MIN_PERCENT": "50",
        "ORT_READABILITY_RESCUE_COOLDOWN_MS": "360",
        "ORT_IDN_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
        "ORT_SCOPED_CACHE_VERSION": "v8_7_9_responsive_turn_safe_ct2",
        "ORT_FAITHFULNESS_V2": "1",
        "ORT_QUR_CORRUPTION_QUARANTINE": "1",
        "ORT_STRICT_CT2_STORY": "1",
        "ORT_DISABLE_ARGOS_PROGRESSIVE_WHEN_CT2": "1",
        "ORT_HARD_STRICT_CT2_STORY": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_FORCE_TRUSTED_PREVIEW": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_TURN_SAFE_OVERLAY": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_SCENE_EXIT_GUARD": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_SEMANTIC_FIDELITY_GUARD": "1",
        "ORT_IDN_OVER_CT2": "1" if ("idn" in key or (not lite and not fast)) else "0",
        "ORT_FINAL_ONLY_SAFE_COMMIT": "1" if ("idn" in key or (not lite and not fast)) else "0",
        "ORT_MODE_POLICY_VERSION": f"{APP_VERSION_TAG}_mode_policy_v2",
        "ORT_DIALOG_STABILITY_ACCUMULATOR": "1",
        "ORT_OVERLAY_ANTI_FLICKER_BUFFER": "1",
        "ORT_OVERLAY_COMMIT_GATE": "1",
        "ORT_OVERLAY_FINAL_OVERRIDE": "1",
        "ORT_RECORDING_TELEMETRY": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_TEMPORAL_OCR_CONSENSUS": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_MANDATORY_FINAL_COMMIT_V2": "1" if game_u == "GFL2_EXILIUM" else "0",
        "ORT_BAD_CACHE_SHIELD_V2": "1",
        "ORT_STALE_OVERLAY_LIMIT": "1",
    }
    if mode_l == "freeze":
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "freeze_manual",
            "ORT_DIALOG_STABLE_MS": "0",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1"),
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "900",
            "ORT_IMAGE_HASH_THRESHOLD": "5",
            "ORT_TEXT_ROI_MAX_HOLD_MS": "900",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
            "ORT_FREEZE_OCR_OVERRIDE": "1",
            "ORT_FREEZE_OCR_PERCENT": "100",
            "ORT_FREEZE_FINAL_ONLY": "1",
            "ORT_OVERLAY_MIN_VISIBLE_MS": "0",
            "ORT_OVERLAY_MIN_TOKEN_GAIN": "1",
        })
    elif mode_l == "auto":
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "auto_story",
            "ORT_DIALOG_PROGRESSIVE_COMMIT": "1",
            "ORT_DIALOG_STABLE_MS": "0",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1") if fast else "1",
            "ORT_DIALOG_MAX_WAIT_MS": prof.get("max_wait_auto", prof.get("max_auto", "420")),
            "ORT_DIALOG_DUPLICATE_HOLD_MS": prof.get("duplicate_hold", prof.get("duplicate", "850")),
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": "240" if game_u == "GFL2_EXILIUM" else prof.get("progressive_min", prof.get("progressive", "180")),
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "8" if game_u == "GFL2_EXILIUM" else ("2" if key == "fast_v1" else "3"),
            "ORT_AUTO_SMOOTH_MODE": "1",
            "ORT_AUTO_SMOOTH_MIN_MS": "240" if key == "fast_v1" else "260",
            "ORT_AUTO_SMOOTH_MIN_TOKEN_GAIN": "3",
            "ORT_AUTO_SMOOTH_MIN_CHAR_DELTA": "10",
            "ORT_OVERLAY_MIN_VISIBLE_MS": "620" if key == "fast_v1" else ("650" if lite else "500"),
            "ORT_OVERLAY_MIN_TOKEN_GAIN": "3",
            "ORT_OVERLAY_SIMILARITY_THRESHOLD": "0.92",
            "ORT_DIALOG_QUICK_PUNCT_COMMIT": prof.get("quick_punct", "1"),
            "ORT_STABLE_TEXT_COMMIT": "0",
            "ORT_IMAGE_HASH_GATE": "1",
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "15000",
            "ORT_IMAGE_HASH_THRESHOLD": "4",
            "ORT_TEXT_ROI_MAX_HOLD_MS": "15000",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
            "TITAN_AUTO_SNAPSHOT_MIN_MS": "45" if key == "fast_v1" else ("60" if key == "fast_v2" else ("75" if key == "fast_idn" else "90")),
        })
    else:
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "interval_auto",
            "ORT_DIALOG_CLASSIC_INTERVAL": "1",
            "ORT_DIALOG_PROGRESSIVE_COMMIT": "1",
            "ORT_DIALOG_STABLE_MS": "160" if game_u == "GFL2_EXILIUM" else ("0" if fast else "80"),
            "ORT_INTERVAL_STABLE_MODE": "1",
            "ORT_INTERVAL_STORY_AWARE": "1",
            "ORT_INTERVAL_STABLE_MS": "480" if game_u == "GFL2_EXILIUM" else "420",
            "ORT_INTERVAL_MIN_TOKEN_GAIN": "5",
            "ORT_INTERVAL_MIN_CHAR_DELTA": "14",
            "ORT_INTERVAL_PROGRESSIVE_MIN_MS": "380",
            "ORT_OVERLAY_MIN_VISIBLE_MS": "900",
            "ORT_OVERLAY_MIN_TOKEN_GAIN": "4",
            "ORT_OVERLAY_SIMILARITY_THRESHOLD": "0.93",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1") if fast else "1",
            "ORT_DIALOG_MAX_WAIT_MS": prof.get("max_wait_interval", prof.get("max_interval", "550")),
            "ORT_DIALOG_DUPLICATE_HOLD_MS": prof.get("duplicate_hold", prof.get("duplicate", "1300")),
            "ORT_DIALOG_VOICE_HOLD_MS": (("360" if key == "fast_v1" else ("650" if key == "fast_v2" else "850")) if (fast and game_u == "GFL2_EXILIUM") else prof.get("voice", "1200")),
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": prof.get("progressive_min", prof.get("progressive", "180")),
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "2" if key == "fast_v1" else "3",
            "ORT_DIALOG_QUICK_PUNCT_COMMIT": prof.get("quick_punct", "1"),
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "90" if key == "fast_v1" else ("130" if key == "fast_v2" else ("160" if key == "fast_idn" else ("190" if lite else ("220" if game_u == "GFL2_EXILIUM" else "260")))),
            "ORT_IMAGE_HASH_THRESHOLD": "2",
            "ORT_TEXT_ROI_MAX_HOLD_MS": "8000",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
            "TITAN_AUTO_SNAPSHOT_MIN_MS": "45" if key == "fast_v1" else ("60" if key == "fast_v2" else ("75" if key == "fast_idn" else "90")),
        })
    if responsive_story and mode_l == "auto":
        env.update({
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": "260",
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "10",
            "ORT_DIALOG_MAX_WAIT_MS": "420",
            "ORT_DIALOG_DUPLICATE_HOLD_MS": "650",
            "ORT_AUTO_SMOOTH_MIN_MS": "260",
            "ORT_AUTO_SMOOTH_MIN_TOKEN_GAIN": "3",
            "ORT_OVERLAY_MIN_VISIBLE_MS": "500",
            "ORT_RESPONSIVE_QUEUE_TARGET": "0",
        })
    return env

def _performance_reason_text(strategy, fast_state: dict, mode: str) -> str:
    bits = []
    try:
        if (strategy.fast_path or getattr(strategy, "lite_enabled", False)) and not fast_state.get("active"):
            bits.append("CT2 belum aktif: runtime fallback ke Argos; preset OCR di bawah 50% tidak direkomendasikan untuk story GFL2 tanpa Adaptive Readability Rescue.")
        if getattr(strategy, "lite_enabled", False) and int(getattr(strategy, "ocr_resolution_percent", 50)) < 50:
            bits.append("OCR Lite di bawah 50% berjalan sebagai ultra-efficient/diagnostic; v8.7.6 dapat mengulang frame rusak pada 50%+.")
        if strategy.fast_path:
            prof = _fast_profile_modifier(getattr(strategy, "model_key", ""), mode)
            bits.append(prof.get("label", "Fast profile aktif."))
        if str(mode or "").lower() == "freeze":
            bits.append("Freeze = manual story click; scheduler commit langsung.")
        elif str(mode or "").lower() == "interval":
            bits.append("Interval = Freeze otomatis klasik; v8.4 commit cepat pada snapshot baru dan tidak menahan teks terlalu lama.")
        else:
            bits.append("Auto = story otomatis ala visual novel; v8.4 menerjemahkan teks bertahap mengikuti kemunculan dialog.")
        bits.append("Text-aware ROI Change Gate aktif: frame dialog statis tidak memanggil EasyOCR ulang, sedangkan perubahan teks tetap diproses segera.")
        bits.append("Fuzzy Cache Key aktif: typo OCR kecil diarahkan ke cache yang sama.")
        if getattr(strategy, "idn_enabled", False):
            bits.append(f"IDN Quality Layer v8.7 aktif (fondasi v8.6): mode={getattr(strategy, 'idn_quality_mode', lambda: 'balanced')()} + terminology consistency.")
    except Exception:
        pass
    return " ".join(bits)


class ProcessManager:
    def __init__(self):
        self.proc: Optional[subprocess.Popen] = None
        self.lines = []
        self.status = "IDLE"
        self.last_error = ""
        self.lock = threading.Lock()
        self.current_game = "GFL2_EXILIUM"
        self.current_source = "ocr"
        self.source_switching = False
        self.stop_requested = False
        self.stop_at = 0.0
        self.pending_candidate_notice = ""
        self.session = None

    def _push(self, text: str):
        clean = text.rstrip("\n")
        with self.lock:
            # v8.1: full log is preserved on disk; UI keeps a safe in-memory copy/tail.
            self.lines.append(clean)
            max_lines = int(os.environ.get("ORT_WEBUI_LOG_TAIL_LINES", "3000"))
            if max_lines > 0 and len(self.lines) > max_lines:
                self.lines = self.lines[-max_lines:]
        try:
            if self.session:
                self.session.append_line(clean)
        except Exception:
            pass
        try:
            record_runtime_line(self.current_game, clean)
        except Exception:
            pass

    def get_log(self):
        with self.lock:
            return "\n".join(self.lines)

    def clear_log(self):
        """Clear only the WebUI live-log buffer. Session files remain intact for Analyze Last Session."""
        with self.lock:
            self.lines = []
        self._push(f"[WEBUI {APP_VERSION_TAG}] Live Log tampilan direset; file session tetap disimpan untuk Analyze Last Session.")

    def get_status_text(self):
        err = f"\nLAST_ERROR: {self.last_error}" if self.last_error else ""
        return f"STATUS: {self.status}{err}"

    def _reader(self):
        assert self.proc is not None and self.proc.stdout is not None
        for line in self.proc.stdout:
            self._push(line)
        code = self.proc.wait()
        if self.stop_requested:
            self.status = "STOP"
            try:
                save_state({"status": "STOP", "active_engine": "stopped"}, BASE_DIR)
            except Exception:
                pass
            self.stop_at = time.time()
            try:
                close_session("process_stop")
            except Exception:
                pass
            self._prepare_candidate_notice()
        elif code == 0:
            # clean exit, often from ESC / normal close
            self.status = "STOP"
            try:
                save_state({"status": "STOP", "active_engine": "stopped"}, BASE_DIR)
            except Exception:
                pass
            self.stop_at = time.time()
            try:
                close_session("process_exit_0")
            except Exception:
                pass
            self._prepare_candidate_notice()
        else:
            self.status = "ERROR"
            try:
                save_state({"status": "ERROR", "active_engine": "error"}, BASE_DIR)
            except Exception:
                pass
            if not self.last_error:
                self.last_error = f"Process exited with code {code}"
            self._push(f"[WEBUI] Process selesai dengan code {code}")

    def _prepare_candidate_notice(self):
        if self.current_source != "ocr":
            self.pending_candidate_notice = ""
            return
        settings = load_settings()
        items, counts = get_candidates(self.current_game)
        items = [x for x in items if counts.get(x, 0) >= 1][:20]
        if items and settings.get('popup_on_stop', True):
            top = ", ".join(items[:6])
            self.pending_candidate_notice = (
                f"Nama/Kata baru tercatat ({len(items)}): {top}. "
                f"Buka tab Pengolahan Data untuk olah atau skip."
            )
        else:
            self.pending_candidate_notice = ""

    def candidate_notice(self):
        return self.pending_candidate_notice

    def start(self, model, game, mode, engine, interval_ms, ocr_resolution=65, performance_policy="auto", normal_override=False, settings_mode=None, responsive_story_mode=False, diagnostic_profile="baseline", mode_buffer_enabled=False):
        if self.source_switching:
            return self.get_status_text(), self.get_log(), "Pergantian sumber masih menghentikan runtime sebelumnya. Tunggu status Stop, lalu mulai kembali.", self.pending_candidate_notice
        if self.proc and self.proc.poll() is None:
            return self.get_status_text(), self.get_log(), "Model masih berjalan. Stop dulu sebelum start baru.", self.pending_candidate_notice

        settings_mode = (settings_mode or ("manual" if normal_override else "recommended")).lower()
        normal_override = settings_mode in {"manual", "normal"}
        performance_policy = "normal" if normal_override else "auto"
        save_prefs(model, game, mode, engine, interval_ms, ocr_resolution=ocr_resolution, performance_policy=performance_policy, normal_override=normal_override, settings_mode=settings_mode, responsive_story_mode=responsive_story_mode, diagnostic_profile=diagnostic_profile, mode_buffer_enabled=mode_buffer_enabled, translation_source="ocr")
        if load_settings().get("auto_reset_candidates", False):
            try:
                clear_candidates(game)
            except Exception:
                pass
        cfg = get_runtime_config()
        runtime_python = Path(cfg["runtime_python"])
        if not runtime_python.exists():
            self.status = "ERROR"
            self.last_error = f"Runtime Python tidak ditemukan: {runtime_python}"
            self._push(f"[WEBUI] {self.last_error}")
            return self.get_status_text(), self.get_log(), self.last_error, self.pending_candidate_notice

        preset = _resolve_model(model)
        try:
            save_prefs(model, game, mode, engine, interval_ms, model_group=preset.tier, ocr_resolution=ocr_resolution, performance_policy=performance_policy, normal_override=normal_override, settings_mode=settings_mode, mode_buffer_enabled=mode_buffer_enabled, translation_source="ocr")
        except Exception:
            pass
        script_name = preset.script
        script_path = BASE_DIR / script_name
        if not script_path.exists():
            script_name = "TITANMAIN.py"
            script_path = BASE_DIR / script_name
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["ORT_RUNTIME_ROOT"] = cfg["runtime_root"]
        env["ORT_BOOT_MODE"] = str(mode).lower()
        env["ORT_BOOT_ENGINE"] = str(engine).lower()
        env["ORT_BOOT_INTERVAL_MS"] = str(int(interval_ms))
        env["ORT_GAME_OVERRIDE"] = str(game)
        env["ORT_BOOT_OCR_RESOLUTION"] = str(int(ocr_resolution))
        env["ORT_V71_CORE_PIPELINE"] = "1"
        env["ORT_RUNTIME_STRATEGY"] = "1"
        env["ORT_RUNTIME_CONTROL"] = "1"
        env["ORT_RUNTIME_STATUS"] = "1"
        env["ORT_LEGACY_CACHE_WARMUP"] = "0"
        env["ORT_WRITE_LEGACY_CACHE"] = "0"
        env["ORT_WRITE_LEGACY_TRAINING_LOG"] = "0"
        stop_path = BASE_DIR / "runtime_stop_request.json"
        env["ORT_STOP_REQUEST_FILE"] = str(stop_path)
        clear_stop_request(BASE_DIR)
        env.update(preset.env_map())
        env.update(env_from_settings(game, model_key=preset.key, policy_override=("normal" if normal_override else performance_policy), ocr_resolution=int(ocr_resolution)))
        strategy = build_strategy(
            model_key=preset.key,
            model_title=preset.title,
            group=preset.tier,
            family=preset.family,
            game=game,
            policy=("normal" if normal_override else performance_policy),
            requested_engine=engine,
            requested_mode=mode,
            requested_interval_ms=int(interval_ms),
            requested_ocr_resolution=int(ocr_resolution),
            normal_override=bool(normal_override),
        )
        env.update(strategy.to_env())
        # v8.4: strategy recommendations must not overwrite the user-selected WebUI mode.
        # Auto / Freeze / Interval have different UI semantics, while the strategy only provides safe defaults.
        requested_mode = str(mode or "auto").lower()
        requested_engine = str(engine or "hybrid").lower()
        requested_interval_ms = int(interval_ms)
        env["ORT_BOOT_MODE"] = requested_mode
        env["ORT_BOOT_ENGINE"] = requested_engine
        env["ORT_BOOT_INTERVAL_MS"] = str(requested_interval_ms)
        env["ORT_UI_REQUESTED_MODE"] = requested_mode
        env["ORT_UI_REQUESTED_INTERVAL_MS"] = str(requested_interval_ms)
        diagnostic_profile = str(diagnostic_profile or "baseline")
        applied_responsive = bool(responsive_story_mode or diagnostic_profile == "responsive_story")
        env.update(_dialog_scheduler_env(requested_mode, preset.key, game, applied_responsive))
        env["ORT_DIAGNOSTIC_PROFILE"] = diagnostic_profile
        env["ORT_MODE_BUFFER"] = "1" if bool(mode_buffer_enabled) else "0"
        env["ORT_MODE_BUFFER_MS"] = os.environ.get("ORT_MODE_BUFFER_MS", "700")
        if bool(mode_buffer_enabled):
            env["ORT_GFL2_RECORDING_PROFILE"] = "1"
        if diagnostic_profile == "diagnostic_no_name_roi":
            env["ORT_GFL2_SPEAKER_ROI"] = "0"
            env["ORT_DIAGNOSTIC_WARNING"] = "Name ROI disabled for A/B measurement; speaker labels may be inaccurate."
        # v8.4: Lite/Lite IDN can use GPU Efficient with VRAM budget guard.
        try:
            lite_decision = apply_lite_gpu_env(env, model_key=preset.key, group=preset.tier, game=game, requested_engine=requested_engine, requested_ocr=int(ocr_resolution), base_dir=BASE_DIR)
            write_lite_gpu_status(BASE_DIR, lite_decision)
        except Exception:
            lite_decision = None
        # v8.3: propagate detected Fast CT2 model folder to runtime.
        try:
            _fast_mgr_for_env = FastModelManager(BASE_DIR)
            _fast_state_for_env = _fast_mgr_for_env.status()
            _validated_ct2_dir = str(_fast_state_for_env.get("model_dir") or _fast_mgr_for_env.model_dir)
            env["ORT_FAST_CT2_MODEL_DIR"] = _validated_ct2_dir
            env["ORT_LITE_CT2_MODEL_DIR"] = _validated_ct2_dir
            env["TITAN_CT2_EN_ID_DIR"] = _validated_ct2_dir
            env["TITAN_SPM_EN_ID_DIR"] = _validated_ct2_dir
            env["ORT_CT2_MODEL_DIR_USED"] = _validated_ct2_dir
            env["ORT_CT2_SPM_DIR_USED"] = _validated_ct2_dir
            env["ORT_CT2_PATH_REBIND"] = "1"
            env.setdefault("TITAN_CT2_DEVICE", os.environ.get("TITAN_CT2_DEVICE", "cpu"))
            env.setdefault("TITAN_CT2_COMPUTE_TYPE", os.environ.get("TITAN_CT2_COMPUTE_TYPE", "int8"))
            if str(game).upper() == "GFL2_EXILIUM" and not bool(_fast_state_for_env.get("active")):
                env["ORT_CT2_FALLBACK_ACTIVE"] = "1"
                env["ORT_OCR_STORY_MIN_PERCENT"] = "50"
                env["ORT_ADAPTIVE_READABILITY_GUARD"] = "1" if (strategy.fast_path or strategy.lite_enabled) else env.get("ORT_ADAPTIVE_READABILITY_GUARD", "0")
        except Exception:
            pass
        env["ORT_GAME_OVERRIDE"] = str(game)
        env["ORT_GAME_PROFILE"] = str(game)
        env["TITAN_MODEL_LABEL"] = preset.title
        env["ORT_NORMAL_OVERRIDE"] = "1" if normal_override else "0"
        env["ORT_SETTINGS_MODE"] = settings_mode
        # v8.1: inject saved Online Assist config into child runtime environment.
        try:
            online_cfg = apply_online_config_to_env(BASE_DIR)
            for key in ["TITAN_ONLINE_ASSIST", "ORT_ONLINE_PROVIDER", "ORT_ONLINE_ENDPOINT", "ORT_ONLINE_API_KEY", "TITAN_ONLINE_TIMEOUT", "ORT_ONLINE_MAX_CHARS"]:
                if key in os.environ:
                    env[key] = os.environ[key]
            if strategy.level != 4 or strategy.core_profile in {"safe_game", "potato", "fast"}:
                # v8.6: only V4 may use controlled Online Assist in live loop.
                env["TITAN_ONLINE_ASSIST"] = "0"
                env["ORT_ALLOW_ONLINE_ASSIST"] = "0"
            else:
                env["ORT_ALLOW_ONLINE_ASSIST"] = "1"
        except Exception:
            pass
        # v8.9.1: Freeze is snapshot/manual accuracy mode, so it may use OCR 100%
        # even when the selected Lite/Fast model normally uses a lower OCR preset.
        if requested_mode == "freeze" and env.get("ORT_FREEZE_OCR_OVERRIDE", "1") == "1":
            try:
                freeze_ocr = max(int(env.get("ORT_BOOT_OCR_RESOLUTION", ocr_resolution)), int(env.get("ORT_FREEZE_OCR_PERCENT", "100")))
                env["ORT_BOOT_OCR_RESOLUTION"] = str(freeze_ocr)
                env["ORT_OCR_RESOLUTION_PERCENT"] = str(freeze_ocr)
                env["ORT_LITE_APPLIED_OCR"] = str(freeze_ocr)
                env["ORT_FREEZE_OCR_OVERRIDE_APPLIED"] = "1"
            except Exception:
                pass

        # v8.7.6: report the final applied OCR after Lite GPU guard / runtime policy,
        # not only the strategy value before safety or user-override resolution.
        applied_runtime_ocr = int(env.get("ORT_LITE_APPLIED_OCR", env.get("ORT_BOOT_OCR_RESOLUTION", strategy.ocr_resolution_percent)))
        env["ORT_APPLIED_OCR_RESOLUTION_PERCENT"] = str(applied_runtime_ocr)
        env["ORT_REQUESTED_OCR_RESOLUTION_PERCENT"] = str(int(ocr_resolution))
        write_strategy_status(strategy, BASE_DIR, extra={"source": "launcher", "selected_model": model, "selected_game": game, "requested_engine": engine, "requested_mode": mode, "requested_interval_ms": int(interval_ms), "requested_ocr_resolution": int(ocr_resolution), "effective_ocr_resolution": applied_runtime_ocr, "preset_ocr_resolution": getattr(preset, "ocr_resolution_percent", None), "adaptive_ocr_rescue_enabled": env.get("ORT_ADAPTIVE_READABILITY_GUARD", "0") == "1", "ocr_rescue_floor": int(env.get("ORT_OCR_STORY_MIN_PERCENT", "50")), "ct2_fallback_active": env.get("ORT_CT2_FALLBACK_ACTIVE", "0") == "1"})
        try:
            save_state({
                "version": APP_VERSION_TAG,
                "status": "RUNNING",
                "translation_source": "ocr",
                "model": model,
                "game": game,
                "settings_mode": settings_mode,
                "engine": engine,
                "active_engine": strategy.recommended_engine,
                "mode": mode,
                "active_mode": strategy.recommended_mode,
                "interval_ms": int(interval_ms),
                "requested_interval_ms": int(interval_ms),
                "effective_interval_ms": strategy.interval_floor_ms,
                "ocr_resolution": int(ocr_resolution),
                "requested_ocr_resolution": int(ocr_resolution),
                "effective_ocr_resolution": applied_runtime_ocr,
                "preset_ocr_resolution": getattr(preset, "ocr_resolution_percent", None),
                "runtime_ocr_rescue_enabled": env.get("ORT_ADAPTIVE_READABILITY_GUARD", "0") == "1",
                "runtime_ocr_rescue_floor": int(env.get("ORT_OCR_STORY_MIN_PERCENT", "50")),
                "ct2_fallback_active": env.get("ORT_CT2_FALLBACK_ACTIVE", "0") == "1",
                "safe_mode": strategy.core_profile in {"safe_game", "potato"},
                "fast_engine_status": "selected" if strategy.fast_path else "off",
                "dialog_scheduler_profile": _dialog_scheduler_env(mode, preset.key, game, bool(applied_responsive)).get("ORT_DIALOG_SCHEDULER_PROFILE", "-"),
                "fast_profile": env.get("ORT_FAST_PROFILE", "standard"),
                "lite_gpu_profile": env.get("ORT_LITE_GPU_PROFILE", "off"),
                "lite_gpu_reason": env.get("ORT_LITE_GPU_REASON", "-"),
                "responsive_story_mode": bool(applied_responsive),
                "diagnostic_profile": diagnostic_profile,
                "mode_buffer_enabled": bool(mode_buffer_enabled),
                "mode_buffer_ms": int(env.get("ORT_MODE_BUFFER_MS", "0")) if bool(mode_buffer_enabled) else 0,
                "entity_span_pipeline": True,
                "cache_namespace": env.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            }, BASE_DIR)
        except Exception:
            pass

        self.lines = []
        self.last_error = ""
        self.pending_candidate_notice = ""
        self.current_game = str(game)
        self.current_source = "ocr"
        self.session = start_session(BASE_DIR, str(game))
        try:
            env["ORT_SESSION_ID"] = self.session.session_id
            env["ORT_SESSION_FULL_LOG_PATH"] = str(self.session.full_log_path)
            env["ORT_SESSION_JSONL_PATH"] = str(self.session.jsonl_path)
        except Exception:
            pass
        try:
            fast_state = FastModelManager(BASE_DIR).status()
        except Exception:
            fast_state = {"state": "UNKNOWN", "active": False}
        perf_reason = _performance_reason_text(strategy, fast_state, mode)
        try:
            save_state({
                "version": APP_VERSION_TAG,
                "fast_engine_status": fast_state.get("state", "unknown"),
                "fast_engine_active": bool(fast_state.get("active")),
                "dialog_scheduler_profile": env.get("ORT_DIALOG_SCHEDULER_PROFILE", "-"),
                "text_roi_change_gate": env.get("ORT_TEXT_ROI_CHANGE_GATE", "1") == "1",
                "text_roi_max_hold_ms": int(env.get("ORT_TEXT_ROI_MAX_HOLD_MS", "0")),
                "image_hash_gate_fallback": env.get("ORT_IMAGE_HASH_GATE", "1") == "1",
                "fuzzy_cache_key": env.get("ORT_FUZZY_CACHE_KEY", "1") == "1",
                "performance_reason": perf_reason,
                "fast_profile": env.get("ORT_FAST_PROFILE", "standard"),
                "fast_profile_label": env.get("ORT_FAST_PROFILE_LABEL", "-"),
                "lite_gpu_profile": env.get("ORT_LITE_GPU_PROFILE", "off"),
                "lite_gpu_reason": env.get("ORT_LITE_GPU_REASON", "-"),
                "responsive_story_mode": bool(applied_responsive),
                "diagnostic_profile": diagnostic_profile,
                "mode_buffer_enabled": bool(mode_buffer_enabled),
                "mode_buffer_ms": int(env.get("ORT_MODE_BUFFER_MS", "0")) if bool(mode_buffer_enabled) else 0,
                "entity_span_pipeline": True,
                "cache_namespace": env.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            }, BASE_DIR)
        except Exception:
            pass
        self.status = "RUNNING"
        self.stop_requested = False
        effective_interval_msg = int(env.get("ORT_BOOT_INTERVAL_MS", interval_ms))
        self._push(f"[WEBUI {APP_VERSION_TAG}] START {model} | game={game} | strategy={strategy.strategy_name} | mode={str(mode).lower()} | engine={str(engine).lower()} | interval={effective_interval_msg}ms | requested_ocr={int(ocr_resolution)}% | applied_ocr={applied_runtime_ocr}% | rescue_floor={env.get('ORT_OCR_STORY_MIN_PERCENT','50')}% | adaptive_rescue={env.get('ORT_ADAPTIVE_READABILITY_GUARD','0')} | policy={performance_policy} | normal_override={normal_override} | mode_buffer={1 if bool(mode_buffer_enabled) else 0}")
        self._push("[WEBUI] strategy: " + " | ".join(strategy.summary_lines()[:5]))
        self._push(f"[WEBUI {APP_VERSION_TAG}] scheduler={env.get('ORT_DIALOG_SCHEDULER_PROFILE')} | fast_profile={env.get('ORT_FAST_PROFILE')} | diagnostic={diagnostic_profile} | responsive_story={env.get('ORT_RESPONSIVE_STORY_MODE')} | latest_frame_wins={env.get('ORT_LATEST_FRAME_WINS')} | text_roi_gate={env.get('ORT_TEXT_ROI_CHANGE_GATE')}:{env.get('ORT_TEXT_ROI_MAX_HOLD_MS')}ms | turn_state={env.get('ORT_TURN_STATE_MACHINE')} | atomic_overlay={env.get('ORT_TRANSACTIONAL_OVERLAY')} | fuzzy_cache={env.get('ORT_FUZZY_CACHE_KEY')} | voice_hold={env.get('ORT_DIALOG_VOICE_HOLD_MS', '-')}ms | mode_buffer={env.get('ORT_MODE_BUFFER','0')}:{env.get('ORT_MODE_BUFFER_MS','0')}ms")
        if env.get("ORT_FAST_PROFILE_LABEL"):
            self._push(f"[WEBUI {APP_VERSION_TAG}] fast_profile_note={env.get('ORT_FAST_PROFILE_LABEL')}")
        if env.get("ORT_LITE_GPU_EFFICIENT") == "1":
            self._push(f"[WEBUI {APP_VERSION_TAG}] lite_gpu={env.get('ORT_LITE_GPU_PROFILE')} | ct2_allowed={env.get('ORT_LITE_CT2_ALLOWED')} | requested_ocr={env.get('ORT_LITE_REQUESTED_OCR', env.get('ORT_BOOT_OCR_RESOLUTION'))}% | applied_ocr={env.get('ORT_LITE_APPLIED_OCR', env.get('ORT_BOOT_OCR_RESOLUTION'))}% | queue={env.get('ORT_LITE_APPLIED_QUEUE', env.get('TITAN_QUEUE_MAX'))} | reason={env.get('ORT_LITE_GPU_REASON')}")
        if env.get("ORT_GFL_LAYOUT") == "1":
            self._push(f"[WEBUI {APP_VERSION_TAG}] GFL layout=GFL_DIALOG_STANDARD | name_roi=1 | body_roi=1 | footer_mask=1 | scene_guard=1 | cache_normalized=1 | speaker_quarantine=3hits")
        if env.get("ORT_GFL2_SPEAKER_ROI") == "1":
            self._push(f"[WEBUI {APP_VERSION_TAG}] GFL2 speaker_roi=1 | trusted_registry=1 | verified_exact_catalog=1 | dual_helen_helena_guard=1 | full_backend_entity_span=1 | exact_fallback_only=1 | adaptive_readability_guard={env.get('ORT_ADAPTIVE_READABILITY_GUARD','0')} | stale_result_guard=1 | transactional_overlay=1 | single_final_per_turn=1 | explicit_clear=1 | critical_token_guard=1 | stable_final_cache_v2=1 | idn_eval_export=1 | faithfulness_v2=1 | strict_ct2_story=1 | qur_quarantine=1")
        elif diagnostic_profile == "diagnostic_no_name_roi" and str(game).upper() == "GFL2_EXILIUM":
            self._push(f"[WEBUI {APP_VERSION_TAG}][DIAGNOSTIC WARNING] Name ROI OFF hanya untuk uji A/B; label KSVK/Helen/Helena dapat hilang atau salah.")
        if strategy.fast_path and not bool(fast_state.get("active")):
            self._push(f"[WEBUI {APP_VERSION_TAG}][WARN] Fast CT2 belum aktif ({fast_state.get('state')}). Model Fast akan fallback Argos sehingga masih terasa lamban. model_dir={fast_state.get('model_dir', '-')}")
        self._push(f"[WEBUI {APP_VERSION_TAG}] performance_reason={perf_reason}")
        self._push(f"[WEBUI] runtime_python={runtime_python}")
        self._push(f"[WEBUI] script={script_name}")

        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
            # v8 safe-game: turunkan prioritas proses ORT agar game berat tetap diprioritaskan.
            if env.get("TITAN_HEAVY_GAME_SAFE") == "1":
                creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)

        self.proc = subprocess.Popen(
            [str(runtime_python), str(script_path)],
            cwd=str(BASE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        return self.get_status_text(), self.get_log(), f"Menjalankan {model}...", self.pending_candidate_notice

    def start_audio(self, model, game, input_mode="loopback", device_index="-1", language="auto", processing="vad", profile_key="normal", test_file="", audio_mode="hybrid", audio_usage="live_media", audio_engine="azure_fallback", language_correction="balanced", language_lock=False):
        if self.source_switching:
            return self.get_status_text(), self.get_log(), "Pergantian sumber masih menghentikan runtime sebelumnya. Tunggu status Stop, lalu mulai Audio.", self.pending_candidate_notice
        if self.proc and self.proc.poll() is None:
            return self.get_status_text(), self.get_log(), "Sesi lain masih berjalan. Stop terlebih dahulu sebelum memulai Audio.", self.pending_candidate_notice

        version_contract = runtime_version_contract()
        if not version_contract.get("ready"):
            self.status = "ERROR"
            self.last_error = (
                "INSTALASI ORT TERCAMPUR DAN AUDIO DIBLOKIR.\n"
                f"Versi proses ini: {version_contract.get('expected')}. "
                f"Versi file: {version_contract.get('values')}.\n"
                "Tutup seluruh WebUI/Audio ORT, ekstrak ulang patch ke folder instalasi yang sama, pilih Replace/Timpa, lalu jalankan VERIFY_ORT_V8_9_9.bat."
            )
            self._push(f"[WEBUI {APP_VERSION_TAG}][VERSION CONTRACT FAILED] {version_contract}")
            return self.get_status_text(), self.get_log(), self.last_error, ""

        input_mode = str(input_mode or "loopback").strip().lower()
        processing = str(processing or "vad").strip().lower()
        language = str(language or "auto").strip().lower()
        language_correction = str(language_correction or "balanced").strip().lower()
        if language_correction not in {"off", "conservative", "balanced", "aggressive"}:
            language_correction = "balanced"
        language_lock = bool(language_lock)
        requested_audio_mode = normalize_audio_mode(audio_mode)
        requested_audio_usage = normalize_audio_usage(audio_usage)
        requested_audio_engine = normalize_audio_engine(audio_engine)
        profile = get_audio_profile(profile_key)
        plan = resolve_audio_plan(requested_audio_mode, profile.key)
        if input_mode not in {"loopback", "file"}:
            input_mode = "loopback"
        if processing not in {"normal", "vad"}:
            self.status = "ERROR"
            self.last_error = "Isolasi Suara belum diaktifkan pada uji pertama. Gunakan Normal atau VAD."
            return self.get_status_text(), self.get_log(), self.last_error, ""

        local_resolution = (
            resolve_effective_audio_mode(requested_audio_mode, profile.key, BASE_DIR, force=True)
            if requested_audio_engine != "azure"
            else {
                "ready": False,
                "requested_mode": requested_audio_mode,
                "effective_mode": requested_audio_mode,
                "reason": "LOCAL_NOT_REQUESTED",
                "runtime": {},
            }
        )
        # v8.9.9 R2 fix: the GPU installer validates Faster-Whisper Small as
        # the CUDA baseline. Accurate normally asks for a Medium marker, but a
        # Japanese session actually loads Kotoba and performs a model-specific
        # preflight. Do not force that session into CPU Guard before Kotoba gets
        # a chance to validate itself. CPU fallback remains installed and the
        # sidecar still falls back safely when the active-model preflight fails.
        japanese_gpu_candidate = language in {
            "ja", "ja-jp", "ja_specialist", "ja-specialist",
            "japanese_specialist", "japanese-specialist",
        }
        if (
            requested_audio_mode == "hybrid"
            and str(local_resolution.get("effective_mode") or "") == "cpu_guard"
            and japanese_gpu_candidate
            and bool(local_resolution.get("ready"))
            and _validated_cuda_baseline_ready(local_resolution, model="small")
        ):
            local_resolution = dict(local_resolution)
            local_resolution["effective_mode"] = "hybrid"
            local_resolution["reason"] = "HYBRID_CUDA_BASELINE_READY_ACTIVE_MODEL_PREFLIGHT"
            local_resolution["gpu_model_validated"] = True
            local_resolution["hybrid_cuda_baseline_model"] = "small"
        probe_realtime_cloud = bool(
            requested_audio_usage == "live_media"
            and requested_audio_engine in {"azure", "azure_fallback"}
        )
        strict_realtime_cloud = bool(
            requested_audio_usage == "live_media"
            and requested_audio_engine == "azure"
        )
        delivery = resolve_audio_delivery(
            requested_audio_engine,
            bool(local_resolution.get("ready")),
            BASE_DIR,
            force=True,
            network_test=probe_realtime_cloud,
        )
        effective_audio_engine = str(delivery.get("effective") or "unavailable")
        cloud_probe = delivery.get("cloud") or {}
        probe = local_resolution.get("runtime") or {}
        if strict_realtime_cloud and effective_audio_engine != "azure":
            missing = []
            if not cloud_probe.get("installed"):
                missing.append("runtime Azure belum dipasang")
            if not cloud_probe.get("sdk"):
                missing.append("Azure Speech SDK belum siap")
            if os.name == "nt" and not cloud_probe.get("wasapi"):
                missing.append("WASAPI loopback cloud belum siap")
            if not cloud_probe.get("credential_set"):
                missing.append("API key Azure belum tersimpan")
            if not str(cloud_probe.get("region") or "").strip():
                missing.append("region Azure belum tersimpan")
            if cloud_probe.get("network_tested") and not cloud_probe.get("cloud_connected"):
                missing.append("uji koneksi Azure gagal")
            detail = ", ".join(missing) or str(cloud_probe.get("message") or delivery.get("reason") or "Azure belum siap")
            errors = " | ".join(str(item) for item in (cloud_probe.get("errors") or []) if str(item).strip())
            self.status = "ERROR"
            self.last_error = (
                "MODE LIVE MEDIA REAL-TIME TIDAK DIMULAI.\n"
                "Mode Azure murni memerlukan sesi cloud yang benar-benar terhubung. Untuk tetap bekerja tanpa Azure, pilih Local Live atau Azure + Local Live Fallback.\n"
                f"Penyebab: {detail}.\n\n"
                "Buka Pengaturan Audio → Siapkan Runtime Azure → Simpan & Uji Azure sampai cloud_connected=True, "
                "atau pilih Local Live untuk rolling-partial offline yang mulai menerjemahkan selama ucapan berlangsung."
                + (("\n\nDetail Azure: " + errors[-1600:]) if errors else "")
            )
            self._push(
                f"[WEBUI {APP_VERSION_TAG}][REALTIME BLOCKED] requested_engine={requested_audio_engine} | "
                f"effective_engine={effective_audio_engine} | cloud_ready={int(bool(cloud_probe.get('ready')))} | "
                f"cloud_connected={int(bool(cloud_probe.get('cloud_connected')))} | reason={delivery.get('reason', 'AZURE_NOT_READY')}"
            )
            return self.get_status_text(), self.get_log(), self.last_error, ""
        if not delivery.get("ready"):
            self.status = "ERROR"
            self.last_error = (
                f"Mesin Audio {requested_audio_engine.upper()} belum siap ({delivery.get('reason', 'SETUP_REQUIRED')}).\n"
                + cloud_runtime_summary_text(BASE_DIR)
                + "\n\n"
                + audio_runtime_summary_text(profile.key, BASE_DIR, requested_audio_mode)
            )
            return self.get_status_text(), self.get_log(), self.last_error, ""
        loopback_ready = bool(cloud_probe.get("wasapi")) if effective_audio_engine == "azure" else bool(probe.get("live_loopback"))
        if input_mode == "loopback" and not loopback_ready:
            self.status = "ERROR"
            self.last_error = "Audio internal langsung memerlukan Windows WASAPI. Pilih 'File audio uji' untuk pengujian tanpa loopback."
            return self.get_status_text(), self.get_log(), self.last_error, ""

        test_path = None
        if input_mode == "file":
            test_path = Path(str(test_file or "")).expanduser() if str(test_file or "").strip() else None
            if test_path is None or not test_path.exists() or not test_path.is_file():
                self.status = "ERROR"
                self.last_error = "Pilih file audio yang valid sebelum memulai uji file."
                return self.get_status_text(), self.get_log(), self.last_error, ""
            test_path = test_path.resolve()
            if effective_audio_engine == "azure" and test_path.suffix.lower() != ".wav":
                self.status = "ERROR"
                self.last_error = "Uji Azure Live Media memerlukan file WAV PCM 16-bit."
                return self.get_status_text(), self.get_log(), self.last_error, ""
            if requested_audio_usage == "live_media" and effective_audio_engine != "azure" and test_path.suffix.lower() != ".wav":
                self.status = "ERROR"
                self.last_error = "Uji Local Live rolling-partial saat ini memerlukan WAV PCM 16-bit agar timing 20 ms dapat dipertahankan."
                return self.get_status_text(), self.get_log(), self.last_error, ""

        cfg = get_runtime_config()
        runtime_python = Path(cfg["runtime_python"])
        if not runtime_python.exists():
            self.status = "ERROR"
            self.last_error = f"Runtime Python utama ORT tidak ditemukan: {runtime_python}"
            return self.get_status_text(), self.get_log(), self.last_error, ""

        prefs = load_prefs()
        selected_model = model or prefs.get("model") or "ORTCore Lite IDN V3"
        selected_game = str(game or prefs.get("game") or "GFL")
        requested_language = language
        japanese_specialist = language in {"ja_specialist", "ja-specialist", "japanese_specialist", "japanese-specialist"}
        if japanese_specialist:
            language = "ja"
        # v8.9.9: keep the user's selected language as the initial primary language.
        # A balanced watchdog corrects a real mismatch only after repeated evidence,
        # while short foreign dialogue is treated as a temporary code switch.
        language_guard = "LOCKED" if language_lock else f"WATCHDOG_{language_correction.upper()}"
        japanese_specialist_enabled = bool(
            japanese_specialist
            or language in {"ja", "auto"}
            or language_correction != "off"
        )
        cloud_source_locale = normalize_source_locale(language)
        realtime_policy = resolve_live_media_policy(requested_audio_usage, cloud_source_locale, profile.key)
        if effective_audio_engine == "azure" and cloud_source_locale.lower() in {"", "auto", "auto_detect"}:
            self.status = "ERROR"
            self.last_error = "Azure Live Media memerlukan bahasa suara tetap agar subtitle interim tersedia. Untuk GFL2 pilih Japanese."
            return self.get_status_text(), self.get_log(), self.last_error, ""
        effective_audio_mode = str(local_resolution.get("effective_mode") or requested_audio_mode)
        active_spec = plan.primary if effective_audio_mode in {"gpu", "hybrid"} else (plan.fallback or plan.primary)
        preset = _resolve_model(selected_model)
        requested_interval = int(prefs.get("interval_ms", 240) or 240)
        requested_ocr = int(prefs.get("ocr_resolution", 55) or 55)
        settings_mode = str(prefs.get("settings_mode", "recommended") or "recommended")
        save_prefs(
            selected_model,
            selected_game,
            prefs.get("mode", "auto"),
            prefs.get("engine", "hybrid"),
            requested_interval,
            model_group=preset.tier,
            ocr_resolution=requested_ocr,
            settings_mode=settings_mode,
            translation_source="audio",
            audio_input_mode=input_mode,
            audio_device_index=str(device_index),
            audio_language=language,
            audio_processing=processing,
            audio_profile=profile.key,
            audio_mode=requested_audio_mode,
            audio_usage=requested_audio_usage,
            audio_engine=requested_audio_engine,
        )

        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        env["ORT_RUNTIME_ROOT"] = cfg["runtime_root"]
        env["ORT_TRANSLATION_SOURCE"] = "audio"
        env["ORT_AUDIO_SOURCE"] = "1"
        env["ORT_LAUNCHER_VERSION"] = APP_VERSION_TAG
        env["ORT_AUDIO_PIPELINE_CONTRACT"] = "rolling-partial-v2"
        env["ORT_AUDIO_INPUT_MODE"] = input_mode
        env["ORT_AUDIO_DEVICE_INDEX"] = str(device_index or "-1")
        env["ORT_AUDIO_LANGUAGE"] = language
        env["ORT_AUDIO_LANGUAGE_REQUESTED"] = requested_language
        env["ORT_AUDIO_LANGUAGE_GUARD"] = language_guard
        env["ORT_AUDIO_LANGUAGE_AUTOCORRECT"] = language_correction
        env["ORT_AUDIO_LANGUAGE_LOCK"] = "1" if language_lock else "0"
        env["ORT_AUDIO_SHOW_SOURCE"] = "1"
        env["ORT_AUDIO_JA_SPECIALIST"] = "1" if japanese_specialist_enabled else "0"
        env["ORT_AUDIO_ASR_BRIDGE_LANGUAGE"] = "en"
        env["ORT_AUDIO_PROCESSING"] = processing
        env["ORT_AUDIO_PROFILE"] = profile.key
        audio_paths = audio_runtime_paths(BASE_DIR)
        cloud_paths = cloud_runtime_paths(BASE_DIR)
        env["ORT_AUDIO_REQUESTED_MODE"] = requested_audio_mode
        env["ORT_AUDIO_EFFECTIVE_MODE"] = effective_audio_mode
        env["ORT_AUDIO_USAGE"] = requested_audio_usage
        env["ORT_AUDIO_ENGINE_REQUESTED"] = requested_audio_engine
        env["ORT_AUDIO_ENGINE_EFFECTIVE"] = effective_audio_engine
        env["ORT_AUDIO_LOCAL_FALLBACK_READY"] = "1" if local_resolution.get("ready") else "0"
        env["ORT_AUDIO_CLOUD_PYTHON"] = str(cloud_paths["cloud_python"])
        env["ORT_AUDIO_CLOUD_CONFIG"] = str(cloud_paths["config"])
        env["ORT_AUDIO_CLOUD_SOURCE_LOCALE"] = cloud_source_locale
        env["ORT_AUDIO_CLOUD_TARGET_LANGUAGE"] = "id"
        env["ORT_AUDIO_REALTIME_PROFILE"] = realtime_policy.profile
        env["ORT_AUDIO_ASR_DEVICE"] = active_spec.device
        env["ORT_AUDIO_ASR_COMPUTE_TYPE"] = active_spec.compute_type
        env["ORT_AUDIO_PRIMARY_MODEL"] = plan.primary.model_size
        env["ORT_AUDIO_FALLBACK_MODEL"] = plan.fallback.model_size if plan.fallback else ""
        env["ORT_AUDIO_CPU_PYTHON"] = str(audio_paths["cpu_python"])
        env["ORT_AUDIO_GPU_PYTHON"] = str(audio_paths["gpu_python"])
        env["ORT_AUDIO_CAPTURE_PYTHON"] = str(probe.get("capture_python") or audio_paths["cpu_python"])
        env["ORT_AUDIO_RUNTIME_PYTHON"] = env["ORT_AUDIO_CAPTURE_PYTHON"]
        env["ORT_AUDIO_MODEL_ROOT"] = str(audio_paths["model_root"])
        env["ORT_AUDIO_SPOOL_ROOT"] = str(audio_paths["spool_root"])
        env["ORT_AUDIO_TEST_FILE"] = str(test_path) if test_path is not None else ""
        env["ORT_GAME_OVERRIDE"] = selected_game
        env["ORT_GAME_PROFILE"] = selected_game
        env["TITAN_MODEL_LABEL"] = preset.title
        env["ORT_MODEL_KEY"] = preset.key
        env["ORT_MODEL_GROUP"] = preset.tier
        env["ORT_SETTINGS_MODE"] = settings_mode
        env["ORT_DIALOGUE_COMPLETENESS_GATE"] = "0"
        env["ORT_FINAL_ONLY_SAFE_COMMIT"] = "0"
        env["ORT_RESPONSIVE_STORY_MODE"] = "0"
        env["ORT_STRICT_CT2_STORY"] = "0"
        env["ORT_HARD_STRICT_CT2_STORY"] = "0"
        env["ORT_LITE_CT2_ALLOWED"] = "1"
        env["ORT_IDN_OVER_CT2"] = "1"
        env["TITAN_CT2_DEVICE"] = "cpu"
        env["TITAN_CT2_COMPUTE_TYPE"] = "int8"
        env["TITAN_CT2_BEAM"] = str(1 if profile.key == "speed" else (2 if profile.key == "normal" else 4))
        env["OMP_NUM_THREADS"] = str(active_spec.cpu_threads)
        env["ORT_CPU_THREADS"] = str(active_spec.cpu_threads)
        stop_path = BASE_DIR / "runtime_stop_request.json"
        env["ORT_STOP_REQUEST_FILE"] = str(stop_path)
        clear_stop_request(BASE_DIR)
        try:
            env.update(preset.env_map())
            env.update(env_from_settings(selected_game, model_key=preset.key, policy_override="normal", ocr_resolution=requested_ocr))
        except Exception:
            pass
        env.update({
            "ORT_TRANSLATION_SOURCE": "audio",
            "ORT_AUDIO_SOURCE": "1",
            "ORT_LAUNCHER_VERSION": APP_VERSION_TAG,
            "ORT_AUDIO_PIPELINE_CONTRACT": "rolling-partial-v2",
            "ORT_AUDIO_INPUT_MODE": input_mode,
            "ORT_AUDIO_DEVICE_INDEX": str(device_index or "-1"),
            "ORT_AUDIO_LANGUAGE": language,
            "ORT_AUDIO_LANGUAGE_REQUESTED": requested_language,
            "ORT_AUDIO_LANGUAGE_GUARD": language_guard,
            "ORT_AUDIO_LANGUAGE_AUTOCORRECT": language_correction,
            "ORT_AUDIO_LANGUAGE_LOCK": "1" if language_lock else "0",
            "ORT_AUDIO_SHOW_SOURCE": "1",
            "ORT_AUDIO_JA_SPECIALIST": "1" if japanese_specialist_enabled else "0",
            "ORT_AUDIO_ASR_BRIDGE_LANGUAGE": "en",
            "ORT_AUDIO_PROCESSING": processing,
            "ORT_AUDIO_PROFILE": profile.key,
            "ORT_AUDIO_REQUESTED_MODE": requested_audio_mode,
            "ORT_AUDIO_EFFECTIVE_MODE": effective_audio_mode,
            "ORT_AUDIO_USAGE": requested_audio_usage,
            "ORT_AUDIO_ENGINE_REQUESTED": requested_audio_engine,
            "ORT_AUDIO_ENGINE_EFFECTIVE": effective_audio_engine,
            "ORT_AUDIO_LOCAL_FALLBACK_READY": "1" if local_resolution.get("ready") else "0",
            "ORT_AUDIO_CLOUD_PYTHON": str(cloud_paths["cloud_python"]),
            "ORT_AUDIO_CLOUD_CONFIG": str(cloud_paths["config"]),
            "ORT_AUDIO_CLOUD_SOURCE_LOCALE": cloud_source_locale,
            "ORT_AUDIO_CLOUD_TARGET_LANGUAGE": "id",
            "ORT_AUDIO_REALTIME_PROFILE": realtime_policy.profile,
            "ORT_AUDIO_ASR_DEVICE": active_spec.device,
            "ORT_AUDIO_ASR_COMPUTE_TYPE": active_spec.compute_type,
            "ORT_AUDIO_PRIMARY_MODEL": plan.primary.model_size,
            "ORT_AUDIO_FALLBACK_MODEL": plan.fallback.model_size if plan.fallback else "",
            "ORT_AUDIO_CPU_PYTHON": str(audio_paths["cpu_python"]),
            "ORT_AUDIO_GPU_PYTHON": str(audio_paths["gpu_python"]),
            "ORT_AUDIO_CAPTURE_PYTHON": str(
                audio_paths["gpu_python"]
                if effective_audio_mode in {"gpu", "hybrid"}
                else (probe.get("capture_python") or audio_paths["cpu_python"])
            ),
            "ORT_AUDIO_MODEL_ROOT": str(audio_paths["model_root"]),
            "ORT_AUDIO_SPOOL_ROOT": str(audio_paths["spool_root"]),
            "ORT_DIALOGUE_COMPLETENESS_GATE": "0",
            "ORT_FINAL_ONLY_SAFE_COMMIT": "0",
            "ORT_RESPONSIVE_STORY_MODE": "0",
            "ORT_STRICT_CT2_STORY": "0",
            "ORT_HARD_STRICT_CT2_STORY": "0",
            "ORT_LITE_CT2_ALLOWED": "1",
            "ORT_IDN_OVER_CT2": "1",
            "TITAN_CT2_DEVICE": "cpu",
            "TITAN_CT2_COMPUTE_TYPE": "int8",
            "TITAN_CT2_BEAM": str(1 if profile.key == "speed" else (2 if profile.key == "normal" else 4)),
            "OMP_NUM_THREADS": str(active_spec.cpu_threads),
            "ORT_CPU_THREADS": str(active_spec.cpu_threads),
        })
        try:
            fast_manager = FastModelManager(BASE_DIR)
            fast_state = fast_manager.status()
            model_dir = str(fast_state.get("model_dir") or fast_manager.model_dir)
            env["ORT_FAST_CT2_MODEL_DIR"] = model_dir
            env["ORT_LITE_CT2_MODEL_DIR"] = model_dir
            env["TITAN_CT2_EN_ID_DIR"] = model_dir
            env["TITAN_SPM_EN_ID_DIR"] = model_dir
            env["ORT_CT2_MODEL_DIR_USED"] = model_dir
            env["ORT_CT2_SPM_DIR_USED"] = model_dir
            env["ORT_CT2_PATH_REBIND"] = "1"
        except Exception:
            fast_state = {"state": "UNKNOWN", "active": False}

        self.lines = []
        self.last_error = ""
        self.pending_candidate_notice = ""
        self.current_game = selected_game
        self.current_source = "audio"
        self.session = start_session(BASE_DIR, selected_game)
        try:
            env["ORT_SESSION_ID"] = self.session.session_id
            env["ORT_SESSION_FULL_LOG_PATH"] = str(self.session.full_log_path)
            env["ORT_SESSION_JSONL_PATH"] = str(self.session.jsonl_path)
        except Exception:
            pass
        active_engine_label = (
            "audio_azure_live_media"
            if effective_audio_engine == "azure"
            else (
                "audio_local_realtime_rolling_partial"
                if requested_audio_usage == "live_media"
                else f"audio_{effective_audio_mode}_{active_spec.device}_{active_spec.compute_type}"
            )
        )
        active_asr_model = "azure_speech_translation" if effective_audio_engine == "azure" else active_spec.model_size
        active_asr_device = "cloud" if effective_audio_engine == "azure" else active_spec.device
        active_compute = "streaming" if effective_audio_engine == "azure" else active_spec.compute_type
        try:
            save_state({
                "version": APP_VERSION_TAG,
                "status": "RUNNING",
                "translation_source": "audio",
                "model": selected_model,
                "game": selected_game,
                "mode": "audio",
                "active_mode": "audio",
                "engine": effective_audio_engine,
                "requested_engine": requested_audio_engine,
                "active_engine": active_engine_label,
                "audio_usage": requested_audio_usage,
                "audio_engine_requested": requested_audio_engine,
                "audio_engine_effective": effective_audio_engine,
                "audio_cloud_provider": "azure",
                "audio_cloud_connected": False,
                "audio_local_fallback_ready": bool(local_resolution.get("ready")),
                "audio_profile": profile.key,
                "audio_realtime_policy": realtime_policy.as_dict(),
                "audio_requested_mode": requested_audio_mode,
                "audio_effective_mode": effective_audio_mode,
                "audio_asr_model": active_asr_model,
                "audio_primary_model": plan.primary.model_size,
                "audio_fallback_model": plan.fallback.model_size if plan.fallback else "",
                "audio_asr_device": active_asr_device,
                "audio_asr_compute_type": active_compute,
                "audio_processing": processing,
                "audio_input_mode": input_mode,
                "audio_device_index": str(device_index or "-1"),
                "audio_language_requested": requested_language,
                "audio_language": language,
                "audio_language_guard": language_guard,
                "audio_asr_bridge_language": "en",
                "audio_japanese_specialist_requested": bool(japanese_specialist or language == "ja"),
                "audio_cpu_threads": active_spec.cpu_threads,
                "performance_reason": (
                    f"Audio {requested_audio_usage}: requested_engine={requested_audio_engine}, effective_engine={effective_audio_engine}; "
                    + (
                        f"Azure Speech {cloud_source_locale}->id 20ms streaming; endpoint={realtime_policy.segmentation_silence_ms}ms; max_phrase={realtime_policy.segmentation_maximum_ms}ms; local_fallback_ready={bool(local_resolution.get('ready'))}."
                        if effective_audio_engine == "azure"
                        else (
                            f"faster-whisper rolling-partial {active_spec.model_size} {active_spec.device}:{active_spec.compute_type}; "
                            f"multilingual ASR uses source-aware decoding and an English bridge before instant ID translation; endpoint only commits final."
                            if requested_audio_usage == "live_media"
                            else f"faster-whisper segmented {active_spec.model_size} {active_spec.device}:{active_spec.compute_type}."
                        )
                    )
                    + " OCR process disabled."
                ),
            }, BASE_DIR)
        except Exception:
            pass

        self.status = "RUNNING"
        self.stop_requested = False
        self._push(
            f"[WEBUI {APP_VERSION_TAG}] START AUDIO | game={selected_game} | usage={requested_audio_usage} | "
            f"requested_engine={requested_audio_engine} | effective_engine={effective_audio_engine} | profile={profile.key} | "
            f"requested_mode={requested_audio_mode} | effective_mode={effective_audio_mode} | "
            f"asr={active_asr_model}:{active_asr_device}:{active_compute} | local_fallback={active_spec.model_size}:{active_spec.device}:{active_spec.compute_type} | "
            f"threads={active_spec.cpu_threads} | processing={processing} | "
            f"input={input_mode} | requested_language={requested_language} | language={language} | language_guard={language_guard or '-'} | "
            f"auto_correct={language_correction} | language_lock={int(language_lock)} | asr_bridge=en | ja_specialist={int(japanese_specialist_enabled)} | endpoint_ms={realtime_policy.segmentation_silence_ms} | "
            f"max_phrase_ms={realtime_policy.segmentation_maximum_ms} | chunk_ms={realtime_policy.audio_chunk_ms} | ocr_process=disabled"
        )
        self._push(
            f"[WEBUI {APP_VERSION_TAG}] capture_runtime={env['ORT_AUDIO_CAPTURE_PYTHON']} | "
            f"cpu_runtime={audio_paths['cpu_python']} | gpu_runtime={audio_paths['gpu_python']} | "
            f"cloud_runtime={cloud_paths['cloud_python']} | model_root={audio_paths['model_root']}"
        )
        self._push(
            f"[WEBUI {APP_VERSION_TAG}] translation_model={selected_model} | "
            f"cloud={cloud_source_locale}->id | cloud_ready={int(bool(cloud_probe.get('ready')))} | "
            f"local_fallback_ready={int(bool(local_resolution.get('ready')))} | "
            f"fast_ct2={fast_state.get('state', 'UNKNOWN')} | ct2_device=cpu:int8"
        )

        script_path = BASE_DIR / "audio_main.py"
        creationflags = 0
        if os.name == "nt":
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            creationflags |= getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0x00004000)
        self.proc = subprocess.Popen(
            [str(runtime_python), str(script_path)],
            cwd=str(BASE_DIR),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            creationflags=creationflags,
        )
        threading.Thread(target=self._reader, daemon=True).start()
        return (
            self.get_status_text(),
            self.get_log(),
            f"Menjalankan Audio {requested_audio_usage.replace('_', ' ').title()} · "
            f"{requested_audio_engine.upper()} (efektif: {effective_audio_engine})...",
            "",
        )

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.stop_requested = True
            self.status = "STOPPING"
            self.stop_at = time.time()
            self._push(f"[WEBUI {APP_VERSION_TAG}] Graceful STOP requested. Menunggu flush cache/log/session...")
            try:
                request_stop(BASE_DIR, reason="webui_stop", pid=self.proc.pid)
                write_shutdown_status(BASE_DIR, "STOP_REQUESTED", "webui_stop", {"pid": self.proc.pid})
            except Exception as e:
                self.last_error = str(e)

            # Give TITANMAIN time to see the stop-request file and run its own shutdown.
            graceful_timeout = float(os.environ.get("ORT_GRACEFUL_STOP_TIMEOUT_SEC", "6.0"))
            deadline = time.time() + graceful_timeout
            try:
                if os.name == 'nt':
                    # Process was created with CREATE_NEW_PROCESS_GROUP, so CTRL_BREAK can be delivered.
                    try:
                        self.proc.send_signal(getattr(subprocess, "CTRL_BREAK_EVENT", 1))
                    except Exception:
                        pass
                else:
                    try:
                        self.proc.terminate()
                    except Exception:
                        pass
                while time.time() < deadline and self.proc.poll() is None:
                    time.sleep(0.15)
            except Exception as e:
                self.last_error = str(e)

            if self.proc.poll() is None:
                self._push(f"[WEBUI {APP_VERSION_TAG}] Graceful stop timeout; fallback hard kill.")
                try:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'], capture_output=True, text=True, timeout=10)
                    else:
                        self.proc.kill()
                except Exception as e:
                    self.last_error = str(e)
            else:
                self._push(f"[WEBUI {APP_VERSION_TAG}] Graceful stop selesai; cache/log seharusnya sudah flush.")
            try:
                close_session("webui_stop")
            except Exception:
                pass
            self.status = "STOP"
            try:
                save_state({"status": "STOP", "active_engine": "stopped"}, BASE_DIR)
            except Exception:
                pass
            self.stop_at = time.time()
            self._prepare_candidate_notice()
        else:
            self.status = "IDLE"
        return self.get_status_text(), self.get_log(), "Stop selesai.", self.pending_candidate_notice

    def prepare_source_switch(self) -> bool:
        proc = self.proc
        if proc is None or proc.poll() is not None:
            return False
        self.source_switching = True
        return True

    def finish_source_switch(self) -> None:
        self.source_switching = False

    def refresh(self):
        if self.status == "STOP" and (not self.proc or self.proc.poll() is not None):
            if time.time() - self.stop_at > 1.2:
                self.status = "IDLE"
        return self.get_status_text(), self.get_log(), self.last_error or "", self.pending_candidate_notice


MANAGER = ProcessManager()


def start_model(model, game, mode, engine, interval_ms, ocr_resolution=65, performance_policy="auto", normal_override=False, settings_mode=None, responsive_story_mode=False, diagnostic_profile="baseline", mode_buffer_enabled=False):
    return MANAGER.start(model, game, mode, engine, interval_ms, ocr_resolution, performance_policy, normal_override, settings_mode, responsive_story_mode, diagnostic_profile, mode_buffer_enabled)


def start_audio_model(model, game, input_mode="loopback", device_index="-1", language="auto", processing="vad", profile_key="normal", test_file="", audio_mode="hybrid", audio_usage="live_media", audio_engine="azure_fallback", language_correction="balanced", language_lock=False):
    return MANAGER.start_audio(model, game, input_mode, device_index, language, processing, profile_key, test_file, audio_mode, audio_usage, audio_engine, language_correction, language_lock)


def setup_audio_runtime_text(profile_key="normal", audio_mode="hybrid"):
    return setup_audio_runtime(profile_key, BASE_DIR, audio_mode)


def audio_runtime_status_text(profile_key="normal", audio_mode="hybrid", audio_engine="local", audio_usage="live_media"):
    engine = normalize_audio_engine(audio_engine)
    local_text = audio_runtime_summary_text(profile_key, BASE_DIR, audio_mode)
    if engine == "local":
        return f"usage = {normalize_audio_usage(audio_usage)}\naudio_engine = local\n\n{local_text}"
    return (
        f"usage = {normalize_audio_usage(audio_usage)}\n"
        f"audio_engine = {engine}\n\n"
        + cloud_runtime_summary_text(BASE_DIR)
        + "\n\nLOCAL FALLBACK\n"
        + local_text
    )


def audio_devices_for_ui(force=False, audio_mode="hybrid", audio_engine="local"):
    engine = normalize_audio_engine(audio_engine)
    if engine != "local":
        cloud_probe = probe_cloud_runtime(bool(force), BASE_DIR, False)
        if cloud_probe.get("dependency_ready"):
            return cloud_device_choices(BASE_DIR, bool(force))
    return audio_device_choices(BASE_DIR, bool(force), audio_mode)


def audio_runtime_probe(force=False, profile_key="normal", audio_mode="hybrid", audio_engine="local", audio_usage="live_media"):
    resolution = resolve_effective_audio_mode(audio_mode, profile_key, BASE_DIR, force=bool(force))
    probe = resolution.get("runtime") or {}
    model_status = resolution.get("models") or {}
    dependencies_ready = bool(probe.get("ready"))
    model_ready = bool(model_status.get("ready"))
    engine = normalize_audio_engine(audio_engine)
    strict_realtime_cloud = bool(normalize_audio_usage(audio_usage) == "live_media" and engine in {"azure", "azure_fallback"})
    delivery = resolve_audio_delivery(
        engine,
        bool(resolution.get("ready")),
        BASE_DIR,
        force=bool(force),
        network_test=bool(force and strict_realtime_cloud),
    )
    return {
        **probe,
        **resolution,
        "dependencies_ready": dependencies_ready,
        "model_ready": model_ready,
        "model_status": model_status,
        "ready": bool(delivery.get("ready")),
        "audio_engine_requested": engine,
        "audio_engine_effective": delivery.get("effective"),
        "audio_engine_reason": delivery.get("reason"),
        "cloud": delivery.get("cloud") or {},
    }


def setup_audio_cloud_runtime_text():
    return setup_cloud_runtime(BASE_DIR)


def audio_cloud_runtime_status_text():
    return cloud_runtime_summary_text(BASE_DIR)


def audio_cloud_config_values():
    return cloud_config_values(BASE_DIR)


def save_audio_cloud_config_from_ui(region, api_key, source_locale="ja-JP", target_language="id"):
    return save_cloud_config(region, api_key, source_locale, target_language, BASE_DIR, True)


def clear_audio_cloud_credentials_text():
    return clear_cloud_credentials(BASE_DIR)


def prepare_source_switch_stop():
    return MANAGER.prepare_source_switch()


def finish_source_switch_stop():
    MANAGER.finish_source_switch()


def recommendation_summary(game, normal_override=False):
    return recommendation_text(game, allow_normal=bool(normal_override))


def stop_model():
    return MANAGER.stop()


def refresh_state():
    return MANAGER.refresh()


def finish_start():
    return MANAGER.refresh()


def gpu_doctor_text():
    return gpu_summary_text()


def repair_gpu_runtime():
    return install_or_repair_gpu()




def _short(value, default="-"):
    value = default if value in (None, "") else value
    return html.escape(str(value))


def runtime_effective_status_html() -> str:
    """Small WebUI card: requested settings vs strategy-applied runtime values."""
    try:
        state = load_state(BASE_DIR)
    except Exception:
        state = {}
    strategy = read_status("strategy", BASE_DIR, {})
    health = read_status("runtime_health", BASE_DIR, {})
    actions = read_status("runtime_actions", BASE_DIR, {})
    translation = read_status("translation_engine", BASE_DIR, {})
    shutdown = read_status("shutdown", BASE_DIR, {})

    profile = strategy.get("core_profile") or state.get("settings_mode") or "idle"
    selected = state.get("model") or strategy.get("model_title") or "-"
    req_engine = state.get("requested_engine") or state.get("engine") or strategy.get("extra", {}).get("requested_engine") or "-"
    applied_translation = translation.get("applied_engine") or "menunggu terjemahan pertama"
    ocr_engine = actions.get("active_engine") or state.get("active_engine") or "-"
    req_interval = state.get("requested_interval_ms") or state.get("interval_ms") or "-"
    active_interval = strategy.get("interval_floor_ms") or actions.get("effective_interval_ms") or "-"
    req_ocr = state.get("requested_ocr_resolution") or state.get("ocr_resolution") or "-"
    active_ocr = strategy.get("ocr_resolution_percent") or actions.get("ocr_resolution_percent") or "-"
    health_state = health.get("status") or shutdown.get("status") or state.get("status") or "idle"
    perf_reason = state.get("performance_reason") or strategy.get("reason") or "-"
    req_mode = state.get("requested_mode") or state.get("mode") or "-"
    scheduler = state.get("dialog_scheduler_profile") or "-"
    legacy_vault = "enabled" if bool(translation.get("legacy_vault_enabled")) else "isolated"
    fast_state = state.get("fast_engine_status") or strategy.get("extra", {}).get("fast_engine_status") or "-"

    def card(title: str, body: str, sub: str = "") -> str:
        return (
            "<div class='status-card'>"
            f"<b>{html.escape(title)}</b>"
            f"<span>{body}</span>"
            + (f"<small>{html.escape(sub)}</small>" if sub else "")
            + "</div>"
        )

    if str(state.get("translation_source", "ocr")).lower() == "audio":
        audio = read_status("audio_runtime", BASE_DIR, {})
        audio_profile = audio.get("profile") or state.get("audio_profile") or "normal"
        asr_model = audio.get("asr_model") or state.get("audio_asr_model") or "-"
        processing = audio.get("processing") or state.get("audio_processing") or "vad"
        input_mode = audio.get("input_mode") or state.get("audio_input_mode") or "loopback"
        device = audio.get("device") or ("File audio uji" if input_mode == "file" else "Default WASAPI")
        audio_state = audio.get("audio_state") or state.get("audio_state") or state.get("status") or "idle"
        asr_ms = audio.get("asr_ms", "-")
        translation_ms = audio.get("translation_ms", "-")
        total_ms = audio.get("total_ms", "-")
        translation_backend = audio.get("translation_engine") or "menunggu terjemahan pertama"
        last_translation = str(audio.get("last_translation") or "Belum ada hasil")
        requested_audio_mode = audio.get("requested_mode") or state.get("audio_requested_mode") or "hybrid"
        effective_audio_mode = audio.get("effective_mode") or state.get("audio_effective_mode") or requested_audio_mode
        audio_usage = audio.get("audio_usage") or state.get("audio_usage") or "live_media"
        requested_audio_engine = audio.get("audio_engine_requested") or state.get("audio_engine_requested") or "azure_fallback"
        effective_audio_engine = audio.get("audio_engine_effective") or state.get("audio_engine_effective") or requested_audio_engine
        cloud_connected = bool(audio.get("cloud_connected") or state.get("audio_cloud_connected"))
        cloud_result_state = audio.get("cloud_result_state") or "-"
        cloud_ms = audio.get("cloud_ms", "-")
        asr_device = audio.get("asr_device") or state.get("audio_asr_device") or "-"
        asr_compute = audio.get("asr_compute_type") or state.get("audio_asr_compute_type") or "-"
        fallback_model = audio.get("fallback_model") or state.get("audio_fallback_model") or "disabled"
        if len(last_translation) > 92:
            last_translation = last_translation[:89] + "..."
        cloud_active = str(effective_audio_engine).lower() == "azure"
        return "<div class='status-grid'>" + "".join([
            card("Source", f"Audio · {_short(audio_usage)}", "one-way system audio"),
            card("Engine", f"{_short(requested_audio_engine)} → {_short(effective_audio_engine)}", "requested → effective"),
            card("Local Device", f"{_short(requested_audio_mode)} → {_short(effective_audio_mode)}", "fallback execution mode"),
            card("ASR Profile", f"{_short(audio_profile)} · {_short(asr_model)}", f"{asr_device}:{asr_compute}"),
            card("Audio Processing", "PCM streaming" if cloud_active else _short(processing), "interim/final" if cloud_active else "adaptive energy + Silero VAD"),
            card("Input", _short(input_mode), str(device)),
            card("Translation Backend", "Azure Speech ja-JP → id" if cloud_active else _short(translation_backend), f"connected={cloud_connected}" if cloud_active else "English transcript → Indonesian"),
            card("Latency", f"{_short(cloud_ms)} ms" if cloud_active else f"{_short(asr_ms)} + {_short(translation_ms)} = {_short(total_ms)} ms", f"cloud {cloud_result_state}" if cloud_active else "ASR + translation = total"),
            card("Health", _short(audio_state), "audio sidecar / overlay state"),
            card("CPU Threads", _short(audio.get("cpu_threads") or state.get("audio_cpu_threads") or "-"), "profile-controlled budget"),
            card("CPU Fallback", _short(fallback_model), "Hybrid only; GPU mode stays strict"),
            card("Last Output", _short(last_translation), "hasil overlay terakhir"),
        ]) + "</div>"

    return "<div class='status-grid'>" + "".join([
        card("Profile", _short(profile), str(selected)),
        card("Translation Backend", f"{_short(req_engine)} → {_short(applied_translation)}", "requested → applied nyata"),
        card("OCR Device", _short(ocr_engine), "terpisah dari backend translation"),
        card("Interval", f"{_short(req_interval)} ms → {_short(active_interval)} ms", "requested → effective"),
        card("OCR", f"{_short(req_ocr)}% → {_short(active_ocr)}%", "requested → effective"),
        card("Health", _short(health_state), "runtime/action status"),
        card("Fast", _short(fast_state), "CT2 status / fallback warning"),
        card("Mode/Scheduler", f"{_short(req_mode)} → {_short(scheduler)}", "requested → applied scheduler"),
        card("Legacy Vault", _short(legacy_vault), "baseline cache protection"),
        card("Reason", _short(perf_reason), "why performance may feel slow"),
    ]) + "</div>"

def read_full_session_log_for_recap(fallback_text: str = "") -> str:
    sess = current_session()
    if sess:
        txt = sess.read_full_text(max_chars=300000)
        if txt.strip():
            return txt
    path = BASE_DIR / "status" / "session_log.json"
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            full = Path(data.get("full_log_path", ""))
            if full.exists():
                txt = full.read_text(encoding="utf-8-sig")
                return txt[-300000:]
    except Exception:
        pass
    return fallback_text or ""



# v8.9.1 safety defaults injected for subprocess environments.
# If launcher_backend has its own env builder, these are safe fallbacks.
os.environ.setdefault("ORT_PREDICTION_GUARD", "1")
os.environ.setdefault("ORT_UI_DIALOG_FILTER", "1")
os.environ.setdefault("ORT_DIALOGUE_TIMEOUT_SAFETY", "1")
os.environ.setdefault("ORT_DIALOGUE_TIMEOUT_MS", "850")
os.environ.setdefault("ORT_STALE_LAST_GOOD_MAX_REPAINTS", "7")
os.environ.setdefault("ORT_TEXT_ROI_CHANGE_GATE", "1")
os.environ.setdefault("ORT_TEXT_ROI_CHANGE_THRESHOLD", "0.018")
os.environ.setdefault("ORT_TEXT_ROI_MAX_HOLD_MS", "15000")
os.environ.setdefault("ORT_TEXT_ROI_CONFIRM_DELAY_MS", "450")
os.environ.setdefault("ORT_PROGRESSIVE_QUEUE_COALESCE", "1")
os.environ.setdefault("ORT_TURN_STATE_MACHINE", "1")
os.environ.setdefault("ORT_DIALOG_CLEAR_MISSES", "2")
os.environ.setdefault("ORT_DIALOG_CLEAR_MIN_MS", "550")
os.environ.setdefault("ORT_TRANSACTIONAL_OVERLAY", "1")


# v8.9.1 safety defaults.
os.environ.setdefault("ORT_MODE_POLICY_MANAGER", "1")
os.environ.setdefault("ORT_INTERVAL_FAST_SKIP_SAFETY", "1")

# v8.9.1 visible entity badges and policy activation defaults.
os.environ.setdefault("ORT_ENTITY_CONFIDENCE_BADGES", "1")
os.environ.setdefault("ORT_GFL2_ENTITY_REGISTRY", os.path.join(os.path.dirname(os.path.abspath(__file__)), "configs", "gfl2_entity_registry_v8_9_1.json"))
os.environ.setdefault("ORT_MODE_POLICY_MANAGER", "1")
os.environ.setdefault("ORT_INTERVAL_FAST_SKIP_SAFETY", "1")

# v8.9.1 hotfix: silence generic ID waiting placeholders by default.
os.environ.setdefault("ORT_OVERLAY_SILENCE_ENGLISH_PREVIEW", "1")
os.environ.setdefault("ORT_OVERLAY_SHOW_ID_WAITING_PREVIEW", "0")
