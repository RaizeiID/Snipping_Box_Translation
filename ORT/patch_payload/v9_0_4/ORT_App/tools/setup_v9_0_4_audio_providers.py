from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path


SENSEVOICE_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
    "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09.tar.bz2"
)


def run(command: list[str], cwd: Path | None = None) -> None:
    print("$ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=str(cwd) if cwd else None, check=True)


SHERPA_CUDA_INDEX = "https://k2-fsa.github.io/sherpa/onnx/cuda.html"
SHERPA_CUDA12_REQUIREMENT = "sherpa-onnx==1.13.4+cuda12.cudnn9"
SHERPA_CUDA11_REQUIREMENT = "sherpa-onnx==1.13.4+cuda"


def _detect_cuda_variant(python: Path) -> str:
    probe = r'''
try:
    import torch
    version = str(getattr(torch.version, "cuda", "") or "")
    print("cuda12" if version.startswith("12") else "cuda11" if version.startswith("11") else "")
except Exception:
    print("")
'''
    result = subprocess.run(
        [str(python), "-c", probe],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    token = (result.stdout or "").strip().lower()
    return token if token in {"cuda11", "cuda12"} else "cuda12"


def _install_sherpa_runtime(python: Path, device: str, cuda_variant: str = "auto") -> str:
    target = str(device or "cpu").strip().lower()
    if target == "cpu":
        run([str(python), "-m", "pip", "install", "--upgrade", "--force-reinstall", "sherpa-onnx"])
        return "cpu"

    variant = str(cuda_variant or "auto").strip().lower()
    if variant == "auto":
        variant = _detect_cuda_variant(python)
    if variant not in {"cuda11", "cuda12"}:
        raise ValueError(f"Unsupported CUDA variant: {variant}")
    requirement = SHERPA_CUDA12_REQUIREMENT if variant == "cuda12" else SHERPA_CUDA11_REQUIREMENT
    run([
        str(python), "-m", "pip", "install",
        "--upgrade", "--force-reinstall", "--no-cache-dir",
        requirement, "--no-index", "-f", SHERPA_CUDA_INDEX,
    ])
    verify = (
        "import sherpa_onnx; "
        "v=str(getattr(sherpa_onnx,'__version__','')); "
        "print('sherpa_onnx='+v); "
        "assert '+cuda' in v, 'CUDA-enabled sherpa-onnx wheel was not installed'"
    )
    run([str(python), "-c", verify])
    return variant


def install_reazon(
    python: Path,
    runtime_root: Path,
    warm_model: bool,
    *,
    device: str = "cpu",
    cuda_variant: str = "auto",
) -> None:
    target_device = "cuda" if str(device or "cpu").lower() == "cuda" else "cpu"
    sources = runtime_root / "provider_sources"
    repo = sources / "ReazonSpeech"
    sources.mkdir(parents=True, exist_ok=True)
    if not repo.is_dir():
        run(["git", "clone", "--depth", "1", "https://github.com/reazon-research/ReazonSpeech.git", str(repo)])
    else:
        run(["git", "fetch", "--depth", "1", "origin"], cwd=repo)
        run(["git", "reset", "--hard", "FETCH_HEAD"], cwd=repo)

    # Install the Reazon package first. It may pull the ordinary CPU sherpa wheel;
    # the selected CPU/CUDA runtime is force-installed afterwards so the final
    # backend exactly matches the user's requested device.
    run([str(python), "-m", "pip", "install", "--upgrade", str(repo / "pkg" / "k2-asr")])
    installed_variant = _install_sherpa_runtime(python, target_device, cuda_variant)

    if warm_model:
        precision = "int8-fp32" if target_device == "cuda" else "int8"
        warmup = (
            "from reazonspeech.k2.asr import load_model; "
            f"load_model(device={target_device!r}, precision={precision!r}, language='ja'); "
            f"print('ReazonSpeech K2 {target_device.upper()} model ready')"
        )
        run([str(python), "-c", warmup])
    print(f"ReazonSpeech K2 setup ready | device={target_device} | runtime={installed_variant}")


def install_sensevoice(python: Path, model_root: Path) -> Path:
    run([str(python), "-m", "pip", "install", "--upgrade", "sherpa-onnx"])
    target = model_root / "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-int8-2025-09-09"
    if (target / "model.int8.onnx").is_file() and (target / "tokens.txt").is_file():
        print(f"SenseVoice already ready: {target}")
        return target
    model_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ort-sensevoice-") as temp_dir:
        archive = Path(temp_dir) / "sensevoice.tar.bz2"
        print(f"Downloading {SENSEVOICE_URL}", flush=True)
        urllib.request.urlretrieve(SENSEVOICE_URL, archive)
        with tarfile.open(archive, "r:bz2") as handle:
            handle.extractall(model_root)
    if not (target / "model.int8.onnx").is_file():
        raise RuntimeError(f"SenseVoice extraction incomplete: {target}")
    print(f"SenseVoice ready: {target}")
    return target


def install_argos_bridge(python: Path) -> None:
    run([str(python), "-m", "pip", "install", "argostranslate"])
    script = r'''
import argostranslate.package
argostranslate.package.update_package_index()
available = argostranslate.package.get_available_packages()
installed = {(p.from_code, p.to_code) for p in argostranslate.package.get_installed_packages()}
for pair in [("ja", "en"), ("en", "id")]:
    if pair in installed:
        print("Argos already installed", pair)
        continue
    package = next((p for p in available if p.from_code == pair[0] and p.to_code == pair[1]), None)
    if package is None:
        print("Argos package unavailable", pair)
        continue
    path = package.download()
    argostranslate.package.install_from_path(path)
    print("Argos installed", pair)
'''
    run([str(python), "-c", script])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("provider", choices=["reazonspeech_k2", "sensevoice_small", "argos_bridge", "all"])
    parser.add_argument("--runtime-root", required=True)
    parser.add_argument("--model-root", required=True)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-model-warmup", action="store_true")
    parser.add_argument("--device", choices=["cpu", "cuda"], default="cpu")
    parser.add_argument("--cuda-variant", choices=["auto", "cuda11", "cuda12"], default="auto")
    args = parser.parse_args()

    runtime_root = Path(args.runtime_root).expanduser().resolve()
    model_root = Path(args.model_root).expanduser().resolve()
    python = Path(args.python).expanduser().resolve()
    if not python.is_file():
        raise FileNotFoundError(f"Python runtime not found: {python}")

    if args.provider in {"reazonspeech_k2", "all"}:
        install_reazon(
            python, runtime_root, not args.skip_model_warmup,
            device=args.device, cuda_variant=args.cuda_variant,
        )
    if args.provider in {"sensevoice_small", "all"}:
        install_sensevoice(python, model_root)
    if args.provider in {"argos_bridge", "all"}:
        install_argos_bridge(python)

    print(json.dumps({"passed": True, "provider": args.provider}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
