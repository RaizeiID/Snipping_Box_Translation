from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional


AUDIO_ENGINES = {"local", "azure", "azure_fallback"}
AUDIO_USAGES = {"live_media", "conversation"}
REALTIME_PROFILES = {"speed", "normal", "accurate"}


def normalize_audio_engine(value: str) -> str:
    key = str(value or "azure_fallback").strip().lower().replace("-", "_")
    aliases = {
        "cloud": "azure",
        "cloud_fallback": "azure_fallback",
        "azure_local": "azure_fallback",
        "hybrid_cloud": "azure_fallback",
    }
    key = aliases.get(key, key)
    return key if key in AUDIO_ENGINES else "azure_fallback"


def normalize_audio_usage(value: str) -> str:
    key = str(value or "live_media").strip().lower().replace("-", "_")
    aliases = {
        "media": "live_media",
        "streaming": "live_media",
        "live": "live_media",
        "video": "live_media",
        "conversation_mode": "conversation",
    }
    key = aliases.get(key, key)
    return key if key in AUDIO_USAGES else "live_media"


def normalize_realtime_profile(value: str) -> str:
    key = str(value or "normal").strip().lower().replace("-", "_")
    aliases = {
        "instant": "speed",
        "fast": "speed",
        "balanced": "normal",
        "quality": "accurate",
    }
    key = aliases.get(key, key)
    return key if key in REALTIME_PROFILES else "normal"


def normalize_source_locale(value: str) -> str:
    key = str(value or "").strip().lower().replace("_", "-")
    mapping = {
        "ja": "ja-JP",
        "ja-jp": "ja-JP",
        "en": "en-US",
        "en-us": "en-US",
        "zh": "zh-CN",
        "zh-cn": "zh-CN",
        "ko": "ko-KR",
        "ko-kr": "ko-KR",
        "id": "id-ID",
        "id-id": "id-ID",
    }
    return mapping.get(key, str(value or "").strip())


def normalize_target_language(value: str) -> str:
    key = str(value or "id").strip().lower().replace("_", "-")
    if key in {"id", "id-id"}:
        return "id"
    return key.split("-", 1)[0] if key else "id"


@dataclass(frozen=True)
class LiveMediaPolicy:
    profile: str
    segmentation_silence_ms: int
    segmentation_maximum_ms: int
    stable_partial_threshold: int
    initial_silence_ms: int
    connection_timeout_s: float
    final_drain_timeout_s: float
    final_quiet_period_s: float
    minimum_interim_interval_s: float
    audio_chunk_ms: int

    def as_dict(self) -> dict:
        return {
            "profile": self.profile,
            "segmentation_silence_ms": self.segmentation_silence_ms,
            "segmentation_maximum_ms": self.segmentation_maximum_ms,
            "stable_partial_threshold": self.stable_partial_threshold,
            "initial_silence_ms": self.initial_silence_ms,
            "connection_timeout_s": self.connection_timeout_s,
            "final_drain_timeout_s": self.final_drain_timeout_s,
            "final_quiet_period_s": self.final_quiet_period_s,
            "minimum_interim_interval_s": self.minimum_interim_interval_s,
            "audio_chunk_ms": self.audio_chunk_ms,
        }


def resolve_live_media_policy(usage: str, source_locale: str, profile: str) -> LiveMediaPolicy:
    usage_key = normalize_audio_usage(usage)
    profile_key = normalize_realtime_profile(profile)
    japanese = normalize_source_locale(source_locale).lower() == "ja-jp"

    if usage_key == "conversation":
        return LiveMediaPolicy(
            profile=profile_key,
            segmentation_silence_ms=650,
            segmentation_maximum_ms=15000,
            stable_partial_threshold=2,
            initial_silence_ms=10000,
            connection_timeout_s=10.0,
            final_drain_timeout_s=3.0,
            final_quiet_period_s=0.9,
            minimum_interim_interval_s=0.18,
            audio_chunk_ms=20,
        )

    if profile_key == "speed":
        return LiveMediaPolicy(
            profile=profile_key,
            segmentation_silence_ms=280 if japanese else 320,
            segmentation_maximum_ms=6500 if japanese else 7500,
            stable_partial_threshold=1,
            initial_silence_ms=8000,
            connection_timeout_s=8.0,
            final_drain_timeout_s=2.6,
            final_quiet_period_s=0.55,
            minimum_interim_interval_s=0.10,
            audio_chunk_ms=20,
        )
    if profile_key == "accurate":
        return LiveMediaPolicy(
            profile=profile_key,
            segmentation_silence_ms=480 if japanese else 520,
            segmentation_maximum_ms=12000,
            stable_partial_threshold=2,
            initial_silence_ms=10000,
            connection_timeout_s=10.0,
            final_drain_timeout_s=3.5,
            final_quiet_period_s=1.0,
            minimum_interim_interval_s=0.18,
            audio_chunk_ms=20,
        )
    return LiveMediaPolicy(
        profile=profile_key,
        segmentation_silence_ms=350 if japanese else 400,
        segmentation_maximum_ms=8500 if japanese else 10000,
        stable_partial_threshold=1,
        initial_silence_ms=9000,
        connection_timeout_s=9.0,
        final_drain_timeout_s=3.0,
        final_quiet_period_s=0.75,
        minimum_interim_interval_s=0.14,
        audio_chunk_ms=20,
    )


@dataclass(frozen=True)
class CloudEngineDecision:
    requested: str
    effective: str
    ready: bool
    reason: str
    cloud_ready: bool
    local_ready: bool

    def as_dict(self) -> dict:
        return {
            "requested": self.requested,
            "effective": self.effective,
            "ready": self.ready,
            "reason": self.reason,
            "cloud_ready": self.cloud_ready,
            "local_ready": self.local_ready,
        }


def resolve_cloud_engine(requested: str, cloud_ready: bool, local_ready: bool) -> CloudEngineDecision:
    engine = normalize_audio_engine(requested)
    cloud = bool(cloud_ready)
    local = bool(local_ready)
    if engine == "local":
        return CloudEngineDecision(engine, "local_live", local, "LOCAL_REALTIME_READY" if local else "LOCAL_NOT_READY", cloud, local)
    if engine == "azure":
        return CloudEngineDecision(engine, "azure", cloud, "AZURE_READY" if cloud else "AZURE_NOT_READY", cloud, local)
    if cloud:
        return CloudEngineDecision(
            engine,
            "azure",
            True,
            "AZURE_WITH_LOCAL_FALLBACK_READY" if local else "AZURE_READY_LOCAL_FALLBACK_UNAVAILABLE",
            True,
            local,
        )
    if local:
        return CloudEngineDecision(engine, "local_live", True, "AZURE_UNAVAILABLE_LOCAL_REALTIME", False, True)
    return CloudEngineDecision(engine, "unavailable", False, "AZURE_AND_LOCAL_NOT_READY", False, False)


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


class LiveSubtitleStabilizer:
    """Coalesces Azure partial results into a phone-style live subtitle line.

    Every accepted interim replaces the same overlay line. Rapid callback bursts
    are throttled, but the newest partial is accepted as soon as the interval is
    reached. Finals are deduplicated by result id, not just by sentence text, so
    two speakers may legitimately repeat the same short phrase.
    """

    def __init__(self, minimum_interim_interval: float = 0.14, duplicate_window: float = 1.25):
        self.minimum_interim_interval = max(0.05, float(minimum_interim_interval))
        self.duplicate_window = max(0.4, float(duplicate_window))
        self._active_result_id = ""
        self._last_interim_source = ""
        self._last_interim_translation = ""
        self._last_interim_at = 0.0
        self._final_history: Deque[tuple[str, str, float]] = deque(maxlen=20)
        self._completed_result_ids: Deque[tuple[str, float]] = deque(maxlen=20)
        self._sequence = 0
        self._revision = 0

    def accept(self, event: dict, now: Optional[float] = None) -> Optional[dict]:
        event_type = str(event.get("type") or event.get("state") or "").strip().lower()
        if event_type not in {"interim", "final"}:
            return None
        source = _clean_text(event.get("source") or event.get("text"))
        translation = _clean_text(event.get("translation"))
        if not source and not translation:
            return None
        timestamp = time.monotonic() if now is None else float(now)
        result_id = str(event.get("result_id") or event.get("segment_id") or "")

        while self._completed_result_ids and timestamp - self._completed_result_ids[0][1] > self.duplicate_window * 2:
            self._completed_result_ids.popleft()
        if event_type == "interim":
            if result_id and any(previous_id == result_id for previous_id, _ in self._completed_result_ids):
                return None
            changed = source != self._last_interim_source or translation != self._last_interim_translation
            if not changed:
                return None
            if timestamp - self._last_interim_at < self.minimum_interim_interval:
                return None
            if result_id and result_id != self._active_result_id:
                self._revision = 0
            self._active_result_id = result_id or self._active_result_id
            self._last_interim_source = source
            self._last_interim_translation = translation
            self._last_interim_at = timestamp
            self._revision += 1
        else:
            normalized = translation.casefold() or source.casefold()
            while self._final_history and timestamp - self._final_history[0][2] > self.duplicate_window:
                self._final_history.popleft()
            duplicate = False
            if result_id:
                duplicate = any(previous_id == result_id for previous_id, _text, _at in self._final_history)
            else:
                duplicate = any(not previous_id and previous_text == normalized for previous_id, previous_text, _at in self._final_history)
            if duplicate:
                return None
            self._final_history.append((result_id, normalized, timestamp))
            if result_id:
                self._completed_result_ids.append((result_id, timestamp))
            if not result_id or self._active_result_id == result_id:
                self._active_result_id = ""
                self._last_interim_source = ""
                self._last_interim_translation = ""
                self._last_interim_at = 0.0
            self._revision = 0

        self._sequence += 1
        return {
            **event,
            "type": event_type,
            "source": source,
            "translation": translation,
            "stable": event_type == "final",
            "display_sequence": self._sequence,
            "display_revision": self._revision,
        }


class CloudFallbackLatch:
    def __init__(self):
        self._activated = False
        self._reason = ""
        self._replay_path = ""

    @property
    def activated(self) -> bool:
        return self._activated

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def replay_path(self) -> str:
        return self._replay_path

    def activate(self, reason: str, replay_path: str = "") -> Optional[dict]:
        if self._activated:
            return None
        self._activated = True
        self._reason = str(reason or "CLOUD_UNAVAILABLE")
        self._replay_path = str(replay_path or "")
        return {
            "type": "CLOUD_LOCAL_FAILOVER",
            "reason": self._reason,
            "replay_path": self._replay_path,
            "effective_engine": "local_fallback",
        }
