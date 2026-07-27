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

from app.audio.argos_offline import (
    ArgosOfflineError,
    configure_argos_offline_environment,
    get_translation_pair,
)


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
    # Audio segments are already short clauses. Force Argos to MiniSBD so its
    # first translation remains offline and never starts a Stanza resource
    # download. Keep the bridge on CPU to avoid competing with ASR for VRAM.
    configure_argos_offline_environment()
    # v9.0.3: safe mode reduces thread pressure but keeps the validated CT2
    # engine available. Argos recovery is opt-in because switching the whole
    # session to Argos after one timeout caused minute-long subtitle stalls.
    allow_argos_recovery = str(os.environ.get("ORT_AUDIO_ALLOW_ARGOS_RECOVERY", "0")).lower() in {
        "1", "true", "yes", "on"
    }
    if safe_mode and allow_argos_recovery:
        os.environ["ORT_DISABLE_CT2"] = "1"
    else:
        os.environ.pop("ORT_DISABLE_CT2", None)
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
        self._argos_pairs: dict[tuple[str, str], Any] = {}
        self._engine = None
        self._segments: dict[str, SegmentTranslationState] = {}
        self._segment_limit = 32
        self._source_bridge_cache: dict[tuple[str, str], str] = {}
        self._source_bridge_cache_limit = 256
        self._source_bridge_required = str(os.environ.get("ORT_AUDIO_ASR_PROVIDER", "") or "").strip().lower() in {
            "reazonspeech_k2", "sensevoice_small"
        }
        self._source_bridge_ready = False
        self._source_bridge_warmup_ms = 0
        self._init_engine()

    def _init_engine(self) -> None:
        from translation_engine import get_engine

        self._engine = get_engine(BASE_DIR, self._argos_translate, logger=log)
        try:
            self._engine.warmup(None)
        except Exception as exc:
            log(f"[AUDIO TRANSLATION] warmup skipped: {exc}")
        self._prepare_source_bridge()

    def _argos_pair(self, source_code: str, target_code: str):
        key = (str(source_code or "").lower(), str(target_code or "").lower())
        if key in self._argos_pairs:
            return self._argos_pairs[key]
        try:
            value, info = get_translation_pair(key[0], key[1])
            log(
                f"[AUDIO TRANSLATION] Argos pair {key[0]}->{key[1]} ready | "
                f"chunker={info.chunk_type} | device={info.device_type}"
            )
        except ArgosOfflineError as exc:
            log(f"[AUDIO TRANSLATION] Argos pair {key[0]}->{key[1]} unavailable: {exc}")
            value = False
        self._argos_pairs[key] = value
        return value

    def _argos_translate_pair(self, text: str, source_code: str, target_code: str) -> str:
        translator = self._argos_pair(source_code, target_code)
        if translator:
            started = time.perf_counter()
            try:
                output = str(translator.translate(text) or "").strip()
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                if elapsed_ms >= 1000:
                    log(f"[AUDIO TRANSLATION] bridge {source_code}->{target_code} slow | {elapsed_ms}ms")
                return output
            except Exception as exc:
                log(f"[AUDIO TRANSLATION] Argos {source_code}->{target_code} failed: {exc}")
        return ""

    def _prepare_source_bridge(self) -> None:
        if not self._source_bridge_required:
            return
        started = time.perf_counter()
        translator = self._argos_pair("ja", "en")
        if not translator:
            raise RuntimeError(
                "Japanese preview bridge ja->en tidak tersedia pada runtime Audio aktif. "
                "Jalankan Siapkan model yang dipilih untuk CPU/GPU yang digunakan."
            )
        sample = self._argos_translate_pair("これはテストです", "ja", "en")
        if not sample or sample == "これはテストです":
            raise RuntimeError("Japanese preview bridge ja->en gagal functional warm-up")
        self._source_bridge_ready = True
        self._source_bridge_warmup_ms = int((time.perf_counter() - started) * 1000)
        self._source_bridge_cache[("ja", "これはテストです")] = sample
        log(
            f"[AUDIO TRANSLATION] Japanese preview bridge ready | "
            f"engine=argos_ja_en | warmup_ms={self._source_bridge_warmup_ms} | sample={sample}"
        )

    def _bridge_to_english(self, text: str, source_code: str) -> str:
        clean = " ".join(str(text or "").strip().split())
        key = (str(source_code or "").lower(), clean)
        cached = self._source_bridge_cache.get(key)
        if cached is not None:
            return cached
        output = " ".join(self._argos_translate_pair(clean, key[0], "en").split())
        if output:
            if len(self._source_bridge_cache) >= self._source_bridge_cache_limit:
                self._source_bridge_cache.pop(next(iter(self._source_bridge_cache)), None)
            self._source_bridge_cache[key] = output
        return output

    def _argos_translate(self, text: str) -> str:
        output = self._argos_translate_pair(text, "en", "id")
        return output or str(text or "").strip()

    def engine_label(self) -> str:
        if self._engine is not None and getattr(self._engine, "ct2", None) is not None:
            return "ct2_safe" if self.safe_mode else "ct2_fast"
        return "argos_recovery" if self.safe_mode else "argos_offline"

    def _translate_clause(self, clause: str, source_language: str = "en") -> tuple[str, dict]:
        source_code = str(source_language or "en").lower().split("-", 1)[0]
        if source_code != "en":
            # ReazonSpeech/SenseVoice return Japanese transcription. Always build
            # the English preview first, then send that English text through the
            # validated CT2 EN->ID engine. Do not attempt a hidden JA->ID Argos
            # composite because its first lazy load can exceed the watchdog and
            # it provides no English preview for the overlay.
            bridge = self._bridge_to_english(clause, source_code)
            if not bridge or bridge.casefold() == clause.casefold():
                return clause, {
                    "engine": f"{source_code}_bridge_unavailable",
                    "source_language": source_code,
                    "bridge_language": "-",
                    "preview_language": "-",
                    "translation_unavailable": True,
                    "cache": "MISS",
                }
            output, meta = self._engine.translate(bridge, bridge=None)
            meta = dict(meta or {})
            meta.update({
                "source_language": source_code,
                "bridge_language": "en",
                "bridge_text": bridge,
                "preview_text": bridge,
                "preview_language": "en",
                "target_language": "id",
                "bridge_engine": f"argos_{source_code}_en",
                "source_bridge_ready": self._source_bridge_ready,
                "source_bridge_warmup_ms": self._source_bridge_warmup_ms,
            })
            clean = " ".join(str(output or "").strip().split())
            return clean or bridge, meta

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

    def translate(
        self,
        text: str,
        *,
        segment_id: str = "",
        stable: bool = False,
        source_language: str = "en",
    ) -> tuple[str, dict]:
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
                tail_output, tail_meta = self._translate_clause(suffix, source_language)
                outputs = [" ".join([previous.outputs[0], tail_output]).strip()]
                metas = [tail_meta]
                reuse = 1
                delta_mode = True

        if not delta_mode:
            for clause in clauses[reuse:]:
                output, meta = self._translate_clause(clause, source_language)
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
        bridge_parts = [str(item.get("bridge_text") or item.get("preview_text") or "").strip() for item in metas]
        bridge_parts = [item for item in bridge_parts if item]
        if bridge_parts:
            prior_bridge = ""
            if previous is not None and reuse > 0:
                prior_bridge = str(previous.meta.get("bridge_text") or previous.meta.get("preview_text") or "").strip()
            combined_bridge = " ".join([item for item in [prior_bridge, *bridge_parts] if item]).strip()
            merged["bridge_text"] = combined_bridge
            merged["preview_text"] = combined_bridge
            merged["preview_language"] = "en"

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
            source_language=str(request.get("bridge_language") or request.get("source_language") or "en"),
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
        source_bridge_required=translator._source_bridge_required,
        source_bridge_ready=translator._source_bridge_ready,
        source_bridge_warmup_ms=translator._source_bridge_warmup_ms,
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
