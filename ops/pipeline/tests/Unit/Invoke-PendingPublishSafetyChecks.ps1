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

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'AGENTS.md') -PathType Leaf)) {
    throw "Pending publish safety checks resolved an invalid repo root: $repoRoot"
}
if (-not (Test-Path -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine') -PathType Container)) {
    throw "Pending publish safety checks resolved a repo root without ops\pipeline\engine: $repoRoot"
}

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\path_helpers.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\paths\path_capability.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\paths\library_profiles.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_partial.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_result.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_manifest_store.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_transactions.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_push.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_publish_index.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion.ps1')

$script:ProductVersion = 'v5-test-product'
$script:PipelineVersion = 'v5-test'
$script:MinPipelineVersion = 'v5-test'
$script:SourceIdentityV2Algorithm = 'test-v2'
$script:DeferredPublish = $false
$script:StopRequested = $false
$script:StopFlag = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-stop-' + [guid]::NewGuid().ToString('N'))
$script:ProgressItemContexts = @()

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
        [string] $Stage = '',
        [string] $Operation = '',
        [string] $Category = '',
        [string] $Reason,
        [string] $ErrorCode,
        [string] $Tool = '',
        [bool] $Retryable = $false,
        [hashtable] $AdditionalProperties = @{}
    )
    $record = [ordered]@{
        Stage = $Stage
        Operation = $Operation
        Category = $Category
        Reason = $Reason
        ErrorCode = $ErrorCode
        Tool = $Tool
        Retryable = $Retryable
    }
    foreach ($key in @($AdditionalProperties.Keys)) {
        $record[$key] = $AdditionalProperties[$key]
    }
    return [pscustomobject]$record
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

function Set-ProgressStage {
    param(
        [string] $Stage,
        [string] $Status,
        [string] $Route,
        [string] $PushState,
        [string] $SidecarState,
        $Percent,
        [switch] $SaveNow
    )
}

function Set-ProgressItemContext {
    param(
        [string] $DisplayName,
        [string] $FilePath,
        [string] $MediaType,
        [string] $QueuePhase,
        [int] $QueueIndex,
        [int] $QueueTotal
    )
    $script:ProgressItemContexts += [pscustomobject]@{
        DisplayName = $DisplayName
        FilePath = $FilePath
        MediaType = $MediaType
        QueuePhase = $QueuePhase
        QueueIndex = $QueueIndex
        QueueTotal = $QueueTotal
    }
}

function Reset-ProgressItemContext {
}

function New-TestPendingManifest {
    param(
        [Parameter(Mandatory)] [string] $LocalFile,
        [Parameter(Mandatory)] [string] $ServerOut,
        [string] $State = 'parked',
        [string] $SourcePath = ''
    )
    if ([string]::IsNullOrWhiteSpace($SourcePath)) {
        $SourcePath = Join-Path $script:SourceMovies 'Movie.mkv'
    }
    return [ordered]@{
        schema_version                 = 'pending_push_manifest.v1'
        parked_at                      = '2026-05-19T00:00:00Z'
        product_version                = $script:ProductVersion
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
        source_path                    = $SourcePath
        source_size                    = 5
        source_mtime_utc               = '2026-05-19T00:00:00Z'
        output_size                    = 5
        publish_mode                   = 'retry'
        sidecar_files                  = @()
        tx3g_srt_tracks                = @()
        tx3g_srt_failures              = @()
        bdpgs_srt_failures             = @()
        vobsub_srt_failures            = @()
        tx3g_embedded_srt_tracks       = @()
        bdpgs_embedded_srt_tracks      = @()
        vobsub_embedded_srt_tracks     = @()
        tx3g_srt_conversion_enabled    = $true
        tx3g_external_srt_sidecars_enabled = $true
        drop_tx3g_after_conversion     = $false
        bdpgs_srt_conversion_enabled   = $false
        drop_bdpgs_after_conversion    = $false
        vobsub_srt_conversion_enabled  = $false
        drop_vobsub_after_conversion   = $false
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

function Set-TestPipelineRoots {
    param([Parameter(Mandatory)] [System.IO.DirectoryInfo] $Root)

    $script:LocalBase = Join-Path $Root.FullName 'State'
    $script:LocalPendingPush = Join-Path $script:LocalBase 'PendingServerPush'
    $script:LocalEncoded = Join-Path $script:LocalBase 'Encoded'
    $script:SourceMovies = Join-Path $Root.FullName 'Source\Movies'
    $script:SourceTV = Join-Path $Root.FullName 'Source\TV'
    $script:Outsource = Join-Path $Root.FullName 'Server'
    $script:LibraryProfiles = @(
        [pscustomobject]@{
            id = 'movies'
            name = 'Movies'
            enabled = $true
            designation = 'movie'
            source_path = $script:SourceMovies
            output_path = $script:Outsource
            promotion_enabled = $false
            promotion_destination = ''
        },
        [pscustomobject]@{
            id = 'tv'
            name = 'TV'
            enabled = $true
            designation = 'tv'
            source_path = $script:SourceTV
            output_path = $script:Outsource
            promotion_enabled = $false
            promotion_destination = ''
        }
    )
    foreach ($path in @($script:LocalBase, $script:LocalPendingPush, $script:LocalEncoded, $script:SourceMovies, $script:SourceTV, $script:Outsource)) {
        [System.IO.Directory]::CreateDirectory($path) | Out-Null
    }
}

$pendingPushPath = Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_push.ps1'
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
    Set-TestPipelineRoots -Root $Root
    $localOut = Join-Path $script:LocalEncoded 'Movie.mkv'
    $localSrt = Join-Path $script:LocalEncoded 'Movie.eng.srt'
    $serverOut = Join-Path $script:Outsource 'Movie.mkv'
    $sourcePath = Join-Path $script:SourceMovies 'Movie.mkv'
    [System.IO.File]::WriteAllText($localOut, 'media')
    [System.IO.File]::WriteAllText($localSrt, "1`n00:00:00,000 --> 00:00:01,000`nCaption`n")
    [System.IO.File]::WriteAllText($sourcePath, 'source')

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
        -SourcePath $sourcePath `
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
    Set-TestPipelineRoots -Root $Root
    $localOut = Join-Path $script:LocalEncoded 'WrapperSize.mkv'
    $serverOut = Join-Path $script:Outsource 'WrapperSize.mkv'
    $sourcePath = Join-Path $script:SourceMovies 'WrapperSize.mkv'
    [System.IO.File]::WriteAllText($localOut, 'media-size-proof')
    [System.IO.File]::WriteAllText($sourcePath, 'source')

    $parkResult = Invoke-ParkPendingPush `
        -LocalOut $localOut `
        -ServerOut $serverOut `
        -Route 'encode' `
        -SourceIdentity 'source-v1' `
        -SourceIdentityV2 'source-v2' `
        -SourcePath $sourcePath `
        -SourceSize 6 `
        -SourceMTimeUtc '2026-05-19T00:00:00Z' `
        -PublishTransactionId 'tx-size-proof' `
        -PublishMode 'deferred' `
        -MediaType 'movie'

    Assert-True ([bool]$parkResult.Ok) 'Invoke-ParkPendingPush should return the successful park transaction.'
    Assert-Equal ([long]$parkResult.OutputSize) 16L 'Park wrapper did not return the parked media size proof.'
    $manifest = Read-PendingManifestFile -Path ([string]$parkResult.ManifestPath)
    Assert-Equal ([long]$manifest.output_size) 16L 'Pending manifest output_size should match the wrapper transaction size proof.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $manifestPath = Join-Path $script:LocalPendingPush 'missing-payload.manifest.json'
    $missingLocal = Join-Path $script:LocalPendingPush 'missing.mkv'
    $serverOut = Join-Path $script:Outsource 'missing.mkv'
    $manifest = New-TestPendingManifest -LocalFile $missingLocal -ServerOut $serverOut
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)
    $updated = Read-PendingManifestFile -Path $manifestPath

    Assert-Equal ([string]$result.Status) 'missing_payload' 'Missing parked media did not fail closed as missing_payload.'
    Assert-Equal ([string]$updated.manifest_state) 'parked' 'Missing-payload drain must not rewrite an untrusted manifest.'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Missing-payload manifest was incorrectly deleted.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'legacy.mkv'
    $serverOut = Join-Path $script:Outsource 'legacy.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifestPath = Join-Path $script:LocalPendingPush 'legacy.mkv.manifest.json'
    [System.IO.File]::WriteAllText(
        $manifestPath,
        (@{
            manifest_state = 'parked'
            local_file = $payload
            server_out = $serverOut
            source_path = Join-Path $script:SourceMovies 'legacy.mkv'
            output_size = 5
        } | ConvertTo-Json -Depth 5),
        [System.Text.UTF8Encoding]::new($false)
    )

    $drained = Invoke-RetryPendingPushes -Force
    $summary = Get-Content -LiteralPath (Get-PendingDrainSummaryPath) -Raw | ConvertFrom-Json

    Assert-Equal $drained 0 'Legacy manifest drain should not report a recovered publish.'
    Assert-Equal ([string]$summary.status_counts.invalid_manifest) '1' 'Legacy manifest should be recorded as an invalid_manifest drain error.'
    Assert-True (Test-Path -LiteralPath $payload -PathType Leaf) 'Legacy manifest retry moved or deleted the parked payload.'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Legacy manifest retry deleted the manifest.'
    Assert-True (-not (Test-Path -LiteralPath $serverOut -PathType Leaf)) 'Legacy manifest retry published output.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $script:ProgressItemContexts = @()
    $payload = Join-Path $script:LocalPendingPush '20260605_164936__aa67fe5c5e3949409914023f__Clean Final.mkv'
    $serverOut = Join-Path $script:Outsource 'Clean Final.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut
    $manifest['schema_version'] = 'legacy_manifest.v0'
    $manifestPath = Join-Path $script:LocalPendingPush 'display-name.manifest.json'
    [System.IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 10),
        [System.Text.UTF8Encoding]::new($false)
    )

    $drained = Invoke-RetryPendingPushes -Force
    $context = @($script:ProgressItemContexts)[0]

    Assert-Equal $drained 0 'Display-name manifest should not drain when schema validation fails.'
    Assert-Equal ([string]$context.DisplayName) 'Clean Final.mkv' 'Pending drain progress should show the final destination leaf, not the parked payload leaf.'
    Assert-Equal ([string]$context.FilePath) $payload 'Pending drain progress should keep the local parked payload as the diagnostic file path.'
    Assert-Equal ([string]$context.QueuePhase) 'pending_push' 'Pending drain progress context lost pending_push queue phase.'
    Assert-True (Test-Path -LiteralPath $payload -PathType Leaf) 'Display-name progress test mutated the parked payload.'
    Assert-True (-not (Test-Path -LiteralPath $serverOut -PathType Leaf)) 'Display-name progress test published output.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'sidecar-backup-retry.mkv'
    $serverOut = Join-Path $script:Outsource 'sidecar-backup-retry.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut -State 'retry_sidecar_backup_failed'
    $manifestPath = Join-Path $script:LocalPendingPush 'sidecar-backup-retry.manifest.json'
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True ([bool]$trust.Ok) "retry_sidecar_backup_failed manifest should be drainable: $($trust.Reason)"
    Assert-Equal ([string]$trust.ReasonCode) 'OK' 'Backup-failed retry state should not be rejected as DRAIN_STATE_UNSUPPORTED.'
    Assert-True (Test-Path -LiteralPath $payload -PathType Leaf) 'Trust check should not mutate the parked payload.'
    Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'Trust check should not delete the manifest.'
    Assert-True (-not (Test-Path -LiteralPath $serverOut -PathType Leaf)) 'Trust check should not publish output.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $Root.FullName 'ForgedOutsidePending.mkv'
    $serverOut = Join-Path $script:Outsource 'ForgedOutsidePending.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut
    $manifestPath = Join-Path $script:LocalPendingPush 'forged-local.manifest.json'
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True (-not [bool]$trust.Ok) 'Forged local_file outside PendingServerPush was trusted for drain.'
    Assert-Equal ([string]$trust.Status) 'invalid_manifest' 'Forged local_file should be an invalid_manifest drain blocker.'
    Assert-MatchText ([string]$trust.Reason) 'local_file' 'Forged local_file trust failure should name local_file.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'forged-server.mkv'
    $serverOut = Join-Path $Root.FullName 'Source\Movies\forged-server.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut
    $manifestPath = Join-Path $script:LocalPendingPush 'forged-server.manifest.json'
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True (-not [bool]$trust.Ok) 'Forged server_out under a source root was trusted for drain.'
    Assert-Equal ([string]$trust.Status) 'invalid_manifest' 'Forged server_out should be an invalid_manifest drain blocker.'
    Assert-MatchText ([string]$trust.Reason) 'server_out' 'Forged server_out trust failure should name server_out.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'missing-proof.mkv'
    $serverOut = Join-Path $script:Outsource 'missing-proof.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut
    $manifest['publish_transaction_id'] = ''
    $manifestPath = Join-Path $script:LocalPendingPush 'missing-proof.manifest.json'
    [System.IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 10),
        [System.Text.UTF8Encoding]::new($false)
    )

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True (-not [bool]$trust.Ok) 'Manifest with blank transaction proof was trusted for drain.'
    Assert-Equal ([string]$trust.Status) 'invalid_manifest' 'Blank transaction proof should be an invalid_manifest blocker.'
    Assert-MatchText ([string]$trust.Reason) 'publish_transaction_id' 'Blank transaction proof failure should name publish_transaction_id.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'bad-array.mkv'
    $serverOut = Join-Path $script:Outsource 'bad-array.mkv'
    [System.IO.File]::WriteAllText($payload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut $serverOut
    $manifest['sidecar_files'] = 'not-an-array'
    $manifestPath = Join-Path $script:LocalPendingPush 'bad-array.manifest.json'
    [System.IO.File]::WriteAllText(
        $manifestPath,
        ($manifest | ConvertTo-Json -Depth 10),
        [System.Text.UTF8Encoding]::new($false)
    )

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True (-not [bool]$trust.Ok) 'Manifest with string sidecar_files was trusted for drain.'
    Assert-Equal ([string]$trust.Status) 'invalid_manifest' 'String sidecar_files should be an invalid_manifest blocker.'
    Assert-Equal ([string]$trust.ReasonCode) 'REQUIRED_ARRAY_INVALID' 'String sidecar_files should fail required-array validation.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $sourceOriginal = Join-Path $script:SourceMovies 'UnsafeOriginal.mkv'
    $pendingLocal = Join-Path $script:LocalPendingPush 'UnsafeOriginal.mkv'
    [System.IO.File]::WriteAllText($sourceOriginal, 'source-media')
    $manifest = New-TestPendingManifest -LocalFile $pendingLocal -ServerOut (Join-Path $script:Outsource 'UnsafeOriginal.mkv') -State 'pending_move'
    $manifest['original_local_file'] = $sourceOriginal
    $manifest['parked_file'] = $pendingLocal
    $manifestPath = Join-Path $script:LocalPendingPush 'unsafe-original.manifest.json'
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $repaired = Repair-PendingManifestState -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-Equal ([string]$repaired.manifest_state) 'pending_move' 'Unsafe original_local_file should not be recovered.'
    Assert-True (Test-Path -LiteralPath $sourceOriginal -PathType Leaf) 'Unsafe original_local_file under source root was moved.'
    Assert-True (-not (Test-Path -LiteralPath $pendingLocal -PathType Leaf)) 'Unsafe original_local_file created a parked payload.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'sidecar-forged.mkv'
    $sidecarOutsidePending = Join-Path $Root.FullName 'sidecar-forged.eng.srt'
    $sidecarDestination = Join-Path $script:Outsource 'sidecar-forged.eng.srt'
    [System.IO.File]::WriteAllText($payload, 'media')
    [System.IO.File]::WriteAllText($sidecarOutsidePending, "1`n00:00:00,000 --> 00:00:01,000`nCaption`n")
    $manifest = New-TestPendingManifest -LocalFile $payload -ServerOut (Join-Path $script:Outsource 'sidecar-forged.mkv')
    $manifest['sidecar_files'] = @(
        [pscustomobject]@{
            local_file = $sidecarOutsidePending
            server_out = $sidecarDestination
            preserve_existing = $false
            tx3g_record = [pscustomobject]@{ stream_index = 1; language = 'eng' }
        }
    )

    $result = Publish-PendingSidecarFiles -Manifest ([pscustomobject]$manifest) -PublishTransactionId 'tx-forged-sidecar'

    Assert-Equal @($result.Failures).Count 1 'Sidecar outside PendingServerPush should be rejected before publish.'
    Assert-True (-not (Test-Path -LiteralPath $sidecarDestination -PathType Leaf)) 'Sidecar outside PendingServerPush was copied to the final output root.'
    Assert-True (Test-Path -LiteralPath $sidecarOutsidePending -PathType Leaf) 'Sidecar outside PendingServerPush was mutated.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $payload = Join-Path $script:LocalPendingPush 'mixed-safe.mkv'
    $serverOut = Join-Path $script:Outsource 'nested\mixed-safe.mkv'
    [System.IO.Directory]::CreateDirectory((Split-Path $serverOut -Parent)) | Out-Null
    [System.IO.File]::WriteAllText($payload, 'media')
    $mixedPayload = $payload.Replace('\', '/')
    $mixedServer = $serverOut.Replace('\', '/')
    $manifest = New-TestPendingManifest -LocalFile $mixedPayload -ServerOut $mixedServer
    $manifestPath = Join-Path $script:LocalPendingPush 'mixed-safe.manifest.json'
    Write-PendingManifestFile -Path $manifestPath -Manifest $manifest | Out-Null

    $trust = Test-PendingManifestTrustedForDrain -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest (Read-PendingManifestFile -Path $manifestPath)

    Assert-True ([bool]$trust.Ok) "Mixed slash safe pending/output paths were not trusted: $($trust.Reason)"
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $safeLocal = Join-Path $script:LocalPendingPush 'cleanup-safe.mkv'
    $unsafeLocal = Join-Path $Root.FullName 'cleanup-outside.mkv'
    $unsafeSidecar = Join-Path $Root.FullName 'cleanup-outside.srt'
    [System.IO.File]::WriteAllText($safeLocal, 'media')
    [System.IO.File]::WriteAllText($unsafeLocal, 'outside')
    [System.IO.File]::WriteAllText($unsafeSidecar, 'outside-sidecar')
    $manifestPath = Join-Path $script:LocalPendingPush 'cleanup-safe.manifest.json'
    $manifest = [pscustomobject]@{
        sidecar_files = @([pscustomobject]@{ local_file = $unsafeSidecar })
    }

    Remove-PendingDrainLocalArtifacts -Manifest $manifest -LocalPath $unsafeLocal -ManifestPath $manifestPath

    Assert-True (Test-Path -LiteralPath $unsafeLocal -PathType Leaf) 'Pending cleanup removed a local media path outside PendingServerPush.'
    Assert-True (Test-Path -LiteralPath $unsafeSidecar -PathType Leaf) 'Pending cleanup removed a sidecar path outside PendingServerPush.'
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

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $serverOut = Join-Path $script:Outsource 'sidecar-backup-failure.mkv'
    $serverDir = Split-Path -Parent $serverOut
    [System.IO.Directory]::CreateDirectory($serverDir) | Out-Null
    $sidecarPath = Get-SidecarPath $serverOut
    [System.IO.File]::WriteAllText($sidecarPath, 'existing-proof')

    function Copy-Item {
        throw 'simulated sidecar backup failure'
    }
    try {
        $backup = Backup-PublishSidecarForReveal -OutputPath $serverOut -PublishTransactionId 'tx-backup-fail' -Context 'test: '
    } finally {
        Remove-Item Function:\Copy-Item -ErrorAction SilentlyContinue
    }

    Assert-True ([bool]$backup.HadExistingSidecar) 'Backup result should record that an existing sidecar was present.'
    Assert-True (-not [bool]$backup.BackupOk) 'Backup result should fail closed when the existing sidecar cannot be copied.'
    Assert-True (-not (Test-PublishSidecarBackupReadyForReveal -Backup $backup)) 'Backup readiness should reject reveal after existing-sidecar backup failure.'
    Restore-PublishSidecarAfterRevealFailure -OutputPath $serverOut -Backup $backup -Context 'test: '
    Assert-Equal ([System.IO.File]::ReadAllText($sidecarPath)) 'existing-proof' 'Restore after backup failure must not delete the existing final sidecar proof.'
}

Invoke-WithTempRoot {
    param($Root)
    Set-TestPipelineRoots -Root $Root
    $serverDir = $script:Outsource
    $localSidecar = Join-Path $script:LocalPendingPush 'parked.srt'
    $serverSidecar = Join-Path $serverDir 'movie.eng.srt'
    [System.IO.File]::WriteAllText($localSidecar, "1`n00:00:00,000 --> 00:00:01,000`nNew`n")
    [System.IO.File]::WriteAllText($serverSidecar, 'old-srt')
    $mediaPayload = Join-Path $script:LocalPendingPush 'movie.mkv'
    [System.IO.File]::WriteAllText($mediaPayload, 'media')
    $manifest = New-TestPendingManifest -LocalFile $mediaPayload -ServerOut (Join-Path $script:Outsource 'movie.mkv')
    $manifest['sidecar_files'] = @(
        [pscustomobject]@{
            local_file = $localSidecar
            server_out = $serverSidecar
            preserve_existing = $false
            tx3g_record = [pscustomobject]@{ stream_index = 2; language = 'eng'; title = 'English' }
        }
    )

    $originalCopySrtAtomic = (Get-Item -Path function:Copy-SrtAtomic).ScriptBlock
    Set-Item -Path function:Copy-SrtAtomic -Value {
        param(
            [Parameter(Mandatory)] [string] $SourcePath,
            [Parameter(Mandatory)] [string] $DestinationPath
        )
        [System.IO.File]::WriteAllText($DestinationPath, 'failed-new-srt')
        return [pscustomobject]@{ Ok = $false; Reason = 'simulated publish failure after destination write'; CueCount = 0 }
    }
    try {
        $result = Publish-PendingSidecarFiles -Manifest $manifest -PublishTransactionId 'tx-rollback'
    } finally {
        Set-Item -Path function:Copy-SrtAtomic -Value $originalCopySrtAtomic
    }

    Assert-Equal @($result.Failures).Count 1 'Pending sidecar copy failure was not reported.'
    Assert-Equal ([System.IO.File]::ReadAllText($serverSidecar)) 'old-srt' 'Pending sidecar copy failure did not restore the previous SRT.'
    $leftoverBackups = @(Get-ChildItem -LiteralPath $serverDir -Force | Where-Object { $_.Name -like '*.mp-pending-sidecar-backup.*' })
    Assert-Equal $leftoverBackups.Count 0 'Pending sidecar copy failure left backup artifacts behind.'
}

$pendingSidecarTransactionsText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_sidecar_transactions.ps1') -Raw
Assert-MatchText $pendingSidecarTransactionsText 'function Restore-PendingSidecarBackupIntoPlace' 'Pending sidecar restore overwrite fallback helper is missing.'
Assert-MatchText $pendingSidecarTransactionsText '\[System\.IO\.File\]::Move\(\$BackupPath,\s*\$DestinationPath,\s*\$true\)' 'Pending sidecar restore fallback must use overwrite move.'
Assert-MatchText $pendingSidecarTransactionsText 'if \(-not \$copy\.Ok\)[\s\S]+Restore-PendingSidecarBackupIntoPlace' 'Pending sidecar copy failure must restore an existing destination from backup.'

$publishCompletionText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion.ps1') -Raw
$publishCompletionHelperText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_completion\context_builders.ps1') -Raw
Assert-MatchText $publishCompletionHelperText 'function New-PendingParkArguments' 'Publish completion pending-park argument builder is missing.'
Assert-MatchText $publishCompletionHelperText 'function Get-PublishCopyFailureClassification' 'Publish completion pure copy-failure classifier is missing.'
Assert-MatchText $publishCompletionHelperText 'PublishMode = \$PublishMode' 'Pending-park argument builder no longer preserves the supplied publish mode.'
Assert-MatchText $publishCompletionText 'function Get-PendingParkResultOutputSize' 'Publish completion should read output size from the successful park result.'
Assert-True (-not $publishCompletionText.Contains('$localSize = (Get-Item -LiteralPath $Paths.LocalOut')) 'Publish completion must not read LocalOut size after the park transaction moves it.'
Assert-MatchText $publishCompletionText 'Test-PublishSidecarBackupReadyForReveal[\s\S]+Existing final sidecar backup failed before final media reveal' 'Publish completion must fail closed when an existing final sidecar cannot be backed up.'
Assert-MatchText $publishCompletionText 'Get-PendingParkResultOutputSize -ParkResult \$parkResult' 'Pending publish result size should come from the park transaction proof.'
Assert-MatchText $publishCompletionText 'New-PendingParkArguments[\s\S]+-PublishMode \$\(if \(\$copyFailureIsOutputSpace\) \{ ''output-space-deferred'' \}' 'Publish completion no longer marks output-space copy failures as output-space-deferred before parking.'
Assert-MatchText $publishCompletionText 'New-PipelinePublishResult[\s\S]+-PublishState ''pending_publish''[\s\S]+-PublishMode ''output-space-deferred''[\s\S]+-ParkedForOutputSpace:\$true' 'Low-space deferred publish no longer returns pending_publish success after safe parking.'
Assert-MatchText $publishCompletionText 'Clear-SourceFailureState \$SourceFile[\s\S]+output-space deferred publish' 'Low-space deferred publish no longer clears source failure state only after successful parking.'

$pendingDrainText = Get-Content -LiteralPath (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_drain_transaction.ps1') -Raw
Assert-MatchText $pendingDrainText 'Test-PublishSidecarBackupReadyForReveal[\s\S]+retry_sidecar_backup_failed' 'Pending drain must fail closed when an existing final sidecar cannot be backed up.'

Write-Host 'OK: pending publish safety checks passed.'
