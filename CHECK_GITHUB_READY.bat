@echo off
setlocal EnableExtensions
title ORT Translation - GitHub Safety Check

set "ROOT=%~dp0"
echo.
echo ============================================================
echo  ORT Translation - GitHub Safety Check
echo ============================================================
echo.

where git >nul 2>nul
if errorlevel 1 (
  echo [WARN] Git command not found in PATH.
  echo        You can still use EXPORT_GITHUB_SOURCE.bat.
  echo.
  pause
  exit /b 0
)

cd /d "%ROOT%"

if not exist ".git" (
  echo [INFO] This folder is not a Git repository yet.
  echo        Recommended:
  echo        1. Open VSCode at this root folder.
  echo        2. Run: git init
  echo        3. Run this check again before first commit.
  echo.
  pause
  exit /b 0
)

echo [INFO] Checking Git status for heavy/local paths...
echo.

git status --short

echo.
echo [INFO] If you see any of these paths above, DO NOT COMMIT yet:
echo   ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD
echo   ORT/runtime_app/ORT_Runtime
echo   ORT/runtime_app/.venv
echo   ORT/runtime_app/cache
echo   ORT/runtime_app/logs
echo   ORT/runtime_app/backups
echo   ORT/runtime_app/debug_bundles
echo   ORT/cache
echo   ORT/logs
echo   ORT/backups
echo.

echo [INFO] Checking whether ignored files are still tracked...
git ls-files -ci --exclude-standard

echo.
echo If the command above lists files, remove them from Git tracking with:
echo   git rm -r --cached ^<path^>
echo Then commit .gitignore again.
echo.
pause
