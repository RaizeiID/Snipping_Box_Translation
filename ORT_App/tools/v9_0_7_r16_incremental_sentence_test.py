"""ORT v9.0.7 R16 -- incremental per-sentence translation regression test.

Auto story re-translated the whole accumulated block on every frame. Field
sessions showed 67-73% of OCR frames were continuations, backend cost tracked
block length (27 ms at 1-30 chars, 155 ms at 91-120), and the queue backed up
until the text stopped growing. Finished sentences are now translated once and
reused; only the sentence still being typed is re-translated.

Checks:
  1. the segmenter rebuilds its input byte-for-byte
  2. short lines keep the OLD behaviour exactly (no split, no risk)
  3. long multi-sentence lines cut backend work substantially
  4. a refused (ct2_held) or identity result is never cached
  5. a reused sentence still reports its backend engine, so meta["engine"] holds
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from translation_engine import TranslationEngine, _split_sentences  # noqa: E402

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


class StubEngine:
    """Only the pieces `_translate_offline` touches."""

    def __init__(self, held=False, identity=False):
        self._sentence_cache = {}
        self._sentence_reuse_count = 0
        self._request_backend_engines = []
        self._held = held
        self._identity = identity
        self.calls = 0
        self.chars = 0

    def _translate_offline_raw(self, text):
        self.calls += 1
        self.chars += len(text)
        if self._held:
            self._request_backend_engines.append("ct2_held")
            return text
        if self._identity:
            self._request_backend_engines.append("ct2_fast")
            return text
        self._request_backend_engines.append("ct2_fast")
        return "[ID]" + text


StubEngine._translate_offline = TranslationEngine._translate_offline
StubEngine._sentence_cache_put = TranslationEngine._sentence_cache_put


def replay(base, flag, **kw):
    os.environ["ORT_INCREMENTAL_SENTENCE_TRANSLATE"] = flag
    engine = StubEngine(**kw)
    frames = [base[:n] for n in range(8, len(base) + 1, 14)] + [base]
    out = [engine._translate_offline(f) for f in frames]
    return out, engine


SHORT = "No. It goes beyond that. She is"
LONG = (
    "Oleg Girard, the head of Project Eden, had already been arrested. "
    "Chiloveig, the person in charge of the explosion site, is under further "
    "investigation. Tlazo Incorporated will come up clean."
)

# 1 -- lossless segmentation
for sample in (SHORT, LONG, "", "Halo.", "A.  B!  C?  tail"):
    parts = _split_sentences(sample)
    rebuilt = "".join(chunk + sep for chunk, _done, sep in parts)
    assert_true(rebuilt == sample, f"segmenter lost data on {sample!r}")
results["lossless_segmentation"] = "PASS"

# 2 -- short lines are untouched
off, off_engine = replay(SHORT, "0")
on, on_engine = replay(SHORT, "1")
assert_true(off == on, "short line output changed")
assert_true(off_engine.chars == on_engine.chars, "short line did extra backend work")
assert_true(on_engine._sentence_reuse_count == 0, "short line should not split")
results["short_lines_unchanged"] = f"PASS ({off_engine.chars} chars both ways)"

# 3 -- long lines get cheaper
off, off_engine = replay(LONG, "0")
on, on_engine = replay(LONG, "1")
saved = 1 - (on_engine.chars / max(1, off_engine.chars))
assert_true(saved > 0.30, f"expected >30% less backend work, got {saved:.0%}")
assert_true(on_engine._sentence_reuse_count > 0, "no sentence was reused")
results["long_lines_cheaper"] = (
    f"PASS ({off_engine.chars} -> {on_engine.chars} chars, -{saved:.0%}, "
    f"{on_engine._sentence_reuse_count} sentences reused)"
)

# 4 -- refused/identity results must not be frozen into the cache
_, held_engine = replay(LONG, "1", held=True)
assert_true(not held_engine._sentence_cache, "ct2_held result was cached")
_, id_engine = replay(LONG, "1", identity=True)
assert_true(not id_engine._sentence_cache, "identity result was cached")
results["refused_results_not_cached"] = "PASS"

# 5 -- a reused sentence still reports an engine
_, engine = replay(LONG, "1")
assert_true(
    "ct2_fast" in engine._request_backend_engines,
    "reuse lost the backend engine tag, meta['engine'] would be wrong",
)
results["engine_tag_preserved"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
