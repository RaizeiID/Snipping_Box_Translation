"""ORT v8.9.1 Name/Term Prediction Guard v3.

Activation patch goals:
- Load the v8.9.1 registry by default.
- Promote exact and registered-alias speaker/name prefixes into visible labels.
- Repair guarded entity/term OCR typos such as bathildel -> Balthilde.
- Propagate Green/Yellow/Red confidence metadata to the overlay layer.
- Prevent Yellow/Red predictions from entering stable final cache.
- Keep Heli, Helen, Helena, Bathilde/Balthilde aliases, and Commander profile names distinct.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Any


@dataclass
class PredictionEvent:
    ocr: str
    candidate: str
    label: str
    kind: str
    reason: str
    allow_final_cache: bool = False


@dataclass
class PredictionResult:
    text: str
    speaker: Optional[str] = None
    speaker_confidence: str = ""
    speaker_kind: str = ""
    events: List[PredictionEvent] = field(default_factory=list)
    ambiguous: bool = False
    final_cache_blocked: bool = False

    @property
    def telemetry(self) -> Dict[str, int]:
        data: Dict[str, int] = {}
        for ev in self.events:
            key = "prediction_" + ev.label.lower() + "_applied"
            if ev.label.lower() == "red":
                key = "prediction_red_blocked"
            data[key] = data.get(key, 0) + 1
            if ev.kind in {"speaker_label", "character_name", "main_commander"} and ev.label.lower() == "green":
                data["entity_green_labeled"] = data.get("entity_green_labeled", 0) + 1
            if ev.kind in {"character_relation_name", "character_or_story_entity"} and ev.label.lower() == "yellow":
                data["entity_yellow_labeled"] = data.get("entity_yellow_labeled", 0) + 1
            if not ev.allow_final_cache:
                data["prediction_final_cache_blocked"] = data.get("prediction_final_cache_blocked", 0) + 1
        if self.ambiguous:
            data["ambiguous_entity_blocked"] = data.get("ambiguous_entity_blocked", 0) + 1
        if self.speaker:
            data["speaker_label_resolved"] = data.get("speaker_label_resolved", 0) + 1
        return data


class PredictionGuard:
    def __init__(self, registry: Dict[str, Any], *, enabled: bool = True):
        self.registry = registry or {}
        self.enabled = enabled
        self.aliases = list(self.registry.get("aliases", []))
        self.characters = set(str(x) for x in self.registry.get("characters_exact", []))
        self.speaker_labels = list(str(x) for x in self.registry.get("speaker_labels_exact", []))
        self.masked_labels = set(str(x) for x in self.registry.get("masked_identity_labels", []))
        self.role_titles = set(str(x) for x in self.registry.get("role_titles", []))
        self.terms = set(str(x) for x in self.registry.get("unique_terms", []))
        self.alternate_commander = set(str(x) for x in self.registry.get("alternate_commander_profile_candidates", []))
        self.main_commander = str((self.registry.get("main_commander") or {}).get("canonical", "Raizei"))
        self.negative_name_starts = tuple(str(x).lower() for x in self.registry.get("negative_name_starts", []))

    @classmethod
    def from_env(cls) -> "PredictionGuard":
        enabled = os.environ.get("ORT_PREDICTION_GUARD", "1") != "0"
        base = Path(__file__).resolve().parents[2]
        default = base / "configs" / "gfl2_entity_registry_v8_9_1.json"
        if not default.exists():
            default = base / "configs" / "gfl2_entity_registry_v8_9_0.json"
        if not default.exists():
            default = base / "configs" / "gfl2_entity_registry_v8_8_9.json"
        if not default.exists():
            default = base / "configs" / "gfl2_entity_registry_v8_8_8.json"
        path = Path(os.environ.get("ORT_GFL2_ENTITY_REGISTRY", str(default)))
        try:
            registry = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            registry = {}
        return cls(registry, enabled=enabled)

    @staticmethod
    def _similar(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _boundary_pattern(src: str) -> re.Pattern:
        return re.compile(r"(?<![A-Za-z0-9])" + re.escape(src) + r"(?![A-Za-z0-9])", re.IGNORECASE)

    def _contains_boundary(self, text: str, src: str) -> bool:
        if not text or not src:
            return False
        return bool(self._boundary_pattern(src).search(text))

    def _is_exact_registered_entity(self, token: str) -> bool:
        """Return True when a token is an exact approved entity/term.

        This prevents the ambiguity guard from blocking exact names such as
        Heli just because nearby OCR fragments like Hel/Hlen are dangerous.
        """
        t = str(token or "").strip().casefold()
        if not t:
            return False
        pools = list(self.characters) + list(self.speaker_labels) + list(self.terms) + [self.main_commander]
        return any(t == str(x or "").strip().casefold() for x in pools)

    def _word_boundary_replace(self, text: str, src: str, dst: str) -> tuple[str, bool]:
        if not src:
            return text, False
        pattern = self._boundary_pattern(src)
        new = pattern.sub(dst, text)
        return new, new != text

    def _is_ambiguous_fragment(self, token: str) -> bool:
        t = (token or "").strip().lower()
        if not t:
            return False
        if self._is_exact_registered_entity(token):
            return False
        for row in self.registry.get("ambiguous_blocklist", []):
            for frag in row.get("fragments", []):
                f = str(frag).lower()
                if t == f or (len(t) <= 6 and self._similar(t, f) >= 0.90):
                    return True
        if len(t) <= 5:
            near = [nm for nm in self.characters if self._similar(t, nm) >= 0.68]
            if len(near) >= 2:
                return True
        return False

    def classify_prefix(self, text: str) -> Dict[str, Any]:
        s = (text or "").strip()
        low = s.lower()
        for neg in self.negative_name_starts:
            if low.startswith(neg):
                return {"type": "negative_ui_or_narration", "candidate": "", "confidence": "red", "reason": "negative_ui_or_narration"}
        if re.match(r"^\s*(\d+/\d+|\d{1,3}\%)\b", s):
            return {"type": "progress_or_counter", "candidate": "", "confidence": "red", "reason": "progress_or_counter"}

        # Speaker labels first: multi-token display labels.
        for label in sorted(self.speaker_labels, key=len, reverse=True):
            variants = {label, label[1:] if label.lower().startswith("m") else label}
            for v in variants:
                if low == v.lower() or low.startswith(v.lower() + " "):
                    kind = "masked_speaker_label" if label in self.masked_labels else "speaker_label"
                    return {"type": kind, "candidate": label, "confidence": "green", "matched": v, "reason": "exact_prefix_entity_label"}

        # Exact known names / Commander. This is where Raizei, Kenny, Heli, Darture,
        # Poludnitsa, etc. become visible labels when they appear as prefix.
        for nm in sorted(self.characters, key=len, reverse=True):
            nlow = nm.lower()
            if low == nlow or low.startswith(nlow + " "):
                confidence = "green"
                kind = "main_commander" if nm == self.main_commander else "character_name"
                if nm == "Anfiya Sharapova":
                    confidence = "yellow"
                    kind = "character_relation_name"
                return {"type": kind, "candidate": nm, "confidence": confidence, "matched": nm, "reason": "exact_prefix_entity_label"}

        # v8.8.9: registered alias prefix repair. This catches OCR names that
        # arrive as speaker/body prefix before split/translate, e.g. bathildel ...
        # It is intentionally limited to registry aliases and never becomes a
        # global autocorrect system.
        for row in sorted(self.aliases, key=lambda r: len(str(r.get("ocr", ""))), reverse=True):
            src = str(row.get("ocr", "")).strip()
            dst = str(row.get("candidate", "")).strip()
            if not src or not dst:
                continue
            if str(row.get("confidence", "yellow")).lower() == "red":
                continue
            kind = str(row.get("type", "term"))
            if kind not in {"speaker_label", "character_name", "main_commander", "character_relation_name", "masked_speaker_label"}:
                continue
            slow = src.lower().rstrip(" :：|.-–—")
            # Prefix must be token-bounded. Allow punctuation from OCR/speaker separator.
            if not (low == slow or low.startswith(slow + " ") or low.startswith(slow + ":") or low.startswith(slow + "：")):
                continue
            if self._is_ambiguous_fragment(src):
                return {"type": "ambiguous_alias_prefix", "candidate": dst, "confidence": "red", "matched": src, "reason": "ambiguous_entity_guard_blocked"}
            confidence = str(row.get("confidence", "yellow")).lower()
            label = "green" if confidence == "green" else "yellow"
            return {"type": kind, "candidate": dst, "confidence": label, "matched": src, "reason": "registered_alias_prefix_guarded"}

        first = " ".join(s.split()[:3])
        if first in self.role_titles:
            return {"type": "role_title", "candidate": first, "confidence": "yellow", "matched": first, "reason": "role_title_prefix"}
        return {"type": "unknown", "candidate": "", "confidence": "red", "reason": "unknown_prefix"}

    def _strip_prefix(self, text: str, matched: str) -> str:
        if not text or not matched:
            return text
        if text.lower().lstrip().startswith(matched.lower()):
            # Preserve original slice length after leading spaces.
            lead = len(text) - len(text.lstrip())
            return text[lead + len(matched):].lstrip(" :：|.-–—")
        return text

    def apply(self, text: str, *, speaker: str = "", raw_text: str = "", speaker_roi_confidence: float = 0.0) -> PredictionResult:
        original = text or ""
        if not self.enabled or not original:
            return PredictionResult(text=original, speaker=speaker or None)

        text = original
        events: List[PredictionEvent] = []
        resolved_speaker: Optional[str] = speaker or None
        speaker_confidence = ""
        speaker_kind = ""

        prefix = self.classify_prefix(raw_text or text)

        if prefix.get("type") == "ambiguous_alias_prefix":
            events.append(PredictionEvent(str(prefix.get("matched") or ""), str(prefix.get("candidate") or ""), "Red", "ambiguous_entity", str(prefix.get("reason") or "ambiguous_entity_guard_blocked"), False))
            return PredictionResult(text=text, speaker=resolved_speaker, speaker_confidence=speaker_confidence, speaker_kind=speaker_kind, events=events, ambiguous=True, final_cache_blocked=True)

        if prefix.get("type") in {"speaker_label", "masked_speaker_label", "character_name", "main_commander", "character_relation_name"}:
            candidate = str(prefix.get("candidate") or "")
            matched = str(prefix.get("matched") or candidate)
            label = str(prefix.get("confidence") or "green").capitalize()
            kind = str(prefix.get("type") or "character_name")
            # Strip from dialog body if the dialog still contains the prefix.
            text = self._strip_prefix(text, matched)
            resolved_speaker = candidate
            speaker_confidence = label
            speaker_kind = kind
            allow_cache = (label == "Green")
            events.append(PredictionEvent(matched, candidate, label, kind, str(prefix.get("reason") or "exact_prefix_entity_label"), allow_cache))

        # Alias replacements: R2 fix. Only inspect ambiguity or log events if
        # the alias actually appears in the text. This prevents Hell->Heli spam
        # on unrelated OCR lines.
        for row in self.aliases:
            src = str(row.get("ocr", "")).strip()
            dst = str(row.get("candidate", "")).strip()
            label = str(row.get("confidence", "yellow")).capitalize()
            kind = str(row.get("type", "term"))
            if not src or not dst:
                continue
            if not self._contains_boundary(text, src):
                continue
            if self._is_ambiguous_fragment(src):
                events.append(PredictionEvent(src, dst, "Red", kind, "ambiguous_entity_guard_blocked", False))
                continue
            new_text, changed = self._word_boundary_replace(text, src, dst)
            if changed:
                text = new_text
                allow_cache = label == "Green"
                events.append(PredictionEvent(src, dst, label, kind, "registry_alias_guarded", allow_cache))

        for alt in self.alternate_commander:
            if self._contains_boundary(text, alt):
                events.append(PredictionEvent(alt, alt, "Yellow", "alternate_commander_profile", "alternate_profile_not_main_commander", False))

        first = (text.split() or [""])[0]
        if first and self._is_ambiguous_fragment(first):
            events.append(PredictionEvent(first, first, "Red", "ambiguous_entity", "ambiguous_entity_guard_blocked", False))
            return PredictionResult(
                text=text,
                speaker=resolved_speaker,
                speaker_confidence=speaker_confidence,
                speaker_kind=speaker_kind,
                events=events,
                ambiguous=True,
                final_cache_blocked=True,
            )

        final_cache_blocked = any(not ev.allow_final_cache for ev in events)
        return PredictionResult(
            text=text,
            speaker=resolved_speaker,
            speaker_confidence=speaker_confidence,
            speaker_kind=speaker_kind,
            events=events,
            ambiguous=False,
            final_cache_blocked=final_cache_blocked,
        )
