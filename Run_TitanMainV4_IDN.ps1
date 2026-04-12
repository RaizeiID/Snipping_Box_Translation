# Run_TitanMainV4_IDN
# PACK 6.4-IDN-1 (2026-01-05)
# Uses python from PATH. Edit if needed.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$env:TITAN_IDN_STYLE = "neutral"
$env:TITAN_IDN_LOCALIZE = "1"
$env:TITAN_V4_PRIMARY_ENGINE = "DEEPLX"
$env:TITAN_V4_HYBRID_DELAY_MS = "220"
$env:TITAN_PING_INTERVAL_MS = "900"
python (Join-Path $here "TitanMainV4_IDN.py")
pause
