# punctuationcore.py
import os
import json
import re
from typing import Callable, Dict


class PunctuationCore:
    """
    Core untuk:
    - normalisasi tanda baca OCR (fullwidth -> ascii, ellipsis, quote)
    - menjaga "signature" tanda baca dialog (awal/akhir) agar hasil terjemahan mengikuti dialog asli
    - menyimpan statistik pola tanda baca (learning ringan)
    """

    def __init__(self, base_dir: str, log_fn: Callable[[str], None]):
        self.log = log_fn
        self.path = os.path.join(base_dir, "punctuation_stats.json")
        self.stats: Dict[str, int] = {}
        self._dirty = False
        self._load()

    # ---------------- persistence ----------------
    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                self.stats = dict(json.load(f))
        except Exception:
            self.stats = {}

    def flush(self, reason="flush"):
        if not self._dirty:
            return
        try:
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._dirty = False
            self.log(f"[LEARN] punctuation_stats saved ({reason}) | keys={len(self.stats)}")
        except Exception as e:
            self.log(f"[LEARN] punctuation_stats save failed: {e}")

    # ---------------- normalize ----------------
    def normalize_unicode(self, s: str) -> str:
        if not s:
            return s

        # fullwidth punctuation -> ascii
        s = s.replace("，", ",").replace("。", ".").replace("！", "!").replace("？", "?")
        s = s.replace("：", ":").replace("；", ";").replace("（", "(").replace("）", ")")
        s = s.replace("【", "[").replace("】", "]").replace("「", '"').replace("」", '"')
        s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
        s = s.replace("—", "-").replace("–", "-")

        # ellipsis variations -> dots (preserve multi)
        # convert unicode ellipsis char to "..."
        s = s.replace("…", "...")

        # ". . ." -> "..."
        s = re.sub(r"\.\s+\.\s+\.", "...", s)

        # collapse 4-5 dots to 3, 7-8 to 6
        s = re.sub(r"\.{7,}", "......", s)
        s = re.sub(r"\.{4,5}", "...", s)

        # remove weird spaces before punctuation
        s = re.sub(r"\s+([,.;:!?])", r"\1", s)
        # normalize multiple spaces
        s = re.sub(r"[ \t]{2,}", " ", s)

        return s.strip()

    def normalize_for_cache(self, s: str) -> str:
        """
        Normalisasi untuk key cache, agar variasi OCR tanda baca tidak bikin entry terpisah.
        """
        s = self.normalize_unicode(s)
        # trim zero-width
        s = s.replace("\u200b", "").replace("\ufeff", "")
        # normalize whitespace
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # ---------------- signature ----------------
    def extract_signature(self, raw_dialog: str) -> Dict[str, str]:
        """
        Ambil signature tanda baca awal & akhir dari raw dialog.
        Contoh:
          raw: "... Wait!?" -> start="..." end="!?"
        """
        s = (raw_dialog or "").strip()
        s = self.normalize_unicode(s)

        start = ""
        end = ""

        # start ellipsis or dash
        if s.startswith("......"):
            start = "......"
        elif s.startswith("..."):
            start = "..."
        elif s.startswith("- "):
            start = "- "
        elif s.startswith("-"):
            start = "-"

        # trailing punctuation seq
        m = re.search(r"([.!?]+)$", s)
        if m:
            end = m.group(1)
            # normalize long dot seq at end
            if end.startswith("......"):
                end = "......" + re.sub(r"[.]", "", end[6:])
            elif end.startswith("..."):
                end = "..." + re.sub(r"[.]", "", end[3:])

        # store stats (learning ringan)
        key = f"start={start}|end={end}"
        self.stats[key] = int(self.stats.get(key, 0)) + 1
        self._dirty = True
        # flush jarang (biar gak berat)
        if self.stats[key] % 50 == 0:
            self.flush("auto_50_hits")

        return {"start": start, "end": end}

    def apply_signature(self, sig: Dict[str, str], translated: str) -> str:
        """
        Terapkan start/end punctuation signature ke hasil terjemahan.
        """
        if not translated:
            return translated

        t = self.normalize_unicode(translated)

        start = (sig or {}).get("start", "")
        end = (sig or {}).get("end", "")

        # apply start (only if translation missing similar prefix)
        if start in ("......", "..."):
            if not (t.startswith("......") or t.startswith("...")):
                t = start + " " + t
        elif start.startswith("-"):
            if not t.startswith("-"):
                t = start + t

        # apply end: replace trailing punctuation with the raw end (if raw has one)
        if end:
            t = re.sub(r"[.!?]+$", "", t).rstrip()
            t = t + end

        # ensure no extra spaces before punctuation
        t = re.sub(r"\s+([,.;:!?])", r"\1", t)
        t = re.sub(r"\s+", " ", t).strip()

        return t
