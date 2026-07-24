from __future__ import annotations

import faulthandler
import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


BASE_DIR = Path(__file__).resolve().parent
EVENT_PREFIX = "ORT_AUDIO_TRANSLATION_EVENT "


def emit_event(event_type: str, **payload: Any) -> None:
    event = {"type": str(event_type), "ts": time.time(), **payload}
    print(EVENT_PREFIX + json.dumps(event, ensure_ascii=False, separators=(",", ":")), flush=True)


def log(message: str) -> None:
    print(str(message), flush=True)


def configure_native_runtime() -> bool:
    safe_mode = os.environ.get("ORT_AUDIO_TRANSLATION_SAFE_MODE", "0") == "1"
    threads = max(1, min(2, int(os.environ.get("ORT_AUDIO_TRANSLATION_THREADS", "1") or 1)))
    os.environ["OMP_NUM_THREADS"] = str(1 if safe_mode else threads)
    os.environ["OPENBLAS_NUM_THREADS"] = str(1 if safe_mode else threads)
    os.environ["MKL_NUM_THREADS"] = str(1 if safe_mode else threads)
    os.environ["CT2_PACKED_GEMM"] = "0"
    os.environ["CT2_USE_EXPERIMENTAL_PACKED_GEMM"] = "0"
    os.environ.setdefault("ORT_DIALOGUE_COMPLETENESS_GATE", "0")
    os.environ.setdefault("ORT_FINAL_ONLY_SAFE_COMMIT", "0")
    os.environ.setdefault("ORT_RESPONSIVE_STORY_MODE", "0")
    os.environ.setdefault("ORT_STRICT_CT2_STORY", "0")
    os.environ.setdefault("ORT_HARD_STRICT_CT2_STORY", "0")
    os.environ.setdefault("ORT_AUDIO_SOURCE", "1")
    os.environ.setdefault("ORT_TRANSLATION_SOURCE", "audio")
    if safe_mode:
        os.environ["ORT_DISABLE_CT2"] = "1"
    return safe_mode


def split_audio_clauses(text: str) -> list[str]:
    clean = " ".join(str(text or "").strip().split())
    if not clean:
        return []
    clauses = [item.strip() for item in re.split(r"(?<=[.!?…])\s+", clean) if item.strip()]
    expanded: list[str] = []
    for clause in clauses:
        if len(clause.split()) > 28 and re.search(r"[;:]\s+", clause):
            expanded.extend(item.strip() for item in re.split(r"(?<=[;:])\s+", clause) if item.strip())
        else:
            expanded.append(clause)
    return expanded or [clean]


@dataclass
class SegmentTranslationState:
    source: str
    clauses: list[str]
    outputs: list[str]
    meta: dict
    last_used: float


class AudioTranslator:
    def __init__(self, safe_mode: bool):
        self.safe_mode = bool(safe_mode)
        self._argos_translation = None
        self._engine = None
        self._segments: dict[str, SegmentTranslationState] = {}
        self._segment_limit = 32
        self._init_engine()

    def _init_engine(self) -> None:
        from translation_engine import get_engine

        self._engine = get_engine(BASE_DIR, self._argos_translate, logger=log)
        try:
            self._engine.warmup(None)
        except Exception as exc:
            log(f"[AUDIO TRANSLATION] warmup skipped: {exc}")

    def _argos_translate(self, text: str) -> str:
        try:
            if self._argos_translation is None:
                import argostranslate.translate

                installed = argostranslate.translate.get_installed_languages()
                source = next((lang for lang in installed if getattr(lang, "code", "") == "en"), None)
                target = next((lang for lang in installed if getattr(lang, "code", "") == "id"), None)
                self._argos_translation = source.get_translation(target) if source and target else False
            if self._argos_translation:
                return str(self._argos_translation.translate(text) or "").strip()
        except Exception as exc:
            log(f"[AUDIO TRANSLATION] Argos fallback unavailable: {exc}")
        return str(text or "").strip()

    def engine_label(self) -> str:
        if self.safe_mode:
            return "argos_recovery"
        if self._engine is not None and getattr(self._engine, "ct2", None) is not None:
            return "ct2_fast"
        return "argos_offline"

    def _translate_clause(self, clause: str) -> tuple[str, dict]:
        output, meta = self._engine.translate(clause, bridge=None)
        meta = dict(meta or {})
        clean = " ".join(str(output or "").strip().split())
        held = bool(meta.get("overlay_hold")) or "[Terjemahan ditahan:" in clean
        if held:
            recovered = " ".join(str(self._argos_translate(clause) or "").strip().split())
            if recovered and recovered.casefold() != clause.casefold():
                meta["engine"] = "argos_direct_audio_recovery"
                meta["audio_guard_recovered"] = True
                meta["overlay_hold"] = False
                return recovered, meta
        return clean or clause, meta

    def _prune_segments(self) -> None:
        if len(self._segments) <= self._segment_limit:
            return
        oldest = sorted(self._segments.items(), key=lambda item: item[1].last_used)
        for key, _state in oldest[: max(1, len(self._segments) - self._segment_limit)]:
            self._segments.pop(key, None)

    def translate(self, text: str, *, segment_id: str = "", stable: bool = False) -> tuple[str, dict]:
        if self._engine is None:
            return text, {"engine": "source_fallback", "cache": "MISS"}
        source = " ".join(str(text or "").strip().split())
        clauses = split_audio_clauses(source)
        key = str(segment_id or "__default__")
        previous = self._segments.get(key)

        if previous is not None and previous.source.casefold() == source.casefold():
            meta = dict(previous.meta)
            meta.update({
                "audio_incremental": True,
                "audio_reused_clauses": len(previous.clauses),
                "audio_translated_clauses": 0,
                "cache": "HIT_SEGMENT",
            })
            previous.last_used = time.monotonic()
            return " ".join(previous.outputs).strip() or source, meta

        reuse = 0
        if previous is not None:
            maximum = min(len(previous.clauses), len(clauses))
            while reuse < maximum and previous.clauses[reuse].casefold() == clauses[reuse].casefold():
                reuse += 1

        outputs = list(previous.outputs[:reuse]) if previous is not None else []
        metas: list[dict] = []

        # When a single live clause only grows at the end, preserve the already
        # translated prefix and translate the new tail. This prevents Argos from
        # reprocessing a whole paragraph on every 300 ms ASR revision.
        delta_mode = False
        if (
            previous is not None
            and len(clauses) == 1
            and len(previous.clauses) == 1
            and source.casefold().startswith(previous.source.casefold())
            and len(source) > len(previous.source)
            and previous.outputs
        ):
            suffix = source[len(previous.source):].strip(" ,.;:-")
            if len(suffix.split()) >= 2:
                tail_output, tail_meta = self._translate_clause(suffix)
                outputs = [" ".join([previous.outputs[0], tail_output]).strip()]
                metas = [tail_meta]
                reuse = 1
                delta_mode = True

        if not delta_mode:
            for clause in clauses[reuse:]:
                output, meta = self._translate_clause(clause)
                outputs.append(output)
                metas.append(meta)

        engines = [str(item.get("engine") or self.engine_label()) for item in metas]
        caches = [str(item.get("cache") or "MISS") for item in metas]
        if not engines and previous is not None:
            engines = [str(previous.meta.get("engine") or self.engine_label())]
        merged = dict(metas[-1] if metas else (previous.meta if previous is not None else {}))
        merged["engine"] = engines[0] if engines and len(set(engines)) == 1 else "mixed_audio_clauses"
        merged["cache"] = "HIT" if caches and all(item.startswith("HIT") for item in caches) else ("HIT_SEGMENT" if not metas else "MISS")
        merged["audio_clause_count"] = len(clauses)
        merged["audio_clause_engines"] = engines
        merged["audio_preserve_all_clauses"] = True
        merged["audio_incremental"] = True
        merged["audio_reused_clauses"] = reuse
        merged["audio_translated_clauses"] = 1 if delta_mode else max(0, len(clauses) - reuse)
        merged["audio_delta_mode"] = delta_mode
        merged["audio_segment_final"] = bool(stable)

        self._segments[key] = SegmentTranslationState(
            source=source,
            clauses=list(clauses),
            outputs=list(outputs),
            meta=dict(merged),
            last_used=time.monotonic(),
        )
        self._prune_segments()
        return " ".join(outputs).strip() or source, merged


def process_request(translator: AudioTranslator, request: Dict[str, Any]) -> None:
    generation = int(request.get("generation_id", 0) or 0)
    source = " ".join(str(request.get("text") or "").strip().split())
    if not source:
        emit_event("error", stage="request", generation_id=generation, message="empty transcript")
        return
    emit_event(
        "state",
        state="TRANSLATING",
        generation_id=generation,
        safe_mode=translator.safe_mode,
        engine=translator.engine_label(),
    )
    started = time.perf_counter()
    try:
        output, meta = translator.translate(
            source,
            segment_id=str(request.get("segment_id") or ""),
            stable=bool(request.get("stable")),
        )
        translation_ms = int((time.perf_counter() - started) * 1000)
        request_payload = dict(request)
        request_payload.pop("type", None)
        request_payload.pop("text", None)
        emit_event(
            "translation",
            **request_payload,
            text=source,
            translation=output,
            translation_ms=translation_ms,
            total_ms=int(request.get("asr_ms", 0) or 0) + translation_ms,
            translation_engine=str(meta.get("engine") or translator.engine_label()),
            cache=str(meta.get("cache") or "MISS"),
            translation_meta=meta,
            translation_safe_mode=translator.safe_mode,
        )
    except Exception as exc:
        translation_ms = int((time.perf_counter() - started) * 1000)
        request_payload = dict(request)
        request_payload.pop("type", None)
        request_payload.pop("text", None)
        emit_event(
            "translation",
            **request_payload,
            text=source,
            translation=source,
            translation_ms=translation_ms,
            total_ms=int(request.get("asr_ms", 0) or 0) + translation_ms,
            translation_engine="source_fallback",
            cache="MISS",
            translation_error=str(exc),
            translation_safe_mode=translator.safe_mode,
        )


def iter_requests(lines: Iterable[str]) -> Iterable[Dict[str, Any]]:
    for raw in lines:
        line = str(raw or "").strip()
        if not line:
            continue
        try:
            request = json.loads(line)
        except Exception as exc:
            emit_event("error", stage="protocol", message=f"invalid JSON request: {exc}")
            continue
        if isinstance(request, dict):
            yield request
        else:
            emit_event("error", stage="protocol", message="request must be a JSON object")


def main(argv: Optional[Iterable[str]] = None) -> int:
    del argv
    try:
        faulthandler.enable(all_threads=True)
    except Exception:
        pass
    safe_mode = configure_native_runtime()
    emit_event(
        "state",
        state="TRANSLATOR_LOADING",
        safe_mode=safe_mode,
        packed_gemm=False,
        threads=int(os.environ.get("OMP_NUM_THREADS", "1") or 1),
    )
    try:
        translator = AudioTranslator(safe_mode)
    except Exception as exc:
        emit_event("error", stage="translator_init", safe_mode=safe_mode, message=str(exc))
        return 1
    emit_event(
        "state",
        state="TRANSLATOR_READY",
        safe_mode=safe_mode,
        engine=translator.engine_label(),
        packed_gemm=False,
        threads=int(os.environ.get("OMP_NUM_THREADS", "1") or 1),
    )
    for request in iter_requests(sys.stdin):
        request_type = str(request.get("type") or "").lower()
        if request_type == "shutdown":
            break
        if request_type != "translate":
            emit_event("error", stage="protocol", message=f"unsupported request type: {request_type or '-'}")
            continue
        process_request(translator, request)
    emit_event("state", state="TRANSLATOR_STOPPED", safe_mode=safe_mode, engine=translator.engine_label())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
