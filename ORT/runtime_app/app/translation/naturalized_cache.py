from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from app.translation.fuzzy_cache_normalizer import normalize_cache_key
except Exception:
    def normalize_cache_key(text: str) -> str:
        return " ".join(str(text or "").lower().split())

# v8.6: small persistent cache for already-naturalized Indonesian output.
# It is separate from the main scoped cache so raw CT2/Argos outputs do not overwrite
# polished Lite/Normal/Fast IDN results and vice versa.  A cache version is part of
# the key so improved quality rules do not get hidden by older v8.5.x cache entries.

class NaturalizedCache:
    def __init__(self, base_dir: str | os.PathLike[str], *, game: str = "CUSTOM", model_key: str = "", mode: str = "lite_balanced", max_entries: int = 6000, version: str | None = None) -> None:
        self.base_dir = Path(base_dir).resolve()
        self.game = str(game or "CUSTOM").lower()
        self.model_key = str(model_key or "").lower()
        self.mode = str(mode or "lite_balanced").lower()
        self.version = str(version or os.environ.get("ORT_IDN_CACHE_VERSION", "v8_6")).lower()
        self.max_entries = int(max_entries or 6000)
        safe_version = "".join(c if c.isalnum() or c in "_-" else "_" for c in self.version)
        self.path = self.base_dir / "cache" / f"naturalized_idn_cache_{safe_version}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, Dict[str, Any]] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    self._data = {str(k): v for k, v in data.items() if isinstance(v, dict)}
        except Exception:
            self._data = {}

    def _key(self, source: str) -> str:
        return f"{self.version}|{self.game}|{self.model_key}|{self.mode}|{normalize_cache_key(source)}"

    def get(self, source: str) -> Optional[str]:
        key = self._key(source)
        item = self._data.get(key)
        if not item:
            return None
        out = str(item.get("translation") or "").strip()
        if not out:
            return None
        try:
            from app.identity.speaker_registry import has_internal_entity_token
            if has_internal_entity_token(out):
                return None
        except Exception:
            pass
        try:
            from app.translation.faithfulness_gate import assess_translation
            if not assess_translation(str(source or ""), out, progressive=False).allowed:
                return None
        except Exception:
            pass
        item["hits"] = int(item.get("hits") or 0) + 1
        item["last_hit"] = time.time()
        self._dirty = True
        return out

    def set(self, source: str, translation: str, *, engine: str = "") -> None:
        src = str(source or "").strip()
        out = str(translation or "").strip()
        if len(src) < 2 or len(out) < 2:
            return
        try:
            from app.identity.speaker_registry import has_internal_entity_token
            if has_internal_entity_token(out):
                return
        except Exception:
            pass
        try:
            from app.translation.faithfulness_gate import assess_translation
            if not assess_translation(src, out, progressive=False).allowed:
                return
        except Exception:
            pass
        # Avoid caching unstable ellipsis/partial typing fragments.
        if src.endswith("...") or out.endswith("..."):
            return
        key = self._key(src)
        self._data[key] = {
            "source": src,
            "translation": out,
            "engine": str(engine or ""),
            "game": self.game,
            "model_key": self.model_key,
            "mode": self.mode,
            "version": self.version,
            "updated": time.time(),
            "hits": int(self._data.get(key, {}).get("hits") or 0),
        }
        self._dirty = True
        if len(self._data) > self.max_entries:
            self._trim()

    def _trim(self) -> None:
        items = sorted(self._data.items(), key=lambda kv: float(kv[1].get("last_hit") or kv[1].get("updated") or 0), reverse=True)
        self._data = dict(items[: self.max_entries])
        self._dirty = True

    def flush(self) -> None:
        if not self._dirty:
            return
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
        self._dirty = False

    def stats(self) -> dict[str, Any]:
        return {"path": str(self.path), "entries": len(self._data), "mode": self.mode, "version": self.version, "model_key": self.model_key}
