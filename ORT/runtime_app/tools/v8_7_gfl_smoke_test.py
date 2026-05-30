from __future__ import annotations

"""Small dependency-light regression checks for the v8.7 GFL profile.

Run from the project root with:
    python tools/v8_7_gfl_smoke_test.py
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def check() -> list[str]:
    os.environ["ORT_GAME_PROFILE"] = "GFL"
    os.environ["ORT_GFL_ARTIFACT_FILTER"] = "1"
    os.environ["ORT_GFL_CACHE_NORMALIZED"] = "1"
    os.environ["ORT_GFL_CACHE_STABLE_ONLY"] = "1"

    from app.games.gfl_profile import (
        extract_layout_text,
        is_non_dialog_text,
        normalize_gfl_text,
    )
    from app.translation.fuzzy_cache_normalizer import normalize_cache_key
    from cache_store import should_cache_text
    from data_processing_backend import extract_candidates_from_line, get_game_data
    from v7_system_profile import env_from_settings, game_choices

    results: list[str] = []
    assert normalize_gfl_text("Dandelion: Fine. gFn") == "Dandelion: Fine."
    assert normalize_gfl_text("Dandelion: Fine. ngf") == "Dandelion: Fine."
    results.append("footer artifact normalization")

    assert normalize_cache_key("Dandelion: Fine. gFn") == normalize_cache_key("Dandelion: Fine. ngf")
    results.append("normalized GFL cache key")

    assert is_non_dialog_text("GAME DESIGN SUNBORN")
    assert extract_candidates_from_line("[OCR] CHARACTER VO SUNBORN gFn", "GFL") == []
    results.append("credit/non-dialog candidate guard")

    detections = [
        ([[15, 15], [130, 15], [130, 40], [15, 40]], "AK-12", 0.98),
        ([[15, 80], [240, 80], [240, 115], [15, 115]], "Shit!", 0.99),
        ([[850, 190], [980, 190], [980, 230], [850, 230]], "GFsystem gFn", 0.92),
    ]
    extracted, meta = extract_layout_text(detections, (250, 1000, 3))
    assert extracted == "AK-12: Shit!", (extracted, meta)
    assert meta["footer_removed"] >= 1
    results.append("Name/Body ROI + footer bbox mask")

    ok, reason = should_cache_text("gFn", "teks")
    assert not ok and reason in {"gfl_non_dialog_or_footer", "source_too_short"}
    results.append("cache contamination rejection")

    env = env_from_settings("GFL")
    assert env["ORT_GFL_LAYOUT"] == "1" and env["ORT_GFL_FOOTER_MASK"] == "1"
    assert any(value == "GFL" for _label, value in game_choices())
    results.append("GFL game selection/env contract")

    gfl_data = get_game_data("GFL")
    assert "AK-12" in gfl_data["names"] and "Task Force DEFY" in gfl_data["special_words"]
    results.append("GFL seeded glossary")
    return results


if __name__ == "__main__":
    done = check()
    print("v8.7 GFL smoke test PASS")
    for item in done:
        print("-", item)
