[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Failure-state identity checks require PowerShell 7. Install pwsh or use the bundled runtime."
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

$script:LogMessages = @()
$script:SourceIdentityV2Algorithm = 'identity-v2-test'

function Write-Log {
    param([string] $Message, [string] $Level = 'INFO')
    $script:LogMessages += [pscustomobject]@{ Level = $Level; Message = $Message }
}

function Remove-PriorityMarkersFromName {
    param([string] $Name)
    return $Name
}

function Get-MediaDuration {
    param([string] $Path)
    return 0.0
}

function Get-SourceVideoCodec {
    param([string] $Path)
    return ''
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\source_identity.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\failures\failure_state.ps1')

function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}

function Assert-Null {
    param($Value, [string] $Message)
    if ($null -ne $Value) { throw $Message }
}

function Assert-NotNull {
    param($Value, [string] $Message)
    if ($null -eq $Value) { throw $Message }
}

function Invoke-WithFailureStateFixture {
    param([scriptblock] $Body)

    $tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('MediaPipelineFailureStateIdentityTest_' + [guid]::NewGuid().ToString('N'))
    try {
        New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null
        $script:LocalFailureMarkers = Join-Path $tempRoot 'Markers'
        $script:LocalFailureReports = Join-Path $tempRoot 'Reports'
        $script:LocalFailureArtifacts = Join-Path $tempRoot 'Artifacts'
        foreach ($path in @($script:LocalFailureMarkers, $script:LocalFailureReports, $script:LocalFailureArtifacts)) {
            New-Item -ItemType Directory -Path $path -Force | Out-Null
        }
        $script:FailureMarkerIndex = $null
        & $Body $tempRoot
    } finally {
        $script:FailureMarkerIndex = $null
        if (Test-Path -LiteralPath $tempRoot -PathType Container) {
            Remove-Item -LiteralPath $tempRoot -Recurse -Force
        }
    }
}

function Write-LegacyFailureMarker {
    param(
        [System.IO.FileInfo] $SourceFile,
        [switch] $OmitSourceIdentity
    )

    $sourceIdentity = Get-SourceIdentityKey $SourceFile
    $payload = [ordered]@{
        schema_version = 'source_failure.v1'
        classification = 'operator_required'
        reason = 'legacy marker'
        stage = 'probe'
        source_full_path = $SourceFile.FullName
        source_path = $SourceFile.FullName
        source_size = $SourceFile.Length
        source_mtime_utc = $SourceFile.LastWriteTimeUtc.ToString('o')
    }
    if (-not $OmitSourceIdentity) {
        $payload['source_identity'] = $sourceIdentity
    }
    $markerPath = Join-Path $script:LocalFailureMarkers "$sourceIdentity.json"
    $payload | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $markerPath -Encoding UTF8
    Invalidate-FailureMarkerIndex
    return $markerPath
}

Invoke-WithFailureStateFixture {
    param([string] $TempRoot)

    $sourcePath = Join-Path $TempRoot 'movie.mkv'
    Set-Content -LiteralPath $sourcePath -Value 'AAAA' -Encoding ASCII
    $oldItem = Get-Item -LiteralPath $sourcePath
    $oldItem.LastWriteTimeUtc = [datetime]'2026-06-12T01:00:00Z'
    $oldItem = Get-Item -LiteralPath $sourcePath

    Write-LegacyFailureMarker -SourceFile $oldItem | Out-Null
    Assert-NotNull (Get-SourceFailureState -SourceFile $oldItem) 'Legacy marker should match the unchanged current source through source_identity.'

    Set-Content -LiteralPath $sourcePath -Value 'BBBB' -Encoding ASCII
    $newItem = Get-Item -LiteralPath $sourcePath
    $newItem.LastWriteTimeUtc = [datetime]'2026-06-12T02:00:00Z'
    $newItem = Get-Item -LiteralPath $sourcePath

    Assert-True ($newItem.Length -eq $oldItem.Length) 'Regression fixture should replace the source with the same byte length.'
    Assert-Null (Get-SourceFailureState -SourceFile $newItem) 'Legacy same-path/same-size marker without source_identity_v2 must not match a replaced source.'
}

Invoke-WithFailureStateFixture {
    param([string] $TempRoot)

    $sourcePath = Join-Path $TempRoot 'metadata-only.mkv'
    Set-Content -LiteralPath $sourcePath -Value 'CCCC' -Encoding ASCII
    $item = Get-Item -LiteralPath $sourcePath
    $item.LastWriteTimeUtc = [datetime]'2026-06-12T03:00:00Z'
    $item = Get-Item -LiteralPath $sourcePath

    Write-LegacyFailureMarker -SourceFile $item -OmitSourceIdentity | Out-Null
    Assert-NotNull (Get-SourceFailureState -SourceFile $item) 'Legacy marker without source_identity should match only exact path, size, and mtime proof.'

    $item.LastWriteTimeUtc = [datetime]'2026-06-12T03:05:00Z'
    $changedItem = Get-Item -LiteralPath $sourcePath
    Assert-Null (Get-SourceFailureState -SourceFile $changedItem) 'Legacy marker without source_identity must not match after mtime proof changes.'
}

Write-Host 'Failure-state identity checks passed.'
