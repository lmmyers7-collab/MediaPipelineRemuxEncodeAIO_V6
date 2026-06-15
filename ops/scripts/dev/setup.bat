@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "SCRIPT_ROOT=%~dp0"
for %%I in ("%SCRIPT_ROOT%..\..\..") do set "PROJECT_ROOT=%%~fI"
set "PIPELINE_ROOT=%PROJECT_ROOT%\ops\pipeline"
set "PIPELINE_ENTRYPOINT_ROOT=%PIPELINE_ROOT%\entrypoints"
set "SETUP_ALIAS_ARGS="

if /i "%~1"=="/?" goto :show_help
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help

if /i "%~1"=="validate" set "SETUP_ALIAS_ARGS=-ValidateOnly"
if /i "%~1"=="quick" set "SETUP_ALIAS_ARGS=-AcceptDefaults"
if /i "%~1"=="defaults" set "SETUP_ALIAS_ARGS=-ListDefaults"

if not exist "%PIPELINE_ENTRYPOINT_ROOT%\Setup-MediaPipeline.ps1" (
    echo ERROR: Setup-MediaPipeline.ps1 was not found in:
    echo   %PIPELINE_ENTRYPOINT_ROOT%
    pause
    exit /b 1
)

if exist "%PIPELINE_ROOT%\tools\ffmpeg\bin" set "PATH=%PIPELINE_ROOT%\tools\ffmpeg\bin;%PATH%"
if exist "%PIPELINE_ROOT%\tools\MKVToolNix" set "PATH=%PIPELINE_ROOT%\tools\MKVToolNix;%PATH%"
if exist "%PIPELINE_ROOT%\runtime\Python" set "PATH=%PIPELINE_ROOT%\runtime\Python;%PATH%"
if exist "%PROJECT_ROOT%\apps\desktop\runtime\Python" set "PATH=%PROJECT_ROOT%\apps\desktop\runtime\Python;%PATH%"

set "PWSH_PATH="
if exist "%PIPELINE_ROOT%\runtime\PowerShell-7.6.0-win-x64\pwsh.exe" set "PWSH_PATH=%PIPELINE_ROOT%\runtime\PowerShell-7.6.0-win-x64\pwsh.exe"

if not defined PWSH_PATH (
    for /d %%D in ("%PIPELINE_ROOT%\runtime\PowerShell-*") do (
        if exist "%%~fD\pwsh.exe" (
            set "PWSH_PATH=%%~fD\pwsh.exe"
            goto :pwsh_resolved
        )
    )
)

if not defined PWSH_PATH (
    for /f "delims=" %%I in ('where pwsh.exe 2^>nul') do (
        if not defined PWSH_PATH set "PWSH_PATH=%%I"
    )
)

:pwsh_resolved
if defined PWSH_PATH (
    echo Launching setup with PowerShell 7: %PWSH_PATH%
    if defined SETUP_ALIAS_ARGS (
        "%PWSH_PATH%" -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ENTRYPOINT_ROOT%\Setup-MediaPipeline.ps1" %SETUP_ALIAS_ARGS%
    ) else (
        "%PWSH_PATH%" -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ENTRYPOINT_ROOT%\Setup-MediaPipeline.ps1" %*
    )
) else (
    echo ERROR: PowerShell 7 was not found.
    echo Expected bundled runtime under "%PIPELINE_ROOT%\runtime\PowerShell-7.6.0-win-x64" or pwsh.exe on PATH.
    pause
    exit /b 1
)

set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Setup exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

:show_help
echo MediaPipelineRemuxEncodeAIO setup launcher 1.0
echo.
echo Usage:
echo   ops\scripts\dev\setup.bat
echo   ops\scripts\dev\setup.bat validate
echo   ops\scripts\dev\setup.bat quick
echo   ops\scripts\dev\setup.bat defaults
echo.
echo Examples:
echo   ops\scripts\dev\setup.bat
echo     Runs the interactive setup wizard.
echo.
echo   ops\scripts\dev\setup.bat validate
echo     Validates the current config only.
echo.
echo   ops\scripts\dev\setup.bat quick
echo     Uses default answers where possible.
echo.
echo   ops\scripts\dev\setup.bat defaults
echo     Prints the default config template.
echo.
pause
exit /b 0
