@echo off
setlocal EnableExtensions EnableDelayedExpansion
title ORT Translation - Export GitHub Source ZIP

set "ROOT=%~dp0"
set "OUT=%ROOT%ORT_GITHUB_SOURCE_EXPORT.zip"
set "PS=%TEMP%\ort_export_github_source_%RANDOM%.ps1"

echo.
echo ============================================================
echo  ORT Translation - GitHub Source Export
echo ============================================================
echo  This will create a GitHub-safe ZIP and exclude:
echo  - ORT\_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD
echo  - runtime/model/cache/log/backups/debug folders
echo  - active user data/preferences
echo  - Python cache/temp files
echo.

if exist "%OUT%" del /f /q "%OUT%"

> "%PS%" echo $ErrorActionPreference = 'Stop'
>> "%PS%" echo $root = (Resolve-Path '%ROOT%').Path
>> "%PS%" echo $out = Join-Path $root 'ORT_GITHUB_SOURCE_EXPORT.zip'
>> "%PS%" echo $excludePatterns = @(
>> "%PS%" echo   '\\ORT\\_LOCAL_RUNTIME_WEB_DO_NOT_UPLOAD(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\ORT_Runtime(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\.venv(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\venv(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\env(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\models?(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\cache(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\logs(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\backups(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\debug_bundles(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\status(\\^|$)',
>> "%PS%" echo   '\\ORT\\runtime_app\\reports(\\^|$)',
>> "%PS%" echo   '\\ORT\\cache(\\^|$)',
>> "%PS%" echo   '\\ORT\\logs(\\^|$)',
>> "%PS%" echo   '\\ORT\\backups(\\^|$)',
>> "%PS%" echo   '\\ORT\\debug_bundles(\\^|$)',
>> "%PS%" echo   '\\ORT\\status(\\^|$)',
>> "%PS%" echo   '\\ORT\\reports(\\^|$)',
>> "%PS%" echo   '\\__pycache__(\\^|$)',
>> "%PS%" echo   '\\.git(\\^|$)'
>> "%PS%" echo )
>> "%PS%" echo $excludeFiles = @('*.pyc','*.pyo','*.pyd','*.log','*.tmp','*.bak','*.old','*.orig','*.swp','*.swo','*.mkv','*.mp4')
>> "%PS%" echo Add-Type -AssemblyName System.IO.Compression.FileSystem
>> "%PS%" echo if (Test-Path $out) { Remove-Item $out -Force }
>> "%PS%" echo $zip = [System.IO.Compression.ZipFile]::Open($out, [System.IO.Compression.ZipArchiveMode]::Create)
>> "%PS%" echo try {
>> "%PS%" echo   $files = Get-ChildItem -Path $root -Recurse -File -Force ^| Where-Object {
>> "%PS%" echo     $rel = $_.FullName.Substring($root.Length).TrimStart('\')
>> "%PS%" echo     if ($rel -eq 'ORT_GITHUB_SOURCE_EXPORT.zip') { return $false }
>> "%PS%" echo     foreach ($p in $excludePatterns) { if ($rel -match $p) { return $false } }
>> "%PS%" echo     foreach ($f in $excludeFiles) { if ($_.Name -like $f) { return $false } }
>> "%PS%" echo     return $true
>> "%PS%" echo   }
>> "%PS%" echo   foreach ($file in $files) {
>> "%PS%" echo     $rel = $file.FullName.Substring($root.Length).TrimStart('\')
>> "%PS%" echo     [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $rel, [System.IO.Compression.CompressionLevel]::Optimal) ^| Out-Null
>> "%PS%" echo   }
>> "%PS%" echo } finally {
>> "%PS%" echo   $zip.Dispose()
>> "%PS%" echo }
>> "%PS%" echo Write-Host "Created:" $out

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS%"
set "ERR=%ERRORLEVEL%"
del /f /q "%PS%" >nul 2>&1

if not "%ERR%"=="0" (
  echo.
  echo [ERROR] Export failed.
  pause
  exit /b %ERR%
)

echo.
echo [OK] Created GitHub-safe source ZIP:
echo %OUT%
echo.
pause
