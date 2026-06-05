@echo off
setlocal
cd /d "%~dp0"

set "REPO_ROOT=%~dp0..\..\.."
set "SCRIPT=%REPO_ROOT%\apps\desktop\tauri\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1"
set "PWSH=%REPO_ROOT%\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"
if not exist "%PWSH%" set "PWSH=pwsh"

if exist "%SCRIPT%" (
    "%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo Tauri preview launcher not found.
echo Expected:
echo   apps\desktop\tauri\Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1
pause
exit /b 1
