"""ORT Translation v7.9 online assist router.

V4 remains offline-first.  This router only assists when it is safe:
- short bounded timeout
- circuit breaker after repeated failures
- runtime pressure pause via ORT_ONLINE_DISABLED / set_pressure_disabled
- provider status file for Dashboard

Supported providers intentionally use simple HTTP contracts so missing optional
online services never break the offline game translator.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from status_manager import write_status

ROOT = Path(__file__).resolve().parent

class OnlineAssistRouter:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None, timeout: Optional[float] = None, logger=print):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.log = logger
        self.timeout = float(timeout if timeout is not None else os.environ.get("TITAN_ONLINE_TIMEOUT", "1.2"))
        self.provider = os.environ.get("ORT_ONLINE_PROVIDER", "libretranslate").lower().strip()
        self.endpoint = os.environ.get("ORT_ONLINE_ENDPOINT", "").strip()
        self.enabled = os.environ.get("TITAN_ONLINE_ASSIST", "0") == "1"
        self.disabled_until = 0.0
        self.fail_count = 0
        self.max_fail = int(os.environ.get("ORT_ONLINE_MAX_FAIL", "3"))
        self.breaker_sec = float(os.environ.get("ORT_ONLINE_BREAKER_SEC", "45"))
        self.last_state = "INIT"
        self.last_reason = "router created"
        self.write_status("INIT", "router created")

    def set_pressure_disabled(self, disabled: bool, reason: str = "runtime pressure") -> None:
        if disabled:
            self.disabled_until = max(self.disabled_until, time.time() + float(os.environ.get("ORT_ONLINE_PRESSURE_PAUSE_SEC", "25")))
            self.write_status("PAUSED", reason)
        elif self.last_state == "PAUSED" and time.time() >= self.disabled_until:
            self.write_status("READY", "runtime pressure cleared")

    def available(self) -> bool:
        if not self.enabled:
            self.write_status("OFF", "TITAN_ONLINE_ASSIST=0")
            return False
        if os.environ.get("ORT_ONLINE_DISABLED", "0") == "1":
            self.set_pressure_disabled(True, "disabled by runtime health")
            return False
        if time.time() < self.disabled_until:
            self.write_status("PAUSED", f"paused until {int(self.disabled_until)}")
            return False
        if not self.endpoint:
            self.write_status("NOT_CONFIGURED", "ORT_ONLINE_ENDPOINT is empty")
            return False
        return True

    def _post_libretranslate(self, text: str, source: str, target: str) -> str:
        import requests  # type: ignore
        payload = {"q": text, "source": source, "target": target, "format": "text"}
        api_key = os.environ.get("ORT_ONLINE_API_KEY", "").strip()
        if api_key:
            payload["api_key"] = api_key
        r = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        return str(data.get("translatedText") or data.get("translation") or "").strip()

    def _post_generic(self, text: str, source: str, target: str) -> str:
        import requests  # type: ignore
        payload = {"text": text, "q": text, "source": source, "target": target}
        r = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            for key in ("translatedText", "translation", "result", "text", "output"):
                val = data.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
        return ""

    def translate(self, text: str, source: str = "en", target: str = "id") -> str:
        text = (text or "").strip()
        if not text:
            return ""
        max_chars = int(os.environ.get("ORT_ONLINE_MAX_CHARS", "220"))
        if len(text) > max_chars:
            self.write_status("SKIPPED", f"text too long for online assist ({len(text)}>{max_chars})")
            return ""
        if not self.available():
            return ""
        try:
            if self.provider in {"libretranslate", "libre"}:
                out = self._post_libretranslate(text, source, target)
            elif self.provider in {"custom", "deeplx", "gas", "google_apps_script"}:
                out = self._post_generic(text, source, target)
            else:
                self.write_status("UNSUPPORTED", f"provider={self.provider}")
                return ""
            if out and out != text:
                self.fail_count = 0
                self.write_status("ACTIVE", f"provider={self.provider}")
                return out.strip()
            self.write_status("EMPTY", "provider returned empty/identity result")
        except Exception as exc:
            self.fail_count += 1
            if self.fail_count >= self.max_fail:
                self.disabled_until = time.time() + self.breaker_sec
                self.write_status("CIRCUIT_BREAKER", f"{type(exc).__name__}: {exc}")
            else:
                self.write_status("FAILED", f"{type(exc).__name__}: {exc}")
        return ""

    def status(self) -> Dict[str, Any]:
        return {
            "version": "v7.9",
            "state": self.last_state,
            "enabled": self.enabled,
            "provider": self.provider,
            "endpoint_configured": bool(self.endpoint),
            "timeout": self.timeout,
            "disabled_until": self.disabled_until,
            "fail_count": self.fail_count,
            "max_fail": self.max_fail,
            "reason": self.last_reason,
            "runtime_disabled": os.environ.get("ORT_ONLINE_DISABLED", "0") == "1",
        }

    def write_status(self, state: str, reason: str) -> None:
        self.last_state = state
        self.last_reason = reason
        data = self.status()
        try:
            write_status("online_assist", data, self.base_dir)
        except Exception:
            pass
