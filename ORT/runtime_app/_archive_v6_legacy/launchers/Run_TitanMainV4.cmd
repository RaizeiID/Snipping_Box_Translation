:: Run_TitanMainV4.cmd
:: Jalankan dari CMD (bukan PowerShell) jika mau.
:: Catatan: set hanya berlaku untuk jendela ini.

@echo off
set TITAN_ONLINE_URL=http://127.0.0.1:5000/translate
set TITAN_ONLINE_FROM=auto
set TITAN_ONLINE_TIMEOUT=8

set TITAN_GAS_URL=https://script.google.com/macros/s/XXXX/exec
set TITAN_GAS_TOKEN=
set TITAN_GAS_TIMEOUT=12

set TITAN_DEEPLX_URL=http://127.0.0.1:1188
set TITAN_DEEPLX_MODE=free
set TITAN_DEEPLX_TIMEOUT=10

set TITAN_V4_FALLBACK_ONLINE=1
set TITAN_V4_BOX_PRIMARY=AUTO

"C:\Users\Raizei\AppData\Local\Programs\Python\Python312\python.exe" "%~dp0TitanMainV4.py"
