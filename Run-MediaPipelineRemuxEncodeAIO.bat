@echo off
setlocal
cd /d "%~dp0"

if exist "%~dp0Pipeline\\Run-MediaPipelineRemuxEncodeAIO.bat" (
    call "%~dp0Pipeline\\Run-MediaPipelineRemuxEncodeAIO.bat" %*
    exit /b %errorlevel%
)

echo Run launcher not found.
echo Expected:
echo   Pipeline\Run-MediaPipelineRemuxEncodeAIO.bat
pause
exit /b 1
