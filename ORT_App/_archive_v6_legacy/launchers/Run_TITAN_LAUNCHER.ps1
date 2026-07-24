Set-Location $PSScriptRoot
try {
  py -3 .\TITAN_LAUNCHER.py
} catch {
  Write-Host "[!] Launcher error: $($_.Exception.Message)"
}
Write-Host ""
Write-Host "Press Enter to close..."
[void][System.Console]::ReadLine()
