@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

if /i "%~1"=="/?" goto :show_help
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help

set "SETUP_ARGS=%*"
if /i "%~1"=="validate" set "SETUP_ARGS=-ValidateOnly"
if /i "%~1"=="quick" set "SETUP_ARGS=-AcceptDefaults"
if /i "%~1"=="defaults" set "SETUP_ARGS=-ListDefaults"

if exist "%~dp0Tools\ffmpeg\bin" set "PATH=%~dp0Tools\ffmpeg\bin;%PATH%"
if exist "%~dp0Tools\MKVToolNix" set "PATH=%~dp0Tools\MKVToolNix;%PATH%"
if exist "%~dp0Runtime\Python" set "PATH=%~dp0Runtime\Python;%PATH%"
if exist "%~dp0..\DesktopApp\Runtime\Python" set "PATH=%~dp0..\DesktopApp\Runtime\Python;%PATH%"

set "PWSH_PATH="
if exist "%~dp0pwsh.exe" set "PWSH_PATH=%~dp0pwsh.exe"

if not defined PWSH_PATH (
    for /d %%D in ("%~dp0PowerShell-*") do (
        if exist "%%~fD\pwsh.exe" (
            set "PWSH_PATH=%%~fD\pwsh.exe"
            goto :pwsh_resolved
        )
    )
)

if not defined PWSH_PATH (
    for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$cmd=Get-Command pwsh -ErrorAction SilentlyContinue; if($cmd){$cmd.Source}"`) do (
        set "PWSH_PATH=%%I"
    )
)

:pwsh_resolved
if defined PWSH_PATH (
    echo Launching setup with PowerShell 7: !PWSH_PATH!
    "!PWSH_PATH!" -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-MediaPipeline_chatgpt.ps1" !SETUP_ARGS!
) else (
    echo PowerShell 7 was not found. Falling back to Windows PowerShell for setup only.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-MediaPipeline_chatgpt.ps1" !SETUP_ARGS!
)

set "EXIT_CODE=!ERRORLEVEL!"
echo.
echo Setup exited with code !EXIT_CODE!.
pause
exit /b !EXIT_CODE!

:show_help
echo MediaPipelineRemuxEncodeAIO setup launcher 1.0
echo.
echo Usage:
echo   Setup-MediaPipelineRemuxEncodeAIO.bat
echo   Setup-MediaPipelineRemuxEncodeAIO.bat validate
echo   Setup-MediaPipelineRemuxEncodeAIO.bat quick
echo   Setup-MediaPipelineRemuxEncodeAIO.bat defaults
echo.
echo Examples:
echo   Setup-MediaPipelineRemuxEncodeAIO.bat
echo     Runs the interactive setup wizard.
echo.
echo   Setup-MediaPipelineRemuxEncodeAIO.bat validate
echo     Validates the current config only.
echo.
echo   Setup-MediaPipelineRemuxEncodeAIO.bat quick
echo     Uses default answers where possible.
echo.
echo   Setup-MediaPipelineRemuxEncodeAIO.bat defaults
echo     Prints the default config template.
echo.
pause
exit /b 0
