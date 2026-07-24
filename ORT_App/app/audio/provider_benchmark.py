from __future__ import annotations

import json
import os
import subprocess
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class BenchmarkResult:
    provider_id: str
    status: str
    text: str
    elapsed_ms: int
    audio_ms: int
    real_time_factor: float
    model: str
    device: str
    error: str = ""

    def as_dict(self) -> dict:
        return asdict(self)


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        frames = handle.getnframes()
        rate = max(1, handle.getframerate())
    return int(frames * 1000.0 / rate)


def benchmark_provider(
    runtime_python: Path,
    sidecar: Path,
    model_root: Path,
    wav_path: Path,
    provider_id: str,
    device: str = "cpu",
    timeout_s: float = 180.0,
) -> BenchmarkResult:
    audio_ms = wav_duration_ms(wav_path)
    command = [
        str(runtime_python), str(sidecar), "--benchmark-json",
        "--test-file", str(wav_path),
        "--language", "ja",
        "--model-root", str(model_root),
        "--asr-provider", str(provider_id),
        "--model-lock",
        "--asr-device", str(device),
        "--compute-type", "int8_float16" if device == "cuda" else "int8",
        "--profile", "normal",
    ]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    started = time.perf_counter()
    try:
        result = subprocess.run(
            command,
            cwd=str(sidecar.parent),
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=max(30.0, timeout_s),
            check=False,
        )
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        output = (result.stdout or "").strip()
        start = output.rfind("{")
        payload = json.loads(output[start:]) if start >= 0 else {}
        if result.returncode != 0 or not payload.get("passed"):
            return BenchmarkResult(
                provider_id, "FAILED", str(payload.get("text") or ""), elapsed_ms,
                audio_ms, elapsed_ms / max(1.0, audio_ms),
                str(payload.get("model") or provider_id),
                str(payload.get("device") or device),
                str(payload.get("error") or result.stderr or output[-1000:]),
            )
        inference_ms = int(payload.get("asr_ms", elapsed_ms) or elapsed_ms)
        return BenchmarkResult(
            provider_id, "PASS", str(payload.get("text") or ""), inference_ms,
            audio_ms, inference_ms / max(1.0, audio_ms),
            str(payload.get("model") or provider_id),
            str(payload.get("device") or device),
        )
    except Exception as exc:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        return BenchmarkResult(
            provider_id, "FAILED", "", elapsed_ms, audio_ms,
            elapsed_ms / max(1.0, audio_ms), provider_id, device,
            f"{type(exc).__name__}: {exc}",
        )


def benchmark_many(
    runtime_python: Path,
    sidecar: Path,
    model_root: Path,
    wav_path: Path,
    provider_ids: Iterable[str],
    device: str,
) -> list[BenchmarkResult]:
    return [
        benchmark_provider(runtime_python, sidecar, model_root, wav_path, provider_id, device)
        for provider_id in provider_ids
    ]


def results_markdown(results: Iterable[BenchmarkResult]) -> str:
    rows = []
    for item in results:
        text = item.text.replace("|", "\\|").replace("\n", " ")[:180]
        error = item.error.replace("|", "\\|").replace("\n", " ")[:180]
        rows.append(
            f"| {item.provider_id} | {item.status} | {item.device} | {item.elapsed_ms} | {item.real_time_factor:.3f} | {text or error} |"
        )
    return "\n".join([
        "### Provider benchmark result",
        "RTF below 1.0 means inference is faster than the audio duration. Accuracy must still be judged against the same reference clip.",
        "",
        "| Provider | Status | Device | ASR ms | RTF | Transcript / error |",
        "|---|---|---:|---:|---:|---|",
        *rows,
    ])
