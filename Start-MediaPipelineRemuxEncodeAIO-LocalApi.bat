@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat" (
    call "%~dp0DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat" %*
    exit /b %errorlevel%
)

echo Local API launcher not found.
echo Expected:
echo   DesktopApp\Launch-MediaPipelineRemuxEncodeAIO-LocalApi.bat
pause
exit /b 1
