from __future__ import annotations

import re
from dataclasses import dataclass, field

_TOKEN_RE = re.compile(r"\w+(?:['’-]\w+)*|[^\w\s]", re.UNICODE)


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall(str(text or "").strip())


def _join(tokens: list[str]) -> str:
    text = " ".join(tokens)
    text = re.sub(r"\s+([,.;:!?%\]\)])", r"\1", text)
    text = re.sub(r"([\[\(])\s+", r"\1", text)
    return text.strip()


def _common_prefix(left: list[str], right: list[str]) -> list[str]:
    size = min(len(left), len(right))
    index = 0
    while index < size and left[index].casefold() == right[index].casefold():
        index += 1
    return left[:index]


@dataclass
class ConfirmedPrefixEngine:
    agreement_passes: int = 2
    confirmed: list[str] = field(default_factory=list)
    history: list[list[str]] = field(default_factory=list)

    def update(self, hypothesis: str, *, final: bool = False) -> dict:
        current = _tokens(hypothesis)
        self.history.append(current)
        keep = max(2, int(self.agreement_passes))
        self.history = self.history[-keep:]

        candidate = current
        if not final and len(self.history) >= keep:
            candidate = self.history[0]
            for item in self.history[1:]:
                candidate = _common_prefix(candidate, item)

        already = len(self.confirmed)
        if candidate[:already] != self.confirmed:
            # ASR may revise old words. Keep confirmed output immutable and use
            # the current hypothesis only as live tail.
            live_tail = current
        else:
            if final:
                self.confirmed = current
            elif len(candidate) > already:
                self.confirmed.extend(candidate[already:])
            live_tail = current[len(self.confirmed):] if current[:len(self.confirmed)] == self.confirmed else current

        return {
            "confirmed": _join(self.confirmed),
            "live_tail": _join(live_tail),
            "display": _join(self.confirmed + live_tail),
            "confirmed_tokens": len(self.confirmed),
            "live_tokens": len(live_tail),
            "final": bool(final),
        }


def demo_hypotheses(text: str, agreement_passes: int = 2) -> list[dict]:
    engine = ConfirmedPrefixEngine(agreement_passes=max(2, int(agreement_passes)))
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    result: list[dict] = []
    for index, line in enumerate(lines):
        final = index == len(lines) - 1
        state = engine.update(line, final=final)
        state.update({"step": index + 1, "hypothesis": line})
        result.append(state)
    return result
