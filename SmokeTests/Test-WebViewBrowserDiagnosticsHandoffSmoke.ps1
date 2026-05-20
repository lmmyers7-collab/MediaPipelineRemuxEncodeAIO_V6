param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserDiagnosticsHandoffSmokePython {
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
$python = Resolve-WebViewBrowserDiagnosticsHandoffSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser diagnostics handoff smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView diagnostics handoff controls.'
Write-Host 'Boundary: clicks actual Queue, Completed, and Pending Publish table rows before exercising read-only diagnostics bridge, tail, and allowlisted open controls.'
Write-Host 'Boundary: verifies selected-row investigation signals, current-filter visibility, clear-filter buttons, and text/status/investigation guardrails before launch, rerun, cleanup, or publish decisions.'
Write-Host 'Boundary: verifies Diagnostics Go To Owner Row navigation for Queue, Completed, and Pending Publish without backend commands.'
Write-Host 'Boundary: renders Diagnostics State Artifact Summary, selects backend read-order/artifact rows, then validates bounded backend tail output and diagnostics.open command-result feedback.'
Write-Host 'Boundary: renders Diagnostics ActiveJobs detail rows, including active and malformed records, plus stale runtime-progress guidance.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest DesktopApp.tests.test_webview_browser_diagnostics_handoff_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

