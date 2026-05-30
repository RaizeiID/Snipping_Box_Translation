
from __future__ import annotations
import json, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent
STORE = ROOT / 'game_names_store.json'
SESSION = ROOT / 'runtime_name_candidates.json'
TOKEN_RE = re.compile(r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})')

def load_store():
    try: return json.loads(STORE.read_text(encoding='utf-8'))
    except Exception: return {}

def save_store(data):
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def extract_candidates(text: str):
    seen=[]
    for m in TOKEN_RE.findall(text or ''):
        if len(m) >= 3 and m not in seen:
            seen.append(m)
    return seen[:50]

def save_session_candidates(game: str, items):
    data={game: list(dict.fromkeys(items))}
    SESSION.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

def load_session_candidates(game: str):
    try:
        data=json.loads(SESSION.read_text(encoding='utf-8'))
        return list(data.get(game, []))
    except Exception:
        return []

def merge_names(game: str, new_items):
    data=load_store()
    old=list(data.get(game, []))
    merged=list(dict.fromkeys(old + [x.strip() for x in new_items if str(x).strip()]))
    data[game]=merged
    save_store(data)
    return merged
