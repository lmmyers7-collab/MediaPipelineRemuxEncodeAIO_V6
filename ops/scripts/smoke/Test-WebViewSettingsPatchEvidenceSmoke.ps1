param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewSettingsPatchSmokePython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot
    )

    $candidates = @(
        (Join-Path $ProjectRoot 'apps\desktop\runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'ops\pipeline\runtime\Python\python.exe')
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

    throw 'No Python runtime was found. Expected apps\desktop\runtime\Python\python.exe, ops\pipeline\runtime\Python\python.exe, or python on PATH.'
}

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$python = Resolve-WebViewSettingsPatchSmokePython -ProjectRoot $projectRoot
$appRoot = Join-Path $projectRoot 'apps\desktop'
$srcRoot = Join-Path $projectRoot 'src'

Write-Host 'WebView settings save evidence smoke'
Write-Host 'Boundary: starts a temporary local API against a generated temporary config.'
Write-Host 'Boundary: exercises backend-owned Save review dialog, denied Save Settings, confirmed Save Settings, reload, and command-history evidence.'
Write-Host 'Boundary: does not use the current saved config and does not process media, launch pipeline commands, publish, rename, mutate queue state, or modify source/output/scratch media.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $oldPythonPath = $env:PYTHONPATH
    $env:PYTHONDONTWRITEBYTECODE = '1'
    if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
        $env:PYTHONPATH = $srcRoot
    }
    else {
        $env:PYTHONPATH = "$srcRoot;$oldPythonPath"
    }
    & $python -m mediapipeline.desktop.webview_settings_patch_smoke --app-root $appRoot
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}
