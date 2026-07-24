"""GFL2 trusted/verified-exact Name ROI and temporal selection for v8.7.6.

The name pass is intentionally independent from body OCR.  It accepts only the
trusted identity registry, keeps Helen and Helena distinct, and returns speaker
metadata instead of injecting a guessed label into the body string.
"""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import time
from typing import Iterable

import cv2

from app.identity.speaker_registry import (
    is_distinct_conflict,
    strip_matching_speaker_prefix,
    trusted_alias_map,
    trusted_speaker_names,
    verified_character_speaker_names,
    speaker_exact_names,
)

SEED_NAMES = {
    "DP-12", "KSVK", "Helen", "Helena", "Melanie", "Balthilde", "Phaetusa",
    "Alya Kujou", "Lentine", "Dushevnaya", "Descender Zero", "Dandelion", "Suomi",
}


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def _compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9-]", "", str(text or "").upper())


def _canonical(candidate: str, exact_names: Iterable[str], alias_map: dict[str, str] | None = None, fuzzy_names: Iterable[str] | None = None) -> tuple[str, str]:
    """Return a speaker only from safe matching tiers.

    Official catalog entries are exact-only; reviewed/active names may use the
    conservative fuzzy fallback. This prevents valid roster recovery from
    reviving the old narrative-word false speaker problem.
    """
    raw = _clean(candidate)
    compact = _compact(raw)
    if not compact:
        return "", "empty"
    exact = sorted({str(n).strip() for n in exact_names or [] if str(n).strip()}, key=len, reverse=True)
    fuzzy = sorted({str(n).strip() for n in (fuzzy_names or []) if str(n).strip()}, key=len, reverse=True)
    aliases = {str(k).casefold(): v for k, v in (alias_map or {}).items()}
    for name in exact:
        if compact == _compact(name):
            return name, "verified_or_active_exact"
    if raw.casefold() in aliases:
        return aliases[raw.casefold()], "reviewed_alias"
    # Safe OCR joins after a fully recognized exact name, e.g. "ZhaohuiAlright".
    for name in exact:
        target = _compact(name)
        if compact.startswith(target) and compact[len(target):] in {"IS", "S", "AND", "WAS", "HAS", "ALRIGHT"}:
            return name, "exact_canonical_join"
    scored: list[tuple[float, str]] = []
    for name in fuzzy:
        target = _compact(name)
        if len(target) < 4:
            continue
        score = SequenceMatcher(None, compact, target).ratio()
        if score >= 0.94:
            scored.append((score, name))
    for _, name in sorted(scored, reverse=True):
        for exact_name in exact:
            if compact == _compact(exact_name) and is_distinct_conflict(exact_name, name):
                return exact_name, "fuzzy_blocked_distinct_canonical"
        return name, "reviewed_fuzzy_only"
    return "", "unmatched"


@dataclass
class SpeakerROIResult:
    text: str
    speaker: str = ""
    detected: bool = False
    temporal_hold: bool = False
    thin_glyph_recovered: bool = False
    confidence: float = 0.0
    raw_roi: str = ""
    decision_reason: str = ""
    body_prefix_stripped: bool = False
    roi_ms: float = 0.0
    thin_glyph_ms: float = 0.0


class GFL2SpeakerTracker:
    def __init__(self, known_names: Iterable[str] = (), hold_ms: int = 1800, alias_map: dict[str, str] | None = None, verified_exact_names: Iterable[str] | None = None) -> None:
        registry_names = set(known_names or []) or set(trusted_speaker_names("GFL2_EXILIUM"))
        self.fuzzy_names = registry_names | SEED_NAMES
        self.verified_exact_names = set(verified_exact_names or verified_character_speaker_names("GFL2_EXILIUM"))
        self.known_names = self.fuzzy_names | self.verified_exact_names
        self.alias_map = alias_map or trusted_alias_map("GFL2_EXILIUM")
        self.hold_ms = hold_ms
        self.active_speaker = ""
        self.last_dialog_body = ""
        self.last_detected = 0.0

    def _roi_detect(self, reader, img_gray) -> tuple[str, float, str, str]:
        try:
            h, w = img_gray.shape[:2]
            # Narrower name-only ROI than v8.7.2 to reduce body-text capture.
            roi = img_gray[0:max(20, int(h * 0.31)), 0:max(95, int(w * 0.25))]
            roi = cv2.resize(roi, None, fx=2.3, fy=2.3, interpolation=cv2.INTER_CUBIC)
            roi = cv2.createCLAHE(clipLimit=2.4, tileGridSize=(8, 8)).apply(roi)
            allow = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789- "
            try:
                detections = reader.readtext(roi, detail=1, paragraph=False, allowlist=allow)
            except TypeError:
                detections = reader.readtext(roi, detail=1, paragraph=False)
            best_name, best_conf, best_raw, best_reason = "", 0.0, "", "unmatched"
            for det in detections or []:
                txt = str(det[1] if len(det) > 1 else "")
                conf = float(det[2] if len(det) > 2 else 0.0)
                name, reason = _canonical(txt, self.known_names, self.alias_map, self.fuzzy_names)
                if name and conf >= best_conf and conf >= 0.18:
                    best_name, best_conf, best_raw, best_reason = name, conf, txt, reason
            if not best_name:
                for det in detections or []:
                    txt = str(det[1] if len(det) > 1 else "").strip()
                    conf = float(det[2] if len(det) > 2 else 0.0)
                    if conf >= 0.35 and txt and any(ch.isalpha() for ch in txt):
                        try:
                            from translation_event_logger import append_event
                            append_event("GFL2_NAME_ROI_REJECTED", {"raw_name_roi": txt, "confidence": conf, "reason": "not_in_exact_or_reviewed_matcher"}, source_module="gfl2_speaker_roi")
                        except Exception:
                            pass
                        break
            return best_name, best_conf, best_raw, best_reason
        except Exception:
            return "", 0.0, "", "roi_error"

    @staticmethod
    def _progressive_related(old_body: str, new_body: str) -> bool:
        old = _clean(old_body).casefold()
        new = _clean(new_body).casefold()
        if not old or not new:
            return False
        shorter, longer = sorted((old, new), key=len)
        return len(shorter) >= 4 and longer.startswith(shorter)

    def _body_prefix_candidate(self, text: str) -> tuple[str, str]:
        # Longest-match-first; a compound entity must not be split per token.
        norm = _clean(text)
        for name in sorted(self.known_names, key=len, reverse=True):
            if re.match(rf"^{re.escape(name)}(?:\s+|$|[.:;,-])", norm, re.I):
                return name, "body_exact_prefix"
        return "", ""

    def _recover_initial_i(self, reader, img_gray, text: str) -> tuple[str, bool]:
        # Scoped recovery only: global character-by-character OCR is intentionally avoided.
        match = re.match(r"^(am\b|refuse\b|m\s+|have\s+to\b)", str(text or ""), flags=re.I)
        if not match:
            return text, False
        try:
            h, w = img_gray.shape[:2]
            body = img_gray[int(h * 0.22):max(int(h * 0.85), int(h * 0.22) + 12), 0:max(90, int(w * 0.30))]
            body = cv2.resize(body, None, fx=2.5, fy=2.5, interpolation=cv2.INTER_CUBIC)
            body = cv2.createCLAHE(clipLimit=2.6, tileGridSize=(8, 8)).apply(body)
            probe = " ".join(reader.readtext(body, detail=0, paragraph=False) or [])
            if re.search(r"\bI\s+(?:am|refuse|have)\b|\bI'm\b", probe, flags=re.I):
                if re.match(r"^am\b", text, re.I):
                    return re.sub(r"^am\b", "I am", text, count=1, flags=re.I), True
                if re.match(r"^refuse\b", text, re.I):
                    return re.sub(r"^refuse\b", "I refuse", text, count=1, flags=re.I), True
        except Exception:
            pass
        return text, False

    def process(self, reader, img_gray, body_text: str) -> SpeakerROIResult:
        text = _clean(body_text)
        now = time.time()
        roi_t0 = time.perf_counter()
        detected_name, conf, raw_roi, reason = self._roi_detect(reader, img_gray)
        roi_ms = (time.perf_counter() - roi_t0) * 1000.0
        prefix_name, prefix_reason = self._body_prefix_candidate(text)
        speaker = detected_name or prefix_name
        decision = reason if detected_name else prefix_reason
        temporal = False
        if speaker:
            self.active_speaker = speaker
            self.last_detected = now
        elif self.active_speaker and (now - self.last_detected) * 1000.0 <= self.hold_ms:
            if self._progressive_related(self.last_dialog_body, text):
                speaker = self.active_speaker
                temporal = True
                decision = "temporal_hold"
        body = text
        stripped = False
        if speaker:
            body, stripped = strip_matching_speaker_prefix(text, speaker, "GFL2_EXILIUM")
            self.last_dialog_body = body
        thin_t0 = time.perf_counter()
        body, recovered = self._recover_initial_i(reader, img_gray, body)
        thin_ms = (time.perf_counter() - thin_t0) * 1000.0
        return SpeakerROIResult(text=body, speaker=speaker, detected=bool(detected_name or prefix_name), temporal_hold=temporal, thin_glyph_recovered=recovered, confidence=conf, raw_roi=raw_roi, decision_reason=decision, body_prefix_stripped=stripped, roi_ms=roi_ms, thin_glyph_ms=thin_ms)
