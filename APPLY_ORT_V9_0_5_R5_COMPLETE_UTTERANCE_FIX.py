from __future__ import annotations

import datetime as _dt
import json
import py_compile
import re
import shutil
import subprocess
import sys
from pathlib import Path

PATCH_ID = "v9.0.5-R5-COMPLETE-UTTERANCE-STREAMING"
MARKER = "ORT_R5_COMPLETE_UTTERANCE"


def log(message: str) -> None:
    print(f"[ORT R5] {message}", flush=True)


def find_root(explicit: str = "") -> Path:
    starts: list[Path] = []
    if explicit:
        starts.append(Path(explicit))
    starts.extend([Path(__file__).resolve().parent, Path.cwd()])
    for start in starts:
        current = start.resolve()
        for _ in range(9):
            if (current / "ORT_App" / "audio_realtime_local_sidecar.py").is_file():
                return current
            if current.parent == current:
                break
            current = current.parent
    raise RuntimeError("Root proyek ORT tidak ditemukan. Ekstrak paket langsung ke root proyek ORT.")


def read_source(path: Path) -> tuple[str, str]:
    text = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in text else "\n"
    return text.replace("\r\n", "\n"), newline


def write_source(path: Path, text: str, newline: str) -> None:
    path.write_bytes(text.replace("\r\n", "\n").replace("\n", newline).encode("utf-8"))


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: pola harus berjumlah 1, ditemukan {count}.")
    return text.replace(old, new, 1)


def regex_replace_once(text: str, pattern: str, replacement: str, label: str) -> str:
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.DOTALL | re.MULTILINE)
    if count != 1:
        raise RuntimeError(f"{label}: blok source tidak ditemukan atau ambigu.")
    return updated


def patch_runtime_binding(text: str) -> tuple[str, bool]:
    if "runtime_python=runtime_python" in text and "PROVIDER_RUNTIME_BOUND" in text:
        return text, False
    if re.search(r"(?m)^import sys\s*$", text) is None:
        if "import re\n" in text:
            text = text.replace("import re\n", "import re\nimport sys\n", 1)
        else:
            text = text.replace(
                "from __future__ import annotations\n",
                "from __future__ import annotations\n\nimport sys\n",
                1,
            )
    pattern = r"(?m)^(?P<i>[ \t]*)status = provider_status\(self\.model_root, self\.provider_id, self\.device\)\s*$"
    match = re.search(pattern, text)
    if not match:
        raise RuntimeError("Runtime binding R4 belum terpasang dan call provider_status lama tidak ditemukan.")
    i = match.group("i")
    replacement = "\n".join([
        f"{i}runtime_python = Path(sys.executable).expanduser().resolve()",
        f"{i}self.emit_event(",
        f'{i}    "state",',
        f'{i}    state="PROVIDER_RUNTIME_BOUND",',
        f"{i}    provider_id=self.provider_id,",
        f"{i}    device=self.device,",
        f"{i}    runtime_python=str(runtime_python),",
        f"{i}    model_lock=True,",
        f"{i}    local_realtime=True,",
        f"{i})",
        f"{i}status = provider_status(",
        f"{i}    self.model_root,",
        f"{i}    self.provider_id,",
        f"{i}    self.device,",
        f"{i}    runtime_python=runtime_python,",
        f"{i})",
    ])
    return re.sub(pattern, replacement, text, count=1, flags=re.MULTILINE), True


def patch_turn_context(text: str) -> tuple[str, bool]:
    if f"# {MARKER}: CJK_CONTEXT" in text:
        return text, False
    old_tokens = '''def _tokens(text: str) -> List[str]:
    return _clean_text(text).split()
'''
    new_tokens = f'''# {MARKER}: CJK_CONTEXT
_CLOSING_PUNCTUATION = set("、。！？…,.!?;:)]}}」』】〉》")
_OPENING_PUNCTUATION = set("([{{「『【〈《")


def _is_cjk_token(value: str) -> bool:
    token = str(value or "")
    return bool(token) and all(
        "\\u3040" <= char <= "\\u30ff"
        or "\\u3400" <= char <= "\\u9fff"
        for char in token
    )


def _tokens(text: str) -> List[str]:
    # Japanese normally has no spaces. Character units preserve rolling overlap.
    clean = _clean_text(text)
    tokens: List[str] = []
    latin: List[str] = []

    def flush_latin() -> None:
        if latin:
            tokens.append("".join(latin))
            latin.clear()

    for char in clean:
        if char.isspace():
            flush_latin()
        elif "\\u3040" <= char <= "\\u30ff" or "\\u3400" <= char <= "\\u9fff":
            flush_latin()
            tokens.append(char)
        elif char.isalnum() or char in {{"'", "_", "-"}}:
            latin.append(char)
        else:
            flush_latin()
            tokens.append(char)
    flush_latin()
    return tokens


def _join_tokens(tokens: Iterable[str]) -> str:
    output = ""
    previous = ""
    for raw in tokens:
        token = str(raw or "")
        if not token:
            continue
        if not output:
            output = token
        elif token in _CLOSING_PUNCTUATION:
            output += token
        elif previous in _OPENING_PUNCTUATION:
            output += token
        elif _is_cjk_token(previous) or _is_cjk_token(token):
            output += token
        else:
            output += " " + token
        previous = token
    return output
'''
    text = replace_once(text, old_tokens, new_tokens, "turn_context CJK tokenizer")
    old_result = '''        display = " ".join(display_tokens)
        if truncated:
            display = "… " + display
        return TurnContextResult(
            text=display,
            full_text=" ".join(full_tokens),
'''
    new_result = '''        display = _join_tokens(display_tokens)
        if truncated:
            display = "…" + display
        return TurnContextResult(
            text=display,
            full_text=_join_tokens(full_tokens),
'''
    text = replace_once(text, old_result, new_result, "turn_context CJK joiner")
    return text, True


def patch_locked_adapter(text: str) -> tuple[str, bool]:
    changed = False
    text, runtime_changed = patch_runtime_binding(text)
    changed = changed or runtime_changed
    if f"# {MARKER}: REAZON_THREADS" not in text:
        old_threads = '''            joiner=str(files["joiner"]),
            num_threads=1,
            sample_rate=TARGET_SAMPLE_RATE,
'''
        new_threads = f'''            joiner=str(files["joiner"]),
            # {MARKER}: REAZON_THREADS
            num_threads=max(1, min(4, self.cpu_threads)) if self.device == "cpu" else 1,
            sample_rate=TARGET_SAMPLE_RATE,
'''
        text = replace_once(text, old_threads, new_threads, "Reazon CPU threads")
        changed = True
    if f"# {MARKER}: REAZON_WINDOW" not in text:
        pattern = (
            r"    def _window_seconds\(self, stable: bool\) -> float:\n"
            r".*?"
            r"(?=\n    def transcribe\(self, samples: np\.ndarray, stable: bool = False\))"
        )
        replacement = f'''    def _window_seconds(self, stable: bool) -> float:
        if self.provider_id == PROVIDER_SENSEVOICE:
            return 5.0 if stable else 3.0
        if self.provider_id == PROVIDER_REAZON:
            # {MARKER}: REAZON_WINDOW
            if self.profile in {{"speed", "instant", "fast"}}:
                return 14.0 if stable else 6.5
            if self.profile in {{"accurate", "quality"}}:
                return 20.0 if stable else 10.0
            return 16.0 if stable else 8.0
        if self.provider_id == PROVIDER_KOTOBA and self.device == "cpu":
            return 6.0 if stable else 3.2
        if self.device == "cpu":
            return 6.5 if stable else 3.6
        return 10.0 if stable else 6.5
'''
        text = regex_replace_once(text, pattern, replacement, "Reazon utterance window")
        changed = True
    return text, changed


def patch_sidecar(text: str) -> tuple[str, bool]:
    if f"# {MARKER}: POLICY" in text:
        return text, False
    old_semantic = '''def _has_semantic_text(value: Any) -> bool:
    """Return True for text containing at least one letter/number/CJK symbol."""
    text = _clean_text(value)
    return any(char.isalnum() or "\\u3040" <= char <= "\\u30ff" or "\\u4e00" <= char <= "\\u9fff" for char in text)
'''
    new_semantic = f'''def _has_semantic_text(value: Any) -> bool:
    """Return True for text containing at least one letter/number/CJK symbol."""
    text = _clean_text(value)
    return any(char.isalnum() or "\\u3040" <= char <= "\\u30ff" or "\\u3400" <= char <= "\\u9fff" for char in text)


# {MARKER}: SEMANTIC_UNITS
def _semantic_units(value: Any) -> int:
    text = _clean_text(value)
    units = 0
    inside_latin = False
    for char in text:
        is_cjk = "\\u3040" <= char <= "\\u30ff" or "\\u3400" <= char <= "\\u9fff"
        if is_cjk:
            units += 1
            inside_latin = False
        elif char.isalnum():
            if not inside_latin:
                units += 1
            inside_latin = True
        else:
            inside_latin = False
    return units
'''
    text = replace_once(text, old_semantic, new_semantic, "semantic unit helper")
    policy_pattern = (
        r"def resolve_policy\(profile: str, device: str\) -> LocalRealtimePolicy:\n"
        r".*?"
        r"(?=\n\n@dataclass\nclass Snapshot:)"
    )
    policy_replacement = f'''def resolve_policy(profile: str, device: str) -> LocalRealtimePolicy:
    # {MARKER}: POLICY
    profile_key = str(profile or "normal").strip().lower()
    gpu = str(device or "cpu").strip().lower() == "cuda"
    if profile_key in {{"speed", "instant", "fast"}}:
        return LocalRealtimePolicy(
            profile="speed", first_partial_s=0.72 if gpu else 0.95,
            partial_interval_s=0.48 if gpu else 0.58, endpoint_s=0.72,
            max_phrase_s=14.0, pre_roll_s=0.36, carry_over_s=0.30,
            minimum_rms=0.0032, noise_multiplier=2.25,
            short_pause_s=0.48, long_pause_s=1.30,
            subtitle_window_s=11.0, hard_turn_s=16.0,
        )
    if profile_key in {{"accurate", "quality"}}:
        return LocalRealtimePolicy(
            profile="accurate", first_partial_s=1.05 if gpu else 1.30,
            partial_interval_s=0.78 if gpu else 0.92, endpoint_s=1.00,
            max_phrase_s=20.0, pre_roll_s=0.48, carry_over_s=0.38,
            minimum_rms=0.0038, noise_multiplier=2.65,
            short_pause_s=0.68, long_pause_s=1.75,
            subtitle_window_s=16.0, hard_turn_s=22.0,
        )
    return LocalRealtimePolicy(
        profile="normal", first_partial_s=0.84 if gpu else 1.08,
        partial_interval_s=0.62 if gpu else 0.74, endpoint_s=0.84,
        max_phrase_s=17.0, pre_roll_s=0.42, carry_over_s=0.34,
        minimum_rms=0.0035, noise_multiplier=2.45,
        short_pause_s=0.56, long_pause_s=1.48,
        subtitle_window_s=13.0, hard_turn_s=19.0,
    )
'''
    text = regex_replace_once(text, policy_pattern, policy_replacement, "sentence streaming policy")
    old_context = '''        default_history = 48 if str(os.environ.get("ORT_AUDIO_RESOURCE_POLICY", "normal")).lower() == "efficient" else 72
        history_words = max(24, min(160, int(os.environ.get("ORT_AUDIO_CONTEXT_WORDS", str(default_history)) or default_history)))
        display_words = 42 if profile in {"accurate", "quality"} else 32 if profile == "normal" else 24
        display_words = min(display_words, history_words)
'''
    new_context = f'''        # {MARKER}: CONTEXT_CAPACITY
        default_history = 160 if str(os.environ.get("ORT_AUDIO_RESOURCE_POLICY", "normal")).lower() == "efficient" else 240
        history_words = max(96, min(480, int(os.environ.get("ORT_AUDIO_CONTEXT_WORDS", str(default_history)) or default_history)))
        display_words = 192 if profile in {{"accurate", "quality"}} else 144 if profile == "normal" else 112
        display_words = min(display_words, history_words)
'''
    text = replace_once(text, old_context, new_context, "turn context capacity")
    partial_pattern = (
        r"    def _should_emit_partial\(self, result_id: str, previous: str, current: str, now: float\) -> bool:\n"
        r".*?"
        r"(?=\n    def _emit_reject_throttled)"
    )
    partial_replacement = f'''    def _should_emit_partial(
        self, result_id: str, previous: str, current: str,
        now: float, audio_seconds: float,
    ) -> bool:
        # {MARKER}: PARTIAL_GATE
        clean = _clean_text(current)
        if not _has_semantic_text(clean):
            return False
        units = _semantic_units(clean)
        japanese = _contains_japanese(clean)
        minimum_units = 4 if japanese else 2
        sentence_end = clean.endswith((".", "!", "?", "…", "。", "！", "？"))
        if not previous:
            minimum_audio = 0.82 if self.profile in {{"speed", "instant", "fast"}} else 1.00
            if float(audio_seconds or 0.0) < minimum_audio:
                return False
            return units >= minimum_units or (sentence_end and units >= 2)
        old = _clean_text(previous)
        if old.casefold() == clean.casefold():
            return False
        elapsed = now - float(self.last_emit_at_by_result.get(result_id, 0.0) or 0.0)
        previous_units = _semantic_units(old)
        unit_growth = units - previous_units
        meaningful_growth = max(2, int(max(1, previous_units) * 0.18))
        if unit_growth >= meaningful_growth and elapsed >= 0.38:
            return True
        rewrite_amount = _partial_growth(old, clean)
        if elapsed >= 0.95 and units >= minimum_units + 1 and rewrite_amount >= 0.35:
            return True
        if sentence_end and units >= minimum_units and elapsed >= 0.42:
            return True
        return bool(elapsed >= 1.35 and units >= minimum_units and unit_growth > 0)
'''
    text = regex_replace_once(text, partial_pattern, partial_replacement, "partial sentence gate")
    fallback_pattern = (
        r'(?m)^(?P<i>[ \t]*)final_context_fallback = bool\(\n'
        r'(?P=i)    snapshot\.stable\n'
        r'(?P=i)    and previous\n'
        r'(?P=i)    and \(not text or not _has_semantic_text\(text\)\)\n'
        r'(?P=i)\)\n'
    )
    fallback_match = re.search(fallback_pattern, text)
    if not fallback_match:
        raise RuntimeError("final coverage guard: blok source tidak ditemukan.")
    i = fallback_match.group("i")
    new_fallback = "\n".join([
        f"{i}# {MARKER}: FINAL_COVERAGE_GUARD",
        f"{i}current_units = _semantic_units(text)",
        f"{i}previous_units = _semantic_units(previous)",
        f"{i}final_context_fallback = bool(",
        f"{i}    snapshot.stable and previous and (",
        f"{i}        not text or not _has_semantic_text(text)",
        f"{i}        or current_units < max(2, int(previous_units * 0.72))",
        f"{i}    )",
        f"{i})",
        "",
    ])
    text = re.sub(fallback_pattern, new_fallback, text, count=1)

    metadata_pattern = (
        r'(?m)^(?P<i>[ \t]*)metadata\["turn_context_words"\] = len\(previous\.split\(\)\)\n'
        r'(?P=i)metadata\["turn_display_words"\] = len\(previous\.split\(\)\)\n'
    )
    metadata_match = re.search(metadata_pattern, text)
    if not metadata_match:
        raise RuntimeError("Japanese context metadata: blok source tidak ditemukan.")
    i = metadata_match.group("i")
    metadata_replacement = (
        f'{i}metadata["turn_context_words"] = _semantic_units(previous)\n'
        f'{i}metadata["turn_display_words"] = _semantic_units(previous)\n'
    )
    text = re.sub(metadata_pattern, metadata_replacement, text, count=1)

    invocation_pattern = (
        r'(?m)^(?P<i>[ \t]*)if not snapshot\.stable and not self\._should_emit_partial'
        r'\(snapshot\.result_id, previous, text, now\):\n'
    )
    invocation_match = re.search(invocation_pattern, text)
    if not invocation_match:
        raise RuntimeError("partial gate invocation: call source tidak ditemukan.")
    i = invocation_match.group("i")
    invocation_replacement = "\n".join([
        f"{i}if not snapshot.stable and not self._should_emit_partial(",
        f"{i}    snapshot.result_id, previous, text, now, snapshot.audio_seconds,",
        f"{i}):",
        "",
    ])
    text = re.sub(invocation_pattern, invocation_replacement, text, count=1)
    return text, True


def run_checked(command: list[str], label: str, cwd: Path | None = None) -> None:
    log(label)
    result = subprocess.run(
        command, cwd=str(cwd) if cwd else None, text=True,
        encoding="utf-8", errors="replace", capture_output=True, check=False,
    )
    if result.stdout:
        print(result.stdout.rstrip(), flush=True)
    if result.stderr:
        print(result.stderr.rstrip(), file=sys.stderr, flush=True)
    if result.returncode != 0:
        raise RuntimeError(f"{label} gagal dengan exit code {result.returncode}.")
    log(f"{label}: PASS")


def main() -> int:
    root = find_root(sys.argv[1] if len(sys.argv) > 1 else "")
    sidecar = root / "ORT_App" / "audio_realtime_local_sidecar.py"
    context = root / "ORT_App" / "app" / "audio" / "turn_context.py"
    adapter = root / "ORT_App" / "app" / "audio" / "locked_asr_adapter.py"
    cpu_python = root / "ORT_Runtime" / "audio_cpu" / ".venv" / "Scripts" / "python.exe"
    gpu_python = root / "ORT_Runtime" / "audio_gpu" / ".venv" / "Scripts" / "python.exe"
    if not cpu_python.is_file():
        raise RuntimeError(f"Runtime CPU tidak ditemukan: {cpu_python}")
    timestamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = root / "ORT" / "backups" / f"ORT_V9_0_5_R5_COMPLETE_UTTERANCE_{timestamp}"
    status_dir = root / "ORT" / "status"
    backup_root.mkdir(parents=True, exist_ok=True)
    status_dir.mkdir(parents=True, exist_ok=True)
    targets = [sidecar, context, adapter]
    originals: dict[Path, bytes] = {}
    changed_files: list[str] = []
    log(f"Root proyek: {root}")
    for source in targets:
        if not source.is_file():
            raise RuntimeError(f"Source tidak ditemukan: {source}")
        originals[source] = source.read_bytes()
        destination = backup_root / source.relative_to(root)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    try:
        sidecar_text, sidecar_nl = read_source(sidecar)
        context_text, context_nl = read_source(context)
        adapter_text, adapter_nl = read_source(adapter)
        sidecar_new, sidecar_changed = patch_sidecar(sidecar_text)
        context_new, context_changed = patch_turn_context(context_text)
        adapter_new, adapter_changed = patch_locked_adapter(adapter_text)
        if sidecar_changed:
            write_source(sidecar, sidecar_new, sidecar_nl)
            changed_files.append(str(sidecar.relative_to(root)))
        if context_changed:
            write_source(context, context_new, context_nl)
            changed_files.append(str(context.relative_to(root)))
        if adapter_changed:
            write_source(adapter, adapter_new, adapter_nl)
            changed_files.append(str(adapter.relative_to(root)))
        for cache in (root / "ORT_App" / "app" / "audio" / "__pycache__", root / "ORT_App" / "__pycache__"):
            if cache.exists():
                shutil.rmtree(cache, ignore_errors=True)
        for source in targets:
            py_compile.compile(str(source), doraise=True)
        run_checked([str(cpu_python), "-m", "py_compile", *(str(p) for p in targets)], "CPU py_compile", root)
        if gpu_python.is_file():
            run_checked([str(gpu_python), "-m", "py_compile", *(str(p) for p in targets)], "CUDA py_compile", root)
        context_test = backup_root / "verify_r5_context.py"
        context_test.write_text('''import json, sys\nfrom pathlib import Path\nroot=Path(sys.argv[1]).resolve()\nsys.path.insert(0,str(root/"ORT_App"))\nfrom app.audio.turn_context import RollingTurnContext\nctx=RollingTurnContext(max_history_words=240,display_words=160)\nresult=None\nfor item in ["私はこの作戦を","私はこの作戦を最後まで","この作戦を最後までやり遂げます。"]:\n    result=ctx.update("ja-test",item,stable=item.endswith("。"))\nassert result is not None\nassert "私はこの作戦を最後までやり遂げます。" in result.full_text,result.full_text\nassert "私 は" not in result.full_text,result.full_text\nprint(json.dumps({"passed":True,"full_text":result.full_text,"units":result.full_words},ensure_ascii=False,indent=2))\n''', encoding="utf-8")
        run_checked([str(cpu_python), str(context_test), str(root)], "Japanese rolling context test", root)
        run_checked([str(cpu_python), str(sidecar), "--self-test-json"], "Streaming partial integration self-test", root)
        status = {
            "patch": PATCH_ID,
            "applied_at": _dt.datetime.now().astimezone().isoformat(),
            "project_root": str(root),
            "backup_root": str(backup_root),
            "changed_files": changed_files,
            "cjk_context": True,
            "sentence_partial_gate": True,
            "final_coverage_guard": True,
            "reazon_complete_window": True,
            "models_downloaded": False,
            "verification": "PASS",
        }
        status_file = status_dir / "V9_0_5_R5_COMPLETE_UTTERANCE.json"
        status_file.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
        rollback_py = backup_root / "ROLLBACK_R5_COMPLETE_UTTERANCE.py"
        pairs = [(str(backup_root / p.relative_to(root)), str(p)) for p in targets]
        rollback_py.write_text(
            "from pathlib import Path\nimport shutil\n" +
            f"pairs={pairs!r}\n" +
            "for source,target in pairs:\n    Path(target).parent.mkdir(parents=True,exist_ok=True)\n    shutil.copy2(source,target)\nprint('ROLLBACK R5: PASS')\n",
            encoding="utf-8",
        )
        (backup_root / "ROLLBACK_R5_COMPLETE_UTTERANCE.bat").write_text(
            "@echo off\r\nchcp 65001 >nul\r\n" + f'"{cpu_python}" "{rollback_py}"\r\npause\r\n',
            encoding="utf-8",
        )
        log("FIX SELESAI")
        print("ORT v9.0.5 R5 Complete Utterance Streaming: PASS", flush=True)
        print(f"Backup : {backup_root}", flush=True)
        print(f"Status : {status_file}", flush=True)
        print("Model tidak diunduh ulang.", flush=True)
        return 0
    except Exception:
        log("Verifikasi gagal; memulihkan source asli.")
        for source, data in originals.items():
            source.write_bytes(data)
        raise


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ORT R5][ERROR] {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
