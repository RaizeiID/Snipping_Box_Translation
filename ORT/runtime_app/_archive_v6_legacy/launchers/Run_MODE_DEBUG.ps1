# Run_MODE_DEBUG
# PACK 6.4-IDN-1 (2026-01-05)
# Uses python from PATH. Edit if needed.

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here
python (Join-Path $here "MODE_DEBUG.py")
pause
