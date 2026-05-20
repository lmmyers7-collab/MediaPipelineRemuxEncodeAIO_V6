param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserSettingsLaunchSmokePython {
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
$python = Resolve-WebViewBrowserSettingsLaunchSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser settings/launch smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives real backend-served WebView Settings and Launch controls.'
Write-Host 'Boundary: validates staged settings patch handoff, Settings-to-Launch intent status, and backend Preview/Save result visibility.'
Write-Host 'Boundary: validates Launch Active Media Policy Boundary separates saved launch-active policy from staged subtitle/audio/pending-publish candidates.'
Write-Host 'Boundary: validates selectable Launch Risk Handoff proof-chain detail for saved-settings risk rows.'
Write-Host 'Boundary: verifies Preview Patch is called, cancelled Save Patch remains visible, and Save Patch is not posted by the browser smoke.'
Write-Host 'Boundary: does not save settings, process media, launch pipeline commands, publish, rename files, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest DesktopApp.tests.test_webview_browser_settings_launch_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}

