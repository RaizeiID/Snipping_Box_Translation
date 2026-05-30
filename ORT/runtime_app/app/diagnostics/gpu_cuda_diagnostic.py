from __future__ import annotations
import subprocess, json, sys
from pathlib import Path

def gpu_cuda_diagnostic_text(base_dir=None) -> str:
    lines = ["GPU / Torch CUDA Diagnostic v8.1", "================================"]
    try:
        import torch
        lines.append(f"torch version       : {getattr(torch, '__version__', '-')}")
        lines.append(f"torch cuda version  : {getattr(torch.version, 'cuda', None)}")
        ok = bool(torch.cuda.is_available())
        lines.append(f"torch.cuda available: {ok}")
        if ok:
            lines.append(f"device count        : {torch.cuda.device_count()}")
            lines.append(f"device 0            : {torch.cuda.get_device_name(0)}")
        else:
            lines.append("reason hint         : Torch CPU build / CUDA driver mismatch / CUDA not visible in venv")
    except Exception as exc:
        lines.append(f"torch check error   : {exc}")
    try:
        p = subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total,memory.free", "--format=csv,noheader"], capture_output=True, text=True, timeout=5)
        if p.returncode == 0:
            lines.append("")
            lines.append("nvidia-smi:")
            lines.extend("  " + x for x in p.stdout.strip().splitlines())
        else:
            lines.append("")
            lines.append("nvidia-smi: not available or failed")
    except Exception as exc:
        lines.append("")
        lines.append(f"nvidia-smi error    : {exc}")
    return "\n".join(lines)
