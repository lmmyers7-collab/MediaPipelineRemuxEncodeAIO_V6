param()

$ErrorActionPreference = 'Stop'

function Resolve-LocalApiSampleValidationSmokePython {
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
$python = Resolve-LocalApiSampleValidationSmokePython -ProjectRoot $projectRoot

Write-Host 'Local API sample validation contract smoke'
Write-Host 'Boundary: starts temporary token-protected local API instances against generated temporary state.'
Write-Host 'Boundary: executes only /api/sample-validation/preview and /api/sample-validation/append validation-evidence routes plus read-only sample-validation and diagnostics reads.'
Write-Host 'Boundary: validates token enforcement, strict JSON record validation, current-backend-evidence preview, command history, diagnostics tail allowlist, and validation-log readback.'
Write-Host 'Boundary: writes sample_validation_log.jsonl only inside temporary test state.'
Write-Host 'Boundary: does not open a browser, process media, launch pipeline commands, run audit, run CSV rerun, publish, rename files, save settings, mutate queue state, drain pending publish, or modify source/output/scratch media.'
Write-Host 'Boundary: does not accept outputs, clear failures, rewrite completed manifests, rewrite sidecars, probe FFmpeg/ffprobe, or scan arbitrary media shares.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.python.desktop.test_sample_validation_api -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}



