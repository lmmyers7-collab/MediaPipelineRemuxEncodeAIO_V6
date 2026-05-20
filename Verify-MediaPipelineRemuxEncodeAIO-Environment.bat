@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0Pipeline\\PowerShell-7.6.0-win-x64\\pwsh.exe" (
    "%~dp0Pipeline\\PowerShell-7.6.0-win-x64\\pwsh.exe" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1"
    pause
    exit /b %errorlevel%
)

where pwsh >nul 2>nul
if %errorlevel%==0 (
    pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1"
    pause
    exit /b %errorlevel%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Verify-MediaPipelineRemuxEncodeAIO-Environment.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
