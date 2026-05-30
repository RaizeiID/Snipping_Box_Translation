"""ORT Translation v8.0 Online Assist configuration helper."""
from __future__ import annotations
import json, os
from pathlib import Path
from typing import Any, Dict
from online_assist_router import OnlineAssistRouter
from status_manager import write_status

CONFIG_NAME = "online_assist_config.json"

def config_path(base_dir: str | os.PathLike[str] | None = None) -> Path:
    return Path(base_dir or Path(__file__).resolve().parent).resolve() / CONFIG_NAME

def load_online_config(base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    path = config_path(base_dir)
    default = {"enabled": False, "provider": "libretranslate", "endpoint": "", "api_key": "", "timeout": 1.2, "max_chars": 220}
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                default.update(data)
    except Exception:
        pass
    return default

def save_online_config(provider: str = "libretranslate", endpoint: str = "", api_key: str = "", timeout: float = 1.2, enabled: bool = False, base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    data = {"enabled": bool(enabled), "provider": provider or "libretranslate", "endpoint": endpoint or "", "api_key": api_key or "", "timeout": float(timeout or 1.2), "max_chars": 220}
    path = config_path(base_dir)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    try: write_status("online_config", {"version":"v8.0", "path": str(path), **{k:v for k,v in data.items() if k != "api_key"}}, base_dir)
    except Exception: pass
    return data

def apply_online_config_to_env(base_dir: str | os.PathLike[str] | None = None) -> Dict[str, Any]:
    cfg = load_online_config(base_dir)
    os.environ["TITAN_ONLINE_ASSIST"] = "1" if cfg.get("enabled") else "0"
    os.environ["ORT_ONLINE_PROVIDER"] = str(cfg.get("provider") or "libretranslate")
    os.environ["ORT_ONLINE_ENDPOINT"] = str(cfg.get("endpoint") or "")
    os.environ["ORT_ONLINE_API_KEY"] = str(cfg.get("api_key") or "")
    os.environ["TITAN_ONLINE_TIMEOUT"] = str(cfg.get("timeout") or 1.2)
    os.environ["ORT_ONLINE_MAX_CHARS"] = str(cfg.get("max_chars") or 220)
    return cfg


def online_assist_config_values(base_dir: str | os.PathLike[str] | None = None):
    """Return values in WebUI-friendly order: enabled, provider, endpoint, api_key, timeout."""
    cfg = load_online_config(base_dir)
    return bool(cfg.get("enabled")), str(cfg.get("provider") or "libretranslate"), str(cfg.get("endpoint") or ""), str(cfg.get("api_key") or ""), float(cfg.get("timeout") or 1.2)


def save_online_config_text(enabled: bool, provider: str, endpoint: str, api_key: str, timeout: float, base_dir: str | os.PathLike[str] | None = None) -> str:
    cfg = save_online_config(provider=provider, endpoint=endpoint, api_key=api_key, timeout=timeout, enabled=enabled, base_dir=base_dir)
    return "\n".join([
        "Online Assist configuration saved.",
        f"enabled = {cfg.get('enabled')}",
        f"provider = {cfg.get('provider')}",
        f"endpoint_configured = {bool(cfg.get('endpoint'))}",
        f"timeout = {cfg.get('timeout')}",
        "Note: V4 models use online assist offline-first; WUWA Safe Game keeps online assist disabled by strategy unless overridden.",
    ])


def online_assist_status_text(base_dir: str | os.PathLike[str] | None = None) -> str:
    cfg = load_online_config(base_dir)
    apply_online_config_to_env(base_dir)
    r = OnlineAssistRouter(base_dir)
    data = r.status()
    return "\n".join([
        f"Online Assist = {data['state']}",
        f"config_enabled = {cfg.get('enabled')}",
        f"runtime_enabled = {data['enabled']}",
        f"provider = {data['provider']}",
        f"endpoint_configured = {data['endpoint_configured']}",
        f"timeout = {data['timeout']}",
        f"fail_count = {data['fail_count']}/{data['max_fail']}",
        f"runtime_disabled = {data['runtime_disabled']}",
        f"config_path = {config_path(base_dir)}",
        f"reason = {data['reason']}",
    ])

def test_online_assist(base_dir: str | os.PathLike[str] | None = None, text: str = "Hello") -> str:
    apply_online_config_to_env(base_dir)
    r = OnlineAssistRouter(base_dir)
    out = r.translate(text, source="en", target="id")
    data = r.status()
    return "\n".join([
        f"state = {data['state']}",
        f"provider = {data['provider']}",
        f"endpoint_configured = {data['endpoint_configured']}",
        f"input = {text}",
        f"output = {out or '-'}",
        f"reason = {data['reason']}",
    ])
