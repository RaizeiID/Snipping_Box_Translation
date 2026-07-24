"""ORT v8.8.8-r2 Commander Profile Resolver."""
from __future__ import annotations

MAIN_COMMANDER = "Raizei"
ALTERNATE_PROFILE_CLUSTER = {"ARVITA ID", "ArVITA ID", "ATVITA ID", "AFVITA ID", "ArVITAID", "ATVITA IO"}


def resolve_commander_token(token: str) -> dict:
    t = (token or "").strip()
    if t.lower() == MAIN_COMMANDER.lower():
        return {"kind": "main_commander", "canonical": MAIN_COMMANDER, "confidence": "green"}
    if t in ALTERNATE_PROFILE_CLUSTER:
        return {"kind": "alternate_profile_candidate", "canonical": t, "confidence": "yellow"}
    if t.lower() == "commander":
        return {"kind": "role_title", "canonical": "Commander", "confidence": "green"}
    return {"kind": "unknown", "canonical": t, "confidence": "red"}
