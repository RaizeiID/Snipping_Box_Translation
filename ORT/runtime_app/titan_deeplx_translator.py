# titan_deeplx_translator.py
from __future__ import annotations

from typing import Callable

import requests


class DeepLXTranslatorCore:
    """
    DeepLX self-host endpoint (berbeda-beda fork).
    Default path ditentukan oleh mode:
      - free : /translate
      - v1   : /v1/translate
      - v2   : /v2/translate
    Payload:
      { text, source_lang, target_lang }
    """

    def __init__(self, log_fn: Callable[[str], None], base_url: str, mode: str = "free", timeout: float = 10.0) -> None:
        self.log = log_fn
        self.base_url = (base_url or "").strip().rstrip("/")
        self.mode = (mode or "free").strip().lower()
        self.timeout = float(timeout or 10.0)

        if not self.base_url:
            raise ValueError("DeepLX base_url empty")

        if self.mode in ("v1", "pro"):
            self.endpoint = f"{self.base_url}/v1/translate"
        elif self.mode in ("v2", "official"):
            self.endpoint = f"{self.base_url}/v2/translate"
        else:
            self.endpoint = f"{self.base_url}/translate"

    def translate(self, text: str, source: str = "auto", target: str = "id") -> str:
        text = (text or "").strip()
        if not text:
            return ""

        payload = {"text": text, "source_lang": source or "auto", "target_lang": target or "id"}
        r = requests.post(self.endpoint, json=payload, timeout=self.timeout)
        r.raise_for_status()

        # try json
        try:
            data = r.json()
            if isinstance(data, dict):
                out = data.get("data") or data.get("translation") or data.get("translatedText") or data.get("text")
                if isinstance(out, str) and out.strip():
                    return out.strip()
                # some forks: {"code":200,"message":"ok","data":"..."}
                d2 = data.get("data")
                if isinstance(d2, dict):
                    out2 = d2.get("text") or d2.get("translatedText") or d2.get("translation")
                    if isinstance(out2, str) and out2.strip():
                        return out2.strip()
        except Exception:
            pass

        return (r.text or "").strip() or text
