@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_ROOT=%~dp0"
for %%I in ("%SCRIPT_ROOT%..\..") do set "PROJECT_ROOT=%%~fI"
set "PIPELINE_ROOT=%PROJECT_ROOT%\Pipeline"

if /i "%~1"=="/?" goto :show_help
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help

set "SETUP_ARGS=%*"
if /i "%~1"=="validate" set "SETUP_ARGS=-ValidateOnly"
if /i "%~1"=="quick" set "SETUP_ARGS=-AcceptDefaults"
if /i "%~1"=="defaults" set "SETUP_ARGS=-ListDefaults"

if not exist "%PIPELINE_ROOT%\Setup-MediaPipeline.ps1" (
    echo ERROR: Setup-MediaPipeline.ps1 was not found in:
    echo   %PIPELINE_ROOT%
    pause
    exit /b 1
)

if exist "%PIPELINE_ROOT%\Tools\ffmpeg\bin" set "PATH=%PIPELINE_ROOT%\Tools\ffmpeg\bin;%PATH%"
if exist "%PIPELINE_ROOT%\Tools\MKVToolNix" set "PATH=%PIPELINE_ROOT%\Tools\MKVToolNix;%PATH%"
if exist "%PIPELINE_ROOT%\Runtime\Python" set "PATH=%PIPELINE_ROOT%\Runtime\Python;%PATH%"
if exist "%PROJECT_ROOT%\DesktopApp\Runtime\Python" set "PATH=%PROJECT_ROOT%\DesktopApp\Runtime\Python;%PATH%"

set "PWSH_PATH="
if exist "%PIPELINE_ROOT%\pwsh.exe" set "PWSH_PATH=%PIPELINE_ROOT%\pwsh.exe"

if not defined PWSH_PATH (
    for /d %%D in ("%PIPELINE_ROOT%\PowerShell-*") do (
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
    "!PWSH_PATH!" -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ROOT%\Setup-MediaPipeline.ps1" !SETUP_ARGS!
) else (
    echo PowerShell 7 was not found. Falling back to Windows PowerShell for setup only.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ROOT%\Setup-MediaPipeline.ps1" !SETUP_ARGS!
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
echo   scripts\dev\setup.bat
echo   scripts\dev\setup.bat validate
echo   scripts\dev\setup.bat quick
echo   scripts\dev\setup.bat defaults
echo.
echo Examples:
echo   scripts\dev\setup.bat
echo     Runs the interactive setup wizard.
echo.
echo   scripts\dev\setup.bat validate
echo     Validates the current config only.
echo.
echo   scripts\dev\setup.bat quick
echo     Uses default answers where possible.
echo.
echo   scripts\dev\setup.bat defaults
echo     Prints the default config template.
echo.
pause
exit /b 0
