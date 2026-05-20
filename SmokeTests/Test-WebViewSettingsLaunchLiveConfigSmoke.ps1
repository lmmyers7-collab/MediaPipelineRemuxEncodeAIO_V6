param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewLiveConfigSmokePython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $candidates = @(
        (Join-Path $ProjectRoot 'DesktopApp\Runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'Pipeline\Runtime\Python\python.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pathPython = Get-Command python -ErrorAction SilentlyContinue
    if ($pathPython) {
        return $pathPython.Source
    }

    throw 'No Python runtime was found. Expected DesktopApp\Runtime\Python\python.exe, Pipeline\Runtime\Python\python.exe, or python on PATH.'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$python = Resolve-WebViewLiveConfigSmokePython -ProjectRoot $projectRoot
$desktopAppRoot = Join-Path $projectRoot 'DesktopApp'

Write-Host 'WebView settings/launch live-config smoke'
Write-Host 'Boundary: starts a temporary local API using the current saved config.'
Write-Host 'Boundary: validates read-only Settings and Launch policy handoff visibility against live config data.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, or modify source/output/scratch media.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONDONTWRITEBYTECODE = '1'
    if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $env:PYTHONPATH = $desktopAppRoot
    }
    else {
        $env:PYTHONPATH = "$desktopAppRoot;$oldPythonPath"
    }
    & $python -m mediapipeline_desktop_app.webview_settings_live_smoke --app-root $desktopAppRoot
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}

