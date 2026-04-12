#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TitanGameNameClassifier.py

UPDATE NOTES (2026-01-05)
- NEW: AUTO-LOCK mode (window title / process name) untuk deteksi game lebih cepat & akurat.
  - Env: TITAN_GAME_AUTOLOCK=1/0 (default 1)
  - Env: TITAN_GAME_AUTOLOCK_SOURCE=process|title|both (default both)
  - Env: TITAN_GAME_AUTOLOCK_INTERVAL_MS (default 900)
  - Mapping files (auto dibuat jika belum ada):
    - titan_game_process_map.json  (exe -> GAME_ID)
    - titan_game_title_map.json    (regex title -> GAME_ID)
  - Jika cocok, active_game akan di-lock (hard lock) dan dicetak ke terminal.
  - Saat game berubah (alt-tab ke game lain), autolock akan mengganti active_game otomatis.
- Existing: roster-based detection (names familiar) tetap ada sebagai fallback/konfirmasi.
- Existing: per-game name storage + anti cross-game pollution:
  - protect_text() hanya melabel nama roster + nama permanen dari active_game (jika sudah lock).
- Existing: UI support:
  - CLASSIFIER.short_label() => "GFL2" / "WUWA" / "AK" / "..."

Catatan:
- Auto-lock hanya aktif di Windows (os.name == "nt"). Di OS lain akan otomatis nonaktif.
"""

from __future__ import annotations

import json
import os
import re
import time
import threading
import fnmatch
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

def _env(name: str, default: str="") -> str:
    return (os.environ.get(name) or default).strip()

def _env_bool(name: str, default: bool=False) -> bool:
    v = _env(name, "")
    if not v:
        return default
    v = v.lower()
    if v in ("1","true","yes","y","on"): return True
    if v in ("0","false","no","n","off"): return False
    return default

def _env_int(name: str, default: int) -> int:
    try:
        return int((_env(name, "") or default))
    except Exception:
        return default

def _now() -> float:
    return time.time()

# -------------------------
# Name heuristics
# -------------------------
ROLE_WORDS = {
    "chief","commander","captain","boss","leader","director",
    "agent","operator","officer","doctor","dr","mr","mrs","ms",
    "teacher","professor","prof","sir","maam","ma'am","senpai"
}
ORG_HINTS = {"group","team","unit","department","dept","company","corp","inc","ltd","committee","bureau","agency","squad","platoon"}
ACRONYM_RE = re.compile(r"^[A-Z0-9]{2,}$")

def is_alias_or_title(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    low = n.lower()
    if low in ROLE_WORDS:
        return True
    if ACRONYM_RE.match(n):
        return True
    for h in ORG_HINTS:
        if f" {h}" in f" {low}":
            return True
    return False

def looks_like_person_name(name: str) -> bool:
    n = (name or "").strip()
    if len(n) < 3 or len(n) > 28:
        return False
    if any(ch.isdigit() for ch in n):
        return False
    if any(ch in "_/\\[]{}()<>@#$%^&*+=|" for ch in n):
        return False
    if ACRONYM_RE.match(n):
        return False
    parts = n.split()
    if len(parts) > 3:
        return False
    for p in parts:
        pp = p.replace("'", "")
        if len(pp) < 2:
            return False
        if not (pp[0].isupper() and pp[1:].islower()):
            return False
    return True

# -------------------------
# Default rosters (seed)
# -------------------------
DEFAULT_ROSTERS: Dict[str, List[str]] = {
    "GFL2_EXILIUM": ["Leva","Groza","Klukai","Commander","Kalina","Robella","Dandelion","Persica"],
    "WUWA": ["Rover","Chisa","Zani","Phoebe"],
    "ARKNIGHTS": ["Amiya","Kal'tsit","Ch'en","Exusiai","Texas","Doctor"],
}

ROOT = Path(__file__).resolve().parent
ROSTER_PATH = ROOT / "titan_game_rosters.json"
STATS_PATH  = ROOT / "titan_game_stats.json"
NAMES_PATH  = ROOT / "titan_names_per_game.json"
PROC_MAP_PATH = ROOT / "titan_game_process_map.json"
TITLE_MAP_PATH = ROOT / "titan_game_title_map.json"

DEFAULT_PROCESS_MAP = {
    "gfl2.exe": "GFL2_EXILIUM",
    "wutheringwaves.exe": "WUWA",
    "wuwa.exe": "WUWA",
    "arknights.exe": "ARKNIGHTS",
}
DEFAULT_TITLE_RULES = [
    {"pattern": r"gfl2|exilium", "game": "GFL2_EXILIUM"},
    {"pattern": r"wuthering\s*waves|wuwa", "game": "WUWA"},
    {"pattern": r"arknights", "game": "ARKNIGHTS"},
]

@dataclass
class GameDecision:
    game: Optional[str]
    confidence: float
    top_score: float
    second_score: float
    reason: str = ""

def _safe_write_json(path: Path, obj) -> None:
    try:
        path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

def _safe_read_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default

# -------------------------
# Windows foreground detection
# -------------------------
def _get_foreground_title_pid() -> Tuple[str, int]:
    if os.name != "nt":
        return "", 0
    try:
        import ctypes
        import ctypes.wintypes as wt

        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "", 0

        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""

        pid = wt.DWORD(0)
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return title, int(pid.value)
    except Exception:
        return "", 0

def _pid_to_exe_name(pid: int) -> str:
    if os.name != "nt" or pid <= 0:
        return ""
    try:
        import psutil  # type: ignore
        return (psutil.Process(pid).name() or "").strip()
    except Exception:
        pass
    try:
        import ctypes
        import ctypes.wintypes as wt
        kernel32 = ctypes.windll.kernel32

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, wt.DWORD(pid))
        if not h:
            return ""
        try:
            size = wt.DWORD(4096)
            buf = ctypes.create_unicode_buffer(4096)
            if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
                full = buf.value or ""
                return os.path.basename(full)
        finally:
            kernel32.CloseHandle(h)
    except Exception:
        pass
    return ""

# -------------------------
# Classifier
# -------------------------
class GameNameClassifier:
    def __init__(self) -> None:
        self._lock = threading.RLock()

        self.min_points = float(_env_int("TITAN_GAME_MIN_POINTS", 4))
        self.min_margin = float(_env_int("TITAN_GAME_MIN_MARGIN", 2))
        self.min_ratio  = float(_env_int("TITAN_GAME_MIN_RATIO_X10", 16)) / 10.0

        self.bootstrap_unique_needed = int(_env_int("TITAN_GAME_BOOTSTRAP_UNIQUE", 2))
        self.bootstrap_margin_needed = int(_env_int("TITAN_GAME_BOOTSTRAP_MARGIN", 1))
        self.bootstrap_timeout_sec = float(_env_int("TITAN_GAME_BOOTSTRAP_TTL_SEC", 900))

        self.session_ttl_sec = float(_env_int("TITAN_SESSION_NAME_TTL_SEC", 3600))

        self.allow_learn_new_names = _env_bool("TITAN_ALLOW_LEARN_NEW_NAMES", False)

        self.autolock_enabled = _env_bool("TITAN_GAME_AUTOLOCK", True) and (os.name == "nt")
        self.autolock_source = (_env("TITAN_GAME_AUTOLOCK_SOURCE", "both") or "both").lower()
        self.autolock_interval_ms = int(_env_int("TITAN_GAME_AUTOLOCK_INTERVAL_MS", 900))
        self.autolock_allow_switch = _env_bool("TITAN_GAME_AUTOLOCK_ALLOW_SWITCH", True)
        self.autolock_sticky = _env_bool("TITAN_GAME_AUTOLOCK_STICKY", True)

        self.rosters: Dict[str, Set[str]] = {}
        self.name_to_games: Dict[str, Set[str]] = {}
        self.per_game_names: Dict[str, Set[str]] = {}
        self.stats: Dict[str, Dict[str, float]] = {}
        self.observed_counts: Dict[str, int] = {}
        self.session_names: Dict[str, float] = {}
        self.roster_hits: Dict[str, Dict[str, float]] = {}

        self.active_game: Optional[str] = None
        self.last_decision: GameDecision = GameDecision(None, 0.0, 0.0, 0.0, "init")
        self._last_emitted_game: Optional[str] = None
        self._pending_emit: Optional[GameDecision] = None

        self.hard_locked: bool = False
        self.hard_lock_source: str = ""

        self.process_map: Dict[str, str] = {}
        self.title_rules: List[Tuple[re.Pattern, str]] = []

        self._stop_autolock = threading.Event()

        self._load_rosters()
        self._load_names()
        self._load_stats()
        self._load_autolock_maps()

        if self.autolock_enabled:
            threading.Thread(target=self._autolock_loop, daemon=True, name="TITAN_AUTOLOCK").start()

    def _load_rosters(self) -> None:
        data = _safe_read_json(ROSTER_PATH, default=None)
        if not isinstance(data, dict):
            data = DEFAULT_ROSTERS
            _safe_write_json(ROSTER_PATH, data)

        rosters: Dict[str, Set[str]] = {}
        for game, names in data.items():
            if isinstance(game, str) and isinstance(names, list):
                rosters[game.upper()] = set(str(n).strip() for n in names if str(n).strip())
        self.rosters = rosters

        idx: Dict[str, Set[str]] = {}
        for g, ns in self.rosters.items():
            for n in ns:
                idx.setdefault(n.strip(), set()).add(g)
        self.name_to_games = idx

    def _load_names(self) -> None:
        data = _safe_read_json(NAMES_PATH, default=None)
        out: Dict[str, Set[str]] = {}
        if isinstance(data, dict):
            for game, names in data.items():
                if isinstance(names, list):
                    out[str(game).upper()] = set(str(n).strip() for n in names if str(n).strip())
        self.per_game_names = out

    def _save_names(self) -> None:
        _safe_write_json(NAMES_PATH, {g: sorted(list(ns)) for g, ns in self.per_game_names.items()})

    def _load_stats(self) -> None:
        data = _safe_read_json(STATS_PATH, default=None)
        if isinstance(data, dict):
            sc = data.get("scores", {})
            ob = data.get("observed", {})
            self.stats = {str(k): dict(v) for k, v in sc.items()} if isinstance(sc, dict) else {}
            self.observed_counts = {str(k): int(v) for k, v in ob.items()} if isinstance(ob, dict) else {}
            ag = data.get("active_game", None)
            self.active_game = str(ag).upper() if isinstance(ag, str) and ag.strip() else None
            self.hard_locked = bool(data.get("hard_locked", False))
            self.hard_lock_source = str(data.get("hard_lock_source", "") or "")
        else:
            self.stats = {}
            self.observed_counts = {}

    def _save_stats(self) -> None:
        _safe_write_json(STATS_PATH, {
            "active_game": self.active_game,
            "hard_locked": self.hard_locked,
            "hard_lock_source": self.hard_lock_source,
            "scores": self.stats,
            "observed": self.observed_counts,
            "last_decision": self.last_decision.__dict__,
            "autolock": {
                "enabled": self.autolock_enabled,
                "source": self.autolock_source,
                "interval_ms": self.autolock_interval_ms,
            }
        })

    def _load_autolock_maps(self) -> None:
        pm = _safe_read_json(PROC_MAP_PATH, default=None)
        if not isinstance(pm, dict):
            pm = DEFAULT_PROCESS_MAP
            _safe_write_json(PROC_MAP_PATH, pm)
        self.process_map = {str(k).strip().lower(): str(v).strip().upper() for k, v in pm.items() if str(k).strip() and str(v).strip()}

        tr = _safe_read_json(TITLE_MAP_PATH, default=None)
        if not isinstance(tr, list):
            tr = DEFAULT_TITLE_RULES
            _safe_write_json(TITLE_MAP_PATH, tr)

        compiled: List[Tuple[re.Pattern, str]] = []
        for it in tr:
            if not isinstance(it, dict):
                continue
            pat = str(it.get("pattern") or "").strip()
            game = str(it.get("game") or "").strip().upper()
            if not pat or not game:
                continue
            try:
                compiled.append((re.compile(pat, re.IGNORECASE), game))
            except Exception:
                pass
        self.title_rules = compiled

    def stop(self) -> None:
        try:
            self._stop_autolock.set()
        except Exception:
            pass

    def _detect_game_from_process(self, exe: str) -> Optional[str]:
        e = (exe or "").strip().lower()
        if not e:
            return None
        if e in self.process_map:
            return self.process_map[e]
        for key, game in self.process_map.items():
            k = (key or "").strip().lower()
            if not k:
                continue
            if k.startswith("re:"):
                try:
                    if re.search(k[3:], e, re.IGNORECASE):
                        return game
                except Exception:
                    continue
            if "*" in k or "?" in k:
                if fnmatch.fnmatch(e, k):
                    return game
            if k and k in e:
                return game
        return None

    def _detect_game_from_title(self, title: str) -> Optional[str]:
        t = (title or "").strip()
        if not t:
            return None
        for rx, game in self.title_rules:
            try:
                if rx.search(t):
                    return game
            except Exception:
                pass
        return None

    def _autolock_loop(self) -> None:
        while not self._stop_autolock.is_set():
            try:
                title, pid = _get_foreground_title_pid()
                exe = _pid_to_exe_name(pid)

                game = None
                source = ""

                if self.autolock_source in ("both", "process") and exe:
                    g = self._detect_game_from_process(exe)
                    if g:
                        game = g
                        source = f"autolock_process({exe})"

                if (not game) and self.autolock_source in ("both", "title") and title:
                    g = self._detect_game_from_title(title)
                    if g:
                        game = g
                        source = f"autolock_title({title[:48]})"

                if game:
                    with self._lock:
                        prev = self.active_game
                        if (prev != game) and (self.autolock_allow_switch or not prev):
                            self.active_game = game
                            self.hard_locked = True
                            self.hard_lock_source = source

                            self.stats.setdefault(game, {})
                            self.stats[game]["score"] = max(float(self.stats[game].get("score", 0.0)), 999.0)

                            self.last_decision = GameDecision(game, 1.0, 999.0, 0.0, source)
                            self._pending_emit = self.last_decision
                            self._save_stats()
                            self._maybe_emit_terminal()
                else:
                    if not self.autolock_sticky:
                        with self._lock:
                            if self.hard_locked:
                                self.hard_locked = False
                                self.hard_lock_source = ""
                                self._save_stats()

            except Exception:
                pass

            try:
                self._stop_autolock.wait(max(0.2, self.autolock_interval_ms / 1000.0))
            except Exception:
                time.sleep(0.9)

    def _gc_session(self) -> None:
        now = _now()
        dead = [n for n, ts in self.session_names.items() if (now - ts) > self.session_ttl_sec]
        for n in dead:
            self.session_names.pop(n, None)

    def _match_roster_name(self, name: str) -> Optional[str]:
        low = (name or "").strip().lower()
        if not low:
            return None
        for canonical in self.name_to_games.keys():
            if canonical.lower() == low:
                return canonical
        return None

    def _name_weight(self, canonical: str) -> float:
        games = self.name_to_games.get(canonical, set())
        c = len(games) if games else 0
        if c <= 1: return 2.0
        if c == 2: return 1.2
        return 0.8

    def _bootstrap_counts(self) -> List[Tuple[str, int]]:
        now = _now()
        out: List[Tuple[str, int]] = []
        for g, hits in self.roster_hits.items():
            n = 0
            for _, ts in hits.items():
                if (now - ts) <= self.bootstrap_timeout_sec:
                    n += 1
            out.append((g, n))
        out.sort(key=lambda x: x[1], reverse=True)
        return out

    def _maybe_emit_terminal(self) -> None:
        if self._pending_emit is None:
            return
        gd = self._pending_emit
        self._pending_emit = None
        if gd.game and gd.game != self._last_emitted_game:
            self._last_emitted_game = gd.game
            try:
                print(f"[GAME] Detected/Locked: {gd.game} | conf={gd.confidence:.2f} | reason={gd.reason} | top={gd.top_score:.1f} second={gd.second_score:.1f}")
            except Exception:
                pass

    def observe_name(self, name: str, source: str="unknown") -> None:
        n = (name or "").strip()
        if not n:
            return
        with self._lock:
            self._gc_session()
            self.session_names[n] = _now()
            self.observed_counts[n] = int(self.observed_counts.get(n, 0)) + 1

            canonical = self._match_roster_name(n)
            if canonical:
                for g in self.name_to_games.get(canonical, set()):
                    self.stats.setdefault(g, {})
                    self.stats[g]["score"] = float(self.stats[g].get("score", 0.0)) + self._name_weight(canonical)
                    self.roster_hits.setdefault(g, {})[canonical] = _now()

            if self.active_game and looks_like_person_name(n) and not is_alias_or_title(n):
                self.stats.setdefault(self.active_game, {})
                self.stats[self.active_game]["score"] = float(self.stats[self.active_game].get("score", 0.0)) + 0.3

            self.decide_game()
            self._save_stats()
            self._maybe_emit_terminal()

    def observe_text(self, text: str, source: str="dialog") -> None:
        t = (text or "")
        if not t:
            return
        for canonical in self.name_to_games.keys():
            pat = re.compile(rf"(?<!\w){re.escape(canonical)}(?!\w)", re.IGNORECASE)
            if pat.search(t):
                self.observe_name(canonical, source=source)

    def decide_game(self) -> GameDecision:
        with self._lock:
            if self.hard_locked and self.active_game:
                self.last_decision = GameDecision(self.active_game, 1.0, 999.0, 0.0, self.hard_lock_source or "hard_locked")
                return self.last_decision

            b = self._bootstrap_counts()
            if b:
                top_g, top_n = b[0]
                second_n = b[1][1] if len(b) > 1 else 0
                if top_n >= max(1, self.bootstrap_unique_needed) and (top_n - second_n) >= self.bootstrap_margin_needed:
                    prev = self.active_game
                    self.active_game = str(top_g).upper()
                    conf = min(1.0, 0.55 + 0.15 * (top_n - 1))
                    self.last_decision = GameDecision(self.active_game, conf, float(top_n), float(second_n), "bootstrap_unique_hits")
                    if self.active_game != prev:
                        self._pending_emit = self.last_decision
                    return self.last_decision

            scores = []
            for g, obj in self.stats.items():
                try:
                    scores.append((str(g).upper(), float(obj.get("score", 0.0))))
                except Exception:
                    pass
            scores.sort(key=lambda x: x[1], reverse=True)
            if not scores:
                self.last_decision = GameDecision(self.active_game, 0.0, 0.0, 0.0, "no_scores")
                return self.last_decision

            top_g, top_s = scores[0]
            second_s = scores[1][1] if len(scores) > 1 else 0.0
            margin = top_s - second_s
            ratio = (top_s / max(0.0001, second_s)) if second_s > 0 else 999.0
            confident = (top_s >= self.min_points) and (margin >= self.min_margin) and (ratio >= self.min_ratio)

            conf = 0.0
            prev = self.active_game
            reason = "score_unconfident"
            if confident:
                conf = min(1.0, (top_s - self.min_points) / max(1.0, self.min_points))
                self.active_game = top_g
                reason = "score_confident"
            self.last_decision = GameDecision(self.active_game, conf, top_s, second_s, reason)
            if self.active_game and self.active_game != prev:
                self._pending_emit = self.last_decision
            return self.last_decision

    def is_name_in_active_roster(self, name: str) -> bool:
        if not self.active_game:
            return False
        canonical = self._match_roster_name(name)
        if not canonical:
            return False
        return canonical in self.rosters.get(self.active_game, set())

    def add_permanent(self, name: str) -> Tuple[bool, str, Optional[str]]:
        n = (name or "").strip()
        if not n:
            return False, "empty", None
        if is_alias_or_title(n):
            return False, "alias_or_title", None
        if not looks_like_person_name(n):
            return False, "not_person_name", None

        if self.active_game:
            if self.is_name_in_active_roster(n) or self.allow_learn_new_names:
                g = self.active_game
                self.per_game_names.setdefault(g, set()).add(n)
                self._save_names()
                return True, "saved", g
            return False, "not_in_active_roster", None

        canonical = self._match_roster_name(n)
        if canonical:
            games = self.name_to_games.get(canonical, set())
            if len(games) == 1:
                g = list(games)[0]
                self.per_game_names.setdefault(g, set()).add(n)
                self._save_names()
                return True, "unique_roster", g
        return False, "no_active_game", None

    def short_label(self) -> str:
        g = (self.active_game or "").upper()
        if not g:
            return "..."
        if g.startswith("GFL2"):
            return "GFL2"
        if g.startswith("WUWA"):
            return "WUWA"
        if g.startswith("ARK"):
            return "AK"
        return g[:6]

    def get_protected_names(self) -> List[str]:
        names: Set[str] = set()
        if self.active_game:
            names |= set(self.rosters.get(self.active_game, set()))
            names |= set(self.per_game_names.get(self.active_game, set()))
        return sorted([x for x in names if len(x) >= 3], key=len, reverse=True)

    def protect_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        src = text or ""
        out = src
        mapping: Dict[str, str] = {}
        idx = 0
        for nm in self.get_protected_names():
            pat = re.compile(rf"(?<!\w){re.escape(nm)}(?!\w)")
            if not pat.search(out):
                continue
            token = f"⟦NM{idx}⟧"
            idx += 1
            out = pat.sub(token, out)
            mapping[token] = nm
        return out, mapping

    def restore_text(self, text: str, mapping: Dict[str, str]) -> str:
        out = text or ""
        for token, nm in mapping.items():
            out = out.replace(token, nm)
        return out

CLASSIFIER = GameNameClassifier()
