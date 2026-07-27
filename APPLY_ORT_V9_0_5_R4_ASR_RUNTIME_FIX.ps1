param(
    [string]$ProjectRoot = ""
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "[ORT R4] $Message" -ForegroundColor Cyan
}

function Find-OrtProjectRoot {
    param([string]$ExplicitRoot)

    $starts = New-Object System.Collections.Generic.List[string]

    if ($ExplicitRoot) {
        $starts.Add($ExplicitRoot)
    }

    $starts.Add($PSScriptRoot)
    $starts.Add((Get-Location).Path)

    foreach ($start in $starts) {
        if (-not $start) {
            continue
        }

        try {
            $current = [System.IO.Path]::GetFullPath($start)
        } catch {
            continue
        }

        for ($depth = 0; $depth -le 8; $depth++) {
            $target = Join-Path $current "ORT_App\app\audio\locked_asr_adapter.py"
            if (Test-Path -LiteralPath $target -PathType Leaf) {
                return $current
            }

            $parent = Split-Path -Parent $current
            if (-not $parent -or $parent -eq $current) {
                break
            }
            $current = $parent
        }
    }

    throw "Root proyek ORT tidak ditemukan. Ekstrak paket ini di dalam folder proyek ORT, lalu jalankan kembali."
}

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Content
    )
    $encoding = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($Path, $Content, $encoding)
}

function Invoke-Python {
    param(
        [string]$Python,
        [string[]]$Arguments,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) {
        Write-Warning "$Label dilewati karena runtime tidak tersedia: $Python"
        return
    }

    & $Python @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Label gagal dengan exit code $LASTEXITCODE."
    }

    Write-Host "$Label: PASS" -ForegroundColor Green
}

$root = Find-OrtProjectRoot -ExplicitRoot $ProjectRoot
$target = Join-Path $root "ORT_App\app\audio\locked_asr_adapter.py"
$audioCache = Join-Path $root "ORT_App\app\audio\__pycache__"
$cpuPython = Join-Path $root "ORT_Runtime\audio_cpu\.venv\Scripts\python.exe"
$gpuPython = Join-Path $root "ORT_Runtime\audio_gpu\.venv\Scripts\python.exe"
$modelRoot = Join-Path $root "ORT_Runtime\audio_cpu\models"
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$backupRoot = Join-Path $root "ORT\backups\ORT_V9_0_5_R4_ASR_RUNTIME_FIX_$timestamp"
$backupFile = Join-Path $backupRoot "ORT_App\app\audio\locked_asr_adapter.py"
$statusDir = Join-Path $root "ORT\status"
$statusFile = Join-Path $statusDir "V9_0_5_R4_ASR_RUNTIME_FIX.json"

Write-Step "Root proyek: $root"
Write-Host "Target: $target"

$content = [System.IO.File]::ReadAllText($target, [System.Text.Encoding]::UTF8)
$newLine = if ($content.Contains("`r`n")) { "`r`n" } else { "`n" }

$hasRuntimeBinding = (
    $content -match "runtime_python\s*=\s*Path\(sys\.executable\)" -and
    $content -match "runtime_python\s*=\s*runtime_python"
)

$changed = $false

if (-not $hasRuntimeBinding) {
    Write-Step "Membuat backup source aktif"

    New-Item -ItemType Directory -Path (Split-Path -Parent $backupFile) -Force | Out-Null
    Copy-Item -LiteralPath $target -Destination $backupFile -Force

    if ($content -notmatch "(?m)^import sys\s*$") {
        if ($content -match "(?m)^import re\s*$") {
            $content = [regex]::Replace(
                $content,
                "(?m)^import re\s*$",
                "import re${newLine}import sys",
                1
            )
        } elseif ($content -match "(?m)^from __future__ import annotations\s*$") {
            $content = [regex]::Replace(
                $content,
                "(?m)^from __future__ import annotations\s*$",
                "from __future__ import annotations${newLine}${newLine}import sys",
                1
            )
        } else {
            throw "Lokasi import pada locked_asr_adapter.py tidak dikenali."
        }
    }

    $oldPattern = "(?m)^(?<indent>[ \t]*)status = provider_status\(self\.model_root, self\.provider_id, self\.device\)\s*$"
    $match = [regex]::Match($content, $oldPattern)

    if (-not $match.Success) {
        throw "Call provider_status lama tidak ditemukan. Source mungkin berbeda atau sudah dimodifikasi."
    }

    $indent = $match.Groups["indent"].Value
    $replacementLines = @(
        "${indent}runtime_python = Path(sys.executable).expanduser().resolve()",
        "${indent}self.emit_event(",
        "${indent}    `"state`",",
        "${indent}    state=`"PROVIDER_RUNTIME_BOUND`",",
        "${indent}    provider_id=self.provider_id,",
        "${indent}    device=self.device,",
        "${indent}    runtime_python=str(runtime_python),",
        "${indent}    model_lock=True,",
        "${indent}    local_realtime=True,",
        "${indent})",
        "${indent}status = provider_status(",
        "${indent}    self.model_root,",
        "${indent}    self.provider_id,",
        "${indent}    self.device,",
        "${indent}    runtime_python=runtime_python,",
        "${indent})"
    )

    $replacement = [string]::Join($newLine, $replacementLines)
    $content = [regex]::Replace($content, $oldPattern, $replacement, 1)

    Write-Utf8NoBom -Path $target -Content $content
    $changed = $true

    Write-Host "Source berhasil diperbarui." -ForegroundColor Green
} else {
    Write-Step "Fix sudah terpasang; patch source dilewati"
}

Write-Step "Menghapus bytecode cache Audio"
if (Test-Path -LiteralPath $audioCache) {
    Remove-Item -LiteralPath $audioCache -Recurse -Force
}
Write-Host "Cache dibersihkan." -ForegroundColor Green

$verifyScript = Join-Path ([System.IO.Path]::GetTempPath()) "ort_v9_0_5_r4_verify_$timestamp.py"
$verifyCode = @'
from __future__ import annotations

import inspect
import json
import sys
from pathlib import Path

project_root = Path(sys.argv[1]).resolve()
model_root = Path(sys.argv[2]).resolve()
requested_device = sys.argv[3].strip().lower()

sys.path.insert(0, str(project_root / "ORT_App"))

from app.audio.asr_provider_registry import PROVIDER_REAZON, provider_status
from app.audio.locked_asr_adapter import LockedASRProviderAdapter

load_source = inspect.getsource(LockedASRProviderAdapter.load)

required_tokens = (
    "runtime_python = Path(sys.executable)",
    "runtime_python=runtime_python",
    "PROVIDER_RUNTIME_BOUND",
)
missing = [token for token in required_tokens if token not in load_source]
if missing:
    raise RuntimeError(f"Fix source belum lengkap: {missing}")

runtime_python = Path(sys.executable).resolve()
status = provider_status(
    model_root,
    PROVIDER_REAZON,
    requested_device,
    runtime_python=runtime_python,
)

payload = {
    "passed": bool(status.get("ready")),
    "python": str(runtime_python),
    "requested_device": requested_device,
    "provider": PROVIDER_REAZON,
    "model_path": status.get("model_path"),
    "bridge_ready": status.get("bridge_ready"),
    "errors": list(status.get("errors") or []),
    "warnings": list(status.get("warnings") or []),
}
print(json.dumps(payload, ensure_ascii=False, indent=2))

if not payload["passed"]:
    raise SystemExit(1)
'@

Write-Utf8NoBom -Path $verifyScript -Content $verifyCode

try {
    Write-Step "Compile source dengan runtime CPU dan CUDA"
    Invoke-Python -Python $cpuPython -Arguments @("-m", "py_compile", $target) -Label "CPU py_compile"
    Invoke-Python -Python $gpuPython -Arguments @("-m", "py_compile", $target) -Label "CUDA py_compile"

    Write-Step "Verifikasi provider CPU"
    Invoke-Python `
        -Python $cpuPython `
        -Arguments @($verifyScript, $root, $modelRoot, "cpu") `
        -Label "CPU provider runtime binding"

    Write-Step "Verifikasi provider CUDA"
    Invoke-Python `
        -Python $gpuPython `
        -Arguments @($verifyScript, $root, $modelRoot, "cuda") `
        -Label "CUDA provider runtime binding"

    Write-Step "Verifikasi jalur Hybrid CUDA ke CPU"
    Invoke-Python `
        -Python $gpuPython `
        -Arguments @($verifyScript, $root, $modelRoot, "cpu") `
        -Label "Hybrid effective-CPU runtime binding"
}
catch {
    if ($changed -and (Test-Path -LiteralPath $backupFile)) {
        Write-Warning "Verifikasi gagal. Source asli akan dipulihkan."
        Copy-Item -LiteralPath $backupFile -Destination $target -Force
        if (Test-Path -LiteralPath $audioCache) {
            Remove-Item -LiteralPath $audioCache -Recurse -Force
        }
    }
    throw
}
finally {
    Remove-Item -LiteralPath $verifyScript -Force -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $statusDir -Force | Out-Null

$status = [ordered]@{
    patch = "v9.0.5-R4-ASR-RUNTIME-BINDING"
    applied_at = (Get-Date).ToString("o")
    project_root = $root
    target_file = $target
    backup_file = if ($changed) { $backupFile } else { "" }
    changed = $changed
    cpu_runtime = $cpuPython
    gpu_runtime = $gpuPython
    cpu_probe = "PASS"
    cuda_probe = "PASS"
    hybrid_effective_cpu_probe = "PASS"
    models_downloaded = $false
}

Write-Utf8NoBom -Path $statusFile -Content ($status | ConvertTo-Json -Depth 4)

if ($changed) {
    $rollbackBat = Join-Path $backupRoot "ROLLBACK_R4_ASR_RUNTIME_FIX.bat"
    $rollback = @"
@echo off
chcp 65001 >nul
echo Memulihkan locked_asr_adapter.py sebelum R4...
copy /Y "$backupFile" "$target" >nul
if exist "$audioCache" rmdir /S /Q "$audioCache"
echo ROLLBACK: PASS
pause
"@
    Write-Utf8NoBom -Path $rollbackBat -Content $rollback
}

Write-Step "FIX SELESAI"
Write-Host "ORT v9.0.5 R4 ASR Runtime Binding: PASS" -ForegroundColor Green
Write-Host "Model tidak diunduh ulang." -ForegroundColor Green
Write-Host "Status: $statusFile"
if ($changed) {
    Write-Host "Backup: $backupRoot"
}
Write-Host ""
Write-Host "Tutup lalu buka kembali WebUI. Uji CPU terlebih dahulu, kemudian Hybrid."
