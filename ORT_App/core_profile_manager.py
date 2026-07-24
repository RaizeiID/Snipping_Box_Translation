"""ORT Translation v8.0 core profile manager.

This layer prevents every legacy/experimental Core from running for every model.
Each model strategy gets a small, explicit set of active engineers so Fast/Lite
stay light while V3/V5 can use deeper QA and naturalization.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, Any

from status_manager import write_status as _write_status

ROOT = Path(__file__).resolve().parent
STATUS_PATH = ROOT / "status" / "core_profile.json"

BASE_ACTIVE = {
    "ResourceSentinel",
    "AdaptiveThrottle",
    "Sanitizer",
    "EdgeCaseDetector",
    "DuplicateSubtitleSuppressor",
    "SmartCacheRouter",
    "MemoryVault",
    "Failover",
    "ValidationGate",
    "BlackBox",
    "Overseer",
    "FallbackStrategy",
}

PROFILE_ACTIVE = {
    "fast": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
    },

    "lite_efficient": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "Sanitizer",
        "DuplicateSubtitleSuppressor",
    },
    "lite_idn_efficient": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "Sanitizer",
        "DuplicateSubtitleSuppressor",
        "TerminologyConstraint",
    },
    "light": BASE_ACTIVE | {
        "TextStitcher",
        "SpellWeaver",
        "ContextBuffer",
        "TimelineTracker",
        "EntityDiscovery",
    },
    "balanced": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "TextStitcher",
        "SpellWeaver",
        "VisionAnalyst",
        "ContextBuffer",
        "TimelineTracker",
        "Narrative",
        "Sociologist",
        "EntityDiscovery",
        "LearningEngine",
        "FeedbackCollector",
        "LoreKeeper",
        "ProfessorSyntax",
        "ProfessorTone",
        "TerminologyConstraint",
        "QualityEstimation",
        "LQAReport",
    },
    "safe_game": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "TextStitcher",
        "SpellWeaver",
        "VisionAnalyst",
        "ContextBuffer",
        "TimelineTracker",
        "EntityDiscovery",
        "LearningEngine",
        "LQAReport",
    },
    "potato": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "TextStitcher",
        "VisionAnalyst",
    },
    "quality": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "PipelineOptimizer",
        "TextStitcher",
        "Sanitizer",
        "SpellWeaver",
        "VisionAnalyst",
        "ContextBuffer",
        "TimelineTracker",
        "Narrative",
        "Sociologist",
        "CharacterArc",
        "EntityDiscovery",
        "LearningEngine",
        "FeedbackCollector",
        "DynamicBatching",
        "LoreKeeper",
        "ProfessorSyntax",
        "ProfessorTone",
        "ProfessorLogic",
        "StyleGuide",
        "TerminologyConstraint",
        "BilingualConsistency",
        "QualityEstimation",
        "ValidationGate",
        "LQAReport",
    },
    "hybrid": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "PipelineOptimizer",
        "TextStitcher",
        "SpellWeaver",
        "VisionAnalyst",
        "ContextBuffer",
        "TimelineTracker",
        "Narrative",
        "Sociologist",
        "EntityDiscovery",
        "LearningEngine",
        "FeedbackCollector",
        "DynamicBatching",
        "LoreKeeper",
        "ProfessorSyntax",
        "ProfessorTone",
        "TerminologyConstraint",
        "QualityEstimation",
        "PromptDirector",
        "LQAReport",
    },
    "natural": BASE_ACTIVE | {
        "LatencyBudgetManager",
        "PriorityScheduler",
        "PipelineOptimizer",
        "TextStitcher",
        "SpellWeaver",
        "VisionAnalyst",
        "ContextBuffer",
        "TimelineTracker",
        "Narrative",
        "Sociologist",
        "CharacterArc",
        "EntityDiscovery",
        "LearningEngine",
        "FeedbackCollector",
        "DynamicBatching",
        "LoreKeeper",
        "ProfessorSyntax",
        "ProfessorTone",
        "ProfessorLogic",
        "StyleGuide",
        "TerminologyConstraint",
        "BilingualConsistency",
        "QualityEstimation",
        "ValidationGate",
        "LQAReport",
    },
}

# Still parked even if a profile requests them, unless explicitly enabled.
HARD_PARKED = {
    "CaptureSpecialist": "Alternative Tesseract capture can conflict with EasyOCR/mss and external install.",
    "Helsinki": "Alternative translation loader can duplicate Argos memory; translation_engine owns engine routing.",
    "AsyncOrchestrator": "Extra worker pool can conflict with QThread runtime.",
    "Formatter": "Main translation box renderer is locked.",
    "UIConstraint": "Main translation box layout is locked.",
    "MultiCandidateGenerator": "Needs a separate engine contract; too expensive for live loop.",
    "BackTranslationVerifier": "Adds extra translation calls; keep for offline QA/benchmark.",
    "ConsistencyAuditor": "Offline audit tool, not live runtime.",
    "RegressionTest": "Manual diagnostics only.",
    "ConfigMaster": "Future config consolidation only.",
    "Synapse": "Future event bus only.",
    "Semantics": "Needs packet contract; future extension.",
    "Dean": "Council aggregator is too heavy for live OCR.",
}

@dataclass
class CoreDecision:
    core: str
    active: bool
    reason: str


def _normalize_profile(profile: str) -> str:
    p = (profile or "balanced").strip().lower()
    if p in {"lite", "lite_efficient"}:
        return "lite_efficient"
    if p in {"lite_idn", "lite_idn_efficient"}:
        return "lite_idn_efficient"
    if p in {"safe"}:
        return "safe_game"
    if p in {"deep", "v5"}:
        return "natural"
    return p if p in PROFILE_ACTIVE else "balanced"


def active_core_set(strategy: Any = None, env: Dict[str, str] | None = None) -> Tuple[str, set[str]]:
    env = env or os.environ
    profile = getattr(strategy, "core_profile", None) or env.get("ORT_CORE_PROFILE", "balanced")
    profile = _normalize_profile(profile)
    active = set(PROFILE_ACTIVE.get(profile, PROFILE_ACTIVE["balanced"]))
    group = (getattr(strategy, "group", None) or env.get("ORT_MODEL_GROUP", "normal")).lower()
    key = (getattr(strategy, "model_key", None) or env.get("ORT_MODEL_KEY", "")).lower()
    if group == "fast" or key.startswith("fast"):
        profile = "fast"
        active = set(PROFILE_ACTIVE["fast"])
    if "lite" in group and profile not in {"fast", "potato"}:
        profile = "lite_idn_efficient" if "idn" in group or "idn" in key else "lite_efficient"
        active = set(PROFILE_ACTIVE[profile])
    if env.get("TITAN_HEAVY_GAME_SAFE", "0") == "1" and profile not in {"fast", "potato", "lite_efficient", "lite_idn_efficient"}:
        profile = "safe_game"
        active = set(PROFILE_ACTIVE["safe_game"])
    if env.get("ORT_FORCE_ALL_CORES", "0") == "1":
        # Debug only. Hard-parked still stays parked.
        active = set().union(*PROFILE_ACTIVE.values())
    return profile, active


def decide_core(core_name: str, slot_active: bool = True, slot_reason: str = "", strategy: Any = None) -> CoreDecision:
    if core_name in HARD_PARKED:
        return CoreDecision(core_name, False, HARD_PARKED[core_name])
    if not slot_active:
        return CoreDecision(core_name, False, slot_reason or "parked by slot definition")
    profile, active = active_core_set(strategy)
    if core_name in active:
        return CoreDecision(core_name, True, f"active for profile={profile}")
    return CoreDecision(core_name, False, f"not needed for profile={profile}; parked to save latency/resource")


def write_profile_status(base_dir: str | os.PathLike[str] | None = None, strategy: Any = None, decisions: Dict[str, Dict[str, Any]] | None = None) -> None:
    base = Path(base_dir or ROOT).resolve()
    profile, active = active_core_set(strategy)
    data = {
        "version": "v8.4.3",
        "profile": profile,
        "active_core_names": sorted(active),
        "active_count_target": len(active),
        "hard_parked": HARD_PARKED,
        "decisions": decisions or {},
    }
    try:
        _write_status("core_profile", data, base)
    except Exception:
        pass
