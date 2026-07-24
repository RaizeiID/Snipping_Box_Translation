:: Run_TitanMainV1_IDN
:: PACK 6.4-IDN-1 (2026-01-05)
:: Edit python path below if needed. Default uses python from PATH.

@echo off
cd /d "%~dp0"
set TITAN_IDN_STYLE=neutral
set TITAN_IDN_LOCALIZE=1
python "%~dp0TitanMainV1_IDN.py"
pause
