from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app.open_architecture.runtime_control import PartialTranslationGate, PreloadBarrier, TranslationWatchdogPolicy
from app.open_architecture.streaming.confirmed_prefix import ConfirmedPrefixEngine
from build_info import APP_VERSION_TAG
from audio_realtime_local_sidecar import _wait_for_start_gate


def main() -> int:
    assert APP_VERSION_TAG == "v9.0.4"

    barrier = PreloadBarrier()
    barrier.begin(now=100.0)
    assert barrier.mark_translator_ready() is False
    assert barrier.activated is False
    assert barrier.mark_asr_ready() is True
    assert barrier.activated is True
    assert barrier.mark_asr_ready() is False

    prefix = ConfirmedPrefixEngine(agreement_passes=2)
    a = prefix.update("私たちは", final=False)
    b = prefix.update("私たちはここを", final=False)
    c = prefix.update("私たちはここを離れなければならない", final=True)
    assert a["display"] == "私たちは"
    assert b["confirmed"] == "私たちは"
    assert c["display"] == "私たちはここを離れなければならない"

    gate = PartialTranslationGate("normal")
    decisions = [
        gate.should_submit("私たちは", confirmed="", stable=False, now=1.00),
        gate.should_submit("私たちはここ", confirmed="", stable=False, now=1.20),
        gate.should_submit("私たちはここを", confirmed="私たちは", stable=False, now=1.25),
        gate.should_submit("私たちはここを離れる", confirmed="私たちは", stable=False, now=1.40),
        gate.should_submit("私たちはここを離れなければならない", confirmed="私たちはここを", stable=False, now=1.50),
        gate.should_submit("私たちはここを離れなければならない。", confirmed="私たちはここを離れなければならない。", stable=True, now=1.70),
    ]
    assert decisions[0][0] is True
    assert decisions[1][0] is False
    assert decisions[2][0] is True
    assert decisions[3][0] is False
    assert decisions[4][0] is True
    assert decisions[5][0] is True

    assert TranslationWatchdogPolicy.for_profile("speed").timeout_s < TranslationWatchdogPolicy.for_profile("normal").timeout_s
    assert TranslationWatchdogPolicy.for_profile("normal").timeout_s < TranslationWatchdogPolicy.for_profile("accurate").timeout_s

    with tempfile.TemporaryDirectory(prefix="ort-lab-gate-") as tmp:
        gate_path = Path(tmp) / "capture.start"
        writer = threading.Thread(
            target=lambda: (time.sleep(0.05), gate_path.write_text("START\n", encoding="utf-8")),
            daemon=True,
        )
        writer.start()
        _wait_for_start_gate(str(gate_path), timeout_s=2.0)
        writer.join(timeout=1.0)
        assert gate_path.is_file()

    webui = (APP_ROOT / "webui.py").read_text(encoding="utf-8-sig")
    audio = (APP_ROOT / "audio_main.py").read_text(encoding="utf-8-sig")
    sidecar = (APP_ROOT / "audio_realtime_local_sidecar.py").read_text(encoding="utf-8-sig")
    assert "Copy Log Lab" in webui
    assert 'elem_id="oa_live_log"' in webui
    assert "Preload & Mulai Audio Lab" in webui
    assert "TRANSLATION WATCHDOG" in audio
    assert "LAB PRELOAD" in audio
    assert "PRELOAD_WAITING_FOR_START" in sidecar
    assert "list(segments)" in sidecar

    result = {
        "passed": True,
        "version": APP_VERSION_TAG,
        "preload_barrier": "PASS",
        "cjk_confirmed_prefix": "PASS",
        "partial_coalescing": decisions,
        "translation_watchdog": {
            "speed_s": TranslationWatchdogPolicy.for_profile("speed").timeout_s,
            "normal_s": TranslationWatchdogPolicy.for_profile("normal").timeout_s,
            "accurate_s": TranslationWatchdogPolicy.for_profile("accurate").timeout_s,
        },
        "log_copy": "PASS",
        "overlay_readiness_gate": "PASS",
        "sidecar_start_gate": "PASS",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
