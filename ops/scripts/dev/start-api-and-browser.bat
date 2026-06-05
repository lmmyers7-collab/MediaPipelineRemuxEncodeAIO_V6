@echo off
setlocal
cd /d "%~dp0"

for %%I in ("%~dp0..\..\..") do set "REPO_ROOT=%%~fI"
set "SCRIPT=%REPO_ROOT%\apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1"
set "PWSH=%REPO_ROOT%\ops\pipeline\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"
if not exist "%PWSH%" set "PWSH=pwsh"

if exist "%SCRIPT%" (
    "%PWSH%" -NoProfile -ExecutionPolicy Bypass -File "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo API + Browser launcher not found.
echo Expected:
echo   apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1
pause
exit /b 1
