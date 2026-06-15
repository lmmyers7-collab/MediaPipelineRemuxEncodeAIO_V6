function Resolve-WebViewBrowserSmokePython {
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
        Write-Warning "Using python from PATH for WebView browser smoke because bundled Python runtimes were not found: $($pathPython.Source)"
        return $pathPython.Source
    }

    throw 'No Python runtime was found. Expected apps\desktop\runtime\Python\python.exe, ops\pipeline\runtime\Python\python.exe, or python on PATH.'
}

function Invoke-WebViewBrowserSmokeUnittest {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProjectRoot,

        [Parameter(Mandatory = $true)]
        [string]$Module,

        [switch]$AllowSkippedTests
    )

    $python = Resolve-WebViewBrowserSmokePython -ProjectRoot $ProjectRoot
    Write-Host "Python: $python"

    Push-Location -LiteralPath $ProjectRoot
    $previousPythonPath = $env:PYTHONPATH
    $previousDontWriteBytecode = $env:PYTHONDONTWRITEBYTECODE
    try {
        $env:PYTHONDONTWRITEBYTECODE = '1'
        $srcPath = Join-Path $ProjectRoot 'src'
        $env:PYTHONPATH = if ([string]::IsNullOrWhiteSpace($previousPythonPath)) { $srcPath } else { "$srcPath;$previousPythonPath" }
        $output = & $python -m unittest $Module -q 2>&1 | ForEach-Object { [string]$_ }
        $exitCode = $LASTEXITCODE
        $output | ForEach-Object { Write-Host $_ }
        if ($exitCode -ne 0) {
            exit $exitCode
        }

        $skipOutput = @($output | Where-Object {
            $_ -match '\bskipped=\d+\b' -or
            $_ -match '^OK \(skipped=\d+\)'
        })
        if (-not $AllowSkippedTests -and $skipOutput.Count -gt 0) {
            Write-Error ("Browser smoke reported skipped tests. Install Node.js and Chrome/Edge, or rerun with -AllowSkippedTests for local diagnostics. Output: {0}" -f ($skipOutput -join ' | '))
            exit 1
        }
    }
    finally {
        $env:PYTHONPATH = $previousPythonPath
        $env:PYTHONDONTWRITEBYTECODE = $previousDontWriteBytecode
        Pop-Location
    }
}
