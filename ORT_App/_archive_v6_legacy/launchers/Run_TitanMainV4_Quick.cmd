:: Run_TitanMainV4
:: PACK 6.4-IDN-1 (2026-01-05)
:: Edit python path below if needed. Default uses python from PATH.

@echo off
cd /d "%~dp0"
set TITAN_ONLINE_URL=http://127.0.0.1:5000/translate
set TITAN_ONLINE_FROM=auto
set TITAN_ONLINE_TIMEOUT=8
python "%~dp0TitanMainV4.py"
pause
