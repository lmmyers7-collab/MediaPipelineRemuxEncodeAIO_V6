@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "SCRIPT_ROOT=%~dp0"
for %%I in ("%SCRIPT_ROOT%..\..") do set "PROJECT_ROOT=%%~fI"
set "PIPELINE_ROOT=%PROJECT_ROOT%\Pipeline"

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

if not exist "%PIPELINE_ROOT%\MediaPipeline_chatgpt.ps1" (
    echo ERROR: MediaPipeline_chatgpt.ps1 was not found in:
    echo   %PIPELINE_ROOT%
    pause
    exit /b 1
)

if not exist "%PIPELINE_ROOT%\MediaPipeline_config_chatgpt.psd1" if not exist "%PIPELINE_ROOT%\MediaPipeline_config.psd1" (
    echo ERROR: No config file was found next to the pipeline.
    echo Checked:
    echo   %PIPELINE_ROOT%\MediaPipeline_config_chatgpt.psd1
    echo   %PIPELINE_ROOT%\MediaPipeline_config.psd1
    echo.
    echo Run scripts\dev\setup.bat first.
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
    echo Launching pipeline with PowerShell 7: !PWSH_PATH!
    "!PWSH_PATH!" -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ROOT%\MediaPipeline_chatgpt.ps1"
) else (
    echo PowerShell 7 was not resolved by the launcher.
    echo Trying Windows PowerShell so the script can self-relaunch if a bundled runtime exists.
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PIPELINE_ROOT%\MediaPipeline_chatgpt.ps1"
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
echo   scripts\dev\run.bat
echo   scripts\dev\run.bat validate
echo   scripts\dev\run.bat setup
echo.
echo Commands:
echo   no args   Run the pipeline
echo   validate  Run setup validation only
echo   setup     Open the setup wizard
echo.
pause
exit /b 0
