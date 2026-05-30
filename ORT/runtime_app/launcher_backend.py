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

BASE_DIR = Path(__file__).resolve().parent
RUNTIME_CFG = BASE_DIR / "runtime_paths.json"
PREFS_PATH = BASE_DIR / "webui_prefs.json"
try:
    cleanup_legacy_status_files(BASE_DIR)
except Exception:
    pass


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        pass
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


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
    lines = ["ORT Translation v8.4 Diagnostic Dashboard", f"status_dir = {BASE_DIR / 'status'}"]
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
            "Repair / Rebind CT2 Model & SPM Path v8.8.1",
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
        "responsive_story_mode": False,
        "diagnostic_profile": "baseline",
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


def save_prefs(model, game, mode, engine, interval_ms, model_group=None, ocr_resolution=None, performance_policy=None, normal_override=None, settings_mode=None, ui_mode=None, responsive_story_mode=None, diagnostic_profile=None):
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
    _save_json(PREFS_PATH, data)
    try:
        save_state({"version": "v8.8.1", "model": model, "game": game, "mode": mode, "engine": engine, "requested_engine": engine, "requested_mode": mode, "requested_interval_ms": int(interval_ms), "interval_ms": int(interval_ms), "requested_ocr_resolution": data.get("ocr_resolution"), "ocr_resolution": data.get("ocr_resolution"), "settings_mode": data.get("settings_mode", "recommended"), "responsive_story_mode": bool(data.get("responsive_story_mode", False)), "diagnostic_profile": str(data.get("diagnostic_profile", "baseline"))}, BASE_DIR)
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
    }
    if mode_l == "freeze":
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "freeze_manual",
            "ORT_DIALOG_STABLE_MS": "0",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1"),
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "900",
            "ORT_IMAGE_HASH_THRESHOLD": "5",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
        })
    elif mode_l == "auto":
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "auto_story",
            "ORT_DIALOG_PROGRESSIVE_COMMIT": "1",
            "ORT_DIALOG_STABLE_MS": "0",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1") if fast else "1",
            "ORT_DIALOG_MAX_WAIT_MS": prof.get("max_wait_auto", prof.get("max_auto", "420")),
            "ORT_DIALOG_DUPLICATE_HOLD_MS": prof.get("duplicate_hold", prof.get("duplicate", "850")),
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": prof.get("progressive_min", prof.get("progressive", "180")),
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "2" if key == "fast_v1" else "3",
            "ORT_DIALOG_QUICK_PUNCT_COMMIT": prof.get("quick_punct", "1"),
            "ORT_STABLE_TEXT_COMMIT": "0",
            "ORT_IMAGE_HASH_GATE": "0",
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "70" if key == "fast_v1" else ("110" if key == "fast_v2" else ("130" if key == "fast_idn" else ("150" if lite else "160"))),
            "ORT_IMAGE_HASH_THRESHOLD": "2",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
            "TITAN_AUTO_SNAPSHOT_MIN_MS": "45" if key == "fast_v1" else ("60" if key == "fast_v2" else ("75" if key == "fast_idn" else "90")),
        })
    else:
        env.update({
            "ORT_DIALOG_SCHEDULER_PROFILE": "interval_auto",
            "ORT_DIALOG_CLASSIC_INTERVAL": "1",
            "ORT_DIALOG_PROGRESSIVE_COMMIT": "1",
            "ORT_DIALOG_STABLE_MS": "0" if fast else "80",
            "ORT_DIALOG_STABLE_REPEATS": prof.get("stable_repeats", "1") if fast else "1",
            "ORT_DIALOG_MAX_WAIT_MS": prof.get("max_wait_interval", prof.get("max_interval", "550")),
            "ORT_DIALOG_DUPLICATE_HOLD_MS": prof.get("duplicate_hold", prof.get("duplicate", "1300")),
            "ORT_DIALOG_VOICE_HOLD_MS": (("360" if key == "fast_v1" else ("650" if key == "fast_v2" else "850")) if (fast and game_u == "GFL2_EXILIUM") else prof.get("voice", "1200")),
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": prof.get("progressive_min", prof.get("progressive", "180")),
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "2" if key == "fast_v1" else "3",
            "ORT_DIALOG_QUICK_PUNCT_COMMIT": prof.get("quick_punct", "1"),
            "ORT_IMAGE_HASH_MAX_HOLD_MS": "90" if key == "fast_v1" else ("130" if key == "fast_v2" else ("160" if key == "fast_idn" else ("190" if lite else ("220" if game_u == "GFL2_EXILIUM" else "260")))),
            "ORT_IMAGE_HASH_THRESHOLD": "2",
            "ORT_STABLE_COMMIT_MS": "0",
            "ORT_STABLE_COMMIT_REPEATS": "1",
            "TITAN_AUTO_SNAPSHOT_MIN_MS": "45" if key == "fast_v1" else ("60" if key == "fast_v2" else ("75" if key == "fast_idn" else "90")),
        })
    if responsive_story and mode_l == "auto":
        env.update({
            "ORT_DIALOG_PROGRESSIVE_MIN_MS": "270",
            "ORT_DIALOG_PROGRESSIVE_MIN_DELTA": "10",
            "ORT_DIALOG_MAX_WAIT_MS": "320",
            "ORT_DIALOG_DUPLICATE_HOLD_MS": "500",
            "ORT_RESPONSIVE_QUEUE_TARGET": "1",
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
        bits.append("Image Hash Gate disesuaikan profil: Auto dibuat relaxed agar teks bertahap tidak tertahan, Interval/Freeze tetap hemat scan saat cocok.")
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
        self._push("[WEBUI v8.8.1] Live Log tampilan direset; file session tetap disimpan untuk Analyze Last Session.")

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

    def start(self, model, game, mode, engine, interval_ms, ocr_resolution=65, performance_policy="auto", normal_override=False, settings_mode=None, responsive_story_mode=False, diagnostic_profile="baseline"):
        if self.proc and self.proc.poll() is None:
            return self.get_status_text(), self.get_log(), "Model masih berjalan. Stop dulu sebelum start baru.", self.pending_candidate_notice

        settings_mode = (settings_mode or ("manual" if normal_override else "recommended")).lower()
        normal_override = settings_mode in {"manual", "normal"}
        performance_policy = "normal" if normal_override else "auto"
        save_prefs(model, game, mode, engine, interval_ms, ocr_resolution=ocr_resolution, performance_policy=performance_policy, normal_override=normal_override, settings_mode=settings_mode, responsive_story_mode=responsive_story_mode, diagnostic_profile=diagnostic_profile)
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
            save_prefs(model, game, mode, engine, interval_ms, model_group=preset.tier, ocr_resolution=ocr_resolution, performance_policy=performance_policy, normal_override=normal_override, settings_mode=settings_mode)
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
        # v8.7.6: report the final applied OCR after Lite GPU guard / runtime policy,
        # not only the strategy value before safety or user-override resolution.
        applied_runtime_ocr = int(env.get("ORT_LITE_APPLIED_OCR", env.get("ORT_BOOT_OCR_RESOLUTION", strategy.ocr_resolution_percent)))
        env["ORT_APPLIED_OCR_RESOLUTION_PERCENT"] = str(applied_runtime_ocr)
        env["ORT_REQUESTED_OCR_RESOLUTION_PERCENT"] = str(int(ocr_resolution))
        write_strategy_status(strategy, BASE_DIR, extra={"source": "launcher", "selected_model": model, "selected_game": game, "requested_engine": engine, "requested_mode": mode, "requested_interval_ms": int(interval_ms), "requested_ocr_resolution": int(ocr_resolution), "effective_ocr_resolution": applied_runtime_ocr, "preset_ocr_resolution": getattr(preset, "ocr_resolution_percent", None), "adaptive_ocr_rescue_enabled": env.get("ORT_ADAPTIVE_READABILITY_GUARD", "0") == "1", "ocr_rescue_floor": int(env.get("ORT_OCR_STORY_MIN_PERCENT", "50")), "ct2_fallback_active": env.get("ORT_CT2_FALLBACK_ACTIVE", "0") == "1"})
        try:
            save_state({
                "version": "v8.8.1",
                "status": "RUNNING",
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
                "entity_span_pipeline": True,
                "cache_namespace": env.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            }, BASE_DIR)
        except Exception:
            pass

        self.lines = []
        self.last_error = ""
        self.pending_candidate_notice = ""
        self.current_game = str(game)
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
                "version": "v8.8.1",
                "fast_engine_status": fast_state.get("state", "unknown"),
                "fast_engine_active": bool(fast_state.get("active")),
                "dialog_scheduler_profile": env.get("ORT_DIALOG_SCHEDULER_PROFILE", "-"),
                "image_hash_gate": env.get("ORT_IMAGE_HASH_GATE", "1") == "1",
                "fuzzy_cache_key": env.get("ORT_FUZZY_CACHE_KEY", "1") == "1",
                "performance_reason": perf_reason,
                "fast_profile": env.get("ORT_FAST_PROFILE", "standard"),
                "fast_profile_label": env.get("ORT_FAST_PROFILE_LABEL", "-"),
                "lite_gpu_profile": env.get("ORT_LITE_GPU_PROFILE", "off"),
                "lite_gpu_reason": env.get("ORT_LITE_GPU_REASON", "-"),
                "responsive_story_mode": bool(applied_responsive),
                "diagnostic_profile": diagnostic_profile,
                "entity_span_pipeline": True,
                "cache_namespace": env.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            }, BASE_DIR)
        except Exception:
            pass
        self.status = "RUNNING"
        self.stop_requested = False
        effective_interval_msg = int(env.get("ORT_BOOT_INTERVAL_MS", interval_ms))
        self._push(f"[WEBUI v8.8.1] START {model} | game={game} | strategy={strategy.strategy_name} | mode={str(mode).lower()} | engine={str(engine).lower()} | interval={effective_interval_msg}ms | requested_ocr={int(ocr_resolution)}% | applied_ocr={applied_runtime_ocr}% | rescue_floor={env.get('ORT_OCR_STORY_MIN_PERCENT','50')}% | adaptive_rescue={env.get('ORT_ADAPTIVE_READABILITY_GUARD','0')} | policy={performance_policy} | normal_override={normal_override}")
        self._push("[WEBUI] strategy: " + " | ".join(strategy.summary_lines()[:5]))
        self._push(f"[WEBUI v8.8.1] scheduler={env.get('ORT_DIALOG_SCHEDULER_PROFILE')} | fast_profile={env.get('ORT_FAST_PROFILE')} | diagnostic={diagnostic_profile} | responsive_story={env.get('ORT_RESPONSIVE_STORY_MODE')} | latest_frame_wins={env.get('ORT_LATEST_FRAME_WINS')} | image_hash_gate={env.get('ORT_IMAGE_HASH_GATE')} | fuzzy_cache={env.get('ORT_FUZZY_CACHE_KEY')} | voice_hold={env.get('ORT_DIALOG_VOICE_HOLD_MS', '-')}ms")
        if env.get("ORT_FAST_PROFILE_LABEL"):
            self._push(f"[WEBUI v8.8.1] fast_profile_note={env.get('ORT_FAST_PROFILE_LABEL')}")
        if env.get("ORT_LITE_GPU_EFFICIENT") == "1":
            self._push(f"[WEBUI v8.8.1] lite_gpu={env.get('ORT_LITE_GPU_PROFILE')} | ct2_allowed={env.get('ORT_LITE_CT2_ALLOWED')} | requested_ocr={env.get('ORT_LITE_REQUESTED_OCR', env.get('ORT_BOOT_OCR_RESOLUTION'))}% | applied_ocr={env.get('ORT_LITE_APPLIED_OCR', env.get('ORT_BOOT_OCR_RESOLUTION'))}% | queue={env.get('ORT_LITE_APPLIED_QUEUE', env.get('TITAN_QUEUE_MAX'))} | reason={env.get('ORT_LITE_GPU_REASON')}")
        if env.get("ORT_GFL_LAYOUT") == "1":
            self._push("[WEBUI v8.8.1] GFL layout=GFL_DIALOG_STANDARD | name_roi=1 | body_roi=1 | footer_mask=1 | scene_guard=1 | cache_normalized=1 | speaker_quarantine=3hits")
        if env.get("ORT_GFL2_SPEAKER_ROI") == "1":
            self._push(f"[WEBUI v8.8.1] GFL2 speaker_roi=1 | trusted_registry=1 | verified_exact_catalog=1 | dual_helen_helena_guard=1 | full_backend_entity_span=1 | exact_fallback_only=1 | adaptive_readability_guard={env.get('ORT_ADAPTIVE_READABILITY_GUARD','0')} | stale_overlay_guard=1 | residual_guard=1 | critical_token_guard=1 | stable_final_cache_v2=1 | idn_eval_export=1 | faithfulness_v2=1 | strict_ct2_story=1 | qur_quarantine=1")
        elif diagnostic_profile == "diagnostic_no_name_roi" and str(game).upper() == "GFL2_EXILIUM":
            self._push("[WEBUI v8.8.1][DIAGNOSTIC WARNING] Name ROI OFF hanya untuk uji A/B; label KSVK/Helen/Helena dapat hilang atau salah.")
        if strategy.fast_path and not bool(fast_state.get("active")):
            self._push(f"[WEBUI v8.8.1][WARN] Fast CT2 belum aktif ({fast_state.get('state')}). Model Fast akan fallback Argos sehingga masih terasa lamban. model_dir={fast_state.get('model_dir', '-')}")
        self._push(f"[WEBUI v8.8.1] performance_reason={perf_reason}")
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

    def stop(self):
        if self.proc and self.proc.poll() is None:
            self.stop_requested = True
            self.status = "STOPPING"
            self.stop_at = time.time()
            self._push("[WEBUI v8.8.1] Graceful STOP requested. Menunggu flush cache/log/session...")
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
                self._push("[WEBUI v8.8.1] Graceful stop timeout; fallback hard kill.")
                try:
                    if os.name == 'nt':
                        subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'], capture_output=True, text=True, timeout=10)
                    else:
                        self.proc.kill()
                except Exception as e:
                    self.last_error = str(e)
            else:
                self._push("[WEBUI v8.8.1] Graceful stop selesai; cache/log seharusnya sudah flush.")
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

    def refresh(self):
        if self.status == "STOP" and (not self.proc or self.proc.poll() is not None):
            if time.time() - self.stop_at > 1.2:
                self.status = "IDLE"
        return self.get_status_text(), self.get_log(), self.last_error or "", self.pending_candidate_notice


MANAGER = ProcessManager()


def start_model(model, game, mode, engine, interval_ms, ocr_resolution=65, performance_policy="auto", normal_override=False, settings_mode=None, responsive_story_mode=False, diagnostic_profile="baseline"):
    return MANAGER.start(model, game, mode, engine, interval_ms, ocr_resolution, performance_policy, normal_override, settings_mode, responsive_story_mode, diagnostic_profile)


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

