from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Iterable

from runtime_config import read_runtime_config


def _run(cmd: list[str], timeout: int = 1200) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or '') + ('\n' + p.stderr if p.stderr else '')).strip()
    except Exception as e:
        return 1, str(e)


def detect_nvidia_smi() -> dict:
    info = {'available': False, 'driver_version': '-', 'gpu_name': '-', 'raw': '-'}
    exe = shutil.which('nvidia-smi')
    if not exe:
        return info
    code, out = _run([exe, '--query-gpu=name,driver_version', '--format=csv,noheader'])
    if code == 0 and out:
        first = out.splitlines()[0].strip()
        parts = [p.strip() for p in first.split(',')]
        info['available'] = True
        info['gpu_name'] = parts[0] if parts else '-'
        info['driver_version'] = parts[1] if len(parts) > 1 else '-'
        info['raw'] = out
    else:
        info['raw'] = out or 'nvidia-smi gagal dijalankan'
    return info


def _candidate_runtime_roots() -> Iterable[Path]:
    cfg = read_runtime_config()
    vals = [
        cfg.get('runtime_root'),
        os.environ.get('ORT_RUNTIME_ROOT'),
        cfg.get('project_root'),
        str(Path(__file__).resolve().parent / '_runtime'),
    ]
    seen = set()
    for raw in vals:
        if not raw:
            continue
        p = Path(str(raw))
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        yield p


def _python_candidates() -> Iterable[Path]:
    for root in _candidate_runtime_roots():
        yield root / '.venv' / 'Scripts' / 'python.exe'


def find_runtime_python() -> Path | None:
    for p in _python_candidates():
        try:
            if p.exists():
                return p
        except Exception:
            pass
    return None


def active_runtime_root() -> Path | None:
    py = find_runtime_python()
    if not py:
        return None
    return py.parent.parent.parent


def _torch_probe(py: Path) -> dict:
    code = (
        'import json\n'
        'd={"torch_installed":False,"torch_version":"-","cuda_version":"-","cuda_available":False,"device_count":0,"device_name":"-","err":""}\n'
        'try:\n'
        ' import torch\n'
        ' d["torch_installed"]=True\n'
        ' d["torch_version"]=getattr(torch,"__version__","-")\n'
        ' d["cuda_version"]=getattr(torch.version,"cuda","-") or "-"\n'
        ' d["cuda_available"]=bool(torch.cuda.is_available())\n'
        ' d["device_count"]=int(torch.cuda.device_count()) if d["cuda_available"] else 0\n'
        ' d["device_name"]=str(torch.cuda.get_device_name(0)) if d["device_count"]>0 else "-"\n'
        'except Exception as e:\n'
        ' d["err"]=str(e)\n'
        'print(json.dumps(d))\n'
    )
    rc, out = _run([str(py), '-c', code])
    if rc != 0:
        return {'err': out}
    try:
        return json.loads(out.splitlines()[-1])
    except Exception as e:
        return {'err': f'gagal parsing output torch: {e} | raw={out[:300]}'}


def detect_gpu() -> dict:
    result = {
        'runtime_python': '-',
        'runtime_root': '-',
        'torch_installed': False,
        'cuda_available': False,
        'device_count': 0,
        'device_name': '-',
        'torch_version': '-',
        'cuda_version': '-',
        'mode_hint': 'cpu',
        'notes': [],
    }
    smi = detect_nvidia_smi()
    result['nvidia_smi'] = smi['available']
    result['driver_version'] = smi['driver_version']
    result['smi_gpu_name'] = smi['gpu_name']
    py = find_runtime_python()
    rr = active_runtime_root()
    result['runtime_python'] = str(py) if py else '-'
    result['runtime_root'] = str(rr) if rr else '-'
    if not py:
        checked = '; '.join(str(p) for p in _python_candidates())
        result['notes'].append('Runtime Python tidak ditemukan dari runtime aktif. Jalankan Start dan pilih runtime yang benar.')
        result['notes'].append('Candidates=' + checked)
        result['python'] = platform.python_version()
        result['platform'] = platform.platform()
        return result

    data = _torch_probe(py)
    if data.get('err'):
        result['notes'].append(f"torch cek gagal: {data['err']}")
    else:
        for k in ['torch_installed', 'torch_version', 'cuda_version', 'cuda_available', 'device_count', 'device_name']:
            result[k] = data.get(k, result.get(k))

    if result['cuda_available']:
        result['mode_hint'] = 'gpu'
    elif smi['available']:
        result['mode_hint'] = 'auto'
        result['notes'].append('GPU NVIDIA terdeteksi via nvidia-smi, tetapi Torch di runtime aktif belum memakai build CUDA.')
    else:
        result['mode_hint'] = 'cpu'
        result['notes'].append('GPU NVIDIA tidak terdeteksi via nvidia-smi. Pastikan driver terpasang.')

    if not result['cuda_available'] and str(result['torch_version']).endswith('+cpu'):
        result['notes'].append('Build torch di runtime aktif masih CPU-only.')

    result['python'] = platform.python_version()
    result['platform'] = platform.platform()
    return result


def gpu_summary_text() -> str:
    d = detect_gpu()
    lines = [
        f"runtime_root = {d.get('runtime_root', '-')}",
        f"runtime_python = {d.get('runtime_python', '-')}",
        f"torch_installed = {d['torch_installed']}",
        f"torch_version = {d['torch_version']}",
        f"cuda_build = {d['cuda_version']}",
        f"cuda_available = {d['cuda_available']}",
        f"device_count = {d['device_count']}",
        f"device_name = {d['device_name']}",
        f"nvidia_smi = {d.get('nvidia_smi', False)}",
        f"driver_version = {d.get('driver_version', '-')}",
        f"gpu_name = {d.get('smi_gpu_name', '-')}",
        f"mode_hint = {d['mode_hint']}",
    ]
    if d['notes']:
        lines.append('notes = ' + ' | '.join(d['notes']))
    return '\n'.join(lines)


def install_or_repair_gpu() -> str:
    py = find_runtime_python()
    rr = active_runtime_root()
    if not py:
        tried = '\n'.join(str(p) for p in _python_candidates())
        return 'Runtime Python tidak ditemukan pada runtime aktif. Path yang dicek:\n' + tried

    smi = detect_nvidia_smi()
    log: list[str] = [
        f'Runtime root: {rr}',
        f'Runtime Python: {py}',
        f'nvidia-smi: {smi["available"]}',
        f'GPU: {smi["gpu_name"]}',
        f'Driver: {smi["driver_version"]}',
    ]
    if not smi['available']:
        log.append('GPU NVIDIA/driver belum terdeteksi via nvidia-smi. Install GPU dibatalkan agar tidak membingungkan user.')
        return '\n'.join(log)

    uninstall = [str(py), '-m', 'pip', 'uninstall', '-y', 'torch', 'torchvision', 'torchaudio']
    code, out = _run(uninstall, timeout=1800)
    log.append('$ ' + ' '.join(uninstall))
    log.append(out or '(no output)')

    install = [
        str(py), '-m', 'pip', 'install',
        'torch==2.5.1', 'torchvision==0.20.1', 'torchaudio==2.5.1',
        '--index-url', 'https://download.pytorch.org/whl/cu121'
    ]
    log.append('$ ' + ' '.join(install))
    code, out = _run(install, timeout=7200)
    log.append(out or '(no output)')
    if code != 0:
        log.append('Install CUDA build gagal. Cek koneksi internet, ruang disk, dan kecocokan driver NVIDIA.')
        return '\n'.join(log)

    log.append('--- VERIFY ---')
    log.append(gpu_summary_text())
    verify = detect_gpu()
    if verify['cuda_available']:
        log.append('SUKSES: runtime sekarang sudah mendeteksi CUDA.')
    else:
        log.append('Torch CUDA sudah dicoba dipasang, tetapi CUDA masih belum aktif. Kemungkinan driver tidak cocok atau butuh restart Windows.')
    return '\n'.join(log)
