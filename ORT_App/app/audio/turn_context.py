from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Dict, Iterable, List


_WORD_KEY_RE = re.compile(r"[^0-9A-Za-zÀ-ÖØ-öø-ÿĀ-ž\u3040-\u30ff\u3400-\u9fff']+")


def _clean_text(value: object) -> str:
    return " ".join(str(value or "").strip().split())


# ORT_R5_COMPLETE_UTTERANCE: CJK_CONTEXT
_CLOSING_PUNCTUATION = set("、。！？…,.!?;:)]}」』】〉》")
_OPENING_PUNCTUATION = set("([{「『【〈《")


def _is_cjk_token(value: str) -> bool:
    token = str(value or "")
    return bool(token) and all(
        "\u3040" <= char <= "\u30ff"
        or "\u3400" <= char <= "\u9fff"
        for char in token
    )


def _tokens(text: str) -> List[str]:
    # Japanese normally has no spaces. Character units preserve rolling overlap.
    clean = _clean_text(text)
    tokens: List[str] = []
    latin: List[str] = []

    def flush_latin() -> None:
        if latin:
            tokens.append("".join(latin))
            latin.clear()

    for char in clean:
        if char.isspace():
            flush_latin()
        elif "\u3040" <= char <= "\u30ff" or "\u3400" <= char <= "\u9fff":
            flush_latin()
            tokens.append(char)
        elif char.isalnum() or char in {"'", "_", "-"}:
            latin.append(char)
        else:
            flush_latin()
            tokens.append(char)
    flush_latin()
    return tokens


def _join_tokens(tokens: Iterable[str]) -> str:
    output = ""
    previous = ""
    for raw in tokens:
        token = str(raw or "")
        if not token:
            continue
        if not output:
            output = token
        elif token in _CLOSING_PUNCTUATION:
            output += token
        elif previous in _OPENING_PUNCTUATION:
            output += token
        elif _is_cjk_token(previous) or _is_cjk_token(token):
            output += token
        else:
            output += " " + token
        previous = token
    return output


def _key(token: str) -> str:
    return _WORD_KEY_RE.sub("", str(token or "")).casefold()


def _keys(tokens: Iterable[str]) -> List[str]:
    return [key for key in (_key(token) for token in tokens) if key]


def _find_suffix_prefix_overlap(previous: List[str], current: List[str], maximum: int = 40) -> int:
    if not previous or not current:
        return 0
    limit = min(len(previous), len(current), max(1, int(maximum)))
    left_keys = [_key(token) for token in previous]
    right_keys = [_key(token) for token in current]
    for size in range(limit, 0, -1):
        if left_keys[-size:] == right_keys[:size] and any(left_keys[-size:]):
            return size
    return 0


def _contains_sequence(haystack: List[str], needle: List[str]) -> bool:
    hay = _keys(haystack)
    need = _keys(needle)
    if not hay or not need or len(need) > len(hay):
        return False
    width = len(need)
    return any(hay[index:index + width] == need for index in range(len(hay) - width + 1))


def _similarity(left: List[str], right: List[str]) -> float:
    return SequenceMatcher(None, _keys(left), _keys(right), autojunk=False).ratio()


@dataclass
class TurnContextState:
    committed_tokens: List[str] = field(default_factory=list)
    live_tokens: List[str] = field(default_factory=list)
    last_raw_tokens: List[str] = field(default_factory=list)
    updated_at: float = 0.0
    revisions: int = 0


@dataclass(frozen=True)
class TurnContextResult:
    text: str
    full_text: str
    words: int
    full_words: int
    appended_words: int
    changed: bool
    truncated: bool
    revisions: int


class RollingTurnContext:
    """Assemble rolling ASR hypotheses into one bounded speaking turn.

    A rolling hypothesis is not a delta. The unstable tail is replaced while
    only text that scrolls out through a verified overlap is committed. This
    keeps long dialogue continuous without concatenating every ASR rewrite.
    """

    def __init__(self, *, max_history_words: int = 240, display_words: int = 72) -> None:
        self.max_history_words = max(32, int(max_history_words))
        self.display_words = max(16, int(display_words))
        self._states: Dict[str, TurnContextState] = {}

    def clear(self, turn_id: str) -> None:
        self._states.pop(str(turn_id or ""), None)

    def update(self, turn_id: str, raw_text: str, *, stable: bool = False) -> TurnContextResult:
        key = str(turn_id or "default")
        current = _tokens(raw_text)
        state = self._states.setdefault(key, TurnContextState())
        if not current:
            return self._result(state, appended_words=0, changed=False)

        previous_full = state.committed_tokens + state.live_tokens
        previous_live = list(state.live_tokens)
        appended = 0

        if not previous_live:
            state.live_tokens = current
            appended = len(current)
        elif _contains_sequence(previous_live, current) and len(current) <= len(previous_live):
            # Do not shrink a useful live line because one partial returned only
            # its final few words. A stable final may still replace it below.
            if stable and _similarity(previous_live, current) >= 0.55:
                state.live_tokens = current
        elif _contains_sequence(current, previous_live):
            # Straight prefix growth or a fuller rewrite.
            state.live_tokens = current
            appended = max(0, len(current) - len(previous_live))
        else:
            overlap = _find_suffix_prefix_overlap(previous_live, current)
            if overlap:
                committed = previous_live[:-overlap]
                if committed:
                    state.committed_tokens.extend(committed)
                state.live_tokens = current
                appended = max(0, len(current) - overlap)
            else:
                similarity = _similarity(previous_live, current)
                if similarity >= 0.34:
                    # Same acoustic window, different decoding: replace only the
                    # unstable live tail instead of appending both hypotheses.
                    state.live_tokens = current
                    appended = max(0, len(current) - len(previous_live))
                elif stable or previous_live[-1].endswith((".", "!", "?", "…")):
                    state.committed_tokens.extend(previous_live)
                    state.live_tokens = current
                    appended = len(current)
                else:
                    # Abrupt rewrite without a sentence boundary is usually ASR
                    # correction, not a new clause.
                    state.live_tokens = current

        state.last_raw_tokens = current
        state.updated_at = time.monotonic()
        state.revisions += 1
        self._cap(state)
        changed = previous_full != state.committed_tokens + state.live_tokens
        return self._result(state, appended_words=appended, changed=changed)

    def _cap(self, state: TurnContextState) -> None:
        full = state.committed_tokens + state.live_tokens
        if len(full) <= self.max_history_words:
            return
        overflow = len(full) - self.max_history_words
        if overflow <= len(state.committed_tokens):
            state.committed_tokens = state.committed_tokens[overflow:]
            return
        overflow -= len(state.committed_tokens)
        state.committed_tokens = []
        state.live_tokens = state.live_tokens[overflow:]

    def _result(self, state: TurnContextState, *, appended_words: int, changed: bool) -> TurnContextResult:
        full_tokens = state.committed_tokens + state.live_tokens
        display_tokens = full_tokens[-self.display_words:]
        truncated = len(full_tokens) > len(display_tokens)
        display = _join_tokens(display_tokens)
        if truncated:
            display = "…" + display
        return TurnContextResult(
            text=display,
            full_text=_join_tokens(full_tokens),
            words=len(display_tokens),
            full_words=len(full_tokens),
            appended_words=max(0, int(appended_words)),
            changed=bool(changed),
            truncated=truncated,
            revisions=state.revisions,
        )
