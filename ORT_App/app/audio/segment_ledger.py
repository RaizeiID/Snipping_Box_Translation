from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Deque, Optional


@dataclass(frozen=True)
class SegmentTask:
    segment_id: str
    path: str
    kind: str
    audio_seconds: float
    created_at: float

    @classmethod
    def from_payload(cls, payload: dict) -> "SegmentTask":
        return cls(
            segment_id=str(payload.get("segment_id") or ""),
            path=str(payload.get("path") or ""),
            kind=str(payload.get("kind") or "npy"),
            audio_seconds=float(payload.get("audio_seconds", 0.0) or 0.0),
            created_at=float(payload.get("created_at", 0.0) or 0.0),
        )

    def as_dict(self) -> dict:
        return {
            "segment_id": self.segment_id,
            "path": self.path,
            "kind": self.kind,
            "audio_seconds": self.audio_seconds,
            "created_at": self.created_at,
        }


class SegmentLedger:
    def __init__(self, max_pending: int = 3):
        self.max_pending = max(1, int(max_pending))
        self.pending: Deque[SegmentTask] = deque()
        self.inflight: Optional[SegmentTask] = None

    def submit(self, task: SegmentTask) -> Optional[SegmentTask]:
        if not task.segment_id or not task.path:
            raise ValueError("segment_id and path are required")
        if self.inflight and self.inflight.segment_id == task.segment_id:
            return None
        if any(item.segment_id == task.segment_id for item in self.pending):
            return None
        dropped = None
        if len(self.pending) >= self.max_pending:
            dropped = self.pending.popleft()
        self.pending.append(task)
        return dropped

    def dispatch_next(self) -> Optional[SegmentTask]:
        if self.inflight is not None or not self.pending:
            return None
        self.inflight = self.pending.popleft()
        return self.inflight

    def acknowledge(self, segment_id: str) -> Optional[SegmentTask]:
        if self.inflight is None or self.inflight.segment_id != str(segment_id):
            return None
        completed = self.inflight
        self.inflight = None
        return completed

    def requeue_inflight(self) -> Optional[SegmentTask]:
        if self.inflight is None:
            return None
        task = self.inflight
        self.inflight = None
        self.pending.appendleft(task)
        return task

    def clear(self) -> list[SegmentTask]:
        values = list(self.pending)
        self.pending.clear()
        if self.inflight is not None:
            values.append(self.inflight)
            self.inflight = None
        return values

