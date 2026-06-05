[CmdletBinding()]
param(
    # Port the local API will listen on.  Fixed so the browser URL is predictable.
    # Change this only if 8765 is already in use on your machine.
    [int]$Port = 8765,

    # Open a specific browser by executable name (e.g. 'msedge', 'chrome', 'firefox').
    # Leave empty to use the system default browser.
    [string]$Browser = '',

    # Development escape hatch only. The normal browser launcher keeps API token
    # checks enabled; the backend injects the per-run token into the local page.
    [switch]$NoTokenDevMode,

    # Skip the health-poll and open the browser immediately after launching the API.
    # Useful if the poll keeps timing out in a slow environment; the page will just
    # refresh until the API is ready.
    [switch]$NoWait,

    # Seconds to wait for the API to become healthy before giving up.
    [int]$TimeoutSeconds = 30
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

# ---------------------------------------------------------------------------
# Resolve paths
# ---------------------------------------------------------------------------
$launcherRoot = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$desktopRoot = [System.IO.Path]::GetFullPath((Join-Path $launcherRoot '..'))
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $desktopRoot '..\..'))

# ---------------------------------------------------------------------------
# Resolve Python  (mirrors resolution order used by other launchers)
# ---------------------------------------------------------------------------
function Resolve-PythonCandidates {
    param([string]$DesktopRoot, [string]$ProjectRoot)

    $candidates = @(
        (Join-Path $DesktopRoot  'Runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'ops\pipeline\runtime\Python\python.exe'),
        'python'
    )
    foreach ($candidate in $candidates) {
        if ($candidate -eq 'python' -or (Test-Path -LiteralPath $candidate -PathType Leaf)) { $candidate }
    }

    $commands = @(Get-Command python -All -ErrorAction SilentlyContinue | Where-Object { $_.Source })
    $preferred = @($commands | Where-Object { $_.Source -notmatch '\\WindowsApps\\' }) +
        @($commands | Where-Object { $_.Source -match '\\WindowsApps\\' })
    $preferred | Select-Object -ExpandProperty Source -Unique
}

$pythonCandidates = @(Resolve-PythonCandidates -DesktopRoot $desktopRoot -ProjectRoot $projectRoot)
if (-not $pythonCandidates) {
    Write-Error ('Python runtime not found.  Expected apps\desktop\runtime\Python\python.exe ' +
                 'or ops\pipeline\runtime\Python\python.exe, or python on PATH.')
    exit 1
}

# ---------------------------------------------------------------------------
# Verify the local_api_main module is importable
# ---------------------------------------------------------------------------
$oldPythonPath = $env:PYTHONPATH
$srcRoot = Join-Path $projectRoot 'src'
if ([string]::IsNullOrWhiteSpace($oldPythonPath)) {
    $env:PYTHONPATH = $srcRoot
} else {
    $env:PYTHONPATH = "$srcRoot;$oldPythonPath"
}

Push-Location $desktopRoot
try {
    $python = ''
    $lastImportError = ''
    foreach ($candidate in $pythonCandidates) {
        $check = & $candidate -c 'import mediapipeline.desktop.local_api_main' 2>&1
        if ($LASTEXITCODE -eq 0) {
            $python = [string]$candidate
            break
        }
        $lastImportError = "$candidate`: $check"
    }
    if (-not $python) {
        Write-Error "mediapipeline.desktop.local_api_main could not be imported by any Python candidate: $lastImportError"
        exit 1
    }
} finally {
    Pop-Location
}

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------
$apiUrl = "http://127.0.0.1:$Port"
Write-Host ''
Write-Host 'MediaPipelineRemuxEncodeAIO - API + Browser launcher' -ForegroundColor Cyan
Write-Host "Python  : $python"
Write-Host "API URL : $apiUrl"
if ($NoTokenDevMode) {
    Write-Host "Token auth: DISABLED by explicit -NoTokenDevMode" -ForegroundColor Red
    Write-Host "Warning  : dev-only bypass; do not use for normal local operation or packages." -ForegroundColor Red
} else {
    Write-Host "Token auth: enabled (browser receives a per-run bootstrap token)"
}
Write-Host ''

# ---------------------------------------------------------------------------
# Start the API in a detached console window so it keeps running after this
# script exits.  Normal browser mode keeps API token checks enabled; the public
# local HTML bootstrap provides the page with the per-run token for API calls.
# ---------------------------------------------------------------------------
$apiArgs = @(
    '-m', 'mediapipeline.desktop.local_api_main',
    '--app-root', $desktopRoot,
    '--port',     $Port
)
if ($NoTokenDevMode) {
    $apiArgs += '--no-token'
}

Write-Host 'Starting local API in a new console window...' -ForegroundColor Yellow
$previousNoTokenDevEnv = [Environment]::GetEnvironmentVariable('MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV', 'Process')
if ($NoTokenDevMode) {
    [Environment]::SetEnvironmentVariable('MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV', '1', 'Process')
}
Start-Process -FilePath $python `
              -ArgumentList $apiArgs `
              -WorkingDirectory $desktopRoot `
              -WindowStyle Normal
if ($NoTokenDevMode) {
    [Environment]::SetEnvironmentVariable('MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV', $previousNoTokenDevEnv, 'Process')
}
$env:PYTHONPATH = $oldPythonPath

# ---------------------------------------------------------------------------
# Health poll — wait until the API is accepting connections
# ---------------------------------------------------------------------------
$healthUrl = "$apiUrl/api/health"
$ready     = $false

if ($NoWait) {
    Write-Host '-NoWait: skipping health poll, opening browser immediately.' -ForegroundColor DarkYellow
    $ready = $true
} else {
    Write-Host "Waiting for API to become healthy ($healthUrl)..." -ForegroundColor Yellow
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $null = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2 -ErrorAction Stop
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 400
        }
    }
}

if (-not $ready) {
    Write-Warning ("API did not respond on $healthUrl within ${TimeoutSeconds}s.  " +
                   'The API window may show an error.  Opening browser anyway — ' +
                   'refresh the page once the API is up.')
}

# ---------------------------------------------------------------------------
# Open browser
# ---------------------------------------------------------------------------
if ($Browser) {
    Write-Host "Opening $apiUrl in '$Browser'..." -ForegroundColor Green
    Start-Process -FilePath $Browser -ArgumentList $apiUrl
} else {
    Write-Host "Opening $apiUrl in default browser..." -ForegroundColor Green
    Start-Process $apiUrl
}

Write-Host ''
Write-Host 'The API console window will keep running until you close it.' -ForegroundColor DarkCyan
Write-Host 'To stop the API: close its console window, or press Ctrl-C inside it.' -ForegroundColor DarkCyan
Write-Host ''
