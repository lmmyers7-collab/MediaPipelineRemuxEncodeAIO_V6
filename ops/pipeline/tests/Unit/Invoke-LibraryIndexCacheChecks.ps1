[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Library index cache checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)
$repoRoot = Split-Path -Parent (Split-Path -Parent $pipelineRoot)
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Unable to resolve repository root from $PSCommandPath."
}

. (Join-Path $repoRoot 'ops\pipeline\engine\library\library_index.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:LogMessages += "$Level`:$Message"
}

function Invoke-SourceScanTimeoutPreservesLastGoodCacheCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineLibraryIndexCache_' + [guid]::NewGuid().ToString('N'))
    $previousMovieCache = $script:MovieScanCache
    $previousMovieStamp = $script:MovieScanCacheAt
    $previousScanInterval = $script:SourceScanIntervalSeconds
    $previousScanTimeout = $script:SourceScanTimeoutSeconds
    $previousLogMessages = $script:LogMessages
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $cachedPath = Join-Path $tempRoot 'Cached.mkv'
        Set-Content -LiteralPath $cachedPath -Value 'cached media' -Encoding UTF8
        $cachedFile = Get-Item -LiteralPath $cachedPath
        $script:MovieScanCache = @($cachedFile)
        $script:MovieScanCacheAt = (Get-Date).AddHours(-1)
        $script:SourceScanIntervalSeconds = 1
        $script:SourceScanTimeoutSeconds = 1
        $script:LogMessages = @()

        function Get-ChildItemWithRetry {
            param([string] $Path, [int] $MaxRetries = 2)
            $script:LastRecursivePathScanStatus = 'timeout'
            return @()
        }

        $files = @(Get-CachedSourceFiles -Kind movies -Path $tempRoot -ForceRefresh:$true)

        Assert-Equal $files.Count 1 'Timed-out source scan should preserve last-good movie cache.'
        Assert-Equal ([string]$files[0].FullName) ([string]$cachedFile.FullName) 'Timed-out source scan returned the wrong cached file.'
        Assert-Equal @($script:MovieScanCache).Count 1 'Timed-out source scan should not overwrite MovieScanCache with an empty list.'
        Assert-True (($script:LogMessages -join "`n") -match 'preserving last-good movies cache') 'Timed-out scan should log last-good cache preservation.'
    } finally {
        $script:MovieScanCache = $previousMovieCache
        $script:MovieScanCacheAt = $previousMovieStamp
        $script:SourceScanIntervalSeconds = $previousScanInterval
        $script:SourceScanTimeoutSeconds = $previousScanTimeout
        $script:LogMessages = $previousLogMessages
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-SourceScanTimeoutPreservesLastGoodCacheCheck

Write-Host 'Library index cache checks passed.'
