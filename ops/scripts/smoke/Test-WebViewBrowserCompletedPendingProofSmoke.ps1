param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewBrowserCompletedPendingProofSmokePython {
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
$python = Resolve-WebViewBrowserCompletedPendingProofSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView browser Completed/Pending proof smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: launches installed Chrome/Edge headless and drives the real backend-served Completed/Pending proof board.'
Write-Host 'Boundary: verifies the Completed Real-Media Output Proof ladder, including route/size/media, saved-policy reconciliation, Sample Validation handoff, and missing-output blocker detail.'
Write-Host 'Boundary: verifies exact completed-output to pending-destination overlap and missing-output-without-proof detail.'
Write-Host 'Boundary: verifies selected Pending row Completed Manifest correlation remains read-only.'
Write-Host 'Boundary: verifies same-leaf proof wording remains a duplicate-title hint, not publish proof.'
Write-Host 'Boundary: does not append validation records, does not process media, launch pipeline commands, drain pending publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: skips cleanly when Chrome/Edge is not installed.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.webview.test_webview_browser_completed_pending_proof_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}



