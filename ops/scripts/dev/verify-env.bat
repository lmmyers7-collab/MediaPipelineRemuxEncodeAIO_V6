@echo off
setlocal
cd /d "%~dp0"

for %%I in ("%~dp0..\..\..") do set "REPO_ROOT=%%~fI"
set "PWSH=%REPO_ROOT%\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"

if exist "%PWSH%" (
    "%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-env.ps1"
    pause
    exit /b %errorlevel%
)

where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-env.ps1"
    pause
    exit /b %errorlevel%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0verify-env.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
