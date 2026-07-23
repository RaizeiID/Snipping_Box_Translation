from __future__ import annotations

import hashlib
import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
MANIFEST = PROJECT_ROOT / "SHA256SUMS_V8_9_9_R2_F2.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def run_test(path: Path, timeout: int = 180) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(path)],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    return result.returncode == 0, result.stdout.strip()


def run_self_test(timeout: int = 120) -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / "audio_realtime_local_sidecar.py"), "--self-test-json"],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )
    output = result.stdout.strip()
    passed = result.returncode == 0 and '"passed": true' in output.lower()
    return passed, output


def main() -> int:
    errors: list[str] = []
    checked = 0
    if not MANIFEST.is_file():
        errors.append(f"missing manifest: {MANIFEST}")
    else:
        for line in MANIFEST.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            expected, relative = line.split("  ", 1)
            path = PROJECT_ROOT / relative
            if not path.is_file():
                errors.append(f"missing: {relative}")
                continue
            actual = sha256(path)
            checked += 1
            if actual.lower() != expected.lower():
                errors.append(f"checksum: {relative}")
            if path.suffix == ".py":
                try:
                    py_compile.compile(str(path), doraise=True)
                except Exception as exc:
                    errors.append(f"compile {relative}: {exc}")

    for path in (
        PROJECT_ROOT / "VERSION.txt",
        ROOT / "ORTCORE_VERSION.txt",
        ROOT / "TITANCORE_VERSION.txt",
    ):
        try:
            if path.read_text(encoding="utf-8-sig").strip() != "v8.9.9":
                errors.append(f"version mismatch: {path}")
        except Exception as exc:
            errors.append(f"version read: {path}: {exc}")

    build = (ROOT / "build_info.py").read_text(encoding="utf-8")
    for marker in (
        'RELEASE_NAME = "R2 F2 Long-Turn Context and Japanese Accuracy Fix"',
        'RELEASE_CHANNEL = "v8-9-9-r2-f2-long-turn-japanese-context"',
    ):
        if marker not in build:
            errors.append(f"build marker: {marker}")

    results = []
    for test_path in (
        ROOT / "tools" / "v8_9_9_r2_gpu_cpu_realtime_test.py",
        ROOT / "tools" / "v8_9_9_r2_f1_hybrid_subtitle_continuity_test.py",
        ROOT / "tools" / "v8_9_9_r2_f2_long_turn_japanese_context_test.py",
    ):
        try:
            passed, output = run_test(test_path)
        except Exception as exc:
            passed, output = False, str(exc)
        results.append({"test": test_path.name, "passed": passed, "output": output})
        if not passed:
            errors.append(f"regression {test_path.name}: {output[-3000:]}")

    try:
        self_passed, self_output = run_self_test()
    except Exception as exc:
        self_passed, self_output = False, str(exc)
    results.append({"test": "audio_realtime_local_sidecar --self-test-json", "passed": self_passed})
    if not self_passed:
        errors.append(f"self-test: {self_output[-3000:]}")

    payload = {
        "passed": not errors,
        "version": "v8.9.9",
        "hotfix": "R2 F2 Long-Turn Context and Japanese Accuracy",
        "checked_files": checked,
        "errors": errors,
        "tests": results,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
