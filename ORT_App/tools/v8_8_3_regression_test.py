from __future__ import annotations

import os
import tempfile
import sys
from pathlib import Path

RUNTIME_ROOT = Path(__file__).resolve().parents[1]
if str(RUNTIME_ROOT) not in sys.path:
    sys.path.insert(0, str(RUNTIME_ROOT))


def _make_ct2_model(root: Path) -> Path:
    d = root / "models" / "ct2_opus_mt_en_id"
    d.mkdir(parents=True, exist_ok=True)
    for name in ("model.bin", "source.spm", "target.spm", "shared_vocabulary.json", "config.json"):
        (d / name).write_text("x", encoding="utf-8")
    return d


def test_ct2_path_resolver() -> None:
    from app.runtime.ct2_path_resolver import resolve_ct2_model_dir
    with tempfile.TemporaryDirectory() as td:
        project = Path(td)
        runtime_app = project / "ORT" / "runtime_app"
        runtime_app.mkdir(parents=True)
        expected = _make_ct2_model(project).resolve()
        res = resolve_ct2_model_dir(runtime_app)
        assert res.likely_valid, res
        assert res.path.resolve() == expected, (res.path, expected)


def test_overlay_commit_gate() -> None:
    from app.runtime.overlay_commit_gate import OverlayCommitGate
    gate = OverlayCommitGate(min_visible_ms=800, min_token_gain=3)
    d1 = gate.decide(speaker_html="S", dialog_html="A", plain_translation="Aku masih di sisimu. Kamu tidak sendiri.", source_text="still by your side", turn_id="t1", trusted_preview=True)
    assert d1.commit, d1
    gate.mark_committed(speaker_html="S", dialog_html="A", plain_translation="Aku masih di sisimu. Kamu tidak sendiri.", source_text="still by your side", turn_id="t1", signature=d1.signature)
    d2 = gate.decide(speaker_html="S", dialog_html="B", plain_translation="Aku masih disisimu, kamu tidak sendiri", source_text="Tmstill by yoUr side", turn_id="t1", cache="HIT_STABLE_FINAL")
    assert not d2.commit and d2.state == "DUPLICATE", d2
    d3 = gate.decide(speaker_html="S", dialog_html="C", plain_translation="Aku masih di sisimu.", source_text="shorter", turn_id="t1", trusted_preview=True)
    assert not d3.commit and d3.state in {"NO_DOWNGRADE", "MIN_VISIBLE", "SIMILAR"}, d3
    d4 = gate.decide(speaker_html="S", dialog_html="D", plain_translation="Aku masih di sisimu. Kamu tidak sendiri. Mari kita menunggu Komandan kembali.", source_text="full", turn_id="t1", final=True)
    assert d4.commit, d4


def test_render_signature() -> None:
    from app.runtime.render_signature import similarity
    assert similarity("Tmstill by yoUr side; Youre not alone", "still by your side; You're not alone") >= 0.78


if __name__ == "__main__":
    test_ct2_path_resolver()
    test_render_signature()
    test_overlay_commit_gate()
    print("v8.8.3 regression PASS")
