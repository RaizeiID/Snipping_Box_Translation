# titan_gas_translator.py
from __future__ import annotations

import json
from typing import Callable

import requests


class GoogleAppsScriptTranslatorCore:
    """
    Google Apps Script Web App endpoint (doPost).
    Payload:
      { q, source, target, format, token? }

    Response supports:
      translatedText / text / result
    """

    def __init__(self, log_fn: Callable[[str], None], url: str, token: str = "", timeout: float = 12.0) -> None:
        self.log = log_fn
        self.url = (url or "").strip()
        self.token = (token or "").strip()
        self.timeout = float(timeout or 12.0)
        if not self.url:
            raise ValueError("GAS url is empty")

    def translate(self, text: str, source: str = "auto", target: str = "id") -> str:
        text = (text or "").strip()
        if not text:
            return ""

        payload = {"q": text, "source": source or "auto", "target": target or "id", "format": "text"}
        if self.token:
            payload["token"] = self.token

        r = requests.post(self.url, json=payload, timeout=self.timeout)
        r.raise_for_status()

        # GAS kadang balikin JSON string/plain
        try:
            data = r.json()
        except Exception:
            try:
                data = json.loads(r.text)
            except Exception:
                return (r.text or "").strip()

        if isinstance(data, dict):
            out = data.get("translatedText") or data.get("text") or data.get("result") or ""
            return str(out).strip()

        return str(data).strip()
