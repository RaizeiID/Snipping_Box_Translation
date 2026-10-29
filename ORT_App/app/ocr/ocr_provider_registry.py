"""ORT v9.0.7-R5 open-source OCR provider registry for the Architecture Lab.

The Lab runs community/open-source components, mirroring what
app/audio/asr_provider_registry.py does for ASR. Every provider here is a real
open-source project with its own upstream, licence, and model weights; the Lab
reports availability honestly rather than pretending an uninstalled engine
works.

Why more than EasyOCR
---------------------
EasyOCR is the production engine on the main page and is accurate, but it is a
PyTorch stack: CRAFT detection plus a recognition network, ~80 MB of weights,
and it pulls torch/cuDNN into the process. Measured here on an RTX 4050 it
spends 318-328 ms per frame, which is 70-77% of the whole OCR->translation
path.

RapidOCR is the interesting alternative for the Lab's "lighter and faster"
goal: it is the PP-OCR family exported to ONNX and run through onnxruntime,
which this install already ships (1.26.0). No torch, no cuDNN, models measured
in single-digit MB. That combination is exactly what the Lab exists to test.

Nothing here downloads or installs anything on import. `probe_provider`
reports what is genuinely present so the UI can offer a setup step instead of
failing at run time.
"""
from __future__ import annotations

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

import numpy as np


PROVIDER_EASYOCR = "easyocr_craft"
PROVIDER_RAPIDOCR = "rapidocr_onnx"
PROVIDER_TESSERACT = "tesseract"


@dataclass(frozen=True)
class OCRProviderSpec:
    provider_id: str
    label: str
    owner: str
    backend: str
    license: str
    source_url: str
    install_hint: str
    purpose: str
    supported_devices: tuple[str, ...]
    approx_weights_mb: int
    experimental: bool = False

    def as_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "label": self.label,
            "owner": self.owner,
            "backend": self.backend,
            "license": self.license,
            "source_url": self.source_url,
            "install_hint": self.install_hint,
            "purpose": self.purpose,
            "supported_devices": list(self.supported_devices),
            "approx_weights_mb": self.approx_weights_mb,
            "experimental": self.experimental,
        }


PROVIDERS: dict[str, OCRProviderSpec] = {
    PROVIDER_EASYOCR: OCRProviderSpec(
        provider_id=PROVIDER_EASYOCR,
        label="EasyOCR · CRAFT + CRNN",
        owner="JaidedAI",
        backend="pytorch",
        license="Apache-2.0",
        source_url="https://github.com/JaidedAI/EasyOCR",
        install_hint="pip install easyocr",
        purpose="Production baseline on the main page. Heaviest, and measured here the LEAST accurate of the three on dialogue text.",
        supported_devices=("cpu", "cuda"),
        approx_weights_mb=80,
    ),
    PROVIDER_RAPIDOCR: OCRProviderSpec(
        provider_id=PROVIDER_RAPIDOCR,
        label="RapidOCR · PP-OCR ONNX",
        owner="RapidAI (PP-OCR weights by PaddlePaddle)",
        backend="onnxruntime",
        license="Apache-2.0",
        source_url="https://github.com/RapidAI/RapidOCR",
        install_hint="pip install rapidocr-onnxruntime",
        purpose="Smallest weights and no torch/cuDNN, but measured ~11x slower than Tesseract here. Accuracy is strong.",
        supported_devices=("cpu", "cuda"),
        approx_weights_mb=14,
    ),
    PROVIDER_TESSERACT: OCRProviderSpec(
        provider_id=PROVIDER_TESSERACT,
        label="Tesseract · LSTM",
        owner="Google / tesseract-ocr",
        backend="native binary",
        license="Apache-2.0",
        source_url="https://github.com/tesseract-ocr/tesseract",
        install_hint="install Tesseract binary + pip install pytesseract",
        purpose="Measured fastest AND most accurate on rendered dialogue; CPU-only, so it leaves the GPU entirely to the game.",
        supported_devices=("cpu",),
        approx_weights_mb=15,
    ),
}


def normalize_ocr_provider(value: str) -> str:
    token = str(value or PROVIDER_EASYOCR).strip().lower()
    aliases = {
        "easyocr": PROVIDER_EASYOCR, "craft": PROVIDER_EASYOCR,
        "rapidocr": PROVIDER_RAPIDOCR, "ppocr": PROVIDER_RAPIDOCR, "onnx": PROVIDER_RAPIDOCR,
        "pytesseract": PROVIDER_TESSERACT,
    }
    token = aliases.get(token, token)
    return token if token in PROVIDERS else PROVIDER_EASYOCR


# EasyOCR/RapidOCR language codes -> Tesseract traineddata names.
_TESSERACT_LANG = {
    "en": "eng", "english": "eng",
    "ja": "jpn", "japanese": "jpn", "ja_vert": "jpn_vert",
    "ch_sim": "chi_sim", "zh": "chi_sim", "chinese": "chi_sim",
    "ko": "kor", "korean": "kor",
    "id": "ind", "indonesian": "ind",
}


def tesseract_lang_string(languages) -> str:
    """Map this project's language codes onto Tesseract's, preserving order."""
    seen, out = set(), []
    for code in languages:
        mapped = _TESSERACT_LANG.get(str(code).strip().lower())
        if mapped and mapped not in seen:
            seen.add(mapped)
            out.append(mapped)
    return "+".join(out) or "eng"


def onnxruntime_has_cuda() -> bool:
    """Whether onnxruntime can genuinely run on the GPU here.

    The plain `onnxruntime` wheel is CPU-only; CUDA needs `onnxruntime-gpu`.
    Without this check RapidOCR silently runs on CPU while the UI claims GPU --
    which is exactly what happened in the first benchmark, where the "cuda" row
    was really CPU and its timing matched the CPU row to within noise.
    """
    try:
        import onnxruntime

        return "CUDAExecutionProvider" in onnxruntime.get_available_providers()
    except Exception:
        return False


def effective_devices(provider_id: str) -> tuple[str, ...]:
    """Devices a provider can ACTUALLY use in this install, not in principle."""
    spec = PROVIDERS[normalize_ocr_provider(provider_id)]
    if spec.provider_id == PROVIDER_RAPIDOCR and not onnxruntime_has_cuda():
        return ("cpu",)
    if spec.provider_id == PROVIDER_EASYOCR:
        try:
            import torch

            if not torch.cuda.is_available():
                return ("cpu",)
        except Exception:
            return ("cpu",)
    return spec.supported_devices


def find_tesseract_binary() -> str:
    """Locate the native Tesseract executable.

    PATH first, then the Windows default install directory this project already
    hardcodes elsewhere (CaptureSpecialistCore/TEST_OCR), so a normal install
    that simply was not added to PATH still works.
    """
    import shutil

    found = shutil.which("tesseract")
    if found:
        return found
    for candidate in (
        os.environ.get("ORT_TESSERACT_PATH", ""),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if candidate and Path(candidate).is_file():
            return candidate
    return ""


def _module_present(name: str) -> bool:
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def probe_provider(provider_id: str) -> dict:
    """Report whether a provider can actually run, without importing heavy deps."""
    spec = PROVIDERS[normalize_ocr_provider(provider_id)]
    detail = ""
    if spec.provider_id == PROVIDER_EASYOCR:
        ready = _module_present("easyocr")
        detail = "easyocr module found" if ready else "easyocr not installed"
    elif spec.provider_id == PROVIDER_RAPIDOCR:
        has_pkg = _module_present("rapidocr_onnxruntime")
        has_ort = _module_present("onnxruntime")
        ready = has_pkg and has_ort
        if ready:
            detail = "rapidocr + onnxruntime found"
        elif has_ort:
            detail = "onnxruntime present; rapidocr-onnxruntime package missing (new rapidocr API is not supported)"
        else:
            detail = "onnxruntime and rapidocr missing"
    else:
        # pytesseract is only a wrapper -- without the native binary it imports
        # fine and then fails at call time, so probing the module alone would
        # report a provider as ready when it cannot actually read anything.
        has_pkg = _module_present("pytesseract")
        binary = find_tesseract_binary()
        ready = has_pkg and bool(binary)
        if ready:
            detail = f"pytesseract + binary at {binary}"
        elif has_pkg:
            detail = "pytesseract installed but the Tesseract binary was not found"
        else:
            detail = "pytesseract not installed"
    payload = spec.as_dict()
    devices = effective_devices(spec.provider_id)
    payload.update({
        "ready": bool(ready),
        "detail": detail,
        "effective_devices": list(devices),
        "gpu_available": "cuda" in devices,
    })
    if spec.provider_id == PROVIDER_RAPIDOCR and "cuda" not in devices:
        payload["device_note"] = "CPU saja: paket onnxruntime-gpu belum terpasang"
    elif spec.provider_id == PROVIDER_TESSERACT:
        payload["device_note"] = "CPU saja secara desain; Tesseract tidak punya jalur GPU"
    elif "cuda" in devices:
        payload["device_note"] = "CPU dan GPU tersedia"
    else:
        payload["device_note"] = "CPU saja pada instalasi ini"
    return payload


def probe_all() -> list[dict]:
    return [probe_provider(pid) for pid in PROVIDERS]


class OCREngine:
    """Uniform read(image) -> list[str] across every provider."""

    def __init__(self, provider_id: str, *, gpu: bool = False, languages=("ch_sim", "en"),
                 canvas_size: int = 0, log: Optional[Callable[[str], None]] = None):
        self.provider_id = normalize_ocr_provider(provider_id)
        self.spec = PROVIDERS[self.provider_id]
        self.gpu = bool(gpu) and "cuda" in effective_devices(self.provider_id)
        self.languages = tuple(languages)
        self.canvas_size = int(canvas_size or 0)
        self._log = log or (lambda _m: None)
        self._impl = None

    def load(self) -> None:
        if self._impl is not None:
            return
        if self.provider_id == PROVIDER_EASYOCR:
            import easyocr

            self._impl = easyocr.Reader(list(self.languages), gpu=self.gpu, verbose=False)
        elif self.provider_id == PROVIDER_RAPIDOCR:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except ImportError:
                raise RuntimeError("Pasang rapidocr-onnxruntime melalui requirements_ocr_lab.txt; "
                                   "API paket rapidocr baru belum didukung adapter ini.")
            # ONNX CUDA availability alone does not enable it: RapidOCR defaults
            # all three workers to CPU. Honor the requested device explicitly.
            try:
                threads = max(1, min(os.cpu_count() or 1, int(os.environ.get("TITAN_CPU_THREADS", "4"))))
            except ValueError:
                threads = min(os.cpu_count() or 1, 4)
            self._impl = RapidOCR(
                det_use_cuda=self.gpu, cls_use_cuda=self.gpu, rec_use_cuda=self.gpu,
                intra_op_num_threads=threads, inter_op_num_threads=1,
            )
        else:
            import pytesseract

            binary = find_tesseract_binary()
            if binary:
                pytesseract.pytesseract.tesseract_cmd = binary
            self._impl = pytesseract
        self._log(f"[LAB OCR] {self.spec.label} ready | device={'cuda' if self.gpu else 'cpu'}")

    def read(self, image: np.ndarray) -> list[str]:
        self.load()
        if self.provider_id == PROVIDER_EASYOCR:
            kwargs = {"detail": 0, "paragraph": True}
            if self.canvas_size >= 320:
                kwargs["canvas_size"] = self.canvas_size
            return list(self._impl.readtext(image, **kwargs) or [])
        if self.provider_id == PROVIDER_RAPIDOCR:
            result, _elapsed = self._impl(image)
            # RapidOCR returns [[box, text, score], ...] or None when empty.
            return [str(row[1]) for row in (result or []) if len(row) >= 2]
        text = self._impl.image_to_string(image, lang=tesseract_lang_string(self.languages))
        return [line for line in str(text or "").splitlines() if line.strip()]

    def read_boxes(self, image: np.ndarray, **kwargs) -> list:
        """Return [quadrilateral, text, confidence] using the selected provider.

        Layout/name passes must not silently load a second OCR engine. Tesseract
        word boxes are grouped by line so dialogue layout receives line regions.
        """
        self.load()
        if self.provider_id == PROVIDER_EASYOCR:
            options = {"detail": 1, "paragraph": False}
            if self.canvas_size >= 320:
                options["canvas_size"] = self.canvas_size
            if kwargs.get("allowlist"):
                options["allowlist"] = kwargs["allowlist"]
            return list(self._impl.readtext(image, **options) or [])
        if self.provider_id == PROVIDER_RAPIDOCR:
            result, _elapsed = self._impl(image)
            return [[row[0], str(row[1]), float(row[2])] for row in (result or []) if len(row) >= 3]
        data = self._impl.image_to_data(
            image, lang=tesseract_lang_string(self.languages), output_type=self._impl.Output.DICT,
        )
        lines = {}
        for i, raw in enumerate(data.get("text", [])):
            text = str(raw).strip()
            confidence = float(data["conf"][i])
            if not text or confidence < 0:
                continue
            key = tuple(data[field][i] for field in ("block_num", "par_num", "line_num"))
            x, y = int(data["left"][i]), int(data["top"][i])
            right, bottom = x + int(data["width"][i]), y + int(data["height"][i])
            row = lines.setdefault(key, [x, y, right, bottom, [], []])
            row[:4] = [min(row[0], x), min(row[1], y), max(row[2], right), max(row[3], bottom)]
            row[4].append(text)
            row[5].append(confidence / 100.0)
        return [
            [[[x, y], [right, y], [right, bottom], [x, bottom]], " ".join(words), sum(scores) / len(scores)]
            for x, y, right, bottom, words, scores in lines.values()
        ]


def provider_table_markdown() -> str:
    rows = [
        "| Provider | Status | Perangkat | Backend | Weights | Lisensi | Sumber |",
        "|---|---|---|---|---|---|---|",
    ]
    for item in probe_all():
        state = "✅ siap" if item["ready"] else "⚠️ belum terpasang"
        rows.append(
            f"| {item['label']} | {state} | {'/'.join(item['effective_devices']).upper()} | {item['backend']} | "
            f"~{item['approx_weights_mb']} MB | {item['license']} | [{item['owner']}]({item['source_url']}) |"
        )
    rows.append("")
    for item in probe_all():
        rows.append(f"- **{item['label']}** — {item['device_note']}.")
    for item in probe_all():
        if not item["ready"]:
            rows.append(f"- **{item['label']}** — {item['detail']}. Pasang dengan: `{item['install_hint']}`")
    return "\n".join(rows)


class DualDeviceOCREngine:
    """Run the GPU and CPU copies of an engine on the SAME frame at once.

    "Hybrid" previously meant AUTO_GPU: use the GPU, fall back to the CPU only
    after VRAM pressure forced a reload. Both devices were never busy together,
    which is why it behaved identically to plain GPU.

    This races them instead. Each frame is dispatched to both workers and the
    first result wins; the loser is abandoned. Per-frame latency becomes
    min(gpu, cpu) rather than gpu alone, so it pays off exactly when the GPU is
    contended -- a game rendering in the foreground -- and costs a little when
    the GPU is idle and always wins anyway.

    The two workers sit on different devices, so they do not compete for the
    same silicon. The cost is roughly double the total compute and a second set
    of model weights resident.
    """

    backend = "dual-device"

    def __init__(self, provider_id: str, *, languages=("ch_sim", "en"),
                 canvas_size: int = 0, log=None):
        from concurrent.futures import ThreadPoolExecutor

        self.provider_id = normalize_ocr_provider(provider_id)
        self._log = log or (lambda _m: None)
        self.gpu_engine = OCREngine(self.provider_id, gpu=True, languages=languages,
                                    canvas_size=canvas_size, log=log)
        self.cpu_engine = OCREngine(self.provider_id, gpu=False, languages=languages,
                                    canvas_size=canvas_size, log=log)
        self._pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ort-ocr-dual")
        self.wins = {"gpu": 0, "cpu": 0}

    def load(self) -> None:
        self.gpu_engine.load()
        self.cpu_engine.load()
        self._log(
            f"[OCR] Hybrid dual-device ready | {self.provider_id} | "
            f"gpu={self.gpu_engine.gpu} + cpu worker"
        )

    def read(self, image) -> list:
        from concurrent.futures import FIRST_COMPLETED, wait

        futures = {
            self._pool.submit(self.gpu_engine.read, image): "gpu",
            self._pool.submit(self.cpu_engine.read, image): "cpu",
        }
        done, pending = wait(list(futures), return_when=FIRST_COMPLETED)
        winner = None
        result = []
        for fut in done:
            try:
                result = fut.result()
                winner = futures[fut]
                break
            except Exception:
                continue
        if winner is None:
            # The first finisher failed; fall back to whatever the other returns.
            for fut in pending:
                try:
                    result = fut.result(timeout=30)
                    winner = futures[fut]
                    break
                except Exception:
                    continue
        if winner:
            self.wins[winner] = self.wins.get(winner, 0) + 1
        return result

    def describe(self) -> dict:
        return {"backend": self.backend, "provider": self.provider_id, "wins": dict(self.wins)}


def device_capability_report() -> dict:
    """What this machine can actually offer an OCR engine."""
    report = {"cuda": False, "gpu_name": "", "reason": ""}
    try:
        import torch

        if torch.cuda.is_available():
            report["cuda"] = True
            report["gpu_name"] = torch.cuda.get_device_name(0)
        else:
            report["reason"] = "torch melaporkan CUDA tidak tersedia"
    except Exception as exc:
        report["reason"] = f"torch tidak dapat diperiksa: {type(exc).__name__}"
    return report
