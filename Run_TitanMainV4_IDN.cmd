:: Run_TitanMainV4_IDN
:: PACK 6.4-IDN-1 (2026-01-05)
:: Edit python path below if needed. Default uses python from PATH.

@echo off
cd /d "%~dp0"
set TITAN_IDN_STYLE=neutral
set TITAN_IDN_LOCALIZE=1
set TITAN_V4_PRIMARY_ENGINE=DEEPLX
set TITAN_V4_HYBRID_DELAY_MS=220
set TITAN_PING_INTERVAL_MS=900
python "%~dp0TitanMainV4_IDN.py"
pause
