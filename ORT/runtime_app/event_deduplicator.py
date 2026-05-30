"""ORT Translation v7.9 lightweight event de-duplicator."""
from __future__ import annotations
from collections import OrderedDict
from typing import Any, Dict, Iterable, Iterator

class EventDeduplicator:
    def __init__(self, max_keys: int = 20000):
        self.max_keys = max_keys
        self._seen: OrderedDict[str, None] = OrderedDict()

    def seen(self, key: str) -> bool:
        if not key: return False
        if key in self._seen:
            self._seen.move_to_end(key)
            return True
        self._seen[key] = None
        if len(self._seen) > self.max_keys:
            self._seen.popitem(last=False)
        return False

def iter_unique_events(events: Iterable[Dict[str, Any]]) -> Iterator[Dict[str, Any]]:
    dedupe = EventDeduplicator()
    for ev in events:
        key = str(ev.get("event_id") or "")
        if not key:
            payload = ev.get("payload") if isinstance(ev.get("payload"), dict) else {}
            key = "|".join([str(ev.get("type") or ""), str(ev.get("source_module") or ""), str(payload.get("source") or payload.get("text") or payload.get("line") or "")[:160], str(payload.get("translation") or "")[:160]])
        if dedupe.seen(key):
            continue
        yield ev
