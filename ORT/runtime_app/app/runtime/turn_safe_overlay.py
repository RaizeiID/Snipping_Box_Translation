"""ORT Translation v8.7.9 Turn-Safe Overlay and Scene Exit Guard.

Deterministic UI-state protection for GFL2 story mode.  It prevents an older
translation from remaining visible after a genuine dialog turn change and
rejects obvious reward/map/menu text after a story scene exits.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import re

_SCENE_EXIT = re.compile(
    r"\b(?:collect\s+more\s+to\s+claim\s+rewards?|claim\s+rewards?|mission\s+reward|"
    r"reward\s+preview|battle\s+pass|event\s+reward|stage\s+clear|combat\s+report|"
    r"items?\s+obtained|back\s+to\s+map|normal\s+hard)\b", re.I)
_MENU_BITS = re.compile(r"\b(?:normal|hard|reward|claim|collect|mission|stage|map)\b", re.I)
_DIALOG_LIKE = re.compile(r"[.!?…]|\b(?:I|you|we|they|she|he|Commander)\b", re.I)

@dataclass(frozen=True)
class TurnDecision:
    turn_id: str = ""
    is_new_turn: bool = False
    clear_overlay: bool = False
    scene_exit: bool = False
    reason: str = "same_turn"

def is_scene_exit_text(text: str, speaker: str = "") -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    if _SCENE_EXIT.search(raw):
        return True
    return not str(speaker or "").strip() and bool(_MENU_BITS.search(raw)) and not bool(_DIALOG_LIKE.search(raw)) and len(raw.split()) <= 10

class TurnSafeOverlayController:
    def __init__(self) -> None:
        self._last_speaker = ""
        self._last_body = ""
        self._last_turn_id = ""

    @staticmethod
    def _key(speaker: str, body: str) -> str:
        seed = f"{speaker.strip().casefold()}\n{body.strip().casefold()[:120]}"
        return hashlib.sha1(seed.encode("utf-8", "ignore")).hexdigest()[:12]

    def evaluate(self, speaker: str, body: str, raw_text: str = "") -> TurnDecision:
        speaker = str(speaker or "").strip()
        body = str(body or "").strip()
        raw = str(raw_text or body).strip()
        if is_scene_exit_text(raw, speaker=speaker):
            self._last_speaker = self._last_body = self._last_turn_id = ""
            return TurnDecision(clear_overlay=True, scene_exit=True, reason="scene_exit_ui_non_dialog")
        if not body:
            return TurnDecision(self._last_turn_id, reason="empty_body")
        # Typewriter/progressive OCR expansion is the same turn and must not blink.
        # Ignore a transient terminal mark because OCR may briefly detect a full stop
        # before the following word becomes visible on the next frame.
        current_cmp = re.sub(r"[.!?…]+$", "", body.casefold()).strip()
        previous_cmp = re.sub(r"[.!?…]+$", "", self._last_body.casefold()).strip()
        same_progressive = bool(previous_cmp) and speaker.casefold() == self._last_speaker.casefold() and (
            current_cmp.startswith(previous_cmp) or previous_cmp.startswith(current_cmp)
        )
        if same_progressive:
            self._last_body = body if len(body) >= len(self._last_body) else self._last_body
            return TurnDecision(self._last_turn_id, reason="progressive_same_turn")
        new_turn = bool(self._last_body)
        turn_id = self._key(speaker, body)
        self._last_speaker, self._last_body, self._last_turn_id = speaker, body, turn_id
        return TurnDecision(turn_id, is_new_turn=new_turn, clear_overlay=new_turn, reason="new_dialog_turn" if new_turn else "initial_dialog_turn")
