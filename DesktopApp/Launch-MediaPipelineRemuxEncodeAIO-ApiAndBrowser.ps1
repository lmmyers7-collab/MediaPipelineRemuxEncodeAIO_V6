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
$scriptRoot  = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$desktopRoot = [System.IO.Path]::GetFullPath($scriptRoot)
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $desktopRoot '..'))

# ---------------------------------------------------------------------------
# Resolve Python  (mirrors resolution order used by other launchers)
# ---------------------------------------------------------------------------
function Resolve-Python {
    param([string]$DesktopRoot, [string]$ProjectRoot)

    foreach ($candidate in @(
        (Join-Path $DesktopRoot  'Runtime\Python\python.exe'),
        (Join-Path $ProjectRoot 'Pipeline\Runtime\Python\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }

    $cmd = Get-Command python -All -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -and $_.Source -notmatch '\\WindowsApps\\' } |
        Select-Object -First 1
    if ($cmd -and $cmd.Source) { return [string]$cmd.Source }

    return ''
}

$python = Resolve-Python -DesktopRoot $desktopRoot -ProjectRoot $projectRoot
if (-not $python) {
    Write-Error ('Python runtime not found.  Expected DesktopApp\Runtime\Python\python.exe ' +
                 'or Pipeline\Runtime\Python\python.exe, or python on PATH.')
    exit 1
}

# ---------------------------------------------------------------------------
# Verify the local_api_main module is importable
# ---------------------------------------------------------------------------
Push-Location $desktopRoot
try {
    $check = & $python -c 'import mediapipeline_desktop_app.local_api_main' 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "mediapipeline_desktop_app.local_api_main could not be imported: $check"
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
Write-Host 'MediaPipelineRemuxEncodeAIO V6 - API + Browser launcher' -ForegroundColor Cyan
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
    '-m', 'mediapipeline_desktop_app.local_api_main',
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
