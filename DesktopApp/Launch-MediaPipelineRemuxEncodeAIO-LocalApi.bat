@echo off
setlocal
cd /d "%~dp0"

set "BUNDLED_PYTHON=%~dp0Runtime\Python\python.exe"
set "PIPELINE_PYTHON=%~dp0..\Pipeline\Runtime\Python\python.exe"
set "PYTHON_PATH="
set "APP_IMPORT=import mediapipeline_desktop_app.local_api_main"

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%BUNDLED_PYTHON%" -m mediapipeline_desktop_app.local_api_main --app-root "%~dp0." %*
        exit /b %ERRORLEVEL%
    )
)

if exist "%PIPELINE_PYTHON%" (
    "%PIPELINE_PYTHON%" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%PIPELINE_PYTHON%" -m mediapipeline_desktop_app.local_api_main --app-root "%~dp0." %*
        exit /b %ERRORLEVEL%
    )
)

for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$cmd=Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } | Select-Object -First 1; if($cmd){ $cmd.Source }"`) do (
    set "PYTHON_PATH=%%I"
)

if defined PYTHON_PATH (
    "%PYTHON_PATH%" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%PYTHON_PATH%" -m mediapipeline_desktop_app.local_api_main --app-root "%~dp0." %*
        exit /b %ERRORLEVEL%
    )
)

echo A usable Python runtime was not found for the local API.
echo.
echo Preferred:
echo   DesktopApp\Runtime\Python\python.exe
echo.
echo Local API requirements:
echo   the selected runtime must import:
echo   mediapipeline_desktop_app.local_api_main
pause
exit /b 1
