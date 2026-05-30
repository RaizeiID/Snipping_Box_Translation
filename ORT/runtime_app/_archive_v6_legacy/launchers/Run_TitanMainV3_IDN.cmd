:: Run_TitanMainV3_IDN
:: PACK 6.4-IDN-1 (2026-01-05)
:: Edit python path below if needed. Default uses python from PATH.

@echo off
cd /d "%~dp0"
set TITAN_IDN_STYLE=neutral
set TITAN_IDN_LOCALIZE=1
set TITAN_V3_OPTION=C
python "%~dp0TitanMainV3_IDN.py"
pause
