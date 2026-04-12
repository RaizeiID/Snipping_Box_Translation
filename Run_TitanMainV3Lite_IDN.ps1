# Run_TitanMainV3Lite_IDN
# PACK 6.4-IDN-1 (2026-01-05)
# Uses python from PATH. Edit if needed.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$env:TITAN_IDN_STYLE = "neutral"
$env:TITAN_IDN_LOCALIZE = "1"
$env:TITAN_V3_OPTION = "C"
python (Join-Path $here "TitanMainV3Lite_IDN.py")
pause
