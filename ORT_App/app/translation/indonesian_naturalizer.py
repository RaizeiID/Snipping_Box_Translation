from __future__ import annotations

# v8.6: Fast IDN naturalizer delegates to the shared IDN Quality Layer in fast_light
# mode.  This keeps Fast IDN low-latency while making terminology/pronoun cleanup
# consistent with Lite IDN and Normal IDN.

try:
    from app.translation.idn_quality_layer import apply_idn_quality
except Exception:  # pragma: no cover
    apply_idn_quality = None


def naturalize_fast_idn(source: str, translation: str) -> str:
    out = str(translation or "").strip()
    if not out:
        return out
    if apply_idn_quality is None:
        return out
    return apply_idn_quality(source, out, mode="fast_light", tags=["fast_idn", "idn"])
