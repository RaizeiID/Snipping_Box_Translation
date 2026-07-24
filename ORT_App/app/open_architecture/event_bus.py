from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass(frozen=True)
class ArchitectureEvent:
    event_type: str
    payload: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """Small in-process event bus reserved for Open Architecture providers."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: dict[str, list[Callable[[ArchitectureEvent], None]]] = defaultdict(list)

    def subscribe(self, event_type: str, callback: Callable[[ArchitectureEvent], None]) -> Callable[[], None]:
        token = str(event_type)
        with self._lock:
            self._subscribers[token].append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers.get(token, []):
                    self._subscribers[token].remove(callback)

        return unsubscribe

    def publish(self, event_type: str, **payload: Any) -> ArchitectureEvent:
        event = ArchitectureEvent(str(event_type), dict(payload))
        with self._lock:
            callbacks = tuple(self._subscribers.get(event.event_type, ())) + tuple(self._subscribers.get("*", ()))
        for callback in callbacks:
            callback(event)
        return event
