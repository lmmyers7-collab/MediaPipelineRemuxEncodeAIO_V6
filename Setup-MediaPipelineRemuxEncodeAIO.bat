@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0Pipeline\\Setup-MediaPipelineRemuxEncodeAIO.bat" (
    call "%~dp0Pipeline\\Setup-MediaPipelineRemuxEncodeAIO.bat" %*
    exit /b %errorlevel%
)

echo Setup launcher not found.
echo Expected:
echo   Pipeline\Setup-MediaPipelineRemuxEncodeAIO.bat
pause
exit /b 1
