"""ORT Translation v8.8.6 translation engine layer.

TITANMAIN owns OCR and UI.  This module owns translation routing:
- scoped cache first
- optional Fast CT2 engine
- V4 offline-first online assist through OnlineAssistRouter
- runtime-pressure awareness from runtime_health_applier status
- Argos/offline fallback always safe
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
try:
    from app.runtime.ct2_path_resolver import resolve_ct2_model_dir
except Exception:
    resolve_ct2_model_dir = None
from typing import Callable, Dict, Optional, Tuple

from model_strategy import ModelStrategy, strategy_from_env, write_strategy_status
from cache_store import ScopedCacheStore
from fast_model_manager import FastModelManager
from online_assist_router import OnlineAssistRouter
from online_assist_config import apply_online_config_to_env
from translation_event_logger import append_translation_event, append_event
from status_manager import write_status as _write_status, read_status as _read_status
from app.translation.fuzzy_cache_normalizer import normalize_cache_key
from app.translation.stable_final_cache import StableFinalCachePolicy
from app.diagnostics.idn_evaluation_export import IDNEvaluationExporter
from app.identity.speaker_registry import protect_named_entities, restore_named_entities, has_internal_entity_token
from app.identity.entity_span import process_entity_safe, spans_metadata, residual_internal_marker, translate_entity_safe_source, split_entity_spans, translate_spans
from app.translation.critical_token_guard import safe_normalize as normalize_critical_tokens
from app.translation.faithfulness_gate import assess_translation, safe_fallback_text, quarantine_qur_corruption
from app.translation.dialogue_completeness_gate import hold_incomplete_source, assess_output_coverage
from app.translation.semantic_fidelity_guard import assess_semantic_fidelity

_CJK_RE = re.compile(r"[\u4e00-\u9fff]")


class TranslationEngine:
    def __init__(self, base_dir: str | os.PathLike[str], offline_argos: Callable[[str], str], logger: Callable[[str], None] = print):
        self.base_dir = Path(base_dir).resolve()
        self.offline_argos = offline_argos
        self.log = logger
        self.strategy: ModelStrategy = strategy_from_env()
        self.cache = ScopedCacheStore(
            self.base_dir,
            game=os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")),
            model_key=self.strategy.model_key,
            family=self.strategy.group,
        )
        self.ct2 = None
        self.online_router: Optional[OnlineAssistRouter] = None
        self.naturalized_cache = None
        self.fast_status = FastModelManager(self.base_dir).status()
        self._online_disabled_until = 0.0
        self._last_status_write = 0.0
        self.legacy_vault_enabled = os.environ.get("ORT_ENABLE_LEGACY_VAULT", "0") == "1"
        self.final_cache = StableFinalCachePolicy()
        self.idn_exporter = IDNEvaluationExporter(self.base_dir)
        self._warmup_done = False
        self._request_backend_engines: list[str] = []
        self._request_backend_fallback_reasons: list[str] = []
        self._strict_ct2_request = False
        try:
            apply_online_config_to_env(self.base_dir)
        except Exception:
            pass
        self._init_optional_engines()
        self._init_naturalized_cache()
        self.write_status("INIT")
        write_strategy_status(self.strategy, self.base_dir, extra={
            "cache_path": str(self.cache.path),
            "ct2": bool(self.ct2),
            "fast_status": self.fast_status,
            "online_router": bool(self.online_router),
            "translation_engine": "v8.8.6",
        })


    def _init_naturalized_cache(self) -> None:
        if os.environ.get("ORT_NATURALIZED_CACHE", "0") != "1":
            return
        try:
            from app.translation.naturalized_cache import NaturalizedCache
            self.naturalized_cache = NaturalizedCache(
                self.base_dir,
                game=os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")),
                model_key=self.strategy.model_key,
                mode=os.environ.get("ORT_IDN_QUALITY_MODE", "lite_balanced"),
                version=os.environ.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            )
            self.log(f"[TRANSLATION] Naturalized IDN cache active | entries={self.naturalized_cache.stats().get('entries')} | mode={self.naturalized_cache.stats().get('mode')} | version={self.naturalized_cache.stats().get('version')}")
        except Exception as exc:
            self.naturalized_cache = None
            self.log(f"[TRANSLATION] Naturalized IDN cache unavailable: {exc}")

    def _init_optional_engines(self) -> None:
        if self.strategy.fast_path or self.strategy.engine_policy == "fast" or os.environ.get("ORT_LITE_CT2_ALLOWED", "0") == "1" or os.environ.get("ORT_IDN_OVER_CT2", "0") == "1":
            try:
                from fast_mt_core_ct2 import CT2Config, FastCT2Translator
                if resolve_ct2_model_dir is not None:
                    resolved_ct2 = resolve_ct2_model_dir(self.base_dir)
                    model_dir = resolved_ct2.path
                    model_valid = bool(resolved_ct2.likely_valid)
                else:
                    model_dir = Path(os.environ.get("ORT_LITE_CT2_MODEL_DIR") or self.fast_status.get("model_dir") or os.environ.get("TITAN_CT2_EN_ID_DIR", os.environ.get("ORT_FAST_CT2_MODEL_DIR", str(self.base_dir / "models" / "ct2_opus_mt_en_id"))))
                    model_valid = bool((self.fast_status.get("model_validation") or {}).get("likely_valid")) or os.environ.get("ORT_LITE_CT2_ALLOWED", "0") == "1"
                if model_valid and model_dir.is_dir() and any(model_dir.iterdir()):
                    cfg = CT2Config(
                        model_dir_en_id=str(model_dir),
                        spm_dir_en_id=str(model_dir),
                        beam_size=1,
                        device=os.environ.get("TITAN_CT2_DEVICE", "cpu"),
                        compute_type=os.environ.get("TITAN_CT2_COMPUTE_TYPE", "int8"),
                    )
                    self.ct2 = FastCT2Translator(cfg)
                    self.ct2.warmup()
                    self.log("[TRANSLATION] " + ("IDN-over-CT2 literal engine active" if os.environ.get("ORT_IDN_OVER_CT2", "0") == "1" and not self.strategy.fast_path and os.environ.get("ORT_LITE_CT2_ALLOWED", "0") != "1" else ("Lite CT2 efficient engine active" if os.environ.get("ORT_LITE_CT2_ALLOWED", "0") == "1" and not self.strategy.fast_path else "Fast CT2 engine active")))
                else:
                    self.log(f"[TRANSLATION] Fast CT2 model not found/invalid; using Argos fallback | model_dir={model_dir} | checked=root_models+runtime_app_models")
            except Exception as exc:
                self.ct2 = None
                self.log(f"[TRANSLATION] Fast CT2 unavailable -> Argos fallback: {exc}")

        online_allowed = os.environ.get("ORT_ALLOW_ONLINE_ASSIST", "0") == "1" and self.strategy.level == 4 and not self.strategy.fast_path
        if online_allowed and self.strategy.online_policy in {"hybrid", "timeout_assist", "online_assist"} and os.environ.get("TITAN_ONLINE_ASSIST", "0") == "1":
            try:
                self.online_router = OnlineAssistRouter(self.base_dir, timeout=float(os.environ.get("TITAN_ONLINE_TIMEOUT", "1.2")), logger=self.log)
                self.log("[TRANSLATION] Online assist router ready (offline-first).")
            except Exception as exc:
                self.online_router = None
                self.log(f"[TRANSLATION] Online assist router unavailable: {exc}")

    def _runtime_actions(self) -> Dict[str, object]:
        return _read_status("runtime_actions", self.base_dir, {})

    def _online_paused_by_runtime(self) -> bool:
        actions = self._runtime_actions()
        if bool(actions.get("disable_online", False)):
            return True
        if os.environ.get("ORT_ONLINE_DISABLED", "0") == "1":
            return True
        return time.time() < self._online_disabled_until

    def _translate_offline(self, text: str) -> str:
        if self.ct2:
            try:
                out = self.ct2.translate(text)
                if out and out.strip() and out.strip() != text.strip():
                    self._request_backend_engines.append("ct2_fast")
                    return out.strip()
                reason = "ct2_empty_or_identity_output"
                self._request_backend_fallback_reasons.append(reason)
                append_event("CT2_JOB_FALLBACK", {"reason": reason, "source": str(text or "")[:200]}, source_module="translation_engine")
            except Exception as exc:
                reason = f"{type(exc).__name__}: {exc}"
                self._request_backend_fallback_reasons.append(reason)
                append_event("CT2_JOB_FALLBACK", {"reason": reason, "source": str(text or "")[:200]}, source_module="translation_engine")
                self.log(f"[TRANSLATION] CT2 failed -> offline fallback: {exc}")
        strict_suppression = self._strict_ct2_request and (
            os.environ.get("ORT_HARD_STRICT_CT2_STORY", "1") == "1"
            or os.environ.get("ORT_DISABLE_ARGOS_PROGRESSIVE_WHEN_CT2", "1") == "1"
        )
        if self.ct2 and strict_suppression:
            self._request_backend_engines.append("ct2_held")
            append_event("STRICT_CT2_STORY_FALLBACK_SUPPRESSED", {"reason": self._request_backend_fallback_reasons[-1] if self._request_backend_fallback_reasons else "ct2_no_safe_output", "source": str(text or "")[:200], "hard_strict": os.environ.get("ORT_HARD_STRICT_CT2_STORY", "1") == "1"}, source_module="translation_engine")
            return str(text or "").strip()
        self._request_backend_engines.append("legacy_argos" if self.ct2 else "argos_offline")
        return (self.offline_argos(text) or "").strip()

    def _trusted_preview(self, src: str) -> Optional[Tuple[str, Dict[str, object]]]:
        """Return a CT2-only preview that is never eligible for cache/training."""
        if not self.ct2 or os.environ.get("ORT_FORCE_TRUSTED_PREVIEW", "1") != "1":
            return None
        game_profile = os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM"))
        if game_profile.upper() != "GFL2_EXILIUM":
            return None
        old_strict = self._strict_ct2_request
        self._request_backend_engines = []
        self._request_backend_fallback_reasons = []
        self._strict_ct2_request = True
        started = time.time()
        try:
            spans = split_entity_spans(src, game_profile)
            output, calls = translate_spans(spans, self._translate_offline)
        finally:
            self._strict_ct2_request = old_strict
        engines = set(self._request_backend_engines)
        output = str(output or "").strip()
        if not output or output == src or "ct2_held" in engines or "ct2_fast" not in engines:
            return None
        faith = assess_translation(src, output, progressive=True)
        if not faith.allowed or self._output_is_unsafe(output):
            append_event("TRUSTED_PREVIEW_REJECTED", {"source": src[:300], "reason": faith.reason, "flags": list(faith.flags)}, source_module="translation_engine")
            return None
        extra = {
            "engine": "ct2_trusted_preview", "trusted_preview": True, "preview_pipeline": "ct2_literal_only",
            "overlay_hold": False, "cache_blocked": "trusted_preview_not_final",
            "cache_store": "SKIP_TRUSTED_PREVIEW", "backend_span_calls": int(calls),
            "ms": int((time.time() - started) * 1000), "faithfulness_allowed": True,
            "faithfulness_reason": "safe_trusted_preview", "semantic_flags": [],
        }
        append_event("TRUSTED_PREVIEW_TRANSLATED", {"source": src[:300], "translation": output[:400], "latency_ms": extra["ms"]}, source_module="translation_engine")
        return output, extra

    def _translate_online_assist(self, text: str, offline_out: str) -> str:
        if self._online_paused_by_runtime():
            if self.online_router:
                self.online_router.set_pressure_disabled(True, "runtime health disabled online assist")
            return offline_out
        if self.strategy.core_profile in {"safe_game", "potato", "fast"}:
            return offline_out
        if len(text) > int(os.environ.get("ORT_ONLINE_MAX_CHARS", "220")):
            return offline_out
        if not self.online_router:
            return offline_out
        try:
            online_out = (self.online_router.translate(text) or "").strip()
            if online_out and online_out != text and len(online_out) >= 2:
                return online_out
        except Exception as exc:
            self._online_disabled_until = time.time() + 25.0
            self.log(f"[TRANSLATION] Online assist paused 25s: {exc}")
        return offline_out

    def _cache_event(self, event_type: str, source: str, **extra) -> None:
        payload = {
            "source": str(source or "")[:500],
            "normalized_key": normalize_cache_key(source),
            "namespace": str(self.cache.path.name),
            "model_key": self.strategy.model_key,
            "game": os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")),
        }
        payload.update(extra)
        append_event(event_type, payload, source_module="translation_engine")

    def _store_stable_final(self, source: str, output: str, engine: str, bridge=None, reason: str = "stable_final") -> bool:
        src = str(source or "").strip()
        out = str(output or "").strip()
        if not src or not out:
            return False
        if self._output_is_unsafe(out):
            self._cache_event("ENTITY_RESIDUAL_BLOCKED", src, stage="cache_store", engine=engine)
            return False
        decision = assess_translation(src, out, progressive=False)
        if not decision.allowed:
            self._cache_event("SEMANTIC_CACHE_REJECTED", src, stage="cache_store", engine=engine, reason=decision.reason, flags=list(decision.flags))
            return False
        changed = False
        try:
            if self.naturalized_cache is not None:
                self.naturalized_cache.set(src, out, engine=str(engine or ""))
            changed = bool(self.cache.set(src, out))
            if bridge and self.legacy_vault_enabled:
                bridge.vault_store(src, out)
        finally:
            self._cache_event("CACHE_STORE_STABLE_FINAL", src, engine=engine, reason=reason, changed=changed)
        return changed

    def _output_is_unsafe(self, text: str) -> bool:
        return residual_internal_marker(str(text or "")) or has_internal_entity_token(str(text or ""))

    def _semantic_decision(self, source: str, output: str, *, progressive: bool = False):
        if os.environ.get("ORT_SEMANTIC_FAITHFULNESS_GATE", "1") != "1":
            return assess_translation("", "", progressive=False)
        return assess_translation(source, output, progressive=progressive)

    def _entity_safe_postprocess(self, src: str, translated: str, game_profile: str, bridge=None, *, light_preview: bool = False) -> tuple[str, list[dict], int]:
        """Run IDN rewriting only on text spans; canonical entities are immutable."""
        t0 = time.time()
        actions = self._runtime_actions() if bridge else {}
        tags = [self.strategy.model_key, self.strategy.group, self.strategy.family, self.strategy.core_profile, str(actions.get("status", ""))]

        def process_fragment(fragment: str) -> str:
            out = str(fragment or "")
            if not out:
                return out
            if bridge and not (light_preview and os.environ.get("ORT_RESPONSIVE_SKIP_BRIDGE_PREVIEW", "1") == "1"):
                try:
                    out = bridge.post_translate_text(src, out, context_tags=tags)
                except Exception:
                    pass
            if out and os.environ.get("ORT_IDN_NATURALIZER", "0") == "1" and not light_preview:
                try:
                    from app.translation.indonesian_naturalizer import naturalize_fast_idn
                    out = naturalize_fast_idn(src, out)
                except Exception as exc:
                    self.log(f"[TRANSLATION] Fast IDN naturalizer skipped: {exc}")
            if out and os.environ.get("ORT_IDN_QUALITY_LAYER", "0") == "1":
                try:
                    from app.translation.idn_quality_layer import apply_idn_quality
                    quality_mode = "lite_light" if light_preview else os.environ.get("ORT_IDN_QUALITY_MODE", "lite_balanced")
                    out = apply_idn_quality(src, out, quality_mode, tags=[self.strategy.model_key, self.strategy.group, "preview" if light_preview else "final"])
                except Exception as exc:
                    self.log(f"[TRANSLATION] IDN Quality Layer skipped: {exc}")
            return out

        rendered, spans = process_entity_safe(translated, game_profile, process_fragment)
        ms = int((time.time() - t0) * 1000)
        entity_meta = spans_metadata(spans)
        if entity_meta:
            append_event("ENTITY_SPAN_RESTORED", {"entities": entity_meta, "light_preview": bool(light_preview), "latency_ms": ms}, source_module="translation_engine")
        return rendered, entity_meta, ms

    def warmup(self, bridge=None) -> None:
        """Warm IDN/post-processing modules without consuming a game dialogue."""
        if self._warmup_done or os.environ.get("ORT_IDN_WARMUP", "1") == "0":
            return
        t0 = time.time()
        append_event("IDN_WARMUP_START", {"model_key": self.strategy.model_key}, source_module="translation_engine")
        try:
            sample_src = "Helen: I refuse to abandon Phaetusa at Level II."
            sample_out, _, _ = translate_entity_safe_source(sample_src, os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "GFL2_EXILIUM")), self._translate_offline)
            sample_out = sample_out or "Aku menolak meninggalkan Phaetusa di Level II."
            self._entity_safe_postprocess(sample_src, sample_out, os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "GFL2_EXILIUM")), bridge=bridge, light_preview=False)
        except Exception as exc:
            self.log(f"[TRANSLATION] IDN warmup skipped: {exc}")
        self._warmup_done = True
        elapsed = int((time.time() - t0) * 1000)
        append_event("IDN_WARMUP_DONE", {"model_key": self.strategy.model_key, "latency_ms": elapsed}, source_module="translation_engine")
        self.log(f"[TRANSLATION] IDN warmup complete | {elapsed}ms | model={self.strategy.model_key}")

    def translate(self, text: str, bridge=None) -> Tuple[str, Dict[str, object]]:
        raw_src = (text or "").strip()
        src = raw_src
        meta: Dict[str, object] = {"engine": "", "cache": "MISS", "strategy": self.strategy.strategy_name, "version": "v8.8.6", "responsive_story": os.environ.get("ORT_RESPONSIVE_STORY_MODE", "0") == "1", "entity_span_pipeline": True, "semantic_faithfulness_gate": True, "dialogue_completeness_gate": True}
        if not src:
            append_event("TRANSLATION_SKIPPED", {"reason": "empty"}, source_module="translation_engine")
            return "", meta
        if bridge:
            try:
                src = bridge.pre_translate_text(src)
            except Exception:
                pass
        try:
            if os.environ.get("ORT_GFL_CACHE_NORMALIZED", "0") == "1":
                from app.games.gfl_profile import normalize_gfl_text
                src = normalize_gfl_text(src)
        except Exception:
            pass
        number_protection = None
        number_gap_reason = ""
        try:
            from app.ocr.number_guard import normalize_numeric_ocr, protect_numbers, needs_numeric_dual_pass
            src = normalize_numeric_ocr(src)
            if os.environ.get("ORT_NAME_ALIAS_NORMALIZER", "1") == "1":
                from app.translation.name_alias_normalizer import apply_name_aliases
                src = apply_name_aliases(src, os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "")))
            src = normalize_critical_tokens(src)
            qur_guard = quarantine_qur_corruption(src) if os.environ.get("ORT_QUR_CORRUPTION_QUARANTINE", "1") == "1" else None
            if qur_guard and qur_guard.repaired_source != src:
                append_event("OCR_QUR_CORRUPTION_REPAIRED", {"source_before": src[:240], "source_after": qur_guard.repaired_source[:240], "repair": qur_guard.repair}, source_module="translation_engine")
                src = qur_guard.repaired_source
                meta["qur_quarantine"] = "repaired"
            elif qur_guard and qur_guard.quarantined:
                meta["qur_quarantine"] = "ambiguous"
                meta["qur_quarantine_reason"] = qur_guard.reason
            number_protection = protect_numbers(src)
            need_gap, detected_gap_reason = needs_numeric_dual_pass(src)
            # v8.7.2 critical fix: a negative decision returns diagnostic strings
            # such as no_numeric_context/number_present.  These are not gaps and
            # must never block cache lookup/store for ordinary dialogue.
            number_gap_reason = detected_gap_reason if need_gap else ""
            if need_gap:
                meta["number_gap"] = number_gap_reason
        except Exception:
            number_protection = None
            number_gap_reason = ""
        meta["normalized_source"] = src
        meta["normalized_key"] = normalize_cache_key(src)
        plan = self.final_cache.prepare(src)
        meta["cache_plan"] = plan.relation
        if plan.previous_to_commit is not None:
            self._store_stable_final(plan.previous_to_commit.source, plan.previous_to_commit.output, plan.previous_to_commit.engine, bridge=bridge, reason="dialog_transition")
        accuracy_first = os.environ.get("ORT_FINAL_ONLY_SAFE_COMMIT", "0") == "1"
        completeness = hold_incomplete_source(src, plan.relation, auto_mode=os.environ.get("ORT_DIALOGUE_COMPLETENESS_GATE", "1") == "1", final_only_accuracy=accuracy_first)
        if completeness.hold:
            preview = self._trusted_preview(src) if os.environ.get("ORT_RESPONSIVE_STORY_MODE", "0") == "1" else None
            if preview is not None:
                preview_out, preview_meta = preview
                meta.update(preview_meta)
                meta["hold_reason"] = completeness.reason
                append_event("TRUSTED_PREVIEW_OVERLAY_READY", {"source": src[:300], "translation": preview_out[:400], "reason": completeness.reason, "relation": plan.relation}, source_module="translation_engine")
                self.write_status("TRUSTED_PREVIEW", meta=meta)
                return preview_out, meta
            meta.update({"overlay_hold": True, "hold_reason": completeness.reason, "cache_blocked": "preview_incomplete", "cache_store": "SKIP_PREVIEW_INCOMPLETE", "engine": "held_preview", "ms": 0})
            append_event("PREVIEW_HELD_INCOMPLETE", {"source": src[:300], "reason": completeness.reason, "relation": plan.relation}, source_module="translation_engine")
            self.write_status("HELD_INCOMPLETE", meta=meta)
            return src, meta
        if meta.get("qur_quarantine") == "ambiguous" and plan.relation in {"new", "progressive"}:
            meta.update({"overlay_hold": True, "hold_reason": "qur_ocr_ambiguous_wait_stable", "cache_blocked": "qur_quarantine", "cache_store": "SKIP_QUR_QUARANTINE", "engine": "held_preview", "ms": 0})
            append_event("QUR_CORRUPTION_QUARANTINED", {"source": src[:300], "relation": plan.relation, "reason": meta.get("qur_quarantine_reason", "bare_qur_ambiguous")}, source_module="translation_engine")
            self.write_status("HELD_QUR_QUARANTINE", meta=meta)
            return src, meta
        # Final persistent caches are read before the in-session memo.
        if not number_gap_reason and self.naturalized_cache is not None:
            try:
                nat_cached = self.naturalized_cache.get(src)
                if nat_cached and self._output_is_unsafe(nat_cached):
                    self._cache_event("ENTITY_RESIDUAL_BLOCKED", src, stage="naturalized_cache_hit")
                    nat_cached = None
                if nat_cached:
                    cache_decision = assess_translation(src, nat_cached, progressive=False)
                    if not cache_decision.allowed:
                        self._cache_event("SEMANTIC_CACHE_REJECTED", src, stage="naturalized_cache_hit", reason=cache_decision.reason, flags=list(cache_decision.flags))
                        nat_cached = None
                if nat_cached:
                    meta["cache"] = "HIT_STABLE_FINAL"
                    meta["engine"] = "naturalized_cache"
                    self._cache_event("CACHE_HIT_STABLE_FINAL", src, engine="naturalized_cache", cache="NATURALIZED_IDN_HIT")
                    append_translation_event("CACHE_HIT", source=src, translation=nat_cached, engine="naturalized_cache", cache="HIT_STABLE_FINAL", extra={"strategy": self.strategy.strategy_name}, source_module="translation_engine")
                    return nat_cached, meta
            except Exception:
                pass
        cached = None if number_gap_reason else self.cache.get(src)
        if cached and self._output_is_unsafe(cached):
            self._cache_event("ENTITY_RESIDUAL_BLOCKED", src, stage="scoped_cache_hit")
            cached = None
        if cached:
            cache_decision = assess_translation(src, cached, progressive=False)
            if not cache_decision.allowed:
                self._cache_event("SEMANTIC_CACHE_REJECTED", src, stage="scoped_cache_hit", reason=cache_decision.reason, flags=list(cache_decision.flags))
                cached = None
        if cached:
            meta["cache"] = "HIT_STABLE_FINAL"
            meta["engine"] = "scoped_cache"
            self._cache_event("CACHE_HIT_STABLE_FINAL", src, engine="scoped_cache", cache="SCOPED_HIT")
            append_translation_event("CACHE_HIT", source=src, translation=cached, engine="scoped_cache", cache="HIT_STABLE_FINAL", extra={"strategy": self.strategy.strategy_name}, source_module="translation_engine")
            return cached, meta
        if plan.reuse_output and not number_gap_reason:
            if plan.store_current_immediately:
                self._store_stable_final(src, plan.reuse_output, self.final_cache.candidate.engine if self.final_cache.candidate else "current_dialog_memo", bridge=bridge, reason="stable_repeat")
            meta["cache"] = "DUPLICATE_OCR_SUPPRESSED"
            meta["engine"] = "current_dialog_memo"
            self._cache_event("CACHE_DUPLICATE_OCR_SUPPRESSED", src, reason=plan.reason)
            append_translation_event("CACHE_HIT", source=src, translation=plan.reuse_output, engine="current_dialog_memo", cache="DUPLICATE_OCR_SUPPRESSED", extra={"strategy": self.strategy.strategy_name}, source_module="translation_engine")
            return plan.reuse_output, meta
        if bridge and self.legacy_vault_enabled:
            try:
                vault = "" if number_gap_reason else bridge.vault_get(src)
                if vault:
                    self._store_stable_final(src, vault, "memory_vault", bridge=None, reason="legacy_vault_opt_in")
                    meta["cache"] = "VAULT_HIT"
                    meta["engine"] = "memory_vault"
                    append_translation_event("CACHE_HIT", source=src, translation=vault, engine="memory_vault", cache="VAULT_HIT", extra={"strategy": self.strategy.strategy_name}, source_module="translation_engine")
                    return vault, meta
            except Exception:
                pass
        append_event("TRANSLATION_REQUEST", {"source": src, "strategy": self.strategy.strategy_name, "model_key": self.strategy.model_key, "normalized_key": meta["normalized_key"]}, source_module="translation_engine")
        self._request_backend_engines = []
        self._request_backend_fallback_reasons = []
        t0 = time.time()
        translate_src = number_protection.source if number_protection and getattr(number_protection, "numbers", None) else src
        game_profile = os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM"))
        entity_t0 = time.time()
        # v8.7.6: entities never enter the backend as string placeholders.
        # TextSpan fragments alone are translated and canonical EntitySpan values
        # are composed back unchanged, eliminating ORT_BKEND/BEND/BKED leaks.
        source_spans = split_entity_spans(translate_src, game_profile)
        meta["protected_entities"] = [row["display_name"] for row in spans_metadata(source_spans)]
        meta["entity_match_ms"] = int((time.time() - entity_t0) * 1000)
        backend_t0 = time.time()
        request_progressive = plan.relation in {"new", "progressive"} and not src.rstrip().endswith((".", "!", "?", "…"))
        hard_story = bool(self.ct2 and game_profile.upper() == "GFL2_EXILIUM" and os.environ.get("ORT_HARD_STRICT_CT2_STORY", "1") == "1")
        self._strict_ct2_request = bool(self.ct2 and os.environ.get("ORT_STRICT_CT2_STORY", "1") == "1" and (hard_story or request_progressive or meta.get("qur_quarantine") == "ambiguous"))
        meta["strict_ct2_story"] = self._strict_ct2_request
        meta["hard_strict_ct2_story"] = hard_story
        backend_out, span_backend_calls = translate_spans(source_spans, self._translate_offline)
        meta["backend_span_calls"] = int(span_backend_calls)
        applied_backends = set(self._request_backend_engines)
        if applied_backends == {"ct2_fast"}:
            meta["engine"] = "ct2_fast"
        elif "legacy_argos" in applied_backends and "ct2_fast" in applied_backends:
            meta["engine"] = "mixed_ct2_legacy_argos"
        elif "legacy_argos" in applied_backends:
            meta["engine"] = "legacy_argos"
        else:
            meta["engine"] = "argos_offline"
        if self._request_backend_fallback_reasons:
            meta["ct2_fallback_reasons"] = list(self._request_backend_fallback_reasons)
            meta["fallback_backend_reason"] = ";".join(self._request_backend_fallback_reasons)
        self._strict_ct2_request = False
        if "ct2_held" in applied_backends:
            meta.update({"engine": "held_preview", "overlay_hold": True, "hold_reason": "hard_strict_ct2_no_argos_story", "cache_blocked": "strict_ct2_hold", "cache_store": "SKIP_STRICT_CT2_HOLD", "ms": int((time.time() - t0) * 1000)})
            append_event("STRICT_CT2_STORY_HELD", {"source": src[:300], "reason": meta.get("fallback_backend_reason", "ct2_no_safe_output"), "relation": plan.relation}, source_module="translation_engine")
            self.write_status("HELD_STRICT_CT2", meta=meta)
            return src, meta
        # Preserve online-assist behaviour only for lines without immutable entities;
        # entity-bearing lines favour identity correctness over external rewrite.
        if not meta["protected_entities"] and self.strategy.online_policy in {"hybrid", "timeout_assist", "online_assist"}:
            assisted_raw = self._translate_online_assist(translate_src, backend_out)
            if assisted_raw != backend_out:
                backend_out = assisted_raw
                meta["engine"] = "online_router"
        meta["backend_translate_ms"] = int((time.time() - backend_t0) * 1000)
        out = (backend_out or src).strip()
        try:
            if number_protection is not None:
                from app.ocr.number_guard import restore_numbers
                out = restore_numbers(number_protection, out)
        except Exception:
            pass
        post_backend_out = out
        if self._output_is_unsafe(post_backend_out):
            append_event("ENTITY_RESIDUAL_BLOCKED", {"stage": "backend_restore", "source": src[:240], "unsafe": post_backend_out[:240]}, source_module="translation_engine")
            post_backend_out = src
            meta["entity_fallback"] = "source_after_backend_restore_failure"
        progressive = plan.relation in {"new", "progressive"} and not src.rstrip().endswith((".", "!", "?", "…"))
        backend_faith = assess_translation(src, post_backend_out, progressive=progressive)
        meta["backend_faithfulness_allowed"] = bool(backend_faith.allowed)
        meta["backend_faithfulness_reason"] = backend_faith.reason
        meta["semantic_flags"] = list(backend_faith.flags)
        unsafe_backend_output = ""
        if not backend_faith.allowed:
            unsafe_backend_output = post_backend_out
            meta["cache_blocked"] = "semantic_hallucination"
            meta["semantic_reliability"] = "blocked_backend"
            append_event("SEMANTIC_HALLUCINATION_BLOCKED", {"stage": "backend_output", "source": src[:300], "unsafe_output": str(post_backend_out)[:400], "reason": backend_faith.reason, "flags": list(backend_faith.flags), "engine": meta.get("engine", "")}, source_module="translation_engine")
            if progressive or backend_faith.hold_overlay:
                out = src
                meta["overlay_hold"] = True
                meta["hold_reason"] = "semantic_hallucination_progressive"
                append_event("UNTRUSTED_TRANSLATION_HELD", {"source": src[:300], "reason": backend_faith.reason}, source_module="translation_engine")
            else:
                out = safe_fallback_text(src)
                meta["safe_literal_fallback"] = True
                append_event("SAFE_LITERAL_RETRY_USED", {"source": src[:300], "reason": backend_faith.reason, "mode": "source_safe_fallback"}, source_module="translation_engine")
            entity_spans, idn_post_ms = [], 0
            meta["entity_spans"] = entity_spans
            meta["idn_post_ms"] = idn_post_ms
            meta["preview_pipeline"] = "blocked_before_idn"
            faith = backend_faith
        else:
            responsive = os.environ.get("ORT_RESPONSIVE_STORY_MODE", "0") == "1"
            light_preview = bool(responsive and progressive)
            out, entity_spans, idn_post_ms = self._entity_safe_postprocess(src, post_backend_out, game_profile, bridge=bridge, light_preview=light_preview)
            meta["entity_spans"] = entity_spans
            meta["idn_post_ms"] = idn_post_ms
            meta["preview_pipeline"] = "light" if light_preview else "full"
            try:
                if number_protection is not None:
                    from app.ocr.number_guard import restore_numbers
                    out = restore_numbers(number_protection, out)
            except Exception:
                pass
            if self._output_is_unsafe(out):
                append_event("ENTITY_RESIDUAL_BLOCKED", {"stage": "final_output", "source": src[:240], "unsafe": str(out)[:240]}, source_module="translation_engine")
                out = src
                meta["entity_fallback"] = "safe_source_after_final_residual"
                meta["cache_blocked"] = "residual_entity_token"
                meta["overlay_hold"] = True
                meta["hold_reason"] = "residual_entity_token"
            if os.environ.get("ORT_SEMANTIC_FIDELITY_GUARD", "1") == "1" and not progressive:
                fidelity = assess_semantic_fidelity(src, out, post_backend_out)
                meta["semantic_fidelity_allowed"] = bool(fidelity.allowed)
                meta["semantic_fidelity_reason"] = fidelity.reason
                meta["semantic_fidelity_flags"] = list(fidelity.flags)
                if not fidelity.allowed:
                    polished_candidate = out
                    anchor_faith = assess_translation(src, post_backend_out, progressive=False)
                    if anchor_faith.allowed and not self._output_is_unsafe(post_backend_out):
                        out = post_backend_out
                        meta["idn_polish_drift_fallback"] = True
                        append_event("IDN_POLISH_DRIFT_FALLBACK_TO_CT2_LITERAL", {"source": src[:300], "candidate": str(polished_candidate)[:300], "literal_anchor": str(post_backend_out)[:300], "reason": fidelity.reason, "flags": list(fidelity.flags)}, source_module="translation_engine")
                    else:
                        meta["cache_blocked"] = "semantic_fidelity_drift"
                        meta["overlay_hold"] = True
                        meta["hold_reason"] = "semantic_fidelity_drift_no_safe_anchor"
            faith = assess_translation(src, out, progressive=progressive)
            meta["faithfulness_allowed"] = bool(faith.allowed)
            meta["faithfulness_reason"] = faith.reason
            meta["semantic_flags"] = list(faith.flags)
            meta["semantic_reliability"] = "safe" if faith.allowed else "blocked_final"
            if not faith.allowed:
                unsafe_backend_output = out
                meta["cache_blocked"] = "semantic_hallucination"
                append_event("SEMANTIC_HALLUCINATION_BLOCKED", {"stage": "final_output", "source": src[:300], "unsafe_output": str(out)[:400], "reason": faith.reason, "flags": list(faith.flags), "engine": meta.get("engine", "")}, source_module="translation_engine")
                if progressive or faith.hold_overlay:
                    out = src
                    meta["overlay_hold"] = True
                    meta["hold_reason"] = "semantic_hallucination_progressive"
                    append_event("UNTRUSTED_TRANSLATION_HELD", {"source": src[:300], "reason": faith.reason}, source_module="translation_engine")
                else:
                    out = safe_fallback_text(src)
                    meta["safe_literal_fallback"] = True
                    append_event("SAFE_LITERAL_RETRY_USED", {"source": src[:300], "reason": faith.reason, "mode": "source_safe_fallback"}, source_module="translation_engine")
        meta.setdefault("faithfulness_allowed", bool(faith.allowed))
        meta.setdefault("faithfulness_reason", faith.reason)
        meta["rejected_unsafe_output"] = unsafe_backend_output[:500] if unsafe_backend_output else ""
        coverage = assess_output_coverage(src, out, plan.relation, accuracy_first=accuracy_first)
        meta["coverage_score"] = coverage.output_coverage
        if faith.allowed and not coverage.allowed:
            meta["cache_blocked"] = "output_coverage_low"
            meta["overlay_hold"] = True
            meta["hold_reason"] = coverage.reason
            append_event("OMISSION_SUSPECTED", {"source": src[:300], "output": str(out)[:300], "reason": coverage.reason}, source_module="translation_engine")
        if not meta.get("cache_blocked"):
            self.final_cache.observe_translation(src, out, str(meta.get("engine") or ""))
        if out and not number_gap_reason and not meta.get("cache_blocked"):
            if plan.store_current_immediately:
                self._store_stable_final(src, out, str(meta.get("engine") or ""), bridge=bridge, reason="snapshot_or_confirmed")
                meta["cache_store"] = "STORE_STABLE_FINAL"
            else:
                meta["cache_store"] = "SKIP_PROGRESSIVE_PENDING_FINAL"
                self._cache_event("CACHE_SKIP_PROGRESSIVE", src, reason=plan.reason)
        elif meta.get("cache_blocked"):
            meta["cache_store"] = "SKIP_UNTRUSTED_OR_INCOMPLETE"
            self._cache_event("SEMANTIC_CACHE_REJECTED" if meta.get("cache_blocked") == "semantic_hallucination" else "CACHE_SKIP_UNTRUSTED_OR_INCOMPLETE", src, reason=str(meta.get("cache_blocked")))
        elif number_gap_reason:
            meta["cache_store"] = "SKIP_NUMBER_UNCERTAIN"
            self._cache_event("CACHE_SKIP_NUMBER_UNCERTAIN", src, reason=number_gap_reason)
        meta["ms"] = int((time.time() - t0) * 1000)
        if self.idn_exporter.enabled and os.environ.get("ORT_IDN_QUALITY_LAYER", "0") == "1":
            eval_payload = {
                "model_key": self.strategy.model_key,
                "quality_mode": os.environ.get("ORT_IDN_QUALITY_MODE", ""),
                "game": os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")),
                "source_raw": raw_src,
                "source_normalized": src,
                "protected_entities": list(meta.get("protected_entities", [])),
                "entity_spans": list(meta.get("entity_spans", [])),
                "preview_pipeline": str(meta.get("preview_pipeline", "full")),
                "backend_output": post_backend_out,
                "final_idn_output": out,
                "backend_applied": str(meta.get("engine") or ""),
                "cache": str(meta.get("cache") or "MISS"),
                "cache_store": str(meta.get("cache_store") or ""),
                "latency_ms": int(meta.get("ms") or 0),
                "entity_match_ms": int(meta.get("entity_match_ms") or 0),
                "backend_translate_ms": int(meta.get("backend_translate_ms") or 0),
                "idn_post_ms": int(meta.get("idn_post_ms") or 0),
                "faithfulness_allowed": bool(meta.get("faithfulness_allowed", True)),
                "faithfulness_reason": str(meta.get("faithfulness_reason", "safe")),
                "semantic_flags": list(meta.get("semantic_flags", [])),
                "overlay_hold": bool(meta.get("overlay_hold")),
                "hold_reason": str(meta.get("hold_reason", "")),
                "coverage_score": float(meta.get("coverage_score", 1.0) or 0.0),
                "fallback_backend_reason": str(meta.get("fallback_backend_reason", "")),
                "cache_allowed_after_gate": not bool(meta.get("cache_blocked")),
                "qur_quarantine": str(meta.get("qur_quarantine", "")),
                "strict_ct2_story": bool(meta.get("strict_ct2_story")),
                "hard_strict_ct2_story": bool(meta.get("hard_strict_ct2_story")),
                "trusted_preview": bool(meta.get("trusted_preview")),
                "semantic_fidelity_allowed": bool(meta.get("semantic_fidelity_allowed", True)),
                "semantic_fidelity_reason": str(meta.get("semantic_fidelity_reason", "safe")),
                "semantic_fidelity_flags": list(meta.get("semantic_fidelity_flags", [])),
                "rejected_unsafe_output": str(meta.get("rejected_unsafe_output", "")),
            }
            self.idn_exporter.append(**eval_payload)
            append_event("IDN_EVALUATION", eval_payload, source_module="translation_engine")
        append_translation_event("TRANSLATION_RESULT", source=src, translation=out, engine=str(meta.get("engine") or ""), latency_ms=int(meta.get("ms") or 0), cache=str(meta.get("cache") or "MISS"), extra={"strategy": self.strategy.strategy_name, "model_key": self.strategy.model_key, "core_profile": self.strategy.core_profile, "cache_store": meta.get("cache_store", ""), "normalized_key": meta.get("normalized_key", ""), "semantic_reliability": meta.get("semantic_reliability", ""), "faithfulness_allowed": bool(meta.get("faithfulness_allowed", True)), "faithfulness_reason": meta.get("faithfulness_reason", "safe"), "semantic_flags": meta.get("semantic_flags", []), "overlay_hold": bool(meta.get("overlay_hold")), "hold_reason": meta.get("hold_reason", ""), "coverage_score": meta.get("coverage_score", 1.0), "cache_allowed_after_gate": not bool(meta.get("cache_blocked")), "qur_quarantine": meta.get("qur_quarantine", ""), "strict_ct2_story": bool(meta.get("strict_ct2_story")), "ct2_fallback_reasons": meta.get("ct2_fallback_reasons", []), "fallback_backend_reason": meta.get("fallback_backend_reason", ""), "hard_strict_ct2_story": bool(meta.get("hard_strict_ct2_story")), "trusted_preview": bool(meta.get("trusted_preview")), "semantic_fidelity_reason": meta.get("semantic_fidelity_reason", "safe"), "semantic_fidelity_flags": meta.get("semantic_fidelity_flags", [])}, source_module="translation_engine")
        self.write_status("TRANSLATED", meta=meta)
        return out, meta

    def flush(self) -> None:
        try:
            pending = self.final_cache.candidate_for_flush()
            if pending is not None:
                self._store_stable_final(pending.source, pending.output, pending.engine, bridge=None, reason="runtime_flush")
        except Exception:
            pass
        try:
            self.cache.flush(force=True)
        except TypeError:
            self.cache.flush()
        try:
            if self.naturalized_cache is not None:
                self.naturalized_cache.flush()
        except Exception:
            pass
        self.write_status("FLUSH")

    def write_status(self, state: str, meta: Optional[Dict[str, object]] = None) -> None:
        now = time.time()
        if state == "TRANSLATED" and now - self._last_status_write < 2.0:
            return
        self._last_status_write = now
        payload: Dict[str, object] = {
            "version": "v8.8.6",
            "state": state,
            "strategy": self.strategy.strategy_name,
            "model_key": self.strategy.model_key,
            "group": self.strategy.group,
            "core_profile": self.strategy.core_profile,
            "cache_file": str(self.cache.path),
            "ct2_active": bool(self.ct2),
            "fast_state": self.fast_status.get("state"),
            "online_router": bool(self.online_router),
            "online_paused_by_runtime": self._online_paused_by_runtime(),
            "fast_profile": os.environ.get("ORT_FAST_PROFILE", "standard"),
            "idn_naturalizer": os.environ.get("ORT_IDN_NATURALIZER", "0") == "1",
            "naturalized_cache": bool(self.naturalized_cache),
            "legacy_vault_enabled": self.legacy_vault_enabled,
            "cache_progressive_guard": os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD", "0") == "1",
            "stable_final_cache_v2": self.final_cache.enabled,
            "current_dialog_memo": self.final_cache.memo_enabled,
            "idn_evaluation_export": self.idn_exporter.enabled,
            "entity_span_pipeline": True,
            "semantic_faithfulness_gate": os.environ.get("ORT_SEMANTIC_FAITHFULNESS_GATE", "1") == "1",
            "dialogue_completeness_gate": os.environ.get("ORT_DIALOGUE_COMPLETENESS_GATE", "1") == "1",
            "hard_strict_ct2_story": os.environ.get("ORT_HARD_STRICT_CT2_STORY", "1") == "1",
            "trusted_preview": os.environ.get("ORT_FORCE_TRUSTED_PREVIEW", "1") == "1",
            "semantic_fidelity_guard": os.environ.get("ORT_SEMANTIC_FIDELITY_GUARD", "1") == "1",
            "ct2_model_dir_used": os.environ.get("ORT_CT2_MODEL_DIR_USED", ""),
            "ct2_spm_dir_used": os.environ.get("ORT_CT2_SPM_DIR_USED", ""),
            "responsive_story_mode": os.environ.get("ORT_RESPONSIVE_STORY_MODE", "0") == "1",
            "cache_namespace": os.environ.get("ORT_IDN_CACHE_VERSION", "v8_7_9_responsive_turn_safe_ct2"),
            "requested_engine": os.environ.get("ORT_BOOT_ENGINE", os.environ.get("ORT_ENGINE_POLICY", "offline")),
            "applied_engine": (str((meta or {}).get("engine") or "") if meta else ("ct2_fast" if self.ct2 else "argos_offline")),
            "game_profile": os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "CUSTOM")),
            "gfl_layout": os.environ.get("ORT_GFL_LAYOUT", "0") == "1",
            "gfl_normalized_cache": os.environ.get("ORT_GFL_CACHE_NORMALIZED", "0") == "1",
        }
        if meta:
            payload["last_meta"] = meta
        try:
            _write_status("translation_engine", payload, self.base_dir)
        except Exception:
            pass


_ENGINE: Optional[TranslationEngine] = None


def get_engine(base_dir: str | os.PathLike[str], offline_argos: Callable[[str], str], logger: Callable[[str], None] = print) -> TranslationEngine:
    global _ENGINE
    if _ENGINE is None:
        _ENGINE = TranslationEngine(base_dir, offline_argos, logger)
    return _ENGINE


# Compatibility aliases for older imports.
TranslationEngineV72 = TranslationEngine
TranslationEngineV73 = TranslationEngine
TranslationEngineV74 = TranslationEngine
TranslationEngineV75 = TranslationEngine
TranslationEngineV76 = TranslationEngine
TranslationEngineV77 = TranslationEngine

TranslationEngineV78 = TranslationEngine
TranslationEngineV79 = TranslationEngine
