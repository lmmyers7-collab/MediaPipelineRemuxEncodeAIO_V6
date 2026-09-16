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

function Invoke-UnifiedDiscoveryArtifactValidationCheck {
    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineDiscoveryArtifact_' + [guid]::NewGuid().ToString('N'))
    try {
        $script:LocalBase = $tempRoot
        $script:SourceMovies = Join-Path $tempRoot 'Movies'
        $script:SourceTV = Join-Path $tempRoot 'TV'
        $script:Outsource = Join-Path $tempRoot 'Out'
        $scanDir = Join-Path $tempRoot 'State\Progress\QueueScans\scan-1'
        New-Item -ItemType Directory -Path $script:SourceMovies,$script:SourceTV,$scanDir -Force | Out-Null
        $sourcePath = Join-Path $script:SourceMovies 'Movie.mkv'
        Set-Content -LiteralPath $sourcePath -Value 'media' -Encoding UTF8
        $sourceInfo = Get-Item -LiteralPath $sourcePath
        $candidate = [ordered]@{
            source_path = $sourceInfo.FullName
            root_path = $script:SourceMovies
            source_key = 'SourceMovies'
            media_kind = 'movie'
            name = $sourceInfo.Name
            directory_name = $sourceInfo.DirectoryName
            size_bytes = [long]$sourceInfo.Length
            last_write_utc = $sourceInfo.LastWriteTimeUtc.ToString('o')
            extension = $sourceInfo.Extension
            priority_reasons = @()
            priority_order_ticks = 0
        }
        $candidatePath = Join-Path $scanDir 'source_candidates.jsonl'
        $candidateLine = ($candidate | ConvertTo-Json -Compress -Depth 5) + "`n"
        [System.IO.File]::WriteAllText($candidatePath, $candidateLine, [System.Text.UTF8Encoding]::new($false))
        $candidateHash = (Get-FileHash -LiteralPath $candidatePath -Algorithm SHA256).Hash.ToLowerInvariant()
        $manifestPath = Join-Path $scanDir 'source_manifest.json'
        [ordered]@{
            schema_version = 'queue_discovery_manifest.v1'
            status = 'complete'
            candidates_path = $candidatePath
            candidates_sha256 = $candidateHash
            candidate_count = 1
        } | ConvertTo-Json | Set-Content -LiteralPath $manifestPath -Encoding UTF8

        function Get-MediaPipelineLibraryProfiles { return @() }
        function Get-QueuedEntries {
            param([array]$Files, [string]$RootPath, [switch]$IsTV, [hashtable]$LibraryProfileMetadata, [hashtable]$PriorityManifest)
            return @($Files | ForEach-Object { [pscustomobject]@{ File = $_; IsTV = [bool]$IsTV } })
        }
        function New-MediaQueuePhasePlan {
            param([array]$MovieEntries, [array]$TVEntries)
            return [pscustomobject]@{ MovieCount = @($MovieEntries).Count; TVCount = @($TVEntries).Count }
        }

        $plan = Get-MediaQueueDiscoveryPlanFromArtifact -ManifestPath $manifestPath
        Assert-True ($null -ne $plan) 'Valid unified discovery artifact should be accepted.'
        Assert-Equal ([int]$plan.MovieCount) 1 'Accepted discovery artifact should preserve movie membership.'
        Assert-Equal ([string]$script:LastQueueDiscoveryArtifactDecision) 'accepted' 'Accepted artifact should record its decision.'

        Add-Content -LiteralPath $candidatePath -Value '{}'
        $rejected = Get-MediaQueueDiscoveryPlanFromArtifact -ManifestPath $manifestPath
        Assert-True ($null -eq $rejected) 'Checksum-altered discovery artifact should fall back.'
        Assert-Equal ([string]$script:LastQueueDiscoveryArtifactDecision) 'legacy_fallback' 'Rejected artifact should record fallback.'
    } finally {
        Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue
    }
}

Invoke-SourceScanTimeoutPreservesLastGoodCacheCheck
Invoke-UnifiedDiscoveryArtifactValidationCheck

Write-Host 'Library index cache checks passed.'
