# uniquetokencore.py
import os
import json
import re
from typing import Callable, Dict, Set, List


class UniqueTokenCore:
    """
    Belajar & melabeli "kata unik" (game terms / kode / akronim bertanda baca)
    Contoh: E.L.I.D, ODE-07, AR-15, KCCO-9, dsb.
    Output: wrap HTML biru untuk dialog overlay.
    """

    def __init__(self, base_dir: str, log_fn: Callable[[str], None], promote_after: int = 2):
        self.log = log_fn
        self.path = os.path.join(base_dir, "unique_terms.json")

        self.promote_after = max(2, int(promote_after))
        self.known: Set[str] = set()
        self.candidates: Dict[str, int] = {}
        self._dirty = False

        # blacklist agar tidak menganggap kata umum/karakter sebagai "kata unik"
        self.blacklist = set([
            "THE", "AND", "YOU", "YOUR", "THIS", "THAT", "WITH", "FROM", "HAVE", "WILL",
            "AUTO", "SKIP", "SYSTEM", "UNKNOWN"
        ])

        self._load()

        # regex kandidat kata unik (fokus pada pola yang punya tanda baca / angka / simbol)
        self._rx_candidates: List[re.Pattern] = [
            # E.L.I.D / A.I / U.M.P45 (huruf/digit dipisah titik)
            re.compile(r"\b(?:[A-Z0-9]\.){2,}[A-Z0-9]?\b"),
            # TOKEN bertitik bertingkat: A.BC.12
            re.compile(r"\b[A-Z0-9]{2,}(?:\.[A-Z0-9]{1,}){1,}\b"),
            # ODE-07 / AR-15 / KCCO-9 / X-01A
            re.compile(r"\b[A-Z]{2,}-[A-Z0-9]{1,}\b"),
            # CODE dengan underscore/slash: ELID_CORE / GF2/EXILIUM
            re.compile(r"\b[A-Z0-9]{2,}(?:[_/][A-Z0-9]{2,})+\b"),
        ]

    # ---------------- persistence ----------------
    def _load(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.known = set(data.get("known", []))
            self.candidates = dict(data.get("candidates", {}))
        except Exception:
            self.known = set()
            self.candidates = {}

    def flush(self, reason="flush"):
        if not self._dirty:
            return
        try:
            data = {"known": sorted(self.known), "candidates": self.candidates}
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, self.path)
            self._dirty = False
            self.log(f"[LEARN] unique_terms saved ({reason}) | known={len(self.known)}")
        except Exception as e:
            self.log(f"[LEARN] unique_terms save failed: {e}")

    # ---------------- utils ----------------
    def _canonical(self, token: str) -> str:
        """
        Canonical token untuk lookup:
        - trim whitespace
        - buang pembungkus umum di pinggir (quote, koma, kurung)
        - tapi tetap pertahankan '.' '-' '_' '/' di dalam token
        """
        if not token:
            return ""
        s = token.strip()
        s = re.sub(r"^[\"'(\[{<]+", "", s)
        s = re.sub(r"[\"')\]}>.,;:!?\s]+$", "", s)
        return s

    def _is_valid(self, token: str) -> bool:
        if not token:
            return False
        t = self._canonical(token)
        if not t:
            return False
        if len(t) < 3 or len(t) > 32:
            return False

        up = t.upper()
        if up in self.blacklist:
            return False

        # wajib punya ciri "unik": ada titik/hyphen/underscore/slash atau angka
        if not (("." in t) or ("-" in t) or ("_" in t) or ("/" in t) or re.search(r"\d", t)):
            return False

        # minimal ada huruf
        if not re.search(r"[A-Za-z]", t):
            return False

        return True

    # ---------------- learning ----------------
    def extract_candidates(self, text: str) -> Set[str]:
        if not text:
            return set()
        found = set()
        for rx in self._rx_candidates:
            for m in rx.finditer(text):
                tok = self._canonical(m.group(0))
                if self._is_valid(tok):
                    found.add(tok)
        return found

    def observe(self, text: str):
        """
        Amati text dan update kandidat -> promote jadi known.
        Promote cepat (>=2) agar kata unik cepat terlabel.
        """
        cands = self.extract_candidates(text)
        if not cands:
            return

        promoted_any = False
        for tok in cands:
            if tok in self.known:
                continue
            cnt = int(self.candidates.get(tok, 0)) + 1
            self.candidates[tok] = cnt
            self._dirty = True
            if cnt >= self.promote_after:
                self.known.add(tok)
                self.candidates.pop(tok, None)
                promoted_any = True
                self._dirty = True
                self.log(f"[LEARN] New unique term learned: {tok}")

        if promoted_any:
            self.flush("promote_unique_term")

    # ---------------- highlight ----------------
    def is_known(self, token: str) -> bool:
        tok = self._canonical(token)
        return bool(tok and tok in self.known)

    def highlight_html_blue(self, html_text: str) -> str:
        """
        Wrap kata unik (known) dengan warna biru. Aman untuk string yang sudah mengandung HTML tags.
        """
        if not html_text or not self.known:
            return html_text

        # split by HTML tags, apply replace only on non-tag segments
        parts = re.split(r"(<[^>]+>)", html_text)
        if len(parts) == 1:
            return self._highlight_plain(parts[0])

        out = []
        for p in parts:
            if p.startswith("<") and p.endswith(">"):
                out.append(p)
            else:
                out.append(self._highlight_plain(p))
        return "".join(out)

    def _highlight_plain(self, text: str) -> str:
        if not text:
            return text

        # sort longest-first to prevent partial overlaps
        terms = sorted(self.known, key=len, reverse=True)

        # replace with word-boundary-ish if possible, else literal
        for term in terms:
            esc = re.escape(term)
            if re.fullmatch(r"[A-Za-z0-9_.\-/]+", term):
                # boundary: split by non-word but allow .-_/ inside term
                rx = re.compile(rf"(?<![A-Za-z0-9_.\-/])({esc})(?![A-Za-z0-9_.\-/])")
            else:
                rx = re.compile(esc)

            def repl(m):
                return f"<b style='color:#3AA7FF;'>{m.group(1)}</b>"

            text = rx.sub(repl, text)

        return text
