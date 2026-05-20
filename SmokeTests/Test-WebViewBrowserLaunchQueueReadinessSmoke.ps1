param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserLaunchQueueReadinessSmokePython {
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
$python = Resolve-WebViewBrowserLaunchQueueReadinessSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser Launch/Queue readiness smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state, a generated launch command journal, and a temporary sample-validation record.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and renders real backend-served WebView Launch, Queue, and Schedule readiness panels.'
Write-Host 'Boundary: verifies Launch preflight, Queue launch decision, Schedule guidance, close-readiness, and launch command-review evidence align.'
Write-Host 'Boundary: verifies Launch real-media sample proof handoff mirrors Home worksheet evidence without starting work.'
Write-Host 'Boundary: verifies Launch Sample Validation record evidence mirrors Home record/reconciliation evidence without appending records.'
Write-Host 'Boundary: verifies Pilot category coverage is visible at Launch without turning category evidence into acceptance state.'
Write-Host 'Boundary: verifies saved policy vs Queue route evidence is visible at Launch without changing Start scope or media policy.'
Write-Host 'Boundary: verifies Launch sample execution checklist mirrors Home sample-validation execution guidance without starting work.'
Write-Host 'Boundary: verifies no POST routes are sent while reading launch readiness evidence.'
Write-Host 'Boundary: does not process media, launch pipeline commands, run audit, run CSV rerun, drain pending publish, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

