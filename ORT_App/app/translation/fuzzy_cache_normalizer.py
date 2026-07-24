from __future__ import annotations

import os
import re

_WORD_FIXES = {
    "iike": "like", "iooks": "looks", "iook": "look", "afrald": "afraid", "agaln": "again",
    "safel": "safe", "wonderfull": "wonderful", "volce": "voice", "qujetly": "quietly",
    "exlst": "exist", "waltlng": "waiting", "waitlng": "waiting", "tlme": "time",
    "promlse": "promise", "thlng": "thing", "mlsslng": "missing", "mlssi": "missi",
    "ofher": "of her", "imthe": "im the", "haventarranged": "haven't arranged",
    "doesn": "doesn't", "dont": "don't", "wont": "won't", "youve": "you've", "ive": "i've",
    "lentlne": "Lentine", "ralzei": "Raizei", "alvaand": "Alva and", "allare": "All are",
    "allthe": "All the", "wellfind": "We'll find", "ifthe": "If the", "ifwe": "If we",
    "donttalk": "Don't talk", "isnt": "isn't", "cant": "can't", "willeventually": "will eventually",
    "vaymastina": "Voymastina", "voymastlna": "Voymastina", "voymastiha": "Voymastina", "ralzel": "Raizei", "ralzei": "Raizei", "raizel": "Raizei", "ralizei": "Raizei",
    "keny": "Kenny", "kennv": "Kenny", "bathildel": "Balthilde", "balthildel": "Balthilde", "bathilde": "Balthilde", "balthllde": "Balthilde",
    "thearmor": "The armor", "feelas": "feel as", "ltsll2": "", "ltsil2": "", "ltfail2": "",
    "ifshe": "if she", "isan": "is an", "ofthe": "of the", "ofit": "of it",
    "iike": "like", "apologles": "apologies", "recelved": "received", "ksvkis": "KSVK is",
}


def normalize_cache_key(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    try:
        if os.environ.get("ORT_GFL_CACHE_NORMALIZED", "0") == "1":
            from app.games.gfl_profile import normalize_gfl_cache_text
            s = normalize_gfl_cache_text(s)
    except Exception:
        pass
    s = s.replace("讦", "if").replace("计", "it").replace("比", "it").replace("让", "it")
    s = re.sub(r"[|川州]+", " ", s)
    s = re.sub(r"\byoU\b", "you", s)
    s = re.sub(r"\bYoU\b", "You", s)
    s = re.sub(r"\b0\b", "o", s)
    s = re.sub(r"\bs0\b", "so", s, flags=re.I)
    s = re.sub(r"\b50\b", "so", s)
    words = []
    for w in re.split(r"(\W+)", s):
        key = re.sub(r"[^A-Za-z']", "", w).lower()
        if key in _WORD_FIXES:
            fixed = _WORD_FIXES[key]
            if w[:1].isupper():
                fixed = fixed[:1].upper() + fixed[1:]
            words.append(fixed)
        else:
            words.append(w)
    s = "".join(words)
    s = re.sub(r"\s+", " ", s).strip()
    try:
        from app.translation.name_alias_normalizer import apply_name_aliases
        s = apply_name_aliases(s)
    except Exception:
        pass
    # Cache keys should ignore harmless casing/punctuation jitter.
    s = s.lower()
    s = re.sub(r"[\u2018\u2019]", "'", s)
    s = re.sub(r"\s*([,.;:!?])\s*", r"\1 ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s
