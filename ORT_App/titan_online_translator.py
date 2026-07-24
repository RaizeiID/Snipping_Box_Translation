# titan_online_translator.py
import os
import requests
from typing import Callable


class OnlineTranslatorCore:
    """
    Translator online via HTTP endpoint (LibreTranslate compatible).
    Default endpoint bisa kamu set:
      TITAN_ONLINE_URL=http://localhost:5000/translate
    Default source/target:
      TITAN_ONLINE_FROM=en
      TITAN_ONLINE_TO=id
    """

    def __init__(self, log_fn: Callable[[str], None]):
        self.log = log_fn
        self.url = os.environ.get("TITAN_ONLINE_URL", "http://localhost:5000/translate")
        self.src = os.environ.get("TITAN_ONLINE_FROM", "en")
        self.dst = os.environ.get("TITAN_ONLINE_TO", "id")
        self.timeout = float(os.environ.get("TITAN_ONLINE_TIMEOUT", "2.5"))

    def translate(self, text: str) -> str:
        if not text:
            return ""
        payload = {"q": text, "source": self.src, "target": self.dst, "format": "text"}

        r = requests.post(self.url, json=payload, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()

        # LibreTranslate style: {"translatedText":"..."}
        out = data.get("translatedText")
        if isinstance(out, str) and out.strip():
            return out.strip()

        # Some APIs return {"translation":"..."}
        out2 = data.get("translation")
        if isinstance(out2, str) and out2.strip():
            return out2.strip()

        return text
