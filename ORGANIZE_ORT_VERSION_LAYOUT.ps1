[CmdletBinding()]
param(
    [string]$ProjectRoot = ".",
    [switch]$Apply,
    [switch]$Force,
    [switch]$IndexBackups
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)

function Resolve-OrtRoot {
    param([string]$Candidate)

    $resolved = Resolve-Path -LiteralPath $Candidate -ErrorAction Stop
    $root = $resolved.Path

    $required = @(
        (Join-Path $root "VERSION.txt"),
        (Join-Path $root "ORT_App"),
        (Join-Path $root "ORT_Runtime"),
        (Join-Path $root "ORT")
    )

    foreach ($path in $required) {
        if (-not (Test-Path -LiteralPath $path)) {
            throw "Project root ORT tidak valid. Komponen wajib tidak ditemukan: $path"
        }
    }

    return $root
}

function Get-SafeVersionName {
    param([string]$Root)

    $raw = (Get-Content -LiteralPath (Join-Path $Root "VERSION.txt") -Raw -Encoding UTF8).Trim()
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return "unknown-version"
    }

    return ($raw -replace '[<>:"/\\|?*]', '_')
}

function Get-Sha256Safe {
    param([string]$Path)

    try {
        if (Test-Path -LiteralPath $Path -PathType Leaf) {
            return (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
        }
    } catch {}
    return ""
}

function Get-UniqueDestination {
    param([string]$Destination)

    if (-not (Test-Path -LiteralPath $Destination)) {
        return $Destination
    }

    $parent = Split-Path -Parent $Destination
    $leaf = Split-Path -Leaf $Destination
    $extension = [System.IO.Path]::GetExtension($leaf)
    $baseName = if ($extension) {
        $leaf.Substring(0, $leaf.Length - $extension.Length)
    } else {
        $leaf
    }

    for ($index = 1; $index -lt 10000; $index++) {
        $candidateLeaf = if ($extension) {
            "${baseName}_$index$extension"
        } else {
            "${baseName}_$index"
        }

        $candidate = Join-Path $parent $candidateLeaf
        if (-not (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    throw "Tidak dapat membuat nama tujuan unik untuk: $Destination"
}

function Add-PlanItem {
    param(
        [System.Collections.Generic.List[object]]$Plan,
        [string]$Source,
        [string]$DestinationDirectory,
        [string]$Category
    )

    if (-not (Test-Path -LiteralPath $Source)) {
        return
    }

    $destination = Join-Path $DestinationDirectory (Split-Path -Leaf $Source)
    $destination = Get-UniqueDestination -Destination $destination
    $item = Get-Item -LiteralPath $Source -Force

    $Plan.Add([pscustomobject]@{
        Category = $Category
        Source = $Source
        Destination = $destination
        Type = if ($item.PSIsContainer) { "Directory" } else { "File" }
        SizeBytes = if ($item.PSIsContainer) { $null } else { $item.Length }
        Sha256 = if ($item.PSIsContainer) { "" } else { Get-Sha256Safe -Path $Source }
    })
}

function Get-OrtProcesses {
    param([string]$Root)

    try {
        return @(
            Get-CimInstance Win32_Process -ErrorAction Stop |
            Where-Object {
                $_.ProcessId -ne $PID -and
                $_.CommandLine -and
                $_.CommandLine.IndexOf($Root, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
            } |
            Select-Object ProcessId, Name, CommandLine
        )
    } catch {
        return @()
    }
}

function New-BackupIndex {
    param(
        [string]$BackupRoot,
        [string]$DestinationCsv
    )

    if (-not (Test-Path -LiteralPath $BackupRoot)) {
        return
    }

    $rows = foreach ($directory in Get-ChildItem -LiteralPath $BackupRoot -Directory -Force -ErrorAction SilentlyContinue) {
        $files = @(
            Get-ChildItem -LiteralPath $directory.FullName -Recurse -File -Force -ErrorAction SilentlyContinue
        )
        $total = [long](($files | Measure-Object -Property Length -Sum).Sum)

        [pscustomobject]@{
            BackupName = $directory.Name
            FullPath = $directory.FullName
            LastWriteTime = $directory.LastWriteTime.ToString("o")
            FileCount = $files.Count
            SizeBytes = $total
            SizeMB = [math]::Round($total / 1MB, 2)
        }
    }

    $parent = Split-Path -Parent $DestinationCsv
    New-Item -ItemType Directory -Path $parent -Force | Out-Null
    $rows |
        Sort-Object LastWriteTime -Descending |
        Export-Csv -LiteralPath $DestinationCsv -NoTypeInformation -Encoding UTF8
}

$root = Resolve-OrtRoot -Candidate $ProjectRoot
$version = Get-SafeVersionName -Root $root
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"

$ortRoot = Join-Path $root "ORT"
$releaseRoot = Join-Path $ortRoot "release\$version"
$reportRoot = Join-Path $releaseRoot "reports"
$manifestRoot = Join-Path $releaseRoot "manifests"
$archiveRoot = Join-Path $ortRoot "archive\version_updates\$stamp"
$patchArchiveRoot = Join-Path $archiveRoot "patch_files"
$packageArchiveRoot = Join-Path $archiveRoot "patch_packages"
$diagnosticRoot = Join-Path $ortRoot "debug_bundles\manual\$stamp"
$organizerRoot = Join-Path $ortRoot "maintenance\organizer"
$receiptRoot = Join-Path $organizerRoot "receipts"

$protectedRootNames = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

@(
    ".git",
    ".github",
    ".vscode",
    ".gitattributes",
    ".gitignore",
    "VERSION.txt",
    "README.md",
    "START_HERE.bat",
    "Start WebUI.bat",
    "Start OCR.bat",
    "Runtime.bat",
    "ORT v9 Setup.bat",
    "CHECK_GITHUB_READY.bat",
    "EXPORT_GITHUB_SOURCE.bat",
    "UNTRACK_LOCAL_RUNTIME_FROM_GIT.bat",
    "ORT_App",
    "ORT_Runtime",
    "ORT",
    "models"
) | ForEach-Object { [void]$protectedRootNames.Add($_) }

$plan = [System.Collections.Generic.List[object]]::new()

foreach ($item in Get-ChildItem -LiteralPath $root -Force) {
    if ($protectedRootNames.Contains($item.Name)) {
        continue
    }

    $name = $item.Name

    if ($name -match '^APPLY_ORT_.*\.(bat|py|ps1)$') {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $patchArchiveRoot -Category "Old patch/applicator"
        continue
    }

    if (
        $name -match '^ORT_v\d+(\.\d+)+.*\.(zip|7z|rar)$' -or
        ($item.PSIsContainer -and $name -match '^ORT_v\d+(\.\d+)+.*(Patch|Repair|Update|Diagnostic)')
    ) {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $packageArchiveRoot -Category "Extracted/update package"
        continue
    }

    if (
        $name -match '^ORT_V\d+.*VALIDATION_REPORT\.md$' -or
        $name -match '^ORT_v\d+.*VALIDATION_REPORT\.md$'
    ) {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $reportRoot -Category "Validation report"
        continue
    }

    if (
        $name -match '^(PATCH_SHA256|PAYLOAD_SHA256|manifest_sha256)\.json$' -or
        $name -match '^FULL_PROJECT_MANIFEST_.*\.txt$'
    ) {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $manifestRoot -Category "Release manifest"
        continue
    }

    if (
        $name -match '^RUN_ORT_DIAGNOSTIC.*\.(bat|ps1|py)$' -or
        $name -match '^ORT_.*DIAGNOSTIC.*\.(txt|json|csv|zip|md)$' -or
        $name -match '^ORT_FOLDER_.*\.(txt|csv|zip)$'
    ) {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $diagnosticRoot -Category "Manual diagnostic"
        continue
    }

    if ($name -match '^ORT_V\d+.*\.(md|txt|json)$') {
        Add-PlanItem -Plan $plan -Source $item.FullName `
            -DestinationDirectory $reportRoot -Category "Version report"
        continue
    }
}

Write-Host ""
Write-Host "============================================================"
Write-Host " ORT VERSION LAYOUT ORGANIZER"
Write-Host "============================================================"
Write-Host "Project root : $root"
Write-Host "Version      : $version"
Write-Host "Mode         : $(if ($Apply) { 'APPLY' } else { 'PREVIEW / DRY-RUN' })"
Write-Host ""
Write-Host "Folder yang selalu dilindungi:"
Write-Host "  ORT_App, ORT_Runtime, ORT, models, launcher utama, VERSION.txt"
Write-Host ""

if ($plan.Count -eq 0) {
    Write-Host "Tidak ada artefak root yang perlu dipindahkan." -ForegroundColor Green
    exit 0
}

$plan |
    Select-Object Category, Type,
        @{Name="Source"; Expression={$_.Source.Replace($root, ".")}},
        @{Name="Destination"; Expression={$_.Destination.Replace($root, ".")}} |
    Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "Total item direncanakan: $($plan.Count)"

if (-not $Apply) {
    Write-Host ""
    Write-Host "Belum ada file yang dipindahkan." -ForegroundColor Yellow
    Write-Host "Periksa daftar di atas. Untuk menjalankan:"
    Write-Host ""
    Write-Host 'powershell -ExecutionPolicy Bypass -File ".\ORGANIZE_ORT_VERSION_LAYOUT.ps1" -Apply'
    Write-Host ""
    exit 0
}

$running = Get-OrtProcesses -Root $root
if ($running.Count -gt 0 -and -not $Force) {
    Write-Host ""
    Write-Host "Ditemukan proses yang masih memakai folder ORT:" -ForegroundColor Red
    $running | Format-Table -AutoSize
    Write-Host ""
    Write-Host "Tutup WebUI, Audio Mode, OCR, dan terminal Python ORT lalu jalankan kembali."
    Write-Host "Gunakan -Force hanya apabila Anda benar-benar memahami risikonya."
    exit 6
}

foreach ($directory in @(
    $reportRoot,
    $manifestRoot,
    $patchArchiveRoot,
    $packageArchiveRoot,
    $diagnosticRoot,
    $organizerRoot,
    $receiptRoot
)) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$completed = [System.Collections.Generic.List[object]]::new()

try {
    foreach ($entry in $plan) {
        $destinationParent = Split-Path -Parent $entry.Destination
        New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null

        Write-Host "[MOVE] $($entry.Source.Replace($root, '.'))"
        Move-Item -LiteralPath $entry.Source -Destination $entry.Destination -Force

        $completed.Add([pscustomobject]@{
            Category = $entry.Category
            Source = $entry.Source
            Destination = $entry.Destination
            Type = $entry.Type
            SizeBytes = $entry.SizeBytes
            Sha256 = $entry.Sha256
            MovedAt = (Get-Date).ToString("o")
        })
    }
} catch {
    Write-Host ""
    Write-Host "Penataan gagal: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Mencoba rollback item yang sudah dipindahkan..."

    foreach ($entry in @($completed | Select-Object -Reverse)) {
        try {
            if (
                (Test-Path -LiteralPath $entry.Destination) -and
                -not (Test-Path -LiteralPath $entry.Source)
            ) {
                $sourceParent = Split-Path -Parent $entry.Source
                New-Item -ItemType Directory -Path $sourceParent -Force | Out-Null
                Move-Item -LiteralPath $entry.Destination -Destination $entry.Source -Force
                Write-Host "[ROLLBACK] $($entry.Source.Replace($root, '.'))"
            }
        } catch {
            Write-Host "[ROLLBACK ERROR] $($_.Exception.Message)" -ForegroundColor Red
        }
    }

    exit 7
}

$receiptPath = Join-Path $receiptRoot "organize_$stamp.json"
$rollbackPath = Join-Path $organizerRoot "ROLLBACK_ORGANIZE_$stamp.ps1"
$layoutPolicyPath = Join-Path $organizerRoot "ROOT_LAYOUT_POLICY.md"

$receipt = [ordered]@{
    schema = 1
    action = "ORT version layout organization"
    version = $version
    project_root = $root
    created_at = (Get-Date).ToString("o")
    item_count = $completed.Count
    items = @($completed)
}

$receipt |
    ConvertTo-Json -Depth 8 |
    Set-Content -LiteralPath $receiptPath -Encoding UTF8

$rollbackScript = @'
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$receiptPath = "__RECEIPT_PATH__"
$receipt = Get-Content -LiteralPath $receiptPath -Raw -Encoding UTF8 | ConvertFrom-Json

foreach ($entry in @($receipt.items | Select-Object -Reverse)) {
    if (
        (Test-Path -LiteralPath $entry.Destination) -and
        -not (Test-Path -LiteralPath $entry.Source)
    ) {
        $sourceParent = Split-Path -Parent $entry.Source
        New-Item -ItemType Directory -Path $sourceParent -Force | Out-Null
        Move-Item -LiteralPath $entry.Destination -Destination $entry.Source -Force
        Write-Host "[RESTORE] $($entry.Source)"
    } elseif (Test-Path -LiteralPath $entry.Source) {
        Write-Host "[SKIP] Source sudah ada: $($entry.Source)"
    } else {
        Write-Host "[MISSING] Tidak ditemukan: $($entry.Destination)"
    }
}

Write-Host "Rollback penataan selesai."
'@

$rollbackScript = $rollbackScript.Replace(
    "__RECEIPT_PATH__",
    $receiptPath.Replace("'", "''")
)
$rollbackScript | Set-Content -LiteralPath $rollbackPath -Encoding UTF8

@"
# ORT Root Layout Policy

Root ORT hanya digunakan untuk komponen aktif dan launcher utama.

## Tetap berada di root

- `VERSION.txt`
- `README.md`
- `START_HERE.bat`
- `Start WebUI.bat`
- `Start OCR.bat`
- `Runtime.bat`
- `ORT v9 Setup.bat`
- `ORT_App/`
- `ORT_Runtime/`
- `ORT/`
- `models/`
- `.git*` dan `.vscode/`

## Lokasi artefak versi

- Laporan versi: `ORT/release/<version>/reports/`
- Manifest/checksum: `ORT/release/<version>/manifests/`
- Patch lama: `ORT/archive/version_updates/<timestamp>/patch_files/`
- Paket update: `ORT/archive/version_updates/<timestamp>/patch_packages/`
- Diagnostic manual: `ORT/debug_bundles/manual/<timestamp>/`
- Receipt dan rollback: `ORT/maintenance/organizer/`

## Aturan

1. Update versi harus menulis source aktif langsung ke `ORT_App`.
2. Runtime dan model hanya berada di `ORT_Runtime` atau `models`.
3. Patch/applicator tidak boleh menjadi dependency runtime.
4. Launcher root tidak boleh mengarah ke folder patch atau backup.
5. Folder `ORT/backups` tidak dihapus otomatis.
"@ | Set-Content -LiteralPath $layoutPolicyPath -Encoding UTF8

if ($IndexBackups) {
    $backupIndexPath = Join-Path $organizerRoot "BACKUP_INDEX_$stamp.csv"
    Write-Host "[INDEX] Mengindeks ORT\backups..."
    New-BackupIndex -BackupRoot (Join-Path $ortRoot "backups") `
        -DestinationCsv $backupIndexPath
    Write-Host "Backup index: $backupIndexPath"
}

Write-Host ""
Write-Host "ORT_ORGANIZE_VERSION_LAYOUT: PASS" -ForegroundColor Green
Write-Host "Item dipindahkan : $($completed.Count)"
Write-Host "Receipt          : $receiptPath"
Write-Host "Rollback         : $rollbackPath"
Write-Host "Layout policy    : $layoutPolicyPath"
Write-Host ""
Write-Host "Source aktif, runtime, model, backup, dan launcher utama tidak diubah."
