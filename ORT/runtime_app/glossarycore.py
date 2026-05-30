# glossarycore.py
import os
import json
import re
from typing import Callable, Dict, Tuple


class GlossaryCore:
    """
    Glossary untuk istilah game / akronim / proper noun.
    - Bisa protect source-term agar tidak "diacak" oleh translator.
    - Bisa replace hasil akhir supaya istilah konsisten.

    Format file: glossary.json
    {
      "ELID": "E.L.I.D",
      "ODE-07": "ODE-07",
      "Doll": "Boneka Taktis"
    }
    """

    def __init__(self, base_dir: str, log_fn: Callable[[str], None]):
        self.log = log_fn
        self.path = os.path.join(base_dir, "glossary.json")
        self.data: Dict[str, str] = {}
        self._dirty = False
        self._load()

    def _load(self):
        if not os.path.exists(self.path):
            self.data = {}
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = dict(json.load(f))
        except Exception:
            self.data = {}

    def flush(self, reason="flush"):
        if not self._dirty:
            return
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._dirty = False
            self.log(f"[LEARN] glossary saved ({reason}) | items={len(self.data)}")
        except Exception as e:
            self.log(f"[LEARN] glossary save failed: {e}")

    def add(self, src: str, dst: str, reason="manual_add"):
        src = (src or "").strip()
        dst = (dst or "").strip()
        if not src or not dst:
            return
        if self.data.get(src) == dst:
            return
        self.data[src] = dst
        self._dirty = True
        self.flush(reason)

    def ensure_passthrough(self, term: str, reason="passthrough"):
        """
        Agar istilah tidak diterjemahkan: dst == src
        """
        t = (term or "").strip()
        if not t:
            return
        if self.data.get(t) == t:
            return
        self.data[t] = t
        self._dirty = True

    def _sorted_terms(self):
        return sorted(self.data.keys(), key=len, reverse=True)

    def protect_source(self, text: str) -> Tuple[str, Dict[str, str]]:
        """
        Replace src terms -> placeholder, return (masked_text, placeholder_map)
        placeholder_map: placeholder -> target string (dst)
        """
        if not text or not self.data:
            return text, {}

        masked = text
        repl_map: Dict[str, str] = {}
        idx = 0

        # split by existing placeholders to avoid double-protect
        for src in self._sorted_terms():
            if not src or src not in masked:
                continue

            placeholder = f"__TITAN_GLOSS_{idx}__"
            idx += 1

            # whole word-ish boundary
            esc = re.escape(src)
            rx = re.compile(rf"(?<![A-Za-z0-9_]){esc}(?![A-Za-z0-9_])")

            if rx.search(masked):
                masked = rx.sub(placeholder, masked)
                repl_map[placeholder] = self.data[src]

        return masked, repl_map

    def apply_placeholders(self, text: str, placeholder_map: Dict[str, str]) -> str:
        if not text or not placeholder_map:
            return text
        out = text
        # replace placeholders -> dst
        for ph, dst in placeholder_map.items():
            out = out.replace(ph, dst)
        return out

    def post_replace(self, text: str) -> str:
        """
        Optional: replace src->dst even after translation
        (untuk istilah yang biasanya ikut kebawa atau berubah)
        """
        if not text or not self.data:
            return text
        out = text
        for src in self._sorted_terms():
            dst = self.data.get(src)
            if not dst or src == dst:
                continue
            esc = re.escape(src)
            rx = re.compile(rf"(?<![A-Za-z0-9_]){esc}(?![A-Za-z0-9_])", re.IGNORECASE)
            out = rx.sub(dst, out)
        return out
