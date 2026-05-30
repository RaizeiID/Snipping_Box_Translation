# Run_TitanMainV4
# PACK 6.4-IDN-1 (2026-01-05)
# Uses python from PATH. Edit if needed.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
$env:TITAN_ONLINE_URL = "http://127.0.0.1:5000/translate"
$env:TITAN_ONLINE_FROM = "auto"
$env:TITAN_ONLINE_TIMEOUT = "8"
python (Join-Path $here "TitanMainV4.py")
pause
