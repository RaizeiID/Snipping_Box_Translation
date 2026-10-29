"""ORT v9.0.7 R19 -- read the user's GOAL from the combination they picked.

Every knob so far is read in isolation: the core family sets pipeline character,
the resource ladder scales the numbers, the device axis sets machine headroom.
Nothing asks the obvious question -- *what is this person actually after?*

That question has a real consequence. The strict-CT2 story guard holds any
unfinished fragment rather than let a rough translation through; in one field
session it held 97 frames, 80 of them mid-sentence. For somebody on Fast +
Efisien Maks that hold is wrong: they chose the speed core, they want words on
screen now and accept rough edges. For somebody on V3 + Intensive it is exactly
right. The same guard, opposite verdicts -- because the goal differs, not the
hardware.

Three axes, read together
-------------------------
*Family + level* -- what pipeline the user asked for. Fast/V1 lean speed,
V3/V5/IDN lean accuracy (see model_strategy._base_by_level).

*Resource mode + level* -- placed on the existing 1..15 continuum from
resource_levels.continuum_index: Efisien Maks = 1 (lightest/fastest),
Intensive Maks = 15 (heaviest/most accurate). Low W pulls speed, high W pulls
accuracy.

*Device resource* -- deliberately NOT a goal axis. "Kualitas Optimal" does not
mean the user wants accuracy; it means they are confident the machine has
headroom. It says how hard the system may push toward whichever goal the other
two axes set. That is why Fast + Intensive + Optimal reads as "good quality but
keep it fast" rather than as plain accuracy-first.

The five goals below are the ones the user described, in their words.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.runtime.resource_levels import (
    continuum_index,
    normalize_device_resource,
    normalize_resource_level,
    normalize_resource_mode,
)

# Goal ids, ordered speed -> accuracy.
SPEED_ONLY = "speed_only"
SPEED_ACCURATE = "speed_accurate"
BALANCED = "balanced"
ACCURACY_FIRST = "accuracy_first"
ACCURACY_LIGHT = "accuracy_light"

GOAL_LABELS = {
    SPEED_ONLY: "Kecepatan penuh",
    SPEED_ACCURATE: "Cepat tapi tetap akurat",
    BALANCED: "Seimbang",
    ACCURACY_FIRST: "Akurasi diutamakan",
    ACCURACY_LIGHT: "Akurasi maksimal, tetap ringan",
}

# How each family pulls. (speed_pull, accuracy_pull)
_FAMILY_PULL = {
    "fast": (3.0, -2.0),
    "lite": (1.0, -1.0),
    "lite_idn": (1.0, 0.0),
    "normal": (0.0, 1.0),
    "idn": (-1.0, 2.0),
}

# V1..V5, following _base_by_level: V1 light, V2 balanced, V3 accuracy,
# V4 hybrid (offline-first + online assist), V5 deep IDN.
_LEVEL_PULL = {
    1: (2.0, -1.0),
    2: (1.0, 0.0),
    3: (-1.0, 2.0),
    4: (0.0, 1.0),
    5: (-1.0, 2.0),
}


@dataclass(frozen=True)
class UserIntent:
    goal: str
    label: str
    speed_score: float
    accuracy_score: float
    headroom: int
    weight: int
    # --- what the runtime should DO about it ---
    release_fragments: bool      # let strict CT2 show unfinished text as preview
    fragment_min_words: int      # ...but only once it has this many words
    prefer_final_accuracy: bool  # final must still come from the accurate path
    summary: str

    def as_dict(self) -> dict:
        return {
            "intent_goal": self.goal,
            "intent_label": self.label,
            "intent_speed_score": round(self.speed_score, 2),
            "intent_accuracy_score": round(self.accuracy_score, 2),
            "intent_headroom": self.headroom,
            "intent_weight": self.weight,
            "intent_release_fragments": self.release_fragments,
            "intent_fragment_min_words": self.fragment_min_words,
            "intent_prefer_final_accuracy": self.prefer_final_accuracy,
        }


def _family_of(group: str, model_key: str) -> str:
    token = f"{group} {model_key}".lower()
    if "fast" in token:
        return "fast"
    if "lite" in token and "idn" in token:
        return "lite_idn"
    if "lite" in token:
        return "lite"
    if "idn" in token:
        return "idn"
    return "normal"


def resolve_intent(
    *,
    group: str = "normal",
    model_key: str = "v2",
    level: int = 2,
    resource_mode: str = "stable",
    resource_level=3,
    device_resource: str = "adaptive",
) -> UserIntent:
    family = _family_of(group, model_key)
    mode = normalize_resource_mode(resource_mode)
    r_level = normalize_resource_level(resource_level)
    device = normalize_device_resource(device_resource)
    weight = continuum_index(mode, r_level)          # 1..15
    level = max(1, min(5, int(level or 2)))

    fam_speed, fam_acc = _FAMILY_PULL[family]
    lvl_speed, lvl_acc = _LEVEL_PULL[level]

    # Two contributions, kept separate so the reasoning stays inspectable:
    #   core_tilt   -- what the chosen pipeline is FOR
    #   ladder_tilt -- how far along the 1..15 continuum the user pushed it
    # Positive = speed, negative = accuracy. The ladder pivots on W8, the
    # midpoint between Stabil Maks and Stabil Terendah.
    core_tilt = (fam_speed + lvl_speed) - (fam_acc + lvl_acc)
    ladder_tilt = (8.0 - weight) * 0.55
    tilt = core_tilt + ladder_tilt

    speed = max(0.0, tilt)
    accuracy = max(0.0, -tilt)
    headroom = {"saver": -1, "adaptive": 0, "quality": 1}[device]

    # Anchored on the combinations the user described by name:
    #   Fast V1 + Efisien Maks            -> +11.9  speed only
    #   Fast/V1 + Intensive + Optimal     -> +4.2   fast, still accurate
    #   V2 + Stabil + Adaptif             ->  0.0   truly balanced
    #   V3/IDN V5 + Intensive Maks        -> -7.9   accuracy first
    if tilt >= 6.5:
        goal = SPEED_ONLY
    elif tilt >= 2.0:
        goal = SPEED_ACCURATE
    elif tilt > -2.0:
        goal = BALANCED
    else:
        goal = ACCURACY_FIRST

    # The corner the user called out separately: accuracy is still the goal, but
    # it is being pursued on a light runtime rather than a heavy one.
    if goal == ACCURACY_FIRST and weight <= 5:
        goal = ACCURACY_LIGHT
    # Hemat says the machine is the constraint. Chasing accuracy on a device the
    # user has explicitly asked to spare only produces stutter, so step back one
    # notch toward keeping the story moving.
    if headroom < 0 and goal == ACCURACY_FIRST:
        goal = ACCURACY_LIGHT

    release, min_words = {
        SPEED_ONLY: (True, 1),
        SPEED_ACCURATE: (True, 3),
        BALANCED: (True, 5),
        ACCURACY_FIRST: (False, 0),
        ACCURACY_LIGHT: (False, 0),
    }[goal]
    prefer_final = goal not in (SPEED_ONLY,)

    return UserIntent(
        goal=goal,
        label=GOAL_LABELS[goal],
        speed_score=speed,
        accuracy_score=accuracy,
        headroom=headroom,
        weight=weight,
        release_fragments=release,
        fragment_min_words=min_words,
        prefer_final_accuracy=prefer_final,
        summary=explain(family, level, mode, r_level, device, goal, weight),
    )


# ORT v9.0.7 R28 ----------------------------------------------------------
# Audio had no combination reading at all. The launcher applies the SAME
# resource ladder on the audio path (resolve_resource_plan is called there too),
# but resolve_intent was only ever called for OCR -- so switching the source to
# Audio left the knobs working and the explanation blank.
#
# Audio has no V1..V5 core, but it does have the equivalent: the ASR profile
# (speed vs accurate) and the engine (local rolling-partial vs cloud streaming).
# Those tilt the same way a core does, so they feed the same machinery rather
# than a parallel scale that could drift away from it.
_AUDIO_PROFILE_PULL = {
    # (speed pull, accuracy pull). Three choices, matching the UI radio:
    # Instant / Balanced / Accurate.
    "speed": (3.4, 0.4),
    "normal": (1.6, 1.6),
    "accurate": (0.4, 3.4),
}
_AUDIO_ENGINE_PULL = {
    # Local rolling-partial shows words while the character is still speaking;
    # cloud streaming holds a little longer but returns a better final.
    "local": (1.2, 0.4),
    "azure": (0.4, 1.4),
    "azure_fallback": (0.8, 0.9),
}
_AUDIO_PROFILE_WORD = {"speed": "Instant", "normal": "Balanced", "accurate": "Accurate"}
_AUDIO_ENGINE_WORD = {
    "local": "Local Live", "azure": "Azure Cloud", "azure_fallback": "Azure + Local",
}


def resolve_audio_intent(
    *,
    profile: str = "speed",
    engine: str = "azure_fallback",
    resource_mode: str = "stable",
    resource_level=3,
    device_resource: str = "adaptive",
) -> UserIntent:
    prof = str(profile or "speed").strip().lower()
    if prof not in _AUDIO_PROFILE_PULL:
        prof = "speed"
    eng = str(engine or "azure_fallback").strip().lower()
    if eng not in _AUDIO_ENGINE_PULL:
        eng = "azure_fallback"

    mode = normalize_resource_mode(resource_mode)
    r_level = normalize_resource_level(resource_level)
    device = normalize_device_resource(device_resource)
    weight = continuum_index(mode, r_level)

    p_speed, p_acc = _AUDIO_PROFILE_PULL[prof]
    e_speed, e_acc = _AUDIO_ENGINE_PULL[eng]
    core_tilt = (p_speed + e_speed) - (p_acc + e_acc)
    ladder_tilt = (8.0 - weight) * 0.55
    tilt = core_tilt + ladder_tilt
    headroom = {"saver": -1, "adaptive": 0, "quality": 1}[device]

    if tilt >= 6.5:
        goal = SPEED_ONLY
    elif tilt >= 2.0:
        goal = SPEED_ACCURATE
    elif tilt > -2.0:
        goal = BALANCED
    else:
        goal = ACCURACY_FIRST
    if goal == ACCURACY_FIRST and weight <= 5:
        goal = ACCURACY_LIGHT
    if headroom < 0 and goal == ACCURACY_FIRST:
        goal = ACCURACY_LIGHT

    release, min_words = {
        SPEED_ONLY: (True, 1),
        SPEED_ACCURATE: (True, 3),
        BALANCED: (True, 5),
        ACCURACY_FIRST: (False, 0),
        ACCURACY_LIGHT: (False, 0),
    }[goal]

    summary = (
        f"Anda memakai audio {_AUDIO_ENGINE_WORD[eng]} dengan profil "
        f"{_AUDIO_PROFILE_WORD[prof]}, mode resource {_MODE_WORD[mode]} "
        f"{_LEVEL_WORD[r_level]} (tangga {weight}/15) dan resource perangkat "
        f"{_DEVICE_WORD[device]}. Kesimpulan: {GOAL_LABELS[goal]} — "
        f"{_GOAL_MEANING[goal]}"
    )

    return UserIntent(
        goal=goal,
        label=GOAL_LABELS[goal],
        speed_score=max(0.0, tilt),
        accuracy_score=max(0.0, -tilt),
        headroom=headroom,
        weight=weight,
        release_fragments=release,
        fragment_min_words=min_words,
        prefer_final_accuracy=goal not in (SPEED_ONLY,),
        summary=summary,
    )


_MODE_WORD = {"efficient": "Efisien", "stable": "Stabil", "intensive": "Intensive"}
_LEVEL_WORD = {1: "Terendah", 2: "Rendah", 3: "Menengah", 4: "Tinggi", 5: "Maks"}
_DEVICE_WORD = {"saver": "Hemat", "adaptive": "Adaptif", "quality": "Kualitas Optimal"}
_FAMILY_WORD = {
    "fast": "Fast", "lite": "Lite", "lite_idn": "Lite IDN",
    "idn": "IDN", "normal": "Normal",
}

_GOAL_MEANING = {
    SPEED_ONLY: (
        "teks muncul secepat mungkin dan potongan kalimat yang belum matang tetap "
        "ditampilkan. Akurasi sengaja dikorbankan."
    ),
    SPEED_ACCURATE: (
        "utamanya cepat, tetapi potongan terlalu pendek ditahan dulu dan hasil final "
        "tetap diambil dari jalur yang akurat."
    ),
    BALANCED: (
        "mengalir mengikuti dialog tanpa tersendat, sambil menunggu potongan cukup "
        "matang sebelum ditampilkan."
    ),
    ACCURACY_FIRST: (
        "hanya kalimat yang sudah matang yang ditampilkan. Potongan setengah jadi "
        "ditahan supaya tidak ada terjemahan yang salah arah."
    ),
    ACCURACY_LIGHT: (
        "akurasi dijaga penuh, tetapi runtime-nya tetap ringan — potongan mentah "
        "ditahan tanpa membebani perangkat."
    ),
}


def explain(family: str, level: int, mode: str, r_level: int, device: str, goal: str, weight: int) -> str:
    """One paragraph the player can actually read, in their own terms."""
    core = f"{_FAMILY_WORD[family]} V{level}"
    ladder = f"{_MODE_WORD[mode]} {_LEVEL_WORD[r_level]}"
    machine = _DEVICE_WORD[device]
    return (
        f"Anda memakai core <b>{core}</b> dengan mode resource <b>{ladder}</b> "
        f"(tangga {weight}/15) dan resource perangkat <b>{machine}</b>. "
        f"Kesimpulan: <b>{GOAL_LABELS[goal]}</b> — {_GOAL_MEANING[goal]}"
    )


def intent_from_env(environ=None) -> Optional[UserIntent]:
    """Rebuild the intent inside the runtime process from the launcher's env."""
    import os

    env = environ if environ is not None else os.environ
    try:
        return resolve_intent(
            group=env.get("ORT_MODEL_GROUP", "normal"),
            model_key=env.get("ORT_MODEL_KEY", "v2"),
            level=int(env.get("ORT_MODEL_LEVEL", "2") or 2),
            resource_mode=env.get("ORT_RESOURCE_MODE", "stable"),
            resource_level=env.get("ORT_RESOURCE_LEVEL", "3"),
            device_resource=env.get("ORT_DEVICE_RESOURCE", "adaptive"),
        )
    except Exception:
        return None
