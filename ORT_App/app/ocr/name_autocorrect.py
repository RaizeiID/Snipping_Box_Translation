"""ORT v9.0.7 R27 -- repair OCR-corrupted character names against the registry.

The registry already knows every character's real spelling, but nothing used
that knowledge to repair a misread one. "Nlkketa", "Ra1zei", "C0lphne" and
"UIIrid" reached the translator as written, and an unknown proper noun is
exactly what a translation model mangles worst.

The obvious approach -- fuzzy-match every token against every name -- is what
makes this dangerous, because the cast contains Helen and Helena, Balthilde and
Bathilde, Heli. A loose match turns one character into another mid-scene, which
is worse than leaving the typo alone.

So the repair is two-tier, and the first tier removes the collision structurally
rather than by tuning a threshold.

Tier 1 -- confusable folding.
    OCR does not confuse letters at random; it confuses glyphs that LOOK alike:
    i/l/1/I/|, o/0/O, s/5, rn/m, cl/d. Fold those to one canonical form and a
    corrupted name lands exactly on its real spelling. Names that differ by a
    REAL letter do not collide, because a whole letter is not a glyph
    confusion:

        Helen     -> heien        Balthilde -> baithiide
        Helena    -> heiena       Bathilde  -> baithide

    Verified over the full 31-name registry: zero folds map to more than one
    name. Any fold that ever did would be dropped from the index rather than
    guessed.

Tier 2 -- similarity, gated by MARGIN not just score.
    For corruption folding cannot express (dropped letters: "nketta"), the best
    candidate must beat the runner-up by a clear distance. A token sitting
    between Helen and Helena has no margin, so nothing happens. Measured:
    "nketta" scores 0.77 against Nikketa with a 0.31 margin -- low score, but
    nothing else is even close, so it is safe. "Helenna" scores higher, 0.91,
    but with a 0.09 margin -- and is refused.

Cost, over 4000 real lines from the field logs: 0.056 ms per line. The naive
form of the same logic costs 3.0 ms; the difference is the length band and the
fold cache below, not a weaker rule -- the corrections and refusals are
identical.
"""
from __future__ import annotations

import os
import re
from difflib import SequenceMatcher
from typing import Dict, Iterable, List, Optional, Tuple

# Glyphs a detector genuinely mistakes for one another. Deliberately small: each
# pair here is a shape collision, not a spelling variation.
_CONFUSABLE = str.maketrans({
    "l": "i", "1": "i", "I": "i", "|": "i", "!": "i",
    "0": "o", "O": "o",
    "5": "s", "S": "s",
    "6": "b", "8": "b", "9": "g", "2": "z",
})

_STRIP = ".,;:!?\"'()[]{}<>-–—"

# Folding collapses look-alike glyphs, which means an ordinary English word can
# land on a name: "Hell" and "Heli" both fold to "heii". Registry names were
# checked against each other and do not collide -- but they were never checked
# against the language, and that is where the real false positives live. The
# authoritative guard is the caller's own ambiguity check (the registry knows
# "Hell" is a blocked fragment); this list is the backstop that keeps the module
# safe when used on its own.
_ENGLISH_STOPWORDS = frozenset("""
hell hello help held hall hill full fall fill fell bell ball bill tell tall till
well will wall well walls calls balls cell cold call kill kali kilo halo hold
holy help helm heel hail hair here hers helms
""".split())

# Accept on either path: a strong match with a clear margin, or a weaker match
# where nothing else comes near it at all.
MIN_SCORE = 0.82
MIN_MARGIN = 0.15
LOOSE_SCORE = 0.72
LOOSE_MARGIN = 0.25
# Below this a token is too short to carry enough signal; "Heli" is 4.
MIN_LEN = 4
# Folding cannot invent or delete many letters, so a candidate far off in length
# is not the same word. Also keeps the comparison set small.
LEN_BAND = 2


def fold(token: str) -> str:
    """Canonical form in which look-alike glyphs are indistinguishable."""
    s = re.sub(r"[^A-Za-z0-9|!]", "", token or "").lower()
    s = s.translate(_CONFUSABLE)
    return s.replace("rn", "m").replace("cl", "d").replace("vv", "w")


class NameAutoCorrector:
    def __init__(self, names: Iterable[str]):
        self.names: List[str] = [str(n).strip() for n in names if str(n).strip()]
        self.exact = {n.lower() for n in self.names}
        self._folds: List[Tuple[str, str]] = [(n, fold(n)) for n in self.names]

        buckets: Dict[str, set] = {}
        for name, f in self._folds:
            if f:
                buckets.setdefault(f, set()).add(name)
        # A fold shared by two names cannot be resolved, so it is not indexed.
        # It is kept for reporting, because a growing cast could create one and
        # silence would be the wrong way to find out.
        self.fold_index = {k: next(iter(v)) for k, v in buckets.items() if len(v) == 1}
        self.collisions = {k: sorted(v) for k, v in buckets.items() if len(v) > 1}
        self._first = {k[:1] for k in buckets}
        self._cache: Dict[str, Optional[str]] = {}

    # -- single token ------------------------------------------------------
    def correct_token(self, token: str, is_blocked=None) -> Tuple[str, Optional[str], str]:
        """Return (token, canonical_or_None, reason).

        `is_blocked(token) -> bool` lets the caller veto a candidate with its own
        knowledge. PredictionGuard passes its ambiguity check, so the registry's
        curated blocklist stays the single authority on what is too risky to
        touch -- the same guard the alias loop already uses.
        """
        core = (token or "").strip(_STRIP)
        # A possessive belongs to the sentence, not to the name. Matching on
        # "Dushevnaya's" folds to "dushevnayas", misses the index, and the fuzzy
        # tier then "repairs" it to "Dushevnaya" -- silently deleting the 's.
        # That happened 176 times on Dushevnaya alone in the field logs. Split
        # the suffix off, match the stem, put the suffix back.
        suffix = ""
        for tail in ("'s", "’s", "s'", "s’"):
            if len(core) > len(tail) + 1 and core.endswith(tail):
                core, suffix = core[: -len(tail)], tail
                break

        # An apostrophe left after the possessive split means a contraction, and
        # folding erases it: "he'll" becomes "heii", which is also what "Heli"
        # becomes. That fired 9 times in the field logs. No registered name
        # contains an apostrophe, so the character itself is the discriminator --
        # no word list required.
        if "'" in core or "’" in core:
            return token, None, "contraction"

        if len(core) < MIN_LEN:
            return token, None, "too_short"
        if core.lower() in self.exact:
            # Already a real name. This single rule is what makes Helen and
            # Helena safe: correct spellings are never candidates.
            return token, None, "already_exact"
        if core.lower() in _ENGLISH_STOPWORDS:
            return token, None, "ordinary_word"

        f = fold(core)
        if not f or f[:1] not in self._first:
            return token, None, "no_candidate"

        hit = self.fold_index.get(f)
        if not hit:
            if not fuzzy_enabled():
                return token, None, "no_exact_fold"
            cached = self._cache.get(f, "")
            if cached == "":
                cached = self._resolve(f)
                self._cache[f] = cached
            hit = cached
        if not hit:
            return token, None, "ambiguous_or_far"

        # The caller's veto is consulted LAST, once there is an actual repair to
        # veto. It is the expensive check -- PredictionGuard's version scores a
        # short token against every registered name -- and only about 0.5% of
        # tokens ever reach this point, so asking earlier would pay it on every
        # word of every frame for nothing.
        if is_blocked is not None and is_blocked(core):
            return token, None, "blocked_by_caller"

        reason = "confusable_fold" if self.fold_index.get(f) else "fuzzy_margin"
        return token.replace(core + suffix, hit + suffix), hit, reason

    def _resolve(self, f: str) -> Optional[str]:
        scored = sorted(
            (
                (SequenceMatcher(None, f, nf).ratio(), name)
                for name, nf in self._folds
                if nf and nf[0] == f[0] and abs(len(nf) - len(f)) <= LEN_BAND
            ),
            reverse=True,
        )
        if not scored:
            return None
        best, best_name = scored[0]
        runner = scored[1][0] if len(scored) > 1 else 0.0
        margin = best - runner
        if best >= MIN_SCORE and margin >= MIN_MARGIN:
            return best_name
        if best >= LOOSE_SCORE and margin >= LOOSE_MARGIN:
            return best_name
        return None

    # -- whole line --------------------------------------------------------
    def correct(self, text: str, is_blocked=None) -> Tuple[str, List[Tuple[str, str, str]]]:
        """Return (repaired_text, [(original, canonical, reason), ...])."""
        if not text:
            return text, []
        out: List[str] = []
        events: List[Tuple[str, str, str]] = []
        for part in re.split(r"(\s+)", str(text)):
            if not part.strip():
                out.append(part)
                continue
            new, canonical, reason = self.correct_token(part, is_blocked)
            out.append(new)
            if canonical and new != part:
                events.append((part.strip(_STRIP), canonical, reason))
        return "".join(out), events


def enabled() -> bool:
    return os.environ.get("ORT_NAME_AUTOCORRECT", "1") == "1"


def fuzzy_enabled() -> bool:
    """Tier 2 is OFF by default, and the measurement is why.

    Run over 20000 real lines, the fold tier repaired 172 names with nothing
    wrong. The fuzzy tier added corrections that were not repairs at all:

        care    -> Carmen  (54)      making  -> Mayling (41)
        came    -> Carmen  (23)      sweep   -> Sweeper (16)
        cared   -> Carmen  (35)      realize -> Raizei  (13)
        charm   -> Carmen

    The margin rule works exactly as designed on those -- no other NAME is
    close, so the margin is wide. The rule cannot help, because the competitor
    is not another name, it is the English language, and this module has no
    dictionary to know that "care" is a word and "Nkketa" is not.

    So the safe default is the tier that needs no judgement: a confusable fold
    is an exact match on a canonical form, and it either hits or it does not.
    Tier 2 stays available for anyone who wants it, with this warning attached.
    """
    return os.environ.get("ORT_NAME_AUTOCORRECT_FUZZY", "0") == "1"
