@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_ROOT=%~dp0"
for %%I in ("%SCRIPT_ROOT%..\..\..") do set "PROJECT_ROOT=%%~fI"
set "PIPELINE_ROOT=%PROJECT_ROOT%\ops\pipeline"
set "PIPELINE_ENTRYPOINT_ROOT=%PIPELINE_ROOT%\entrypoints"
set "PIPELINE_CONFIG_ROOT=%PIPELINE_ROOT%\config"
set "PIPELINE_CONFIG_PATH=%PIPELINE_CONFIG_ROOT%\MediaPipeline_config.psd1"
if not exist "%PIPELINE_CONFIG_PATH%" set "PIPELINE_CONFIG_PATH=%PIPELINE_CONFIG_ROOT%\MediaPipeline_config_chatgpt.psd1"

if /i "%~1"=="/?" goto :show_help
if /i "%~1"=="-h" goto :show_help
if /i "%~1"=="--help" goto :show_help
if /i "%~1"=="setup" (
    call "%SCRIPT_ROOT%setup.bat"
    exit /b !ERRORLEVEL!
)
if /i "%~1"=="validate" (
    call "%SCRIPT_ROOT%setup.bat" validate
    exit /b !ERRORLEVEL!
)

if not exist "%PIPELINE_ENTRYPOINT_ROOT%\MediaPipeline.ps1" (
    echo ERROR: MediaPipeline.ps1 was not found in:
    echo   %PIPELINE_ENTRYPOINT_ROOT%
    pause
    exit /b 1
)

if not exist "%PIPELINE_CONFIG_PATH%" (
    echo ERROR: No config file was found in the pipeline config folder.
    echo Checked:
    echo   %PIPELINE_CONFIG_ROOT%\MediaPipeline_config.psd1
    echo   %PIPELINE_CONFIG_ROOT%\MediaPipeline_config_chatgpt.psd1 (legacy)
    echo.
    echo Run ops\scripts\dev\setup.bat first.
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
    echo Launching pipeline with PowerShell 7: !PWSH_PATH!
    "!PWSH_PATH!" -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ENTRYPOINT_ROOT%\MediaPipeline.ps1" -ConfigPath "%PIPELINE_CONFIG_PATH%"
) else (
    echo ERROR: PowerShell 7 was not found.
    echo Expected bundled runtime under "%PIPELINE_ROOT%\runtime\PowerShell-7.6.0-win-x64" or pwsh.exe on PATH.
    pause
    exit /b 1
)

set "EXIT_CODE=!ERRORLEVEL!"
echo.
echo MediaPipeline exited with code !EXIT_CODE!.
pause
exit /b !EXIT_CODE!

:show_help
echo MediaPipelineRemuxEncodeAIO run launcher 1.0
echo.
echo Usage:
echo   ops\scripts\dev\run.bat
echo   ops\scripts\dev\run.bat validate
echo   ops\scripts\dev\run.bat setup
echo.
echo Commands:
echo   no args   Run the pipeline
echo   validate  Run setup validation only
echo   setup     Open the setup wizard
echo.
pause
exit /b 0
