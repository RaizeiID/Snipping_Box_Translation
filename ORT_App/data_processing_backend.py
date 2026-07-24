from __future__ import annotations
import json, re, time
from pathlib import Path
from collections import Counter
from difflib import SequenceMatcher

from app.identity.speaker_registry import (
    load_registry, game_bucket, active_entities, add_simple_view_name, add_sorted_entity,
    delete_entity, migrate_unsorted_entity, save_registry, load_catalog, verified_character_speaker_names
)

ROOT = Path(__file__).resolve().parent
STORE_PATH = ROOT / 'data_processing_store.json'
SETTINGS_PATH = ROOT / 'data_processing_settings.json'
SESSION_PATH = ROOT / 'runtime_candidates.json'

DEFAULT_SETTINGS = {
    'popup_on_stop': False,
    'auto_reset_candidates': True,
    'simple_view_enabled': True,
    'auto_live_candidate_label': False,
    'trust_legacy_npc': False,
    'show_story_spoilers': False,
    'schema_version': 'v8_7_5_safe_defaults',
}

SEED_GFL_NAMES = [
    'Commander', 'Kalina', 'Dandelion', 'AK-12', 'AN-94', 'AK-15', 'Tokarev', 'Groza',
    'M4A1', 'M4 SOPMOD II', 'ST AR-15', 'AR-15', 'RO635', 'UMP45', 'UMP9', 'HK416', 'G11',
    'M16A1', 'Kryuger', 'Helian', 'Persica', 'Angelina', 'Ange', 'Lunasia', 'William'
]
SEED_GFL_SPECIAL = [
    'T-Doll', 'Task Force DEFY', 'DEFY', 'Griffin & Kryuger', 'Paradeus', 'Sangvis Ferri',
    'Nyto', 'White Nyto', 'Black Nyto', 'Neural Cloud', 'Diergate', 'ELID', 'IOP'
]
SEED_GFL_ORIGINALS = {
    'Groza': 'OTs-14', 'AK-12': 'AK-12', 'AN-94': 'AN-94', 'AK-15': 'AK-15',
    'M4A1': 'M4A1', 'ST AR-15': 'ST AR-15', 'M4 SOPMOD II': 'M4 SOPMOD II',
    'UMP45': 'UMP45', 'UMP9': 'UMP9', 'HK416': 'HK416', 'G11': 'G11'
}
SEED_GFL2_NAMES = [
    'Groza', 'Nemesis', 'Leva', 'Commander', 'Mysterious Picture', 'Krolik', 'Colphne',
    'Vepley', 'Peritya', 'Sabrina', 'Qiongjiu', 'Tololo', 'Suomi', 'Klukai', 'Alva',
    'Voymastina', 'Makiatto', 'Daiyan', 'Sharkry', 'Springfield', 'Nagant', 'Ksenia',
    'Ullrid', 'Cheeta', 'Littara', 'Dushevnaya', 'Andoris', 'Mayling', 'Raizei', 'Vivi',
    'Vector', 'Chiloveig', 'Berryfield', 'Cocoon', 'Carmen', 'Another Unfamiliar Worker', 'Helen', 'Helena', 'Balthilde', 'Phaetusa', 'Melanie', 'Alya Kujou', 'Girard', 'DP-12', 'KSVK'
]
SEED_GFL2_SPECIAL = [
    'T-Doll', 'Nyto', 'Project Eden', 'Lviv', 'Mysterious Figure',
    'Enemy Soldier', 'Armed Personnel', 'Marionette Doll', 'Signal Jammer',
    'Culture Fluid', 'Automated Defense System', 'URNC', 'Conglomerate', 'Green Zone', 'Yellow Zone', 'Odesa', 'ELID', 'ELIDs', 'ODE-01', 'Griffin', 'Griffin & Kryuger', 'Blusphere'
]
SEED_GFL2_ORIGINALS = {
    'Groza': 'OTs-14',
    'Alva': 'AN-94',
    'Voymastina': 'AK-15',
    'Leva': 'UMP45',
    'Klukai': 'HK416',
    'Sabrina': 'SPAS-12',
    'Suomi': 'Suomi KP/-31',
    'Nagant': 'Nagant Revolver',
    'Vector': 'Vector',
    'Daiyan': 'Type 95',
    'Springfield': 'M1903 Springfield',
    'DP-12': 'DP-12',
    'KSVK': 'KSVK',
}
SEED_WUWA_NAMES = [
    'Rover', 'Yangyang', 'Chixia', 'Baizhi', 'Jianxin', 'Jiyan', 'Calcharo', 'Encore',
    'Verina', 'Lingyang', 'Sanhua', 'Mortefi', 'Danjin', 'Taoqi', 'Aalto', 'Yinlin',
    'Jinhsi', 'Changli', 'Zhezhi', 'Xiangli Yao', 'Camellya', 'Carlotta', 'Roccia',
    'Phoebe', 'Brant', 'Cantarella', 'Cartethyia', 'Lupa', 'Phrolova', 'Augusta', 'Iuno', 'Galbrena', 'Qiuyuan', 'Chisa', 'Lynae', 'Mornye', 'Aemeath', 'Luuk Herssen', 'Sigrika', 'Youhu', 'Lumi', 'Buling', 'Zani', 'Ciaccona', 'Shorekeeper', 'Roccia'
]
SEED_WUWA_SPECIAL = [
    'Resonator', 'Tacet Discord', 'Tacetite', 'Lament', 'Black Shores', 'Jinzhou',
    'Huanglong', 'Solaris-3', 'Waveworn Phenomenon', 'Echo', 'Forte', 'Resonance',
    'Terminal', 'Sonoro Sphere', 'Overture', 'Fractsidus'
]
SEED_WUWA_ORIGINALS = {}
DEFAULT_GAME_DATA = {
    'names': [],
    'special_words': [],
    'blacklist': [],
    'original_names': {},
    'name_color': 'red',
    'special_color': 'blue',
}
COLOR_CHOICES = ['red', 'blue', 'green', 'orange', 'purple', 'yellow']
COLOR_LABELS = {
    'red': 'Merah',
    'blue': 'Biru',
    'green': 'Hijau',
    'orange': 'Oranye',
    'purple': 'Ungu',
    'yellow': 'Kuning',
}
COLOR_HEX = {
    'red': '#ef4444',
    'blue': '#3b82f6',
    'green': '#22c55e',
    'orange': '#f59e0b',
    'purple': '#a855f7',
    'yellow': '#eab308',
}
BAD_TOKENS = {
    'ocr', 'pipe', 'cache', 'system', 'mode', 'auto', 'freeze', 'interval', 'stable', 'dialog',
    'monolog', 'miss', 'hit', 'high', 'latency', 'stop', 'start', 'click', 'heroic', 'collect',
    'reward', 'rewards', 'running', 'status', 'game', 'exit', 'confirm', 'skip', 'cpu', 'gpu',
    'hybrid', 'gfl2', 'level', 'live', 'log', 'runtime', 'python', 'boot', 'success', 'error',
    'traceback', 'file', 'line', 'process', 'webui', 'idle', 'max', 'loading', 'resources',
    'continue', 'damage', 'stats', 'confirm', 'heroic', 'mode', 'saved',
    'gfn', 'ngf', 'nifn', 'ni5e', 'nfe', 'ylf', 's5gg', 'gfsystem', 'sunborn', 'programming', 'video', 'character', 'conference'
}
TOKEN_RE = re.compile(r"\b([A-Za-z][A-Za-z0-9'\-]+(?:\s+[A-Za-z][A-Za-z0-9'\-]+){0,2})\b")
SIMPLIFY_RE = re.compile(r'[^a-z0-9]')
OCR_PREFIX_RE = re.compile(r'^\[OCR\]\s*')
SPECIAL_HINTS = {
    'soldier', 'personnel', 'figure', 'project', 'eden', 'nyto', 't-doll',
    'tdoll', 'doll', 'unit', 'squad', 'protocol', 'operation', 'system', 'fluid'
}
UI_NOISE_SUBSTRINGS = [
    'collect more to claim rewards', 'heroic mode', 'loading resources', 'damage stats',
    'continue confirm', 'max level', 'pengaturan rekaman', 'saved to', 'click anywhere to exit'
]


def _load_json(path: Path, default):
    try:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8-sig'))
    except Exception:
        pass
    return default


def _save_json(path: Path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def _normalize_item(text: str) -> str:
    s = re.sub(r'\s+', ' ', str(text or '').strip())
    s = s.strip('"\'`.,:;!?()[]{}<>|')
    return s


def _key(text: str) -> str:
    return SIMPLIFY_RE.sub('', _normalize_item(text).lower())


def _familiar_key(text: str) -> str:
    s = _key(text)
    # normalize OCR confusions
    trans = str.maketrans({
        '1': 'l',
        'i': 'l',
        '0': 'o',
        '5': 's',
        '8': 'b',
    })
    return s.translate(trans)


def _dedupe_keep_order(items):
    seen = set()
    out = []
    for item in items or []:
        n = _normalize_item(item)
        if not n:
            continue
        k = _key(n)
        if not k or k in seen:
            continue
        seen.add(k)
        out.append(n)
    return out


def _ensure_game_seed(store: dict, key: str, names, special, originals, name_color='red', special_color='blue'):
    if key not in store:
        store[key] = {
            'names': list(names),
            'special_words': list(special),
            'blacklist': [],
            'original_names': dict(originals),
            'name_color': name_color,
            'special_color': special_color,
        }
    else:
        g = store[key]
        g.setdefault('names', [])
        g.setdefault('special_words', [])
        g.setdefault('blacklist', [])
        g.setdefault('original_names', {})
        g.setdefault('name_color', name_color)
        g.setdefault('special_color', special_color)
        g['names'] = _dedupe_keep_order(g['names'] + list(names))
        g['special_words'] = _dedupe_keep_order(g['special_words'] + list(special))
        for k, v in dict(originals).items():
            g['original_names'].setdefault(k, v)


def _seed_store_if_needed(store: dict) -> dict:
    _ensure_game_seed(store, 'GFL', SEED_GFL_NAMES, SEED_GFL_SPECIAL, SEED_GFL_ORIGINALS, 'red', 'blue')
    _ensure_game_seed(store, 'GFL2_EXILIUM', SEED_GFL2_NAMES, SEED_GFL2_SPECIAL, SEED_GFL2_ORIGINALS, 'red', 'blue')
    _ensure_game_seed(store, 'WUWA', SEED_WUWA_NAMES, SEED_WUWA_SPECIAL, SEED_WUWA_ORIGINALS, 'purple', 'orange')
    _ensure_game_seed(store, 'CUSTOM', [], [], {}, 'red', 'blue')
    return store


def load_store():
    store = _seed_store_if_needed(_load_json(STORE_PATH, {}))
    _save_json(STORE_PATH, store)
    return store


def save_store(data):
    _save_json(STORE_PATH, _seed_store_if_needed(data or {}))


def load_settings():
    existing = _load_json(SETTINGS_PATH, {})
    data = DEFAULT_SETTINGS.copy()
    data.update(existing)
    # One-time safe migration from the pre-registry settings schema. User UI
    # choices introduced in v8.7.3 are not overwritten after this marker exists.
    if existing.get('schema_version') not in {'v8_7_3_safe_defaults', 'v8_7_5_safe_defaults'}:
        if SETTINGS_PATH.exists():
            backup = SETTINGS_PATH.with_name('data_processing_settings_backup_before_v8_7_3.json')
            if not backup.exists():
                backup.write_text(SETTINGS_PATH.read_text(encoding='utf-8-sig'), encoding='utf-8')
        data.update({
            'auto_reset_candidates': True,
            'auto_live_candidate_label': False,
            'trust_legacy_npc': False,
            'simple_view_enabled': bool(existing.get('simple_view_enabled', True)),
            'schema_version': 'v8_7_5_safe_defaults',
        })
        _save_json(SETTINGS_PATH, data)
    return data


def save_settings(settings: dict):
    merged = DEFAULT_SETTINGS.copy()
    merged.update(settings or {})
    _save_json(SETTINGS_PATH, merged)
    return merged


def get_game_data(game: str):
    store = load_store()
    data = DEFAULT_GAME_DATA.copy()
    data.update(store.get(game, {}))
    data['names'] = _dedupe_keep_order(data.get('names', []))
    data['special_words'] = _dedupe_keep_order(data.get('special_words', []))
    data['blacklist'] = _dedupe_keep_order(data.get('blacklist', []))
    originals = data.get('original_names', {}) or {}
    data['original_names'] = {_normalize_item(k): _normalize_item(v) for k, v in originals.items() if _normalize_item(k) and _normalize_item(v)}
    if data['special_color'] == data['name_color']:
        for c in COLOR_CHOICES:
            if c != data['name_color']:
                data['special_color'] = c
                break
    return data


def save_game_data(game: str, data: dict):
    store = load_store()
    clean = DEFAULT_GAME_DATA.copy()
    clean.update(data or {})
    clean['names'] = _dedupe_keep_order(clean.get('names', []))
    clean['special_words'] = _dedupe_keep_order(clean.get('special_words', []))
    clean['blacklist'] = _dedupe_keep_order(clean.get('blacklist', []))
    originals = {}
    for k, v in (clean.get('original_names', {}) or {}).items():
        nk, nv = _normalize_item(k), _normalize_item(v)
        if nk and nv:
            originals[nk] = nv
    clean['original_names'] = originals
    if clean['special_color'] == clean['name_color']:
        raise ValueError('Warna daftar nama dan kata khusus tidak boleh sama.')
    store[game] = clean
    save_store(store)
    return clean


def _load_session():
    return _load_json(SESSION_PATH, {})


def _save_session(data):
    _save_json(SESSION_PATH, data)



def _get_session_bucket(game: str):
    data = _load_session()
    bucket = data.get(game, {}) if isinstance(data.get(game, {}), dict) else {}
    bucket.setdefault('counts', {})
    bucket.setdefault('updated_at', 0)
    bucket.setdefault('confirmed_log', [])
    return data, bucket


def _append_confirmed_log(game: str, category: str, items):
    items = [_normalize_item(x) for x in (items or []) if _normalize_item(x)]
    if not items:
        return
    data, bucket = _get_session_bucket(game)
    rows = list(bucket.get('confirmed_log', []))
    stamp = int(time.time())
    for item in items:
        rows.append({'text': item, 'category': category, 'ts': stamp})
    bucket['confirmed_log'] = rows[-80:]
    data[game] = bucket
    _save_session(data)


def get_confirmed_log(game: str):
    session = _load_session()
    rows = session.get(game, {}).get('confirmed_log', []) if isinstance(session.get(game, {}), dict) else []
    out = []
    for row in rows[-80:]:
        if not isinstance(row, dict):
            continue
        txt = _normalize_item(row.get('text', ''))
        cat = row.get('category', '')
        if txt:
            out.append({'text': txt, 'category': cat or 'name'})
    return out


def render_confirmed_log_html(game: str):
    rows = get_confirmed_log(game)
    if not rows:
        return "<div style='color:#cbd5e1;font-size:13px'>Belum ada kandidat yang dikonfirmasi pada sesi ini.</div>"
    chips = []
    for row in rows[::-1]:
        cat = row.get('category', 'name')
        if cat == 'special':
            color = COLOR_HEX.get(get_game_data(game).get('special_color', 'blue'), '#3b82f6')
            label = 'Kata Khusus'
        elif cat == 'blacklist':
            color = '#eab308'
            label = 'Blacklist'
        else:
            color = COLOR_HEX.get(get_game_data(game).get('name_color', 'red'), '#ef4444')
            label = 'Nama'
        chips.append(
            f"<span style='display:inline-block;margin:4px;padding:6px 10px;border-radius:999px;border:1px solid {color};color:{color};font-weight:700'>{row['text']} <span style='opacity:.75;font-weight:600'>• {label}</span></span>"
        )
    return '<div>' + ''.join(chips) + '</div>'


def add_items_with_feedback(game: str, category: str, items):
    items = _dedupe_keep_order(items)
    if not items:
        return [], []
    data = get_game_data(game)
    if category == 'names':
        existing_list = data['names']
    elif category == 'special_words':
        existing_list = data['special_words']
    elif category == 'blacklist':
        existing_list = data['blacklist']
    else:
        existing_list = []
    exact = {_key(x) for x in existing_list}
    familiar = {_familiar_key(x) for x in existing_list}
    added, duplicates = [], []
    for item in items:
        if _looks_like_known(item, exact, familiar):
            duplicates.append(_normalize_item(item))
            continue
        added.append(_normalize_item(item))
        exact.add(_key(item))
        familiar.add(_familiar_key(item))
    if added:
        if category == 'names':
            data['names'] = _dedupe_keep_order(data['names'] + added)
            save_game_data(game, data)
            _append_confirmed_log(game, 'name', added)
        elif category == 'special_words':
            data['special_words'] = _dedupe_keep_order(data['special_words'] + added)
            save_game_data(game, data)
            _append_confirmed_log(game, 'special', added)
        elif category == 'blacklist':
            data['blacklist'] = _dedupe_keep_order(data['blacklist'] + added)
            save_game_data(game, data)
            _append_confirmed_log(game, 'blacklist', added)
    return added, duplicates

def clear_candidates(game: str):
    data = _load_session()
    bucket = data.get(game, {}) if isinstance(data.get(game, {}), dict) else {}
    bucket['counts'] = {}
    bucket['updated_at'] = 0
    bucket.setdefault('confirmed_log', [])
    data[game] = bucket
    _save_session(data)


def _existing_reference_sets(game: str):
    data = get_game_data(game)
    exact = set()
    familiar = set()
    for item in data['names'] + data['special_words'] + data['blacklist'] + list(data['original_names'].keys()) + list(data['original_names'].values()):
        exact.add(_key(item))
        familiar.add(_familiar_key(item))
    return exact, familiar


def _looks_like_known(item: str, exact_keys: set[str], familiar_keys: set[str]) -> bool:
    k = _key(item)
    fk = _familiar_key(item)
    if not k:
        return True
    if k in exact_keys or fk in familiar_keys:
        return True
    # fuzzy-ish check for OCR confusion against familiar keys
    for existing in familiar_keys:
        if abs(len(existing) - len(fk)) > 2:
            continue
        ratio = SequenceMatcher(None, fk, existing).ratio()
        if ratio >= 0.88:
            return True
    return False


def extract_candidates_from_line(line: str, game: str = ""):
    if not line:
        return []
    raw = line.strip()
    if not raw or not raw.startswith('[OCR]'):
        return []
    raw = OCR_PREFIX_RE.sub('', raw).strip()
    if str(game or '').upper() in {'GFL', 'GIRLS_FRONTLINE', 'GFL1'}:
        try:
            from app.games.gfl_profile import normalize_gfl_text, is_non_dialog_text
            raw = normalize_gfl_text(raw)
            if is_non_dialog_text(raw):
                return []
        except Exception:
            pass
    if not raw:
        return []
    lower_raw = raw.lower()
    if any(sub in lower_raw for sub in UI_NOISE_SUBSTRINGS):
        return []
    if len(raw) > 220:
        return []
    if sum(ch.isdigit() for ch in raw) >= 8:
        return []
    out = []
    for token in TOKEN_RE.findall(raw):
        t = _normalize_item(token)
        if len(t) < 3:
            continue
        if sum(ch.isdigit() for ch in t) >= 2:
            continue
        tl = t.lower()
        if tl in BAD_TOKENS:
            continue
        if re.fullmatch(r'[0-9\W_]+', t):
            continue
        if t.isupper() and len(t) > 4:
            continue
        # require title-like or multi-word terms
        if ' ' in t or any(ch.isupper() for ch in t[1:]) or t[0].isupper():
            out.append(t)
    return _dedupe_keep_order(out)[:40]


def record_runtime_line(game: str, line: str):
    game = game or 'GFL2_EXILIUM'
    items = extract_candidates_from_line(line, game)
    if not items:
        return
    exact_keys, familiar_keys = _existing_reference_sets(game)
    session = _load_session()
    bucket = session.get(game, {'counts': {}, 'updated_at': 0, 'confirmed_log': []})
    counts = Counter(bucket.get('counts', {}))
    for item in items:
        if _looks_like_known(item, exact_keys, familiar_keys):
            continue
        ni = _normalize_item(item)
        counts[ni] += 1
    bucket['counts'] = dict(counts)
    bucket['updated_at'] = int(time.time())
    session[game] = bucket
    _save_session(session)


def get_candidates(game: str):
    session = _load_session()
    counts = Counter({_normalize_item(k): int(v) for k, v in session.get(game, {}).get('counts', {}).items() if _normalize_item(k)})
    items = [name for name, _ in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].lower()))]
    return items, counts


def classify_candidate(name: str, game: str = ""):
    text = _normalize_item(name)
    lower = text.lower()
    parts = lower.split()
    seed_name_keys = {_familiar_key(x) for x in SEED_GFL2_NAMES} | {_familiar_key(x) for x in SEED_GFL2_ORIGINALS.keys()} | {_familiar_key(x) for x in SEED_GFL2_ORIGINALS.values()}
    if str(game or '').upper() in {'GFL', 'GIRLS_FRONTLINE', 'GFL1'}:
        seed_name_keys |= {_familiar_key(x) for x in SEED_GFL_NAMES} | {_familiar_key(x) for x in SEED_GFL_ORIGINALS.keys()} | {_familiar_key(x) for x in SEED_GFL_ORIGINALS.values()}
    if _familiar_key(text) in seed_name_keys:
        return 'name'
    if any(p in SPECIAL_HINTS for p in parts):
        return 'special'
    if len(parts) >= 2:
        return 'special'
    if any(ch.isdigit() for ch in text):
        return 'special'
    return 'name'


def get_candidate_groups(game: str):
    items, counts = get_candidates(game)
    exact_keys, familiar_keys = _existing_reference_sets(game)
    name_candidates, special_candidates = [], []
    for item in items:
        if _looks_like_known(item, exact_keys, familiar_keys):
            continue
        label = f"{item} • {counts.get(item,1)}x"
        group = classify_candidate(item, game)
        if group == 'name':
            name_candidates.append((label, item))
            special_candidates.append((label, item))
        else:
            special_candidates.append((label, item))
            name_candidates.append((label, item))
    return name_candidates, special_candidates



def merge_selected(game: str, names=None, special_words=None, blacklist=None, name_color=None, special_color=None):
    data = get_game_data(game)
    added_names = []
    added_special = []
    added_blacklist = []
    if names:
        before = {_key(x) for x in data['names']}
        data['names'] = _dedupe_keep_order(data['names'] + list(names))
        added_names = [x for x in data['names'] if _key(x) not in before]
    if special_words:
        before = {_key(x) for x in data['special_words']}
        data['special_words'] = _dedupe_keep_order(data['special_words'] + list(special_words))
        added_special = [x for x in data['special_words'] if _key(x) not in before]
    if blacklist:
        before = {_key(x) for x in data['blacklist']}
        data['blacklist'] = _dedupe_keep_order(data['blacklist'] + list(blacklist))
        added_blacklist = [x for x in data['blacklist'] if _key(x) not in before]
    if name_color:
        data['name_color'] = name_color
    if special_color:
        data['special_color'] = special_color
    saved = save_game_data(game, data)
    if added_names:
        _append_confirmed_log(game, 'name', added_names)
    if added_special:
        _append_confirmed_log(game, 'special', added_special)
    if added_blacklist:
        _append_confirmed_log(game, 'blacklist', added_blacklist)
    return saved


def remove_items(game: str, category: str, items):
    data = get_game_data(game)
    remove_keys = {_key(x) for x in (items or [])}
    if category not in data:
        return data
    if isinstance(data[category], list):
        data[category] = [x for x in data[category] if _key(x) not in remove_keys]
    return save_game_data(game, data)


def upsert_original_name(game: str, current_name: str, original_name: str):
    data = get_game_data(game)
    current_name = _normalize_item(current_name)
    original_name = _normalize_item(original_name)
    if not current_name or not original_name:
        raise ValueError('Nama dan original name harus diisi.')
    data['original_names'][current_name] = original_name
    return save_game_data(game, data)


def remove_original_name(game: str, current_name: str):
    data = get_game_data(game)
    current_name = _normalize_item(current_name)
    data['original_names'].pop(current_name, None)
    return save_game_data(game, data)


def render_badge_preview(game: str):
    data = get_game_data(game)
    nc = COLOR_HEX[data['name_color']]
    sc = COLOR_HEX[data['special_color']]
    return (
        f"<div style='display:flex;gap:10px;flex-wrap:wrap'>"
        f"<span style='border:1px solid {nc};color:{nc};padding:6px 10px;border-radius:999px;font-weight:700'>Groza</span>"
        f"<span style='border:1px solid {nc};color:{nc};padding:6px 10px;border-radius:999px;font-weight:700'>Commander</span>"
        f"<span style='border:1px solid {sc};color:{sc};padding:6px 10px;border-radius:999px;font-weight:700'>Project Eden</span>"
        f"<span style='border:1px solid #eab308;color:#eab308;padding:6px 10px;border-radius:999px'>Blacklist: Click anywhere to exit</span>"
        f"</div>"
    )


def render_list_html(items, color_name: str, empty_text: str):
    if not items:
        return f"<div style='color:#cbd5e1;font-size:13px'>{empty_text}</div>"
    color = COLOR_HEX.get(color_name, '#e5e7eb')
    chips = [f"<span style='display:inline-block;margin:4px;padding:6px 10px;border-radius:999px;border:1px solid {color};color:{color};font-weight:700'>{item}</span>" for item in items]
    return "<div>" + "".join(chips) + "</div>"


def render_original_table(game: str):
    data = get_game_data(game)
    rows = []
    for current_name, original in sorted(data['original_names'].items(), key=lambda kv: kv[0].lower()):
        rows.append(f"<tr><td style='padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.08)'>{current_name}</td><td style='padding:6px 10px;border-bottom:1px solid rgba(255,255,255,.08)'>{original}</td></tr>")
    if not rows:
        return "<div style='color:#cbd5e1;font-size:13px'>Belum ada original name tersimpan.</div>"
    return "<table style='width:100%;border-collapse:collapse'><thead><tr><th style='text-align:left;padding:6px 10px'>Nama sekarang</th><th style='text-align:left;padding:6px 10px'>Original Name</th></tr></thead><tbody>" + ''.join(rows) + "</tbody></table>"


# ---------------------------------------------------------------------------
# v8.7.3 Multi-game Identity UI / Trusted Registry helpers
# ---------------------------------------------------------------------------
CATEGORY_LABELS = {
    'protected_character': 'Karakter / Speaker Terlindungi',
    'user_configured': 'Commander / Player Name',
    'approved_role_speaker': 'NPC / Role Disetujui',
    'unsorted_protected': 'Ditambahkan di Tampilan Sederhana',
}


def _game_key(game: str) -> str:
    return str(game or 'CUSTOM').upper()


def identity_detail_categories(game: str):
    key = _game_key(game)
    if key == 'GFL2_EXILIUM':
        return [('protected_character', 'Character / Doll'), ('user_configured', 'Commander Name'), ('approved_role_speaker', 'NPC / Role Speaker')]
    if key == 'WUWA':
        return [('protected_character', 'Playable Resonator'), ('approved_role_speaker', 'Story NPC / Role Speaker')]
    if key == 'GFL':
        return [('protected_character::T-Doll', 'T-Doll'), ('protected_character::Griffin & Allies', 'Karakter Penting / Griffin & Allies'), ('protected_character::Paradeus', 'Karakter Faksi Cerita — Paradeus (priority)'), ('protected_character::Sangvis Ferri', 'Karakter Faksi Cerita — Sangvis Ferri (additional/spoiler)'), ('approved_role_speaker', 'NPC / Role Speaker')]
    return [('protected_character', 'Nama Dilindungi'), ('approved_role_speaker', 'NPC / Role Speaker')]


def _identity_chip(entity: dict, *, unsorted: bool = False) -> str:
    name = entity.get('display_name', '')
    color = '#f59e0b' if unsorted else '#22c55e'
    suffix = ' • Belum disortir' if unsorted else ''
    return f"<span style='display:inline-block;margin:4px;padding:6px 10px;border-radius:999px;border:1px solid {color};color:{color};font-weight:700'>{name}{suffix}</span>"


def render_identity_names_html(game: str, simple_view: bool = True) -> str:
    bucket = game_bucket(_game_key(game))
    entities = active_entities(_game_key(game), include_unsorted=True)
    if not entities:
        return "<div style='color:#cbd5e1;font-size:13px'>Belum ada nama terlindungi.</div>"
    return '<div>' + ''.join(_identity_chip(e, unsorted=(e.get('category') == 'unsorted_protected' and not simple_view)) for e in entities) + '</div>'


def render_identity_terms_html(game: str) -> str:
    bucket = game_bucket(_game_key(game))
    terms = bucket.get('special_terms', [])
    if not terms:
        return "<div style='color:#cbd5e1;font-size:13px'>Belum ada kata khusus.</div>"
    return '<div>' + ''.join(f"<span style='display:inline-block;margin:4px;padding:6px 10px;border-radius:999px;border:1px solid #3b82f6;color:#3b82f6;font-weight:700'>{x}</span>" for x in terms) + '</div>'


def render_identity_blacklist_html(game: str) -> str:
    items = game_bucket(_game_key(game)).get('blacklist', [])
    if not items:
        return "<div style='color:#cbd5e1;font-size:13px'>Blacklist kosong.</div>"
    return '<div>' + ''.join(f"<span style='display:inline-block;margin:4px;padding:6px 10px;border-radius:999px;border:1px solid #eab308;color:#eab308'>{x}</span>" for x in items) + '</div>'


def identity_action_choices(game: str):
    bucket = game_bucket(_game_key(game))
    choices=[]
    for entity in bucket.get('unsorted_protected', []):
        choices.append(f"🟠 {entity.get('display_name')} · Ditambahkan di Tampilan Sederhana (dapat dimigrasi)")
    for cat, label in identity_detail_categories(game):
        for entity in bucket.get(cat, []):
            extra = f" / {entity.get('faction')}" if entity.get('faction') else ''
            choices.append(f"🟢 {entity.get('display_name')} · {label}{extra}")
    return choices


def _selected_name(selected: str) -> tuple[str, bool]:
    raw = str(selected or '')
    is_unsorted = raw.startswith('🟠')
    raw = re.sub(r'^[🟠🟢]\s*', '', raw)
    raw = raw.split(' · ', 1)[0].strip()
    return raw, is_unsorted


def render_identity_header(game: str, simple_view: bool = True) -> str:
    bucket = game_bucket(_game_key(game))
    protected = len(active_entities(_game_key(game), include_unsorted=True))
    terms, blocked = len(bucket.get('special_terms', [])), len(bucket.get('blacklist', []))
    pending = len(bucket.get('pending_session_candidate', []))
    verified_exact = len(verified_character_speaker_names(_game_key(game))) if _game_key(game) == 'GFL2_EXILIUM' else 0
    exact_badge = f" • {verified_exact} Karakter Resmi Exact-Only" if verified_exact else ''
    mode = 'Sederhana' if simple_view else 'Normal / Detail'
    display = {'GFL2_EXILIUM':'GFL2: Exilium','GFL':'Girls\' Frontline','WUWA':'Wuthering Waves','CUSTOM':'Custom'}.get(_game_key(game), game)
    return f"<div style='padding:12px;border:1px solid rgba(255,255,255,.15);border-radius:14px'><b>{display}</b> • Status: <b>{mode}</b><br><span style='font-size:13px'>{protected} Nama Dilindungi{exact_badge} • {terms} Kata Khusus • {blocked} Blacklist • {pending} Kandidat</span><br><span style='font-size:12px;color:#cbd5e1'>Data berlaku hanya untuk game profile terpilih. Nama orange di Mode Normal berasal dari Tampilan Sederhana dan dapat dimigrasikan. Karakter resmi exact-only dapat dilabel dari Name ROI tepat tanpa fuzzy bebas.</span></div>"


def identity_notice(game: str, simple_view: bool) -> str:
    if simple_view:
        return ''
    count = len(game_bucket(_game_key(game)).get('unsorted_protected', []))
    if count:
        return f"⚠️ {count} nama pernah ditambahkan pada Tampilan Sederhana. Klik chip/item orange untuk menghapus atau memigrasikannya ke kategori detail."
    return 'Semua nama terlindungi sudah berada pada kategori detail.'



def render_reference_catalog_html(game: str, show_spoilers: bool = False) -> str:
    key = _game_key(game)
    source = load_catalog().get('games', {}).get(key, {})
    entries = list(source.get('entries', []) or [])
    if key == 'GFL' and not show_spoilers:
        entries = [e for e in entries if not str(e.get('spoiler_level', '')).startswith('advanced')]
    by_group = {}
    for entity in entries:
        faction = str(entity.get('faction') or entity.get('entity_type') or 'Reference')
        by_group.setdefault(faction, []).append(str(entity.get('display_name', '')))
    meta = source.get('source_metadata', {}) or {}
    exact_note = ' • exact-speaker aktif untuk Name ROI' if key == 'GFL2_EXILIUM' else ''
    pieces = [f"<div style='font-size:12px;color:#cbd5e1;margin-bottom:8px'>Katalog referensi: {len(entries)} nama tampil{exact_note} • sumber diperiksa {meta.get('source_checked_at','-')} • {meta.get('coverage_note','')}</div>"]
    for group, names in by_group.items():
        chips=''.join(f"<span style='display:inline-block;margin:3px;padding:4px 8px;border-radius:999px;border:1px solid #64748b;color:#cbd5e1;font-size:12px'>{n}</span>" for n in names[:250])
        pieces.append(f"<div style='margin:8px 0'><b>{group}</b><div>{chips}</div></div>")
    if key == 'GFL' and not show_spoilers:
        pieces.append("<div style='font-size:12px;color:#fbbf24'>Karakter faksi cerita Paradeus/Sangvis Ferri disembunyikan. Centang opsi spoiler untuk menampilkan katalog cerita lanjutan.</div>")
    return ''.join(pieces)

def get_identity_ui_payload(game: str, simple_view: bool = True):
    choices = identity_action_choices(game)
    return (render_identity_header(game, simple_view), render_identity_names_html(game, simple_view), render_identity_terms_html(game), render_identity_blacklist_html(game), choices, identity_notice(game, simple_view))


def _resolve_detail_category(category: str, faction: str = ''):
    raw = str(category or 'protected_character')
    if '::' in raw:
        base, implied_faction = raw.split('::', 1)
        return base, faction or implied_faction
    return raw, faction


def add_identity_name(game: str, name: str, simple_view: bool = True, category: str = 'protected_character', faction: str = ''):
    n = _normalize_item(name)
    if not n:
        raise ValueError('Nama tidak boleh kosong.')
    if simple_view:
        add_simple_view_name(_game_key(game), n)
    else:
        category, faction = _resolve_detail_category(category, faction)
        add_sorted_entity(_game_key(game), n, category, faction=faction)
    return get_identity_ui_payload(game, simple_view)


def delete_identity_choice(game: str, selected: str, simple_view: bool):
    name, _ = _selected_name(selected)
    if not name:
        raise ValueError('Klik/pilih nama yang ingin dihapus.')
    delete_entity(_game_key(game), name)
    return get_identity_ui_payload(game, simple_view)


def migrate_identity_choice(game: str, selected: str, target_category: str, faction: str = ''):
    name, unsorted = _selected_name(selected)
    if not name or not unsorted:
        raise ValueError('Migrasi hanya tersedia untuk nama orange yang ditambahkan melalui Tampilan Sederhana.')
    target_category, faction = _resolve_detail_category(target_category, faction)
    if not migrate_unsorted_entity(_game_key(game), name, target_category, faction=faction):
        raise ValueError('Nama tidak ditemukan pada daftar migrasi.')
    return get_identity_ui_payload(game, False)


def set_simple_view_enabled(enabled: bool):
    settings = load_settings()
    settings['simple_view_enabled'] = bool(enabled)
    return save_settings(settings)
