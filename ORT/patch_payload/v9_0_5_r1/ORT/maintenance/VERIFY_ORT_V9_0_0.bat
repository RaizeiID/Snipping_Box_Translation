@echo off
rem Compatibility entry point. ORT v9.0.5 uses the current verifier.
call "%~dp0VERIFY_ORT_V9_0_5.bat"
exit /b %ERRORLEVEL%
