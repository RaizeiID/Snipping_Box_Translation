"""ORT Translation v8.7.6 scoped cache store with identity-safe namespace versioning.

Scoped cache is the primary cache and adds guardrails so cache files do
not grow into another giant translation_memory.json:
- per game/model JSON file
- read-only legacy warmup
- size/entry pruning
- OCR-noise cache filtering
- migration helper hook for legacy cache
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Dict, Optional, Tuple

from status_manager import write_status as _write_status

try:
    from app.translation.fuzzy_cache_normalizer import normalize_cache_key
except Exception:  # pragma: no cover
    def normalize_cache_key(text: str) -> str:
        return str(text or "").strip().lower()

ROOT = Path(__file__).resolve().parent
_NOISE_RE = re.compile(r"^[\W\d_\s]+$", re.UNICODE)
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_LATIN_RE = re.compile(r"[A-Za-z]")


def _safe_token(value: str, default: str = "custom") -> str:
    value = (value or default).strip().lower()
    value = re.sub(r"[^a-z0-9_\-]+", "_", value)
    return value.strip("_") or default


def should_cache_text(text: str, translation: str = "") -> Tuple[bool, str]:
    text = (text or "").strip()
    translation = (translation or "").strip()
    if len(text) < int(os.environ.get("ORT_CACHE_MIN_SOURCE_LEN", "2")):
        return False, "source_too_short"
    if len(text) > int(os.environ.get("ORT_CACHE_MAX_SOURCE_LEN", "260")):
        return False, "source_too_long"
    if translation and len(translation) > int(os.environ.get("ORT_CACHE_MAX_TARGET_LEN", "600")):
        return False, "target_too_long"
    if _NOISE_RE.match(text):
        return False, "noise_only"
    if not (_CJK_RE.search(text) or _LATIN_RE.search(text)):
        return False, "no_language_signal"
    low = text.lower()
    ui_noise = ("loading", "connecting", "press any key", "fps", "ms", "ping", "uid", "version")
    if len(text) <= 24 and any(tok in low for tok in ui_noise):
        return False, "ui_noise"
    if translation and text == translation and len(text) < 20:
        return False, "identity_short"
    if translation:
        try:
            from app.identity.speaker_registry import has_internal_entity_token
            if has_internal_entity_token(translation):
                return False, "residual_entity_token"
        except Exception:
            pass
    if os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD", "0") == "1":
        if len(text.strip()) < 18 and not text.rstrip().endswith((".", "!", "?", "…")):
            return False, "progressive_short_prefix"
    if os.environ.get("ORT_GFL_CACHE_STABLE_ONLY", "0") == "1":
        try:
            from app.games.gfl_profile import normalize_gfl_cache_text, is_non_dialog_text
            cleaned = normalize_gfl_cache_text(text)
            if is_non_dialog_text(cleaned):
                return False, "gfl_non_dialog_or_footer"
            # Do not let very short progressive frames fill cache with every typed prefix.
            if len(cleaned) < 12 and not cleaned.endswith(("!", "?", ".")):
                return False, "gfl_progressive_short"
        except Exception:
            pass
    return True, "ok"


class ScopedCacheStore:
    def __init__(self, base_dir: str | os.PathLike[str] | None = None, game: Optional[str] = None, model_key: Optional[str] = None, family: Optional[str] = None):
        self.base_dir = Path(base_dir or ROOT).resolve()
        self.cache_dir = self.base_dir / "cache"
        self.cache_dir.mkdir(exist_ok=True)
        self.game = _safe_token(game or os.environ.get("ORT_GAME_PROFILE", os.environ.get("ORT_GAME_OVERRIDE", "custom")))
        self.model_key = _safe_token(model_key or os.environ.get("ORT_MODEL_KEY", "model"), "model")
        self.family = _safe_token(family or os.environ.get("ORT_MODEL_GROUP", "normal"), "normal")
        self.namespace_version = _safe_token(os.environ.get("ORT_SCOPED_CACHE_VERSION", "v8_7_8_faithfulness_v2_strict_ct2_safe"), "v8_7_8_faithfulness_v2_strict_ct2_safe")
        self.path = self.cache_dir / f"translation_memory_{self.game}_{self.family}_{self.model_key}_{self.namespace_version}.json"
        self.legacy_path = self.base_dir / "translation_memory.json"
        self.max_entries = int(os.environ.get("ORT_CACHE_MAX_ENTRIES", "20000"))
        self.max_file_mb = float(os.environ.get("ORT_CACHE_MAX_FILE_MB", "18"))
        self.data: Dict[str, str] = {}
        self._touch: Dict[str, float] = {}
        self.dirty = False
        self._last_flush = 0.0
        self.load()

    def load(self) -> None:
        self.data = {}
        self._touch = {}
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8-sig"))
                if isinstance(raw, dict):
                    # Accept both old {src: dst} and future {items:{src:{text,ts}}}
                    items = raw.get("items") if isinstance(raw.get("items"), dict) else raw
                    for k, v in items.items():
                        if isinstance(v, dict):
                            val = str(v.get("translation", ""))
                            ts = float(v.get("ts", 0) or 0)
                        else:
                            val = str(v)
                            ts = 0.0
                        if isinstance(k, str) and val:
                            self.data[str(k)] = val
                            self._touch[str(k)] = ts
        except Exception:
            self.data = {}
            self._touch = {}
        # Optional lightweight legacy warmup: read only, do not rewrite legacy.
        if os.environ.get("ORT_LEGACY_CACHE_WARMUP", "0") == "1" and len(self.data) < 500:
            try:
                if self.legacy_path.exists():
                    raw = json.loads(self.legacy_path.read_text(encoding="utf-8-sig"))
                    if isinstance(raw, dict):
                        warm = 0
                        for k, v in raw.items():
                            if not isinstance(k, str) or not isinstance(v, str):
                                continue
                            ok, _ = should_cache_text(k, v)
                            if ok:
                                self.data.setdefault(k, v)
                                self._touch.setdefault(k, 0.0)
                                warm += 1
                            if warm >= int(os.environ.get("ORT_LEGACY_WARMUP_LIMIT", "1000")):
                                break
            except Exception:
                pass
        self._prune_if_needed(mark_dirty=False)
        self.write_status()

    def _keys_for(self, text: str) -> list[str]:
        raw = (text or "").strip()
        keys: list[str] = []
        if raw:
            keys.append(raw)
        if os.environ.get("ORT_FUZZY_CACHE_KEY", "1") != "0":
            try:
                norm = normalize_cache_key(raw)
                if norm and norm not in keys:
                    keys.append(norm)
            except Exception:
                pass
        return keys

    def get(self, text: str) -> str:
        for key in self._keys_for(text):
            hit = self.data.get(key, "")
            if hit:
                self._touch[key] = time.time()
                return hit
        return ""

    def set(self, text: str, translation: str) -> bool:
        text = (text or "").strip()
        translation = (translation or "").strip()
        ok, reason = should_cache_text(text, translation)
        if not ok:
            self.write_status(last_skip=reason)
            return False
        changed = False
        for key in self._keys_for(text):
            if not key:
                continue
            if self.data.get(key) == translation:
                self._touch[key] = time.time()
                continue
            self.data[key] = translation
            self._touch[key] = time.time()
            changed = True
        if changed:
            self.dirty = True
            self._prune_if_needed(mark_dirty=True)
        return changed

    def _estimated_size_mb(self) -> float:
        try:
            if self.path.exists():
                return self.path.stat().st_size / (1024 * 1024)
        except Exception:
            pass
        # rough in-memory estimate
        return sum(len(k) + len(v) for k, v in self.data.items()) / (1024 * 1024)

    def _prune_if_needed(self, mark_dirty: bool = True) -> None:
        over_entries = len(self.data) > self.max_entries
        over_size = self._estimated_size_mb() > self.max_file_mb
        if not (over_entries or over_size):
            return
        keep = max(1000, int(self.max_entries * 0.85))
        # Prefer keeping recently used/newer entries, then stable insertion fallback.
        ranked = sorted(self.data.keys(), key=lambda k: self._touch.get(k, 0.0), reverse=True)
        keep_set = set(ranked[:keep])
        for k in list(self.data.keys()):
            if k not in keep_set:
                self.data.pop(k, None)
                self._touch.pop(k, None)
        if mark_dirty:
            self.dirty = True

    def flush(self, force: bool = False) -> bool:
        now = time.time()
        if not force and (not self.dirty or now - self._last_flush < 2.0):
            return False
        self._prune_if_needed(mark_dirty=False)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            # Keep cache file as a flat {source: translation} mapping for backward compatibility.
            # Metadata is written to status/cache.json instead.
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, self.path)
            self.dirty = False
            self._last_flush = now
            self.write_status(last_flush=now)
            return True
        except Exception as exc:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            self.write_status(last_error=str(exc))
            return False

    def write_status(self, **extra) -> None:
        payload = {
            "version": "v8.7.2",
            "cache_file": str(self.path),
            "entries": len(self.data),
            "game": self.game,
            "model_key": self.model_key,
            "family": self.family,
            "max_entries": self.max_entries,
            "max_file_mb": self.max_file_mb,
            "estimated_size_mb": round(self._estimated_size_mb(), 3),
            "legacy_mode": "off_by_default_read_only_when_enabled",
            "pruning": "enabled",
            "fuzzy_cache_key": os.environ.get("ORT_FUZZY_CACHE_KEY", "1") != "0",
            "gfl_normalized_cache": os.environ.get("ORT_GFL_CACHE_NORMALIZED", "0") == "1",
            "gfl_stable_only": os.environ.get("ORT_GFL_CACHE_STABLE_ONLY", "0") == "1",
            "progressive_guard": os.environ.get("ORT_CACHE_PROGRESSIVE_GUARD", "0") == "1",
            "stable_final_cache_v2": os.environ.get("ORT_STABLE_FINAL_CACHE_V2", "1") != "0",
            "current_dialog_memo": os.environ.get("ORT_CURRENT_DIALOG_MEMO", "1") != "0",
            "legacy_vault_enabled": os.environ.get("ORT_ENABLE_LEGACY_VAULT", "0") == "1",
        }
        payload.update(extra)
        try:
            _write_status("cache", payload, self.base_dir)
        except Exception:
            pass


def get_scoped_cache(base_dir: str | os.PathLike[str] | None = None) -> ScopedCacheStore:
    global _CACHE
    try:
        return _CACHE
    except NameError:
        _CACHE = ScopedCacheStore(base_dir)
        return _CACHE
