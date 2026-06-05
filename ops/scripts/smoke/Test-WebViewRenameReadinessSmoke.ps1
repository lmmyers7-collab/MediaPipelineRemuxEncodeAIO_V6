param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewRenameReadinessSmokePython {
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
$python = Resolve-WebViewRenameReadinessSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView rename readiness smoke'
Write-Host 'Boundary: evaluates WebView Rename assets in Node with mocked DOM state.'
Write-Host 'Boundary: verifies Apply Readiness and Pipeline Handoff for a ready single-row scope and a blocked duplicate-target scope.'
Write-Host 'Boundary: verifies large-preview render cap text without calling rename.apply.'
Write-Host 'Boundary: verifies duplicate-target blocking does not call rename.apply.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename files, save settings, mutate queue state, or touch source/output/scratch media.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.webview.test_webview_rename_readiness_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}



