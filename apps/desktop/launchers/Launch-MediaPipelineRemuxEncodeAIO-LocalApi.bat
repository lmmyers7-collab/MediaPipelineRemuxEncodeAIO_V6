@echo off
setlocal
for %%I in ("%~dp0..") do set "DESKTOP_ROOT=%%~fI"
for %%I in ("%DESKTOP_ROOT%\..\..") do set "PROJECT_ROOT=%%~fI"
cd /d "%DESKTOP_ROOT%"

set "BUNDLED_PYTHON=%DESKTOP_ROOT%\runtime\Python\python.exe"
set "PIPELINE_PYTHON=%PROJECT_ROOT%\ops\pipeline\runtime\Python\python.exe"
set "PYTHON_PATH="
set "APP_IMPORT=import mediapipeline.desktop.local_api_main"
set "SOURCE_PYTHONPATH=%PROJECT_ROOT%\src"
if defined PYTHONPATH (
    set "PYTHONPATH=%SOURCE_PYTHONPATH%;%PYTHONPATH%"
) else (
    set "PYTHONPATH=%SOURCE_PYTHONPATH%"
)

if exist "%BUNDLED_PYTHON%" (
    "%BUNDLED_PYTHON%" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%BUNDLED_PYTHON%" -m mediapipeline.desktop.local_api_main --app-root "%DESKTOP_ROOT%" %*
        exit /b %ERRORLEVEL%
    )
)

if exist "%PIPELINE_PYTHON%" (
    "%PIPELINE_PYTHON%" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%PIPELINE_PYTHON%" -m mediapipeline.desktop.local_api_main --app-root "%DESKTOP_ROOT%" %*
        exit /b %ERRORLEVEL%
    )
)

python -c "%APP_IMPORT%" >nul 2>&1
if not errorlevel 1 (
    python -m mediapipeline.desktop.local_api_main --app-root "%DESKTOP_ROOT%" %*
    exit /b %ERRORLEVEL%
)

for /f "usebackq delims=" %%I in (`powershell.exe -NoProfile -Command "$cmds=Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source }; $preferred=@($cmds | Where-Object { $_.Source -notmatch '\\WindowsApps\\' }) + @($cmds | Where-Object { $_.Source -match '\\WindowsApps\\' }); $preferred | Select-Object -ExpandProperty Source -Unique"`) do (
    "%%I" -c "%APP_IMPORT%" >nul 2>&1
    if not errorlevel 1 (
        "%%I" -m mediapipeline.desktop.local_api_main --app-root "%DESKTOP_ROOT%" %*
        exit /b %ERRORLEVEL%
    )
)

echo A usable Python runtime was not found for the local API.
echo.
echo Preferred:
echo   apps\desktop\runtime\Python\python.exe
echo.
echo Local API requirements:
echo   the selected runtime must import:
echo   mediapipeline.desktop.local_api_main
pause
exit /b 1
