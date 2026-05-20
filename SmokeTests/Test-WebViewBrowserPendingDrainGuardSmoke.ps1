param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserPendingDrainGuardSmokePython {
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
$python = Resolve-WebViewBrowserPendingDrainGuardSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser Pending Publish drain guard smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Pending Publish page.'
Write-Host 'Boundary: verifies active Pending Publish display filters are disclosed as local-only and do not narrow backend drain scope.'
Write-Host 'Boundary: injects a backend-shaped blocked recovery dry-run result and verifies Publish Button Guard refreshes immediately.'
Write-Host 'Boundary: verifies a blocked Publish Parked Outputs click records local frontend_guard evidence without posting /api/pipeline/start.'
Write-Host 'Boundary: does not process media, launch pipeline commands, drain pending publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest DesktopApp.tests.test_webview_browser_pending_drain_guard_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

