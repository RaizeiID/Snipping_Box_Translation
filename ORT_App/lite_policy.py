# -*- coding: utf-8 -*-
"""lite_policy.py

Policy helper khusus untuk *model Lite*.

Fokus awal (V1 Lite):
- Debounce hanya untuk mode HIGH_LATENCY (indikator oranye).
- Mode STABLE dan FREEZE TIDAK BOLEH disentuh (tidak ada debounce/penundaan tambahan).
- Tujuan: ketika dialog masih "bertambah" (teks belum full), jangan buru-buru translate.
  Begitu teks sudah stabil (tidak berubah) selama beberapa saat, baru translate.
- Cocok untuk: story mode / manual advance / VA masih bicara tapi teks sudah penuh.

Cara pakai:
- Di model lite, set env:
    TITAN_USE_LITE_POLICY=1
  Opsional tuning:
    TITAN_LITE_STABLE_WINDOW_MS=850
    TITAN_LITE_FORCE_COMMIT_MS=3000
    TITAN_LITE_MIN_LIFE_MS=250

NOTE:
- Fungsi ini sengaja sederhana dan aman (fail-open bila state rusak).
"""

from __future__ import annotations

import time
from typing import Dict, Any


def _now_ms() -> int:
    return int(time.time() * 1000)


def v1_high_latency_should_translate(
    raw_text: str,
    state: Dict[str, Any],
    *,
    stable_window_ms: int = 850,
    force_commit_ms: int = 3000,
    min_life_ms: int = 250,
) -> bool:
    """Return True jika HIGH_LATENCY boleh menerjemahkan sekarang.

    Logika:
    - Saat teks berubah -> reset timer.
    - Jika teks *stabil* selama stable_window_ms -> translate.
    - Jika teks bertahan terlalu lama (force_commit_ms) -> translate (safety).
    - Jangan spam terjemahan untuk teks yang sama (skip jika sudah committed).
    """
    try:
        now = _now_ms()
        txt = (raw_text or "").strip()

        if not txt:
            return False

        last = state.get("last_text")
        last_committed = state.get("last_committed")

        # new/changed text
        if txt != last:
            state["last_text"] = txt
            state["first_seen_ms"] = now
            state["last_change_ms"] = now
            state["committed"] = False
            return False  # jangan langsung translate, tunggu stabil

        # unchanged
        first_seen = int(state.get("first_seen_ms", now))
        last_change = int(state.get("last_change_ms", first_seen))
        life_ms = now - first_seen
        stable_ms = now - last_change

        # minimal life guard (hindari OCR flicker 1-2 frame)
        if life_ms < int(min_life_ms):
            return False

        # if already committed, skip until text changes
        if last_committed == txt:
            return False

        if stable_ms >= int(stable_window_ms):
            return True

        if life_ms >= int(force_commit_ms):
            return True

        return False
    except Exception:
        # fail-open? lebih aman untuk tidak menahan terlalu lama:
        return True


def v1_high_latency_mark_committed(raw_text: str, state: Dict[str, Any] | None) -> None:
    """Tandai teks terakhir sebagai sudah diterjemahkan (agar tidak diulang)."""
    if not state:
        return
    try:
        txt = (raw_text or "").strip()
        if not txt:
            return
        state["last_committed"] = txt
        state["committed"] = True
    except Exception:
        return
