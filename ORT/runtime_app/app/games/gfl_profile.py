from __future__ import annotations

"""Girls' Frontline (GFL1) layout and language helpers.

v8.7 gives the first Girls' Frontline a dedicated profile.  GFL1 is not
GFL2_EXILIUM: its compact dialog panel has a fixed bottom-right GFsystem/footer
widget which repeatedly contaminated OCR and speaker learning in user tests.
This module remains dependency-light so it can be used from OCR, cache,
learning and WebUI paths.
"""

import json
import os
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "configs" / "gfl_dialogue_profile.json"
GFL_KEYS = {"GFL", "GIRLS_FRONTLINE", "GIRLS FRONTLINE", "GFL1"}

_FALLBACK_NAMES = [
    "Commander", "Kalina", "Dandelion", "AK-12", "AN-94", "AK-15", "Tokarev", "Groza",
    "M4A1", "M4 SOPMOD II", "ST AR-15", "RO635", "UMP45", "UMP9", "HK416", "G11",
]
_FALLBACK_TERMS = ["Task Force DEFY", "Griffin & Kryuger", "Paradeus", "T-Doll", "Nyto"]
_FALLBACK_ARTIFACTS = ["gFn", "ngf", "nifn", "ni5e", "nfe", "ylf", "Sn", "S5gg", "GFsystem"]
_FALLBACK_CREDITS = ["CHARACTER VO", "ON SCENE", "GAME DESIGN", "MICA-TEAM", "SUNBORN", "TRUE ENDING"]
_FALLBACK_ALIASES = {
    "AK-I2": "AK-12", "AK-I5": "AK-15", "AN-9A": "AN-94", "M4AI": "M4A1",
    "ST AR-I5": "ST AR-15", "AR-I5": "AR-15", "UMP4S": "UMP45", "UMPg": "UMP9",
    "TokareV": "Tokarev", "Kalinais": "Kalina is", "Kalinaand": "Kalina and",
    "Dandelionthis": "Dandelion this", "Dandelionfortunately": "Dandelion fortunately",
}


def _load_profile() -> dict[str, Any]:
    try:
        if CONFIG_PATH.exists():
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


PROFILE = _load_profile()
GFL_NAMES = tuple(PROFILE.get("names") or _FALLBACK_NAMES)
GFL_TERMS = tuple(PROFILE.get("special_terms") or _FALLBACK_TERMS)
FOOTER_ARTIFACTS = tuple(PROFILE.get("footer_artifacts") or _FALLBACK_ARTIFACTS)
CREDIT_MARKERS = tuple(PROFILE.get("credit_markers") or _FALLBACK_CREDITS)
ALIASES: dict[str, str] = dict(_FALLBACK_ALIASES)
ALIASES.update(PROFILE.get("aliases") or {})

_ARTIFACT_RE = re.compile(r"(?:^|\s)(?:" + "|".join(re.escape(x) for x in FOOTER_ARTIFACTS) + r")(?:\s|$|[.,;:!?])", re.I)
_CREDIT_RE = re.compile("|".join(re.escape(x) for x in CREDIT_MARKERS), re.I)
_ODD_FOOTER_RE = re.compile(r"(?:^|\s)[吊另墨](?:\s|$)")
_WORD_JOIN_FIXES = {
    "isit": "is it", "oris": "or is", "thereis": "there is", "youare": "you are",
    "joinany": "join any", "ofscythes": "of scythes", "througha": "through a",
    "pointon": "point on", "bringa": "bring a", "anescape": "an escape",
    "commanderturns": "Commander turns", "factoriesand": "factories and",
}


def active(game: str | None = None) -> bool:
    g = str(game or os.environ.get("ORT_GAME_PROFILE") or os.environ.get("ORT_GAME_OVERRIDE") or "").strip().upper()
    return g in GFL_KEYS


def clean_footer_artifacts(text: str) -> str:
    s = str(text or "")
    if not s:
        return ""
    s = _ARTIFACT_RE.sub(" ", s)
    s = _ODD_FOOTER_RE.sub(" ", s)
    # footer noise sometimes attaches without a space to punctuation or a truncated end.
    for token in FOOTER_ARTIFACTS:
        s = re.sub(rf"(?i)(?<![A-Za-z]){re.escape(token)}(?![A-Za-z])", " ", s)
    return re.sub(r"\s{2,}", " ", s).strip()


def normalize_gfl_text(text: str) -> str:
    s = clean_footer_artifacts(text)
    if not s:
        return ""
    for raw, fixed in ALIASES.items():
        s = re.sub(rf"\b{re.escape(raw)}\b", fixed, s, flags=re.I)
    for raw, fixed in _WORD_JOIN_FIXES.items():
        s = re.sub(rf"\b{re.escape(raw)}\b", fixed, s, flags=re.I)
    s = re.sub(r"\s+([,.;:!?])", r"\1", s)
    s = re.sub(r"\s{2,}", " ", s).strip()
    return s


def normalize_gfl_cache_text(text: str) -> str:
    s = normalize_gfl_text(text)
    s = re.sub(r"\b(?:the|a|an)\s+", lambda m: m.group(0), s, flags=re.I)
    return s


def is_non_dialog_text(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    if _CREDIT_RE.search(s):
        return True
    # UI/footer-only frame: reject but do not treat normal short dialogue (e.g. "Shit!") as noise.
    cleared = clean_footer_artifacts(s)
    return not bool(re.search(r"[A-Za-z]{2,}", cleared))


def _simple_key(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(text or "").lower())


def canonical_speaker(text: str, threshold: float = 0.88) -> str | None:
    raw = normalize_gfl_text(str(text or "")).strip(" .,:;!?'\"-–—")
    if not raw or len(raw) > 34:
        return None
    key = _simple_key(raw)
    exact = {_simple_key(name): name for name in GFL_NAMES}
    if key in exact:
        return exact[key]
    # Fuzzy matching is limited to short candidate boxes, never an entire body sentence.
    best_name = None
    best_ratio = 0.0
    for name in GFL_NAMES:
        ratio = SequenceMatcher(None, key, _simple_key(name)).ratio()
        if ratio > best_ratio:
            best_name, best_ratio = name, ratio
    return best_name if best_name and best_ratio >= threshold else None


def is_seeded_speaker(text: str) -> bool:
    return canonical_speaker(text, threshold=0.94) is not None


def _bbox_center(bbox: Any) -> tuple[float, float]:
    try:
        xs = [float(p[0]) for p in bbox]
        ys = [float(p[1]) for p in bbox]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    except Exception:
        return 0.0, 0.0


def extract_layout_text(detections: Iterable[Any], image_shape: tuple[int, ...] | list[int]) -> tuple[str, dict[str, Any]]:
    """Convert EasyOCR detail detections into a safe GFL line.

    Footer boxes at the bottom-right are suppressed.  A top-left OCR box is
    accepted as a speaker only when it matches the seeded/high-confidence
    roster; otherwise it remains body/narration text and cannot be learned as
    a character name.
    """
    h = float(image_shape[0] if image_shape else 1)
    w = float(image_shape[1] if len(image_shape) > 1 else 1)
    kept: list[tuple[float, float, str, float]] = []
    removed_footer = 0
    for item in detections or []:
        try:
            bbox, txt = item[0], str(item[1] or "")
            conf = float(item[2]) if len(item) > 2 else 1.0
        except Exception:
            continue
        x, y = _bbox_center(bbox)
        nx, ny = x / max(1.0, w), y / max(1.0, h)
        txt = normalize_gfl_text(txt)
        if not txt:
            removed_footer += 1
            continue
        # Static GFsystem/button area: mask only this corner, not the full bottom row.
        if nx >= 0.77 and ny >= 0.63:
            removed_footer += 1
            continue
        if is_non_dialog_text(txt):
            continue
        if conf >= 0.18:
            kept.append((ny, nx, txt, conf))
    kept.sort(key=lambda row: (round(row[0], 2), row[1]))
    if not kept:
        return "", {"layout": "GFL_DIALOG_STANDARD", "footer_removed": removed_footer, "speaker_roi": False}
    speaker = None
    speaker_idx = None
    # Candidate name is expected near the top-left of the dialog crop.
    for i, (ny, nx, txt, _conf) in enumerate(kept[:3]):
        if ny <= 0.38 and nx <= 0.52:
            candidate = canonical_speaker(txt)
            if candidate:
                speaker, speaker_idx = candidate, i
                break
    body_parts = [row[2] for i, row in enumerate(kept) if i != speaker_idx]
    body = normalize_gfl_text(" ".join(body_parts))
    if speaker and body:
        text = f"{speaker}: {body}"
    elif speaker:
        text = speaker
    else:
        text = normalize_gfl_text(" ".join(row[2] for row in kept))
    return text, {"layout": "GFL_DIALOG_STANDARD", "footer_removed": removed_footer, "speaker_roi": bool(speaker), "speaker": speaker or ""}
