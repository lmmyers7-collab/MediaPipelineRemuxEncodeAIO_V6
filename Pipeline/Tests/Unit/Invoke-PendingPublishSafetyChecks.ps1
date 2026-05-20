[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) {
        throw "Pending publish safety checks require PowerShell 7. Install pwsh or use the bundled runtime."
    }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$testsRoot = Split-Path -Parent $PSCommandPath
$pipelineRoot = Split-Path -Parent (Split-Path -Parent $testsRoot)

. (Join-Path $pipelineRoot 'Modules\PendingManifestStore.ps1')
. (Join-Path $pipelineRoot 'Modules\PendingTransactions.ps1')

$script:PipelineVersion = 'v5-test'
$script:MinPipelineVersion = 'v5-test'
$script:SourceIdentityV2Algorithm = 'test-v2'

function Write-Log {
    param(
        [string] $Message,
        [string] $Level = 'INFO'
    )
}

function Assert-True {
    param(
        [bool] $Condition,
        [string] $Message
    )
    if (-not $Condition) { throw $Message }
}

function Assert-Equal {
    param(
        $Actual,
        $Expected,
        [string] $Message
    )
    if ($Actual -ne $Expected) {
        throw "$Message Expected '$Expected', got '$Actual'."
    }
}

function Assert-MatchText {
    param(
        [string] $Text,
        [string] $Pattern,
        [string] $Message
    )
    if ($Text -notmatch $Pattern) { throw $Message }
}

function Copy-SrtAtomic {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $DestinationPath
    )
    $dir = Split-Path -Parent $DestinationPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    Copy-Item -LiteralPath $SourcePath -Destination $DestinationPath -Force
    return [pscustomobject]@{ Ok = $true; Reason = ''; CueCount = 1 }
}

function Test-SrtFileUsable {
    param([string] $Path)
    $ok = -not [string]::IsNullOrWhiteSpace($Path) -and (Test-Path -LiteralPath $Path -PathType Leaf)
    return [pscustomobject]@{ Ok = [bool]$ok; Reason = if ($ok) { 'ok' } else { 'missing' }; CueCount = if ($ok) { 1 } else { 0 } }
}

function New-StandardFailureRecord {
    param(
        [string] $Reason,
        [string] $ErrorCode
    )
    return [pscustomobject]@{ Reason = $Reason; ErrorCode = $ErrorCode }
}

function Compare-PipelineVersion {
    param(
        [string] $Left,
        [string] $Right
    )
    return $false
}

function Get-SidecarPath {
    param([string] $OutputPath)
    return "$OutputPath.pipeline.json"
}

function New-TestPendingManifest {
    param(
        [Parameter(Mandatory)] [string] $LocalFile,
        [Parameter(Mandatory)] [string] $ServerOut,
        [string] $State = 'parked'
    )
    return [ordered]@{
        schema_version                 = 'pending_push_manifest.v1'
        parked_at                      = '2026-05-19T00:00:00Z'
        pipeline_version               = $script:PipelineVersion
        publish_transaction_id         = 'tx-test'
        manifest_state                 = $State
        local_file                     = $LocalFile
        original_local_file            = $LocalFile
        parked_file                    = $LocalFile
        server_out                     = $ServerOut
        route                          = 'encode'
        source_identity                = 'source-v1'
        source_identity_v2             = 'source-v2'
        source_identity_v2_algorithm   = $script:SourceIdentityV2Algorithm
        source_path                    = 'C:\Source\Movie.mkv'
        source_size                    = 5
        source_mtime_utc               = '2026-05-19T00:00:00Z'
        output_size                    = 5
        publish_mode                   = 'retry'
        sidecar_files                  = @()
        tx3g_srt_tracks                = @()
        tx3g_srt_failures              = @()
        bdpgs_srt_failures             = @()
        tx3g_embedded_srt_tracks       = @()
        bdpgs_embedded_srt_tracks      = @()
        tx3g_srt_conversion_enabled    = $true
        tx3g_external_srt_sidecars_enabled = $true
        drop_tx3g_after_conversion     = $false
        bdpgs_srt_conversion_enabled   = $false
        drop_bdpgs_after_conversion    = $false
    }
}

function Invoke-WithTempRoot {
    param([Parameter(Mandatory)] [scriptblock] $Body)
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ("mediapipeline-pending-safety-" + [guid]::NewGuid().ToString("N"))
    try {
        [System.IO.Directory]::CreateDirectory($root) | Out-Null
        & $Body ([System.IO.DirectoryInfo]::new($root))
    } finally {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$pendingPushPath = Join-Path $pipelineRoot 'Modules\PendingPush.ps1'
$pendingPushText = Get-Content -LiteralPath $pendingPushPath -Raw
foreach ($requiredFunction in @(
    'function Get-PendingDrainSummaryPath',
    'function Write-PendingDrainSummary',
    'function Add-PendingDrainSummaryCount',
    'function New-PendingDrainSummaryItem',
    'function Complete-PendingDrainSummary',
    'function Invoke-RetryPendingPushes'
)) {
    Assert-True ($pendingPushText.Contains($requiredFunction)) "PendingPush.ps1 is missing $requiredFunction."
}
Assert-True (
    $pendingPushText.IndexOf('function New-PendingDrainSummaryItem', [System.StringComparison]::Ordinal) -lt
    $pendingPushText.IndexOf('function Invoke-RetryPendingPushes', [System.StringComparison]::Ordinal)
) 'Pending drain summary item helper must be defined before Invoke-RetryPendingPushes.'
Assert-True ($pendingPushText.Contains('Complete-PendingDrainSummary -Summary $summary -Items $summaryItems')) 'Pending drain completion must pass the mutable summary-items list directly.'
Assert-True (-not $pendingPushText.Contains('Complete-PendingDrainSummary -Summary $summary -Items @($summaryItems)')) 'Pending drain completion must not wrap the mutable summary-items list as a new array.'

Invoke-WithTempRoot {
    param($Root)
    $script:LocalPendingPush = Join-Path $Root.FullName 'State\PendingServerPush'
    $scratch = Join-Path $Root.FullName 'Scratch'
    $serverRoot = Join-Path $Root.FullName 'Server'
    [System.IO.Directory]::CreateDirectory($scratch) | Out-Null
    [System.IO.Directory]::CreateDirectory($serverRoot) | Out-Null
    $localOut = Join-Path $scratch 'Movie.mkv'
    $localSrt = Join-Path $scratch 'Movie.eng.srt'
    $serverOut = Join-Path $serverRoot 'Movie.mkv'
    [System.IO.File]::WriteAllText($localOut, 'media')
    [System.IO.File]::WriteAllText($localSrt, "1`n00:00:00,000 --> 00:00:01,000`nCaption`n")

    $sidecar = [pscustomobject]@{
        LocalPath       = $localSrt
        DestinationPath = "$serverOut.eng.srt"
        Kind            = 'tx3g_srt'
        PreserveExisting = $false
        Record          = [pscustomobject]@{ language = 'eng'; source_stream_index = 3 }
    }
    $transaction = Invoke-PendingParkTransaction `
        -LocalOut $localOut `
        -ServerOut $serverOut `
        -Route 'encode' `
        -SourceIdentity 'source-v1' `
        -SourceIdentityV2 'source-v2' `
        -SourcePath 'C:\Source\Movie.mkv' `
        -SourceSize 5 `
        -SourceMTimeUtc '2026-05-19T00:00:00Z' `
        -PublishTransactionId 'tx-test' `
        -PublishMode 'deferred' `
        -SidecarFiles @($sidecar) `
        -MediaType 'movie'

    Assert-True ([bool]$transaction.Ok) 'Pending park transaction failed.'
    Assert-True (-not (Test-Path -LiteralPath $localOut)) 'Original local media was not moved into PendingServerPush.'
    Assert-True (Test-Path -LiteralPath ([string]$transaction.LocalFile) -PathType Leaf) 'Parked media file is missing.'
    Assert-True (Test-Path -LiteralPath ([string]$transaction.ManifestPath) -PathType Leaf) 'Pending manifest was not written.'
    $manifest = Read-PendingManifestFile -Path ([string]$transaction.ManifestPath)
    Assert-Equal ([string]$manifest.manifest_state) 'parked' 'Pending manifest did not reach parked state.'
    Assert-Equal ([string]$manifest.publish_mode) 'deferred' 'Pending manifest did not preserve deferred publish mode.'
    Assert-Equal ([string]$manifest.media_type) 'movie' 'Pending manifest did not preserve media type.'
    Assert-Equal @($manifest.sidecar_files).Count 1 'Pending manifest did not preserve sidecar entry.'
    $parkedSidecar = [string]$manifest.sidecar_files[0].local_file
    Assert-True (Test-Path -LiteralPath $parkedSidecar -PathType Leaf) 'Parked sidecar file is missing.'
}

Invoke-WithTempRoot {
    param($Root)
    $manifestPath = Join-Path $Root.FullName 'missing-payload.manifest.json'
    $missingLocal = Join-Path $Root.FullName 'State\PendingServerPush\missing.mkv'
    $serverOut = Join-Path $Root.FullName 'Server\missing.mkv'
    $manifest = New-TestPendingManifest -LocalFile $missingLocal -ServerOut $serverOut
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)
    $updated = Read-PendingManifestFile -Path $manifestPath

    Assert-Equal ([string]$result.Status) 'missing_payload' 'Missing parked media did not stay queued as missing_payload.'
    Assert-Equal ([string]$updated.manifest_state) 'missing_payload' 'Missing payload state was not persisted back to manifest.'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Missing-payload manifest was incorrectly deleted.'
}

Invoke-WithTempRoot {
    param($Root)
    $serverOut = Join-Path $Root.FullName 'Server\already.mkv'
    $serverDir = Split-Path -Parent $serverOut
    [System.IO.Directory]::CreateDirectory($serverDir) | Out-Null
    [System.IO.File]::WriteAllText($serverOut, 'media')
    [System.IO.File]::WriteAllText(
        (Get-SidecarPath $serverOut),
        (@{
            schema_version = 'pipeline_sidecar.v1'
            pipeline_version = $script:PipelineVersion
            publish_transaction_id = 'tx-test'
        } | ConvertTo-Json -Depth 5),
        [System.Text.UTF8Encoding]::new($false)
    )
    $weakManifest = [pscustomobject]@{
        output_size = 5
        publish_transaction_id = 'tx-test'
        sidecar_files = @()
        tx3g_srt_tracks = @()
    }

    $accepted = Test-PendingPublishedServerCopy -Manifest $weakManifest -LocalPath '' -ServerPath $serverOut

    Assert-True (-not [bool]$accepted) 'Already-published validation accepted a server copy with transaction/size but no source proof.'
}

Invoke-WithTempRoot {
    param($Root)
    $existingSidecar = Join-Path $Root.FullName 'existing.srt'
    $backupSidecar = Join-Path $Root.FullName '.existing.srt.backup'
    [System.IO.File]::WriteAllText($existingSidecar, 'new')
    [System.IO.File]::WriteAllText($backupSidecar, 'old')
    $newSidecar = Join-Path $Root.FullName 'new.srt'
    [System.IO.File]::WriteAllText($newSidecar, 'new')

    Undo-PendingPublishedSidecarFiles -PublishedSidecars @(
        [ordered]@{ path = $existingSidecar; status = 'written'; existed_before = $true; backup_path = $backupSidecar },
        [ordered]@{ path = $newSidecar; status = 'written'; existed_before = $false; backup_path = '' }
    ) -Context 'test: '

    Assert-Equal ([System.IO.File]::ReadAllText($existingSidecar)) 'old' 'Existing sidecar backup was not restored.'
    Assert-True (-not (Test-Path -LiteralPath $backupSidecar)) 'Sidecar backup was not removed after rollback.'
    Assert-True (-not (Test-Path -LiteralPath $newSidecar)) 'Newly written sidecar was not removed after rollback.'
}

$publishCompletionText = Get-Content -LiteralPath (Join-Path $pipelineRoot 'Modules\PublishCompletion.ps1') -Raw
Assert-MatchText $publishCompletionText 'PublishMode = \$\(if \(\$copyFailureIsOutputSpace\) \{ ''output-space-deferred'' \}' 'Publish completion no longer marks output-space copy failures as output-space-deferred before parking.'
Assert-MatchText $publishCompletionText 'New-PipelinePublishResult[\s\S]+-PublishState ''pending_publish''[\s\S]+-PublishMode ''output-space-deferred''[\s\S]+-ParkedForOutputSpace:\$true' 'Low-space deferred publish no longer returns pending_publish success after safe parking.'
Assert-MatchText $publishCompletionText 'Clear-SourceFailureState \$SourceFile[\s\S]+output-space deferred publish' 'Low-space deferred publish no longer clears source failure state only after successful parking.'

Write-Host 'OK: pending publish safety checks passed.'
