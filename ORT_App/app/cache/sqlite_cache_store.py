from __future__ import annotations
import sqlite3, time
from pathlib import Path

class SQLiteCacheStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()
    def _init(self):
        with sqlite3.connect(self.path) as db:
            db.execute("CREATE TABLE IF NOT EXISTS translations (game TEXT, model TEXT, source_key TEXT, source_text TEXT, translation TEXT, hits INTEGER DEFAULT 0, updated REAL, PRIMARY KEY(game, model, source_key))")
            db.execute("CREATE INDEX IF NOT EXISTS idx_trans_updated ON translations(updated)")
    def get(self, game: str, model: str, key: str):
        with sqlite3.connect(self.path) as db:
            row = db.execute("SELECT translation, hits FROM translations WHERE game=? AND model=? AND source_key=?", (game, model, key)).fetchone()
            if row:
                db.execute("UPDATE translations SET hits=?, updated=? WHERE game=? AND model=? AND source_key=?", (int(row[1])+1, time.time(), game, model, key))
                return row[0]
        return None
    def set(self, game: str, model: str, key: str, source_text: str, translation: str):
        with sqlite3.connect(self.path) as db:
            db.execute("INSERT OR REPLACE INTO translations(game,model,source_key,source_text,translation,hits,updated) VALUES(?,?,?,?,?,?,?)", (game, model, key, source_text, translation, 0, time.time()))
