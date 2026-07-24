"""ORT Translation v8.7.8 Universal Semantic Faithfulness Gate v2.

The gate is deterministic and runs before overlay/cache/export/learning.  It
blocks semantic injections observed in live GFL2 testing, including diacritic
and punctuation variants of Qur'an/tafsir text, and exposes an OCR quarantine
for bare ``Qur`` corruptions of ``our``/``your``.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Iterable

_TOKEN_RE = re.compile(r"[A-Za-zÀ-ÿ0-9']+")


def _norm(value: str) -> str:
    txt = unicodedata.normalize("NFKC", str(value or "")).casefold().replace("’", "'").replace("`", "'")
    return txt


def _ascii(value: str) -> str:
    txt = unicodedata.normalize("NFKD", _norm(value))
    txt = "".join(ch for ch in txt if not unicodedata.combining(ch))
    txt = re.sub(r"[^a-z0-9']+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _ascii(value))


def _words(value: str) -> list[str]:
    return _TOKEN_RE.findall(_norm(value))


def _contains_any(value: str, patterns: Iterable[str]) -> bool:
    return any(re.search(p, value, flags=re.I) for p in patterns)

# Output-only concepts from proven Argos/domain-biased failures. They are only
# rejected when the source has no semantic support for that concept.
_INJECTION_TERMS: dict[str, tuple[str, ...]] = {
    "nabi": (r"\bnabi\b", r"\bpara nabi\b"),
    "quran": (r"\bqur\s*an\b", r"\bal\s*qur\s*an\b", r"\balquran\b", r"\bkoran\b"),
    "ayat": (r"\bayat\b",),
    "zakat": (r"\bzakat\b",),
    "surat": (r"\bsurat\s+(?:al|an|at|az)[ -]",),
    "mekah": (r"\bmekah\b", r"\bmecca\b", r"\bmakkah\b"),
    "luth": (r"\bluth\b", r"\blot\b"),
    "syuaib": (r"\bsyuaib\b", r"\bshu\s*ayb\b"),
    "malaikat": (r"\bmalaikat\b", r"\bangel(?:s)?\b"),
    "kafir": (r"\bkafir\b", r"\bdisbeliever(?:s)?\b", r"\bunbeliever(?:s)?\b"),
    "mukmin": (r"\bmukmin\b", r"\bbeliever(?:s)?\b"),
    "neraka": (r"\bneraka\b", r"\bjahannam\b"),
    "kiamat": (r"\bkiamat\b", r"\bhari kiamat\b"),
    "sekaratul_maut": (r"\bsekaratul maut\b", r"\bsakaratul maut\b"),
    "makkiyyah": (r"\bmakkiy+ah\b", r"\bmadaniy+ah\b"),
    "mubtada": (r"\bmubtada\b",),
    "allah": (r"\ballah\b", r"\bhak allah\b"),
    "al_masyariq": (r"\bal\s*masyariq\b", r"\bal\s*magharib\b"),
}
_SOURCE_SUPPORT: dict[str, tuple[str, ...]] = {
    "nabi": (r"\bprophet(?:s)?\b", r"\bnabi\b"),
    "quran": (r"\bqur\s*an\b", r"\bquran\b", r"\bkoran\b", r"\balquran\b"),
    "ayat": (r"\bverse(?:s)?\b", r"\bayat\b", r"\bquran\b"),
    "zakat": (r"\bzakat\b", r"\balms\b"),
    "surat": (r"\bsurah\b", r"\bchapter\b.*\bquran\b", r"\bsurat\b"),
    "mekah": (r"\bmecca\b", r"\bmakkah\b", r"\bmekah\b"),
    "luth": (r"\blot\b", r"\bluth\b"),
    "syuaib": (r"\bshu\s*ayb\b", r"\bsyuaib\b"),
    "malaikat": (r"\bangel(?:s)?\b", r"\bmalaikat\b"),
    "kafir": (r"\bunbeliever(?:s)?\b", r"\bdisbeliever(?:s)?\b", r"\bkafir\b"),
    "mukmin": (r"\bbeliever(?:s)?\b", r"\bmukmin\b"),
    "neraka": (r"\bhell\b", r"\bjahannam\b", r"\bneraka\b"),
    "kiamat": (r"\bdoomsday\b", r"\bjudgment day\b", r"\bkiamat\b"),
    "sekaratul_maut": (r"\bdeath throes\b", r"\bsekaratul maut\b"),
    "makkiyyah": (r"\bmakkiy+ah\b", r"\bmadaniy+ah\b"),
    "mubtada": (r"\bmubtada\b",),
    "allah": (r"\ballah\b", r"\bgod\b"),
    "al_masyariq": (r"\bmasyariq\b", r"\bmagharib\b"),
}
_TAFSIR_PATTERNS = (
    r"\bayat ini\b", r"\btafsir\b", r"\bpendahuluan\b.*\bmakkiy+ah\b",
    r"\bcatatan amal\b", r"\bsekaratul maut\b", r"\bsurat al\b",
    r"\borang orang yang\b", r"\bdan demi yang\b", r"\btiupan sangkakala\b",
)
_TAFSIR_SOURCE_SUPPORT = (r"\bquran\b", r"\bverse\b", r"\bsurah\b", r"\bscripture\b", r"\breligion\b", r"\bpeople who\b", r"\bthose who\b")

@dataclass(frozen=True)
class SourceQuarantineDecision:
    source: str
    repaired_source: str
    quarantined: bool = False
    reason: str = "safe"
    repair: str = ""

@dataclass(frozen=True)
class FaithfulnessDecision:
    allowed: bool
    reasons: tuple[str, ...] = ()
    injected_terms: tuple[str, ...] = ()
    expansion_ratio: float = 0.0
    source_words: int = 0
    output_words: int = 0
    hold_overlay: bool = False
    source_flags: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        return ";".join(self.reasons) if self.reasons else "safe"

    @property
    def flags(self) -> tuple[str, ...]:
        return self.reasons + tuple(f"injected:{item}" for item in self.injected_terms) + self.source_flags


def quarantine_qur_corruption(source: str) -> SourceQuarantineDecision:
    """Repair deterministic bare-Qur OCR corruptions or quarantine ambiguity.

    A real Qur'an reference contains ``quran/qur'an`` rather than a bare token in
    common English dialogue. Known GFL2 OCR failures converted *our* to *Qur*.
    """
    raw = str(source or "")
    low = _ascii(raw)
    if not re.search(r"\bqur\b", low) or re.search(r"\bqur\s*an\b", low):
        return SourceQuarantineDecision(raw, raw)
    repaired = raw
    # Deterministic observed contexts: ``our best``, ``our reality``, and
    # ``our division of labor``. Avoid guessing ambiguous ownership/secret forms.
    patterns = [
        (r"\bQur(?=\s+best\b)", "our"),
        (r"\bQur(?=\s+reality\b)", "our"),
        (r"\bQur(?=\s+division\b)", "Our"),
        (r"\bQur(?=\s+(?:team|plan|work|home|goal|future)\b)", "our"),
    ]
    for pat, repl in patterns:
        repaired, n = re.subn(pat, repl, repaired, flags=re.I)
        if n:
            return SourceQuarantineDecision(raw, repaired, False, "qur_ocr_repaired", f"Qur->{repl}")
    return SourceQuarantineDecision(raw, raw, True, "bare_qur_ambiguous_hold", "")


def assess_translation(source: str, output: str, *, progressive: bool = False) -> FaithfulnessDecision:
    src = _ascii(source)
    out = _ascii(output)
    src_words = _words(src)
    out_words = _words(out)
    if not out.strip():
        return FaithfulnessDecision(False, ("empty_output",), (), 0.0, len(src_words), 0, progressive)
    expansion = (len(out_words) / max(1, len(src_words))) if src_words else float(len(out_words))
    reasons: list[str] = []
    injected: list[str] = []
    source_flags: list[str] = []
    for term, output_patterns in _INJECTION_TERMS.items():
        if _contains_any(out, output_patterns) and not _contains_any(src, _SOURCE_SUPPORT[term]):
            injected.append(term)
    if injected:
        reasons.append("unsupported_domain_injection:" + ",".join(sorted(set(injected))))
    if _contains_any(out, _TAFSIR_PATTERNS) and not _contains_any(src, _TAFSIR_SOURCE_SUPPORT):
        reasons.append("unsupported_tafsir_pattern")
    qsrc = quarantine_qur_corruption(source)
    if qsrc.quarantined:
        source_flags.append("source:bare_qur_ambiguous")
        if _contains_any(out, _INJECTION_TERMS["quran"]) or _contains_any(out, _TAFSIR_PATTERNS):
            reasons.append("ocr_triggered_qur_religious_injection")
    if len(src_words) <= 6 and len(out_words) >= max(16, len(src_words) * 4):
        reasons.append("extreme_expansion_from_short_source")
    elif len(src_words) <= 14 and expansion >= 4.2 and len(out_words) >= 22:
        reasons.append("extreme_expansion_ratio")
    allowed = not reasons
    return FaithfulnessDecision(
        allowed=allowed,
        reasons=tuple(dict.fromkeys(reasons)),
        injected_terms=tuple(sorted(set(injected))),
        expansion_ratio=round(expansion, 3),
        source_words=len(src_words),
        output_words=len(out_words),
        hold_overlay=bool(progressive or len(src_words) <= 8 or qsrc.quarantined),
        source_flags=tuple(source_flags),
    )


def safe_fallback_text(source: str) -> str:
    src = str(source or "").strip()
    return f"{src}  [Terjemahan ditahan: hasil tidak terpercaya]" if src else "[Terjemahan ditahan: hasil tidak terpercaya]"
