"""ORT Translation v7.9 Runtime Bridge.

Safe orchestrator for the old '*Core.py' modules.
It intentionally does not replace TITANMAIN's UI box or main OCR engine.
Instead it turns useful legacy/experimental cores into supervised workers:
- text cleanup before translation,
- duplicate/noise suppression,
- adaptive throttling for heavy games,
- cache eligibility / memory vault hooks,
- post-translation QA / terminology / naturalization polish,
- lightweight telemetry and status manifest.

All calls are best-effort: one failing core is isolated so the runtime keeps going.
"""
from __future__ import annotations

import importlib
import json
import os
import time
import traceback
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Optional

from model_strategy import strategy_from_env, write_strategy_status
from runtime_health_manager import RuntimeHealthManager
from core_profile_manager import decide_core, write_profile_status
from status_manager import write_status as _write_status


@dataclass
class CoreSlot:
    key: str
    module: str
    class_name: str
    role: str
    stage: str
    active: bool = True
    reason: str = ""


CORE_SLOTS = [
    # Active runtime performance / scheduler
    CoreSlot("ResourceSentinel", "ResourceSentinelCore", "ResourceSentinelCore", "Monitor CPU/RAM pressure", "performance"),
    CoreSlot("AdaptiveThrottle", "AdaptiveThrottleCore", "AdaptiveThrottleCore", "Convert resource pressure to OCR delay", "performance"),
    CoreSlot("LatencyBudgetManager", "LatencyBudgetManagerCore", "LatencyBudgetManagerCore", "Frame budget guard", "performance"),
    CoreSlot("PriorityScheduler", "PrioritySchedulerCore", "PrioritySchedulerCore", "Task priority helper", "performance"),
    CoreSlot("PipelineOptimizer", "PipelineOptimizerCore", "PipelineOptimizerCore", "Translate throttle into pipeline plan", "performance"),
    # Active OCR text hygiene
    CoreSlot("TextStitcher", "TextStitcherCore", "TextStitcherCore", "Join OCR lines", "preprocess"),
    CoreSlot("Sanitizer", "SanitizerCore", "SanitizerCore", "Remove OCR garbage", "preprocess"),
    CoreSlot("SpellWeaver", "SpellWeaverCore", "SpellWeaverCore", "Fix OCR glitches", "preprocess"),
    CoreSlot("EdgeCaseDetector", "EdgeCaseDetectorCore", "EdgeCaseDetectorCore", "Block loops/gibberish", "preprocess"),
    CoreSlot("DuplicateSubtitleSuppressor", "DuplicateSubtitleSuppressorCore", "DuplicateSubtitleSuppressorCore", "Skip repeated subtitle frames", "preprocess"),
    CoreSlot("VisionAnalyst", "VisionAnalystCore", "VisionAnalystCore", "Skip menu/loading text keywords", "preprocess"),
    # Active context / learning
    CoreSlot("ContextBuffer", "ContextBufferCore", "ContextBufferCore", "Keep recent speaker/dialog context", "context"),
    CoreSlot("TimelineTracker", "TimelineTrackerCore", "TimelineTrackerCore", "Session timeline telemetry", "context"),
    CoreSlot("Narrative", "NarrativeCore", "NarrativeCore", "Light narrative analysis hook", "context"),
    CoreSlot("Sociologist", "SociologistCore", "SociologistCore", "Speaker style profiling", "context"),
    CoreSlot("CharacterArc", "CharacterArcCore", "CharacterArcCore", "Character state hook", "context"),
    CoreSlot("EntityDiscovery", "EntityDiscoveryCore", "EntityDiscoveryCore", "Candidate name discovery", "context"),
    CoreSlot("LearningEngine", "LearningEngineCore", "LearningEngineCore", "Collect garbage/correction hints", "learning"),
    CoreSlot("FeedbackCollector", "FeedbackCollectorCore", "FeedbackCollectorCore", "Correction feedback log", "learning"),
    # Active cache / translation helper
    CoreSlot("SmartCacheRouter", "SmartCacheRouterCore", "SmartCacheRouterCore", "Decide cache eligibility", "cache"),
    CoreSlot("MemoryVault", "MemoryVaultCore", "MemoryVaultCore", "Secondary translation memory", "cache"),
    CoreSlot("DynamicBatching", "DynamicBatchingCore", "DynamicBatchingCore", "Batch helper for future fast path", "translation"),
    CoreSlot("Failover", "FailoverCore", "FailoverCore", "Emergency translation fallback", "translation"),
    # Active post-processing / QA
    CoreSlot("LoreKeeper", "LoreKeeperCore", "LoreKeeperCore", "Keep game terms consistent", "postprocess"),
    CoreSlot("ProfessorSyntax", "ProfessorSyntaxCore", "ProfessorSyntaxCore", "Syntax correction", "postprocess"),
    CoreSlot("ProfessorTone", "ProfessorToneCore", "ProfessorToneCore", "Tone polish", "postprocess"),
    CoreSlot("ProfessorLogic", "ProfessorLogicCore", "ProfessorLogicCore", "Logic validation", "postprocess"),
    CoreSlot("StyleGuide", "StyleGuideCore", "StyleGuideCore", "Style normalization", "postprocess"),
    CoreSlot("TerminologyConstraint", "TerminologyConstraintCore", "TerminologyConstraintCore", "Blacklist/term enforcement", "postprocess"),
    CoreSlot("BilingualConsistency", "BilingualConsistencyCore", "BilingualConsistencyCore", "Term consistency", "postprocess"),
    CoreSlot("QualityEstimation", "QualityEstimationCore", "QualityEstimationCore", "Reject bad/hallucinated output", "postprocess"),
    CoreSlot("ValidationGate", "ValidationGateCore", "ValidationGateCore", "Final safe display check", "postprocess"),
    # Telemetry / safety
    CoreSlot("BlackBox", "BlackBoxCore", "BlackBoxCore", "Error/event log", "telemetry"),
    CoreSlot("LQAReport", "LQAReportCore", "LQAReportCore", "Quality event counter", "telemetry"),
    CoreSlot("Overseer", "OverseerCore", "OverseerCore", "Core failure tracker", "telemetry"),
    CoreSlot("FallbackStrategy", "FallbackStrategyCore", "FallbackStrategyCore", "Emergency display/log fallback", "telemetry"),
    # Parked by design: these exist but should not run inside TITANMAIN production loop.
    CoreSlot("CaptureSpecialist", "CaptureSpecialistCore", "CaptureSpecialistCore", "Alternative Tesseract capture path", "parked", active=False, reason="TITANMAIN already uses EasyOCR/mss; enabling Tesseract path can conflict or require external install."),
    CoreSlot("Helsinki", "HelsinkiCore", "HelsinkiCore", "Alternative Argos translation engine", "parked", active=False, reason="TITANMAIN already owns Argos translator; double-loading may download packages or duplicate memory."),
    CoreSlot("AsyncOrchestrator", "AsyncOrchestratorCore", "AsyncOrchestratorCore", "Background worker pool", "parked", active=False, reason="TITANMAIN already uses QThread workers; extra worker pool is kept for future jobs."),
    CoreSlot("Formatter", "FormatterCore", "FormatterCore", "Alternative HTML renderer", "parked", active=False, reason="Main translation box UI is locked; TITANMAIN renderer stays authoritative."),
    CoreSlot("UIConstraint", "UIConstraintCore", "UIConstraintCore", "Alternative UI line wrapper", "parked", active=False, reason="Main translation box layout is locked; avoid injecting <br> before escaping."),
    CoreSlot("PromptDirector", "PromptDirectorCore", "PromptDirectorCore", "Prompt builder for online model", "parked", active=False, reason="Used later for online/V4 path; offline TITANMAIN does not need prompt construction."),
    CoreSlot("MultiCandidateGenerator", "MultiCandidateGeneratorCore", "MultiCandidateGeneratorCore", "Multi candidate translation", "parked", active=False, reason="Requires engine instance contract not present in current TITANMAIN."),
    CoreSlot("BackTranslationVerifier", "BackTranslationVerifierCore", "BackTranslationVerifierCore", "Back translation QA", "parked", active=False, reason="Needs extra engine call and may add latency; planned for V3/V5 quality mode only."),
    CoreSlot("ConsistencyAuditor", "ConsistencyAuditorCore", "ConsistencyAuditorCore", "Offline audit report", "parked", active=False, reason="Run manually from diagnostics, not every OCR frame."),
    CoreSlot("RegressionTest", "RegressionTestCore", "RegressionTestCore", "Diagnostics test runner", "parked", active=False, reason="Manual test tool, not runtime dependency."),
    CoreSlot("ConfigMaster", "ConfigMasterCore", "ConfigMasterCore", "Central config helper", "parked", active=False, reason="Existing JSON settings remain stable for v7.2; keep for future consolidation."),
    CoreSlot("Synapse", "SynapseCore", "SynapseCore", "Event bus", "parked", active=False, reason="Current runtime uses direct calls; event bus reserved for v7.2."),
    CoreSlot("Semantics", "SemanticsCore", "SemanticsCore", "Packet semantics preprocessor", "parked", active=False, reason="Requires packet contract; safer to keep as future bridge extension."),
    CoreSlot("Dean", "DeanCore", "DeanCore", "Review council aggregator", "parked", active=False, reason="Adds overhead and duplicate QA; manual/quality mode candidate."),
]


class RuntimeBridge:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None, logger: Callable[[str], None] = print):
        self.base_dir = Path(base_dir or os.getcwd()).resolve()
        self.log = logger
        self.strategy = strategy_from_env()
        self.health = RuntimeHealthManager(self.base_dir)
        self.instances: Dict[str, Any] = {}
        self.status: Dict[str, Dict[str, Any]] = {}
        self.model_group = os.environ.get("ORT_MODEL_GROUP", "normal").lower()
        self.model_key = os.environ.get("ORT_MODEL_KEY", "").lower()
        self.game = os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")).upper()
        self.policy = os.environ.get("ORT_PERFORMANCE_POLICY", "balanced").lower()
        self.heavy_safe = self.strategy.core_profile in {"safe_game", "potato"} or os.environ.get("TITAN_HEAVY_GAME_SAFE", "0") == "1"
        self.fast_mode = self.strategy.fast_path or os.environ.get("TITAN_FAST_MODE", "0") == "1" or self.model_group == "fast"
        self.lite_mode = self.strategy.lite_enabled or os.environ.get("TITAN_LITE_MODE", "0") == "1" or "lite" in self.model_group
        self.idn_mode = self.strategy.idn_enabled or os.environ.get("TITAN_IDN_MODE", "0") == "1" or "idn" in self.model_group
        self.legacy_vault_enabled = os.environ.get("ORT_ENABLE_LEGACY_VAULT", "0") == "1"
        self.naturalize = self.strategy.naturalize_depth >= 1 or os.environ.get("TITAN_NATURALIZE_MAX", "0") == "1" or os.environ.get("ORT_IDN_NATURALIZER", "0") == "1" or self.idn_mode
        self.last_resource_status = "NORMAL"
        self.last_throttle: Dict[str, Any] = {"sleep": 0.0, "skip": 0, "disabled_cores": []}
        self._preprocess_counter = 0
        self._last_status_write = 0.0
        self._load_cores()
        self.write_status(force=True)

    def _load_cores(self) -> None:
        import sys
        if str(self.base_dir) not in sys.path:
            sys.path.insert(0, str(self.base_dir))
        profile_decisions = {}
        for slot in CORE_SLOTS:
            if slot.key == "MemoryVault" and not self.legacy_vault_enabled:
                self.status[slot.key] = {"status": "PARKED", "stage": slot.stage, "role": slot.role, "reason": "v8.7.3 clean baseline: legacy vault isolated (set ORT_ENABLE_LEGACY_VAULT=1 to opt in)."}
                profile_decisions[slot.key] = {"active": False, "reason": self.status[slot.key]["reason"], "stage": slot.stage, "role": slot.role}
                continue
            decision = decide_core(slot.key, slot_active=slot.active, slot_reason=slot.reason, strategy=self.strategy)
            profile_decisions[slot.key] = {"active": decision.active, "reason": decision.reason, "stage": slot.stage, "role": slot.role}
            if not decision.active:
                self.status[slot.key] = {"status": "PARKED", "stage": slot.stage, "role": slot.role, "reason": decision.reason}
                continue
            try:
                module = importlib.import_module(slot.module)
                cls = getattr(module, slot.class_name)
                self.instances[slot.key] = cls()
                self.status[slot.key] = {"status": "ACTIVE", "stage": slot.stage, "role": slot.role, "reason": decision.reason}
            except Exception as exc:
                self.instances[slot.key] = None
                self.status[slot.key] = {
                    "status": "FAILED",
                    "stage": slot.stage,
                    "role": slot.role,
                    "reason": f"{type(exc).__name__}: {exc}",
                }
                self._event("RuntimeBridge", "CORE_LOAD_FAIL", f"{slot.key}: {exc}")
        write_profile_status(self.base_dir, self.strategy, profile_decisions)

    def status_line(self) -> str:
        active = sum(1 for s in self.status.values() if s.get("status") == "ACTIVE")
        parked = sum(1 for s in self.status.values() if s.get("status") == "PARKED")
        failed = sum(1 for s in self.status.values() if s.get("status") == "FAILED")
        vault_state = "enabled" if self.legacy_vault_enabled else "isolated"
        return f"[RUNTIME] Runtime bridge active | cores={active} active, {parked} parked, {failed} failed | profile={self.strategy.core_profile} | strategy={self.strategy.strategy_name} | policy={self.policy} | model={self.model_group}/{self.model_key} | game={self.game} | legacy_vault={vault_state}"

    def write_status(self, force: bool = False) -> None:
        now = time.time()
        if not force and now - self._last_status_write < 15:
            return
        self._last_status_write = now
        data = {
            "version": "v8.7.3",
            "timestamp": now,
            "summary": self.status_line(),
            "policy": self.policy,
            "game": self.game,
            "model_group": self.model_group,
            "model_key": self.model_key,
            "strategy": self.strategy.strategy_name,
            "core_profile": self.strategy.core_profile,
            "postprocess_level": self.strategy.postprocess_level,
            "fast_profile": os.environ.get("ORT_FAST_PROFILE", "standard"),
            "legacy_vault_enabled": self.legacy_vault_enabled,
            "idn_naturalizer": os.environ.get("ORT_IDN_NATURALIZER", "0") == "1",
            "qa_level": self.strategy.qa_level,
            "active_count": sum(1 for s in self.status.values() if s.get("status") == "ACTIVE"),
            "parked_count": sum(1 for s in self.status.values() if s.get("status") == "PARKED"),
            "failed_count": sum(1 for s in self.status.values() if s.get("status") == "FAILED"),
            "cores": self.status,
        }
        try:
            _write_status("core_bridge", data, self.base_dir)
        except Exception:
            pass

    def _core(self, name: str) -> Any:
        return self.instances.get(name)

    def _event(self, source: str, event_type: str, details: Any) -> None:
        bb = self._core("BlackBox")
        if bb and hasattr(bb, "log_event"):
            try:
                bb.log_event(source, event_type, str(details))
                return
            except Exception:
                pass
        # fallback: quiet file log to avoid stdout spam
        try:
            log_dir = self.base_dir / "logs"
            log_dir.mkdir(exist_ok=True)
            with open(log_dir / "bridge_events.log", "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%H:%M:%S')}] {source} {event_type}: {details}\n")
        except Exception:
            pass

    def _safe(self, core: str, method: str, *args, default=None, **kwargs):
        inst = self._core(core)
        if not inst or not hasattr(inst, method):
            return default
        try:
            return getattr(inst, method)(*args, **kwargs)
        except Exception as exc:
            self.status.setdefault(core, {})["last_error"] = f"{type(exc).__name__}: {exc}"
            self._event(core, f"{method}_FAIL", traceback.format_exc(limit=1))
            return default

    # ------------------------------------------------------------------
    # Performance / throttle
    # ------------------------------------------------------------------
    def update_throttle(self) -> Dict[str, Any]:
        self._safe("LatencyBudgetManager", "start_frame")
        status = self._safe("ResourceSentinel", "check_vital_signs", default="NORMAL") or "NORMAL"
        self.last_resource_status = str(status)
        rec = self._safe("AdaptiveThrottle", "recommend_action", self.last_resource_status, default=None)
        if not isinstance(rec, dict):
            rec = {"sleep": 0.0, "skip": 0, "disabled_cores": []}
        self.last_throttle = rec
        return rec

    def extra_loop_sleep_ms(self, default_ms: int, using_gpu: bool) -> int:
        rec = self.update_throttle()
        try:
            extra = float(rec.get("sleep", 0.0)) * 1000.0
        except Exception:
            extra = 0.0
        if self.lite_mode:
            # v8.5: Lite/Lite IDN should be efficient but not sluggish.  Use GPU
            # lightly with a lower loop floor, and let VRAM/throttle add delay only
            # when the system is actually under pressure.
            try:
                env_extra = int(os.environ.get("ORT_LITE_EXTRA_SLEEP_MS", "0") or "0")
            except Exception:
                env_extra = 0
            if using_gpu:
                floor_ms = max(42, min(70, env_extra or 42))
            else:
                floor_ms = max(85, min(130, env_extra or 85))
        elif self.heavy_safe:
            floor_ms = 140 if not using_gpu else 90
        elif self.fast_mode:
            floor_ms = 28 if not using_gpu else 12
        else:
            floor_ms = default_ms
        if self.last_resource_status == "WARNING":
            floor_ms = max(floor_ms, 180 if not using_gpu else 100)
        elif self.last_resource_status == "CRITICAL":
            floor_ms = max(floor_ms, 360 if not using_gpu else 220)
        try:
            health_extra = self.health.recommended_extra_sleep_ms()
        except Exception:
            health_extra = 0
        return int(max(default_ms, floor_ms, extra, health_extra))

    # ------------------------------------------------------------------
    # OCR preprocess
    # ------------------------------------------------------------------
    def preprocess_ocr_text(self, raw: Any, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        meta = meta or {}
        self._preprocess_counter += 1
        self.write_status(force=False)
        throttle = self.update_throttle()

        text = raw
        if isinstance(raw, list):
            text = self._safe("TextStitcher", "stitch", raw, default=" ".join(map(str, raw)))
        text = str(text or "").strip()
        if not text:
            return {"process": False, "text": "", "reason": "empty", "sleep_ms": 0, "status": self.last_resource_status}

        # Loading/menu keyword detection from OCR text list.
        vision_tag = self._safe("VisionAnalyst", "scan_for_keywords", [text], default="DIALOG")
        if vision_tag in {"LOADING_SCREEN", "MAIN_MENU"} and self.heavy_safe:
            return {"process": False, "text": text, "reason": f"vision:{vision_tag}", "sleep_ms": 180, "status": self.last_resource_status}

        text = self._safe("Sanitizer", "clean", text, default=text) or text
        text = self._safe("SpellWeaver", "fix", text, default=text) or text
        try:
            if self.game in {"GFL", "GIRLS_FRONTLINE", "GFL1"}:
                from app.games.gfl_profile import normalize_gfl_text, is_non_dialog_text
                text = normalize_gfl_text(text)
                if is_non_dialog_text(text):
                    return {"process": False, "text": text, "reason": "gfl_non_dialog_or_footer", "sleep_ms": 80, "status": self.last_resource_status}
            elif self.game in {"GFL2", "GFL2_EXILIUM"}:
                from app.ocr.ocr_noise_normalizer import normalize_ocr_noise
                text = normalize_ocr_noise(text)
        except Exception:
            pass
        try:
            if os.environ.get("ORT_NAME_ALIAS_NORMALIZER", "1") == "1":
                from app.translation.name_alias_normalizer import apply_name_aliases
                text = apply_name_aliases(text, self.game)
        except Exception:
            pass
        text = str(text or "").strip()
        if len(text) < 2:
            return {"process": False, "text": text, "reason": "too_short_after_clean", "sleep_ms": 0, "status": self.last_resource_status}

        safe = self._safe("EdgeCaseDetector", "is_safe", text, default=True)
        if safe is False:
            self._safe("LearningEngine", "analyze_garbage_candidate", text)
            return {"process": False, "text": text, "reason": "edge_block", "sleep_ms": 120, "status": self.last_resource_status}

        # Fast mode intentionally has a looser duplicate filter so quick dialog changes are not missed.
        if not self.fast_mode:
            should = self._safe("DuplicateSubtitleSuppressor", "should_process", text, default=True)
            if should is False:
                return {"process": False, "text": text, "reason": "duplicate", "sleep_ms": 0, "status": self.last_resource_status}

        sleep_ms = 0
        if self.last_resource_status == "WARNING":
            sleep_ms = 80 if self.heavy_safe else 30
        elif self.last_resource_status == "CRITICAL":
            # Do not hard-stop; just back off so game stays responsive.
            sleep_ms = 260 if self.heavy_safe else 120
        try:
            sleep_ms = max(sleep_ms, int(float(throttle.get("sleep", 0.0)) * 1000.0))
        except Exception:
            pass
        return {"process": True, "text": text, "reason": "ok", "sleep_ms": sleep_ms, "status": self.last_resource_status}

    # ------------------------------------------------------------------
    # Translation hooks
    # ------------------------------------------------------------------
    def pre_translate_text(self, text: str) -> str:
        text = str(text or "").strip()
        text = self._safe("Sanitizer", "clean", text, default=text) or text
        text = self._safe("SpellWeaver", "fix", text, default=text) or text
        try:
            if self.game in {"GFL", "GIRLS_FRONTLINE", "GFL1"}:
                from app.games.gfl_profile import normalize_gfl_text
                text = normalize_gfl_text(text)
            elif self.game in {"GFL2", "GFL2_EXILIUM"}:
                from app.ocr.ocr_noise_normalizer import normalize_ocr_noise
                text = normalize_ocr_noise(text)
        except Exception:
            pass
        try:
            if os.environ.get("ORT_NAME_ALIAS_NORMALIZER", "1") == "1":
                from app.translation.name_alias_normalizer import apply_name_aliases
                text = apply_name_aliases(text, self.game)
        except Exception:
            pass
        return str(text or "").strip()

    def should_cache(self, text: str) -> bool:
        raw = str(text or "").strip()
        if os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD", "0") == "1" and len(raw) < 18 and not raw.endswith((".", "!", "?", "…")):
            return False
        ok = self._safe("SmartCacheRouter", "check_cache_eligibility", raw, default=True)
        return bool(ok)

    def vault_get(self, text: str) -> str:
        if not self.legacy_vault_enabled:
            return ""
        out = self._safe("MemoryVault", "retrieve", text, default="")
        return str(out or "")

    def vault_store(self, source: str, target: str) -> None:
        if self.legacy_vault_enabled and source and target:
            self._safe("MemoryVault", "store", source, target)

    def failover_translate(self, text: str) -> str:
        return str(self._safe("Failover", "translate_emergency", text, default=text) or text)

    def post_translate_text(self, source: str, translation: str, context_tags: Optional[Iterable[str]] = None) -> str:
        context_tags = list(context_tags or [])
        out = str(translation or "").strip()
        if not out:
            return out
        original_out = out
        # v8.4 Fast Lock: Fast profiles must not be slowed down by heavyweight NLP
        # warm-up/postprocess cores. Fast IDN still receives its lightweight rule-based
        # naturalizer in translation_engine after this bridge hook.
        fast_light_post = os.environ.get("ORT_FAST_SKIP_HEAVY_BRIDGE_POST", "0") == "1" or os.environ.get("ORT_FAST_PROFILE", "") in {"fast_v1_speed_first", "fast_v2_balanced", "fast_idn_naturalized"}
        lite_light_post = os.environ.get("ORT_LITE_IDN_LIGHT_POST", "0") == "1"
        if fast_light_post or lite_light_post:
            out = self._safe("TerminologyConstraint", "enforce", out, default=out) or out
            if lite_light_post and os.environ.get("ORT_IDN_QUALITY_LAYER", "0") == "1" and os.environ.get("ORT_IDN_QUALITY_ENGINE_PASS", "1") != "1":
                try:
                    from app.translation.idn_quality_layer import apply_idn_quality
                    out = apply_idn_quality(source, out, os.environ.get("ORT_IDN_QUALITY_MODE", "lite_balanced"), context_tags)
                except Exception:
                    pass
            gate = self._safe("ValidationGate", "inspect", out, default=(out, False))
            if isinstance(gate, tuple) and gate:
                out = gate[0]
            return str(out or "").strip()
        # Preserve game terms first.
        out = self._safe("LoreKeeper", "enforce_lore", out, default=out) or out
        out = self._safe("ProfessorSyntax", "correct", out, default=out) or out
        if self.naturalize or self.idn_mode or "idn" in self.model_group:
            out = self._safe("ProfessorTone", "polish", out, context_tags, default=out) or out
            out = self._safe("StyleGuide", "format", out, default=out) or out
            out = self._safe("BilingualConsistency", "enforce", out, default=out) or out
        out = self._safe("TerminologyConstraint", "enforce", out, default=out) or out
        # QA: if suspicious, fallback to pre-QA output rather than blocking the UI.
        qa = self._safe("QualityEstimation", "assess", source, out, default=(True, "OK"))
        if isinstance(qa, tuple) and len(qa) >= 2 and qa[0] is False:
            self._event("QualityEstimation", "REJECT", f"{qa[1]} | src={source[:80]} | out={out[:80]}")
            # v8.7.8 fail closed: never return the backend hallucination that QA rejected.
            # TranslationEngine catches this internal marker and holds the overlay/cache.
            out = "__ORT_ENTITY_QA_REJECTED__"
        logic = True
        if self.strategy.qa_level in {"strict", "normal"} and not self.fast_mode:
            logic = self._safe("ProfessorLogic", "validate", source, out, default=True)
        if logic is False:
            self._event("ProfessorLogic", "REJECT", f"src={source[:80]} | out={out[:80]}")
            out = "__ORT_ENTITY_LOGIC_REJECTED__"
        gate = self._safe("ValidationGate", "inspect", out, default=(out, False))
        if isinstance(gate, tuple) and gate:
            out = gate[0]
        return str(out or "").strip()

    def observe_dialog(self, speaker: Optional[str], dialog: str, translation: str = "") -> None:
        speaker = speaker or ""
        dialog = dialog or ""
        if not dialog:
            return
        self._safe("ContextBuffer", "push", speaker, dialog)
        self._safe("TimelineTracker", "log_event", "DIALOG", f"{speaker}: {dialog[:160]}" if speaker else dialog[:160])
        if speaker:
            self._safe("Sociologist", "profile", speaker, dialog)
            # CharacterArc currently needs explicit alignment; only ping status so it becomes supervised without inventing alignment.
            self._safe("CharacterArc", "get_status", speaker)
        self._safe("Narrative", "analyze", dialog)
        self._safe("EntityDiscovery", "investigate", dialog, [])
        if translation:
            self._safe("LQAReport", "track_event", "TRANSLATED")

    def observe_translate_ms(self, ms: float) -> None:
        try:
            self.health.observe_translate_ms(ms)
            self.health.snapshot(force=True)
        except Exception:
            pass

    def observe_ocr_ms(self, ms: float) -> None:
        try:
            self.health.observe_ocr_ms(ms)
        except Exception:
            pass

    def flush(self, reason: str = "manual") -> None:
        self.write_status(force=True)
        vault = self._core("MemoryVault")
        if vault and hasattr(vault, "_save_memory"):
            try:
                vault._save_memory()
            except Exception:
                pass
        self._event("RuntimeBridge", "FLUSH", reason)

# Compatibility aliases for old wrappers; active code imports RuntimeBridge directly.
UnifiedRuntimeBridge = RuntimeBridge

