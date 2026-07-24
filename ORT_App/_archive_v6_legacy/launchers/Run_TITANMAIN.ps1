# Run_TITANMAIN
# PACK 6.4-IDN-1 (2026-01-05)
# Uses python from PATH. Edit if needed.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
python (Join-Path $here "TITANMAIN.py")
pause
