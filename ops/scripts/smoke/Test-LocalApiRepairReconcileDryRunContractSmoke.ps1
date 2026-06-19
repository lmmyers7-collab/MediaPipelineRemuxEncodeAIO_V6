param()

$ErrorActionPreference = 'Stop'

function Resolve-LocalApiRepairReconcileDryRunSmokePython {
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
$python = Resolve-LocalApiRepairReconcileDryRunSmokePython -ProjectRoot $projectRoot

Write-Host 'Local API Repair/Reconcile dry-run contract smoke'
Write-Host 'Boundary: starts only temporary token-protected local API fixtures through Python tests.'
Write-Host 'Boundary: validates completed and pending-publish backend dry-run POST routes with effect=none.'
Write-Host 'Boundary: verifies strict request fields, required dry-run schema fields, command-journal suppression, and no file mutation for fixture manifests, sidecars, payloads, outputs, and sources.'
Write-Host 'Boundary: does not add WebView controls, write manifests or sidecars, move/delete parked payloads, drain pending publish, publish outputs, rerun media, or touch source/output/scratch media.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m pytest `
        tests\python\desktop\test_repair_reconcile_dry_run.py `
        tests\python\desktop\test_api_command_contracts.py `
        tests\python\desktop\test_api_contract_payload.py `
        tests\webview\test_webview_frontend_mutation_boundary.py `
        -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
