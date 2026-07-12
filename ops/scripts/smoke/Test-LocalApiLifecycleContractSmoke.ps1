param()

$ErrorActionPreference = 'Stop'

function Resolve-LocalApiLifecycleContractSmokePython {
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
$python = Resolve-LocalApiLifecycleContractSmokePython -ProjectRoot $projectRoot

Write-Host 'Local API lifecycle contract smoke'
Write-Host 'Boundary: starts temporary token-protected local API instances against generated temporary state.'
Write-Host 'Boundary: validates /api/backend/close-readiness safe and continuous schedule-stop watcher blocked payloads.'
Write-Host 'Boundary: validates /api/backend/shutdown token enforcement, safe info result, and watcher-blocked failure result.'
Write-Host 'Boundary: does not open a browser, process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host 'Boundary: direct backend shutdown POST is exercised only against temporary test backends.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.python.desktop.test_local_api_lifecycle_contract_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
