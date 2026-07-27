[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$receiptPath = "D:\AI TRANSLATOR\ORT_Translation_v8_8_1\ORT\maintenance\organizer\receipts\organize_20260725_212903.json"
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
