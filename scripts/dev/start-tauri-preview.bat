@echo off
setlocal
cd /d "%~dp0"

set "SCRIPT=%~dp0..\..\DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1"
set "PWSH=%~dp0..\..\Pipeline\PowerShell-7.6.0-win-x64\pwsh.exe"
if not exist "%PWSH%" set "PWSH=pwsh"

if exist "%SCRIPT%" (
    "%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo Tauri preview launcher not found.
echo Expected:
echo   DesktopApp\tauri_shell\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1
pause
exit /b 1
