from __future__ import annotations

def safe_text(fn, fallback: str = "Status belum tersedia. Klik refresh setelah runtime berjalan.") -> str:
    try:
        return str(fn())
    except Exception as exc:
        return f"{fallback}\nDetail: {exc}"
