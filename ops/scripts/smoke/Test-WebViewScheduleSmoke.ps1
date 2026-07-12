param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewScheduleSmokePython {
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
$python = Resolve-WebViewScheduleSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView schedule smoke'
Write-Host 'Boundary: evaluates WebView Schedule assets in Node with mocked DOM state.'
Write-Host 'Boundary: verifies Schedule Coverage Review, selected day detail, table status legend, Schedule Editor preview/save routing, and app-state-write result copy.'
Write-Host 'Boundary: does not start pipeline commands, override schedule gates, mutate queue state, touch media files, or write app state from frontend code.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    & $python -m unittest tests.webview.test_webview_schedule_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    Pop-Location
}
