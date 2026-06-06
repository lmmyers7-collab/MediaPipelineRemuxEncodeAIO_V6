param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserLifecycleSmokePython {
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
$python = Resolve-WebViewBrowserLifecycleSmokePython -ProjectRoot $projectRoot
$srcRoot = Join-Path $projectRoot 'src'

Write-Host 'WebView browser backend lifecycle smoke'
Write-Host 'Boundary: starts temporary local API instances against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Diagnostics backend lifecycle controls.'
Write-Host 'Boundary: validates close-readiness blocked shutdown rejection while the continuous schedule-stop watcher is armed.'
Write-Host 'Boundary: validates terminal stop-requested watcher evidence stays visible without blocking safe close.'
Write-Host 'Boundary: validates safe close-readiness posts exactly through backend-owned /api/backend/shutdown after confirmation.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
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
    & $python -m unittest tests.webview.test_webview_browser_lifecycle_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $oldPythonPath
    Pop-Location
}



