"""ORT v9.0.7 R24 -- Argos must reach standby without blocking boot.

Argos was a fallback whose start-up cost landed at the worst moment. Measured
on a clean process: get_translation() returns in 0 ms, but the FIRST real
translate() takes 10.7 s (the model and sentence splitter load there), and the
second takes 65 ms. That first call was paid lazily, at the first CT2 -> Argos
crossing, mid-session -- and 33 of 131 recorded sessions crossed at least once,
across 881 crossings total.

So the fallback behaved like a generator that needs ten seconds to start, not
like a no-break changeover. R24 pays that cost on a background thread during
boot instead. The properties that have to hold:

  * boot is never blocked, however slow or broken the warm-up is
  * a warm-up failure is survivable -- CT2 serves every frame anyway
  * the env gate can turn it off without touching code
"""
from __future__ import annotations

import json
import re
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

results: dict[str, object] = {}


def assert_true(cond, msg):
    if not cond:
        raise AssertionError(msg)


SRC = (Path(__file__).resolve().parent.parent / "TITANMAIN.py").read_text(
    encoding="utf-8", errors="replace"
)

m = re.search(r"^_ARGOS_STANDBY_STATE.*?(?=^def _argos_warn_once)", SRC, re.S | re.M)
assert_true(m, "_start_argos_standby not found in TITANMAIN.py")

LOGS: list[str] = []
CALLS: list[tuple] = []


def make_ns(env, translate):
    ns = {
        "os": type("O", (), {"environ": env})(),
        "time": time,
        "threading": threading,
        "log": LOGS.append,
        "_argos_translate": translate,
    }
    exec(m.group(0), ns)
    return ns


# --- 1. a slow warm-up must not hold up boot --------------------------------
def slow(text, src, dst):
    CALLS.append((src, dst))
    time.sleep(1.5)
    return "ok"


ns = make_ns({}, slow)
t0 = time.time()
th = ns["_start_argos_standby"]()
boot_blocked_ms = (time.time() - t0) * 1000

assert_true(th is not None, "standby thread was not started")
assert_true(th.daemon, "standby thread is not a daemon; it would hold the app open")
assert_true(boot_blocked_ms < 250, f"boot blocked for {boot_blocked_ms:.0f} ms")
results["boot_not_blocked"] = f"PASS ({boot_blocked_ms:.0f} ms)"

th.join(timeout=10)
assert_true(ns["_ARGOS_STANDBY_STATE"]["ready"], "standby never reported ready")
assert_true(CALLS == [("en", "id")], f"warmed the wrong pair: {CALLS}")
results["warms_en_id"] = "PASS"

# The probe must be a real sentence -- a bare word can skip the sentence
# splitter, which is where most of the 10.7 s actually goes.
probe = re.search(r'_argos_translate\(\s*"([^"]+)"', m.group(0))
assert_true(probe, "warm-up probe text not found")
assert_true(
    len(probe.group(1).split()) >= 4 and probe.group(1).rstrip().endswith("."),
    f"probe {probe.group(1)!r} is too trivial to load the splitter",
)
results["probe_is_a_sentence"] = "PASS"


# --- 2. a broken warm-up must be survivable ---------------------------------
def boom(text, src, dst):
    raise RuntimeError("no network")


LOGS.clear()
ns2 = make_ns({}, boom)
th2 = ns2["_start_argos_standby"]()
th2.join(timeout=10)

assert_true(not ns2["_ARGOS_STANDBY_STATE"]["ready"], "failed warm-up claimed ready")
assert_true("no network" in ns2["_ARGOS_STANDBY_STATE"]["error"], "error not recorded")
assert_true(any("Standby warm-up failed" in x for x in LOGS), "failure was silent")
results["failure_survivable"] = "PASS"


# --- 3. the gate must actually gate -----------------------------------------
CALLS.clear()
ns3 = make_ns({"ORT_ARGOS_STANDBY": "0"}, slow)
assert_true(ns3["_start_argos_standby"]() is None, "gate did not stop the warm-up")
assert_true(CALLS == [], "warm-up ran despite the gate")
results["env_gate_respected"] = "PASS"

results["passed"] = True
print(json.dumps(results, ensure_ascii=False, indent=2))
