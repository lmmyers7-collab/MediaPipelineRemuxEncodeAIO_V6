param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserMaintenanceChangeLedgerSmokePython {
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
$python = Resolve-WebViewBrowserMaintenanceChangeLedgerSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser Maintenance change-ledger smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the backend-served WebView Maintenance tab.'
Write-Host 'Boundary: verifies ledger rows, selected detail, filters, empty state, hygiene copy, and read-only GET usage.'
Write-Host 'Boundary: verifies no media, queue, settings, pending-publish, rename, or other mutation POST is issued.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest DesktopApp.tests.test_webview_browser_maintenance_change_ledger_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
