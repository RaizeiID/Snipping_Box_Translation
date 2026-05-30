@echo off
setlocal EnableExtensions
title ORT Translation - Untrack Local Runtime From Git

cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Git command not found in PATH.
  pause
  exit /b 1
)

if not exist ".git" (
  echo [INFO] This folder is not a Git repository.
  pause
  exit /b 0
)

echo.
echo This will remove heavy/local folders from Git tracking only.
echo It will NOT delete files from your laptop.
echo.
pause

git rm -r --cached ORT/_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD 2>nul
git rm -r --cached ORT/runtime_app/ORT_Runtime 2>nul
git rm -r --cached ORT/runtime_app/.venv 2>nul
git rm -r --cached ORT/runtime_app/venv 2>nul
git rm -r --cached ORT/runtime_app/env 2>nul
git rm -r --cached ORT/runtime_app/models 2>nul
git rm -r --cached ORT/runtime_app/cache 2>nul
git rm -r --cached ORT/runtime_app/logs 2>nul
git rm -r --cached ORT/runtime_app/backups 2>nul
git rm -r --cached ORT/runtime_app/debug_bundles 2>nul
git rm -r --cached ORT/runtime_app/status 2>nul
git rm -r --cached ORT/runtime_app/reports 2>nul
git rm -r --cached ORT/cache 2>nul
git rm -r --cached ORT/logs 2>nul
git rm -r --cached ORT/backups 2>nul
git rm -r --cached ORT/debug_bundles 2>nul
git rm -r --cached ORT/status 2>nul
git rm -r --cached ORT/reports 2>nul

echo.
echo [OK] Done. Now run:
echo   git status
echo   git add .gitignore ORT/.gitignore .gitattributes
echo   git commit -m "chore: ignore local runtime and generated data"
echo.
pause
