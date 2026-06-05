@echo off
setlocal
cd /d "%~dp0"

for %%I in ("%~dp0..\..\..") do set "REPO_ROOT=%%~fI"
set "SCRIPT=%REPO_ROOT%\apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat"

if exist "%SCRIPT%" (
    call "%SCRIPT%" %*
    exit /b %errorlevel%
)

echo Local API launcher not found.
echo Expected:
echo   apps\desktop\launchers\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat
pause
exit /b 1
