param()

$ErrorActionPreference = 'Stop'

function Resolve-WebViewRowDetailSmokePython {
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
$python = Resolve-WebViewRowDetailSmokePython -ProjectRoot $projectRoot

Write-Host 'WebView row detail smoke'
Write-Host 'Boundary: starts a temporary local API against generated temporary state.'
Write-Host 'Boundary: evaluates backend-served WebView JavaScript with mocked DOM selected-row state.'
Write-Host 'Boundary: validates Queue, Completed, and Pending Publish row details plus diagnostics handoff text.'
Write-Host 'Boundary: does not process media, launch pipeline commands, publish, rename, save settings, mutate queue state, or modify source/output/scratch media.'
Write-Host "Python: $python"

Push-Location -LiteralPath $projectRoot
$previousPythonPath = $env:PYTHONPATH
try {
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $srcPath = Join-Path $projectRoot 'src'
    if ([string]::IsNullOrWhiteSpace($previousPythonPath)) {
        $env:PYTHONPATH = $srcPath
    } else {
        $env:PYTHONPATH = $srcPath + [IO.Path]::PathSeparator + $previousPythonPath
    }
    & $python -m unittest tests.webview.test_webview_row_detail_smoke -q
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
finally {
    $env:PYTHONPATH = $previousPythonPath
    Pop-Location
}
