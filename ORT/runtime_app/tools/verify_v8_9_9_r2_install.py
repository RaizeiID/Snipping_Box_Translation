from __future__ import annotations

import hashlib
import json
import py_compile
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parents[1]
MANIFEST = PROJECT_ROOT / "SHA256SUMS_V8_9_9_R2.txt"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    versions = [
        PROJECT_ROOT / "VERSION.txt",
        ROOT / "ORTCORE_VERSION.txt",
        ROOT / "TITANCORE_VERSION.txt",
    ]
    for path in versions:
        if path.read_text(encoding="utf-8-sig").strip() != "v8.9.9":
            errors.append(f"version mismatch: {path}")
    test = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "v8_9_9_r2_gpu_cpu_realtime_test.py")],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        check=False,
    )
    if test.returncode != 0:
        errors.append("regression: " + test.stdout[-3000:])
    payload = {"passed": not errors, "checked_files": checked, "errors": errors, "regression_output": test.stdout.strip()}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
