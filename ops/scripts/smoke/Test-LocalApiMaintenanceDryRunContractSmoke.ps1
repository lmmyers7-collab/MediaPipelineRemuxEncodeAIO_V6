param()

$ErrorActionPreference = 'Stop'

function Resolve-LocalApiMaintenanceDryRunSmokePython {
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
$python = Resolve-LocalApiMaintenanceDryRunSmokePython -ProjectRoot $projectRoot

Write-Host 'Local API Maintenance dry-run contract smoke'
Write-Host 'Boundary: starts a temporary token-protected local API against generated temporary state.'
Write-Host 'Boundary: executes only /api/maintenance/release-dry-run, /api/maintenance/completed-backfill-dry-run, and /api/maintenance/retention-dry-run backend dry-run POST routes.'
Write-Host 'Boundary: validates token enforcement, command history, release dry-run no-manifest/no-zip evidence, completed-manifest backfill dry-run no-manifest-write evidence, and retention dry-run no-delete/no-move evidence.'
Write-Host 'Boundary: command journal and RunLogs evidence are written only inside temporary test state.'
Write-Host 'Boundary: does not open a browser, process media, launch pipeline commands, run audit, run CSV rerun, publish, rename files, save settings, mutate queue state, drain pending publish, or modify source/output/scratch media.'
Write-Host 'Boundary: does not create a release package, write a release manifest, write a zip package, rewrite completed manifests, or delete/move/archive retention candidates.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.python.desktop.test_local_api_maintenance_dry_run_contract_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
