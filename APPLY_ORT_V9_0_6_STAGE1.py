from __future__ import annotations

import datetime as dt
import json
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

PATCH_ID = "v9.0.6-stage1-domain-registry"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def log(message: str) -> None:
    print(f"[ORT v9.0.6 S1] {message}", flush=True)


def find_root(explicit: str = "") -> Path:
    starts = [Path(explicit)] if explicit else []
    starts += [Path(__file__).resolve().parent, Path.cwd()]
    for start in starts:
        current = start.resolve()
        for _ in range(9):
            if (current / "ORT_App" / "app" / "audio" / "locked_asr_adapter.py").is_file():
                return current
            if current.parent == current:
                break
            current = current.parent
    raise RuntimeError("Root proyek ORT tidak ditemukan.")


def write_utf8(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def run_checked(command: list[str], label: str, cwd: Path) -> None:
    import os
    env = dict(os.environ)
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}")
    log(f"{label}: PASS")


def patch_adapter(text: str) -> tuple[str, bool]:
    marker = "ORT_V9_0_6_STAGE1_DOMAIN_REGISTRY"
    if marker in text:
        return text, False

    import_line = "from .gfl2_domain_registry import normalize_domain_text\n"
    anchor = "from .asr_provider_registry import ("
    if import_line not in text:
        if anchor not in text:
            raise RuntimeError("Import anchor locked_asr_adapter tidak ditemukan.")
        text = text.replace(anchor, import_line + "\n" + anchor, 1)

    old = "        text, meta = self._recognize(audio, stable)\n"
    new = (
        "        text, meta = self._recognize(audio, stable)\n"
        "        # ORT_V9_0_6_STAGE1_DOMAIN_REGISTRY\n"
        "        text, domain_matches = normalize_domain_text(text)\n"
    )
    if old not in text:
        raise RuntimeError("Hook hasil ASR tidak ditemukan.")
    text = text.replace(old, new, 1)

    result_anchor = '            "model_used": self.provider_id,\n'
    result_insert = (
        '            "model_used": self.provider_id,\n'
        '            "domain_registry_version": "v9.0.6-stage1",\n'
        '            "domain_matches": domain_matches,\n'
    )
    if result_anchor not in text:
        raise RuntimeError("Metadata result anchor tidak ditemukan.")
    text = text.replace(result_anchor, result_insert, 1)
    return text, True


REGISTRY_JSON = '{\n  "schema_version": 1,\n  "release": "v9.0.6-stage1",\n  "game": "GFL2_EXILIUM",\n  "review_status": "user_approved",\n  "characters": [\n    {\n      "canonical": "Yoshiro",\n      "aliases": [\n        "Yoshlro",\n        "LYoshiro",\n        "FYoshiro",\n        "oshiro"\n      ],\n      "role": "current_commander",\n      "priority": "critical"\n    },\n    {\n      "canonical": "Vasily",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Kenny",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Asteria",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Niter",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Ateraxis",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Lentine",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Lydia",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Klukai",\n      "aliases": [\n        "Klukal",\n        "FKlukai",\n        "Klukais"\n      ],\n      "role": "character",\n      "priority": "high"\n    },\n    {\n      "canonical": "Anjelie",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Groza",\n      "aliases": [\n        "HGroza",\n        "rGroza"\n      ],\n      "role": "character",\n      "priority": "high"\n    },\n    {\n      "canonical": "Zoe",\n      "aliases": [\n        "ZOe",\n        "Zoes"\n      ],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Wulfgar",\n      "aliases": [\n        "Ulfgar",\n        "ulfgar"\n      ],\n      "role": "character",\n      "priority": "high"\n    },\n    {\n      "canonical": "Caldwell",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Dandelion",\n      "aliases": [\n        "Dandelions"\n      ],\n      "role": "important_character",\n      "priority": "critical"\n    },\n    {\n      "canonical": "Mayling",\n      "aliases": [],\n      "role": "character",\n      "priority": "high"\n    },\n    {\n      "canonical": "Voymastina",\n      "aliases": [\n        "FVoymastina"\n      ],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Springfield",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Zhaohui",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Mechty",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Andoris",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Ullrid",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "AK-12",\n      "aliases": [\n        "AK12",\n        "AK十二",\n        "A . K",\n        "A. K",\n        "AK 12"\n      ],\n      "role": "character",\n      "priority": "high"\n    },\n    {\n      "canonical": "Lisa",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Vector",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Leva",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal"\n    },\n    {\n      "canonical": "Helen",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal",\n      "guards": [\n        "do_not_merge_with_Helena"\n      ]\n    },\n    {\n      "canonical": "Helena",\n      "aliases": [],\n      "role": "character",\n      "priority": "normal",\n      "guards": [\n        "do_not_merge_with_Helen"\n      ]\n    }\n  ],\n  "unique_terms": [\n    {\n      "canonical": "Mokosh",\n      "aliases": [\n        "okosh",\n        "okosh\'s",\n        "Mokosch"\n      ],\n      "type": "place_or_community",\n      "translate": false,\n      "priority": "critical"\n    },\n    {\n      "canonical": "Elmo",\n      "aliases": [],\n      "type": "unique_term",\n      "translate": false,\n      "priority": "high"\n    },\n    {\n      "canonical": "Pike Node",\n      "aliases": [\n        "Pike node",\n        "PikeNode",\n        "pike node"\n      ],\n      "type": "location_or_system",\n      "translate": false,\n      "priority": "critical"\n    }\n  ],\n  "rules": {\n    "preserve_canonical_spelling": true,\n    "do_not_translate_unique_terms": true,\n    "speaker_dialog_split_guard": {\n      "enabled": true,\n      "example_invalid_entity": "Yoshiro Dandelion",\n      "interpretation": "speaker_name_plus_dialog_addressee"\n    },\n    "training_policy": {\n      "raw_logs_are_quarantined": true,\n      "only_user_approved_entities_are_active": true,\n      "incorrect_translations_must_not_enter_cache_or_training": true\n    }\n  }\n}'
MODULE_SOURCE = 'from __future__ import annotations\n\nimport json\nimport re\nfrom functools import lru_cache\nfrom pathlib import Path\nfrom typing import Any\n\n_DATA_PATH = Path(__file__).resolve().parent / "data" / "gfl2_exilium_registry.json"\n\n\n@lru_cache(maxsize=1)\ndef load_registry() -> dict[str, Any]:\n    return json.loads(_DATA_PATH.read_text(encoding="utf-8"))\n\n\ndef _alias_rows() -> list[tuple[str, str, str, str]]:\n    registry = load_registry()\n    rows: list[tuple[str, str, str, str]] = []\n    for group_name in ("characters", "unique_terms"):\n        entity_type = "character" if group_name == "characters" else "unique_term"\n        for item in registry[group_name]:\n            canonical = str(item["canonical"])\n            role = str(item.get("role") or item.get("type") or "")\n            rows.append((canonical, canonical, entity_type, role))\n            for alias in item.get("aliases", []):\n                rows.append((str(alias), canonical, entity_type, role))\n    rows.sort(key=lambda row: len(row[0]), reverse=True)\n    return rows\n\n\ndef _replace_alias(text: str, alias: str, canonical: str) -> tuple[str, int]:\n    escaped = re.escape(alias)\n    if re.fullmatch(r"[A-Za-z0-9 .\'-]+", alias):\n        pattern = rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"\n    else:\n        pattern = escaped\n    return re.subn(pattern, canonical, text, flags=re.IGNORECASE)\n\n\ndef normalize_domain_text(value: Any) -> tuple[str, list[dict[str, str]]]:\n    text = " ".join(str(value or "").strip().split())\n    matches: list[dict[str, str]] = []\n    if not text:\n        return text, matches\n\n    seen: set[tuple[str, str]] = set()\n    for alias, canonical, entity_type, role in _alias_rows():\n        updated, count = _replace_alias(text, alias, canonical)\n        if count:\n            text = updated\n            key = (canonical, entity_type)\n            if key not in seen:\n                seen.add(key)\n                matches.append({\n                    "canonical": canonical,\n                    "type": entity_type,\n                    "role": role,\n                    "matched_alias": alias,\n                })\n    return text, matches\n\n\ndef normalize_asr_text(value: Any) -> tuple[str, list[dict[str, str]]]:\n    return normalize_domain_text(value)\n\n\ndef normalize_ocr_text(value: Any) -> tuple[str, list[dict[str, str]]]:\n    return normalize_domain_text(value)\n\n\ndef protected_terms() -> set[str]:\n    registry = load_registry()\n    return {\n        str(item["canonical"])\n        for item in registry["unique_terms"]\n        if item.get("translate") is False\n    }\n'
TEST_SOURCE = 'from __future__ import annotations\n\nimport json\nimport sys\nfrom pathlib import Path\n\nif hasattr(sys.stdout, "reconfigure"):\n    sys.stdout.reconfigure(encoding="utf-8", errors="replace")\n\nroot = Path(sys.argv[1]).resolve()\nsys.path.insert(0, str(root / "ORT_App"))\n\nfrom app.audio.gfl2_domain_registry import load_registry, normalize_domain_text, protected_terms\n\ntests = {\n    "Ulfgar": "Wulfgar",\n    "Yoshlro": "Yoshiro",\n    "AK十二": "AK-12",\n    "Klukal": "Klukai",\n    "PikeNode": "Pike Node",\n    "okosh": "Mokosh",\n}\nresults = {}\nfor source, expected in tests.items():\n    output, matches = normalize_domain_text(source)\n    assert output == expected, (source, output, expected)\n    results[source] = {"output": output, "matches": matches}\n\nregistry = load_registry()\ncharacters = {item["canonical"]: item for item in registry["characters"]}\nunique_terms = {item["canonical"]: item for item in registry["unique_terms"]}\n\nassert characters["Yoshiro"]["role"] == "current_commander"\nassert characters["Dandelion"]["role"] == "important_character"\nassert "Wulfgar" in characters and "Ulfgar" not in characters\nassert unique_terms["Mokosh"]["type"] == "place_or_community"\nassert protected_terms() == {"Mokosh", "Elmo", "Pike Node"}\n\nprint(json.dumps({\n    "passed": True,\n    "character_count": len(characters),\n    "unique_term_count": len(unique_terms),\n    "protected_terms": sorted(protected_terms()),\n    "tests": results,\n}, ensure_ascii=False, indent=2))\n'


def main() -> int:
    root = find_root(sys.argv[1] if len(sys.argv) > 1 else "")
    adapter = root / "ORT_App" / "app" / "audio" / "locked_asr_adapter.py"
    module = root / "ORT_App" / "app" / "audio" / "gfl2_domain_registry.py"
    data = root / "ORT_App" / "app" / "audio" / "data" / "gfl2_exilium_registry.json"
    audit = root / "ORT" / "audit" / "v9_0_6_stage1_registry_audit.json"
    status = root / "ORT" / "status" / "V9_0_6_STAGE1.json"

    cpu = root / "ORT_Runtime" / "audio_cpu" / ".venv" / "Scripts" / "python.exe"
    gpu = root / "ORT_Runtime" / "audio_gpu" / ".venv" / "Scripts" / "python.exe"
    if not cpu.is_file():
        raise RuntimeError(f"Runtime CPU tidak ditemukan: {cpu}")

    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = root / "ORT" / "backups" / f"ORT_V9_0_6_STAGE1_{timestamp}"
    backup.mkdir(parents=True, exist_ok=True)

    originals: dict[Path, bytes | None] = {}
    targets = [adapter, module, data, audit, status]
    for target in targets:
        originals[target] = target.read_bytes() if target.exists() else None
        if target.exists():
            destination = backup / target.relative_to(root)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, destination)

    try:
        registry_payload = json.loads(REGISTRY_JSON)
        write_utf8(data, json.dumps(registry_payload, ensure_ascii=False, indent=2))
        write_utf8(module, MODULE_SOURCE)

        adapter_text = adapter.read_text(encoding="utf-8-sig")
        newline = "\r\n" if "\r\n" in adapter_text else "\n"
        normalized = adapter_text.replace("\r\n", "\n")
        patched, changed = patch_adapter(normalized)
        adapter.write_text(patched.replace("\n", newline), encoding="utf-8", newline="")

        audit_payload = {
            "release": PATCH_ID,
            "created_at": dt.datetime.now().astimezone().isoformat(),
            "source": "user_reviewed_streaming_session",
            "approved_character_count": len(registry_payload["characters"]),
            "approved_unique_term_count": len(registry_payload["unique_terms"]),
            "critical_entities": ["Yoshiro", "Dandelion", "Wulfgar", "Mokosh", "Pike Node"],
            "corrections": {"Ulfgar": "Wulfgar", "Mokosh": "unique_term/place_or_community"},
            "mandatory_stage1": {
                "Yoshiro": "current_commander",
                "Dandelion": "important_character",
                "Mokosh": "unique_term",
                "Elmo": "unique_term",
                "Pike Node": "unique_term",
            },
            "training_state": "quarantined_until_audited",
            "raw_log_auto_training": False,
            "next_stage_candidates": [
                "audio_ocr_fusion",
                "short_utterance_ja_lexicon",
                "translation_contamination_guard",
                "cache_quality_gate",
                "final_polarity_guard",
            ],
        }
        write_utf8(audit, json.dumps(audit_payload, ensure_ascii=False, indent=2))

        for cache in [
            root / "ORT_App" / "app" / "audio" / "__pycache__",
            root / "ORT_App" / "__pycache__",
        ]:
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)

        py_compile.compile(str(module), doraise=True)
        py_compile.compile(str(adapter), doraise=True)
        run_checked([str(cpu), "-m", "py_compile", str(module), str(adapter)], "CPU py_compile", root)
        if gpu.is_file():
            run_checked([str(gpu), "-m", "py_compile", str(module), str(adapter)], "CUDA py_compile", root)

        test_script = backup / "verify_stage1.py"
        write_utf8(test_script, TEST_SOURCE)
        run_checked([str(cpu), str(test_script), str(root)], "Registry verification", root)

        status_payload = {
            "patch": PATCH_ID,
            "applied_at": dt.datetime.now().astimezone().isoformat(),
            "project_root": str(root),
            "backup_root": str(backup),
            "registry_file": str(data),
            "audio_integration": True,
            "ocr_shared_registry_ready": True,
            "ocr_runtime_hook": False,
            "approved_characters": len(registry_payload["characters"]),
            "approved_unique_terms": len(registry_payload["unique_terms"]),
            "models_downloaded": False,
            "verification": "PASS",
        }
        write_utf8(status, json.dumps(status_payload, ensure_ascii=False, indent=2))

        rollback = backup / "ROLLBACK_V9_0_6_STAGE1.py"
        rows = []
        for target, original in originals.items():
            rows.append({
                "target": str(target),
                "backup": str(backup / target.relative_to(root)),
                "existed": original is not None,
            })
        write_utf8(
            rollback,
            "import shutil\nfrom pathlib import Path\n"
            f"rows={rows!r}\n"
            "for row in rows:\n"
            "    target=Path(row['target'])\n"
            "    if row['existed']:\n"
            "        target.parent.mkdir(parents=True,exist_ok=True)\n"
            "        shutil.copy2(row['backup'],target)\n"
            "    elif target.exists():\n"
            "        target.unlink()\n"
            "print('ROLLBACK v9.0.6 STAGE 1: PASS')\n",
        )
        rollback_bat = backup / "ROLLBACK_V9_0_6_STAGE1.bat"
        rollback_bat.write_text(
            f'@echo off\r\nchcp 65001 >nul\r\n"{cpu}" "{rollback}"\r\npause\r\n',
            encoding="utf-8",
        )

        log("UPDATE SELESAI")
        print("ORT v9.0.6 Stage 1 Domain Registry: PASS")
        print(f"Status : {status}")
        print(f"Backup : {backup}")
        return 0

    except Exception:
        log("Verifikasi gagal; memulihkan source.")
        for target, original in originals.items():
            if original is None:
                if target.exists():
                    target.unlink()
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(original)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ORT v9.0.6 S1][ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise SystemExit(1)
