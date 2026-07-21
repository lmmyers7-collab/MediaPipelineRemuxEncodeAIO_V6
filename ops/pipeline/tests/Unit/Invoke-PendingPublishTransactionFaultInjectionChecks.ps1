[CmdletBinding()]
param()

if ($PSVersionTable.PSVersion.Major -lt 7) {
    $pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
    if (-not $pwsh) { $pwsh = (Get-Command pwsh -ErrorAction SilentlyContinue).Source }
    if (-not $pwsh) { throw 'Pending publish transaction fault checks require PowerShell 7.' }
    & $pwsh -NoProfile -ExecutionPolicy Bypass -File $PSCommandPath @args
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')

. (Join-Path $repoRoot 'ops\pipeline\engine\shared\path_helpers.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_manifest_store.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\publish_partial.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_transactions.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\sidecar.ps1')
. (Join-Path $repoRoot 'ops\pipeline\engine\publish\pending_push.ps1')

$script:PipelineVersion = 'fault-test-v1'
$script:ProductVersion = 'fault-test-product'
$script:MinPipelineVersion = 'fault-test-v1'
$script:SourceIdentityV2Algorithm = 'fault-test-v2'

function Write-Log { param([string] $Message, [string] $Level = 'INFO') }
function Compare-PipelineVersion { param([string] $Left, [string] $Right); return $false }
function Get-SidecarPath { param([string] $OutputPath); return "$OutputPath.pipeline.json" }
function Test-SrtFileUsable {
    param([string] $Path)
    $ok = Test-Path -LiteralPath $Path -PathType Leaf -ErrorAction SilentlyContinue
    return [pscustomobject]@{ Ok = [bool]$ok; Reason = if ($ok) { 'ok' } else { 'missing' }; CueCount = if ($ok) { 1 } else { 0 } }
}
function New-StandardFailureRecord {
    param(
        [string] $Stage = '', [string] $Operation = '', [string] $Category = '',
        [string] $Reason, [string] $ErrorCode, [string] $Tool = '',
        [bool] $Retryable = $false, [hashtable] $AdditionalProperties = @{}
    )
    $record = [ordered]@{ Reason = $Reason; ErrorCode = $ErrorCode; Stage = $Stage; Retryable = $Retryable }
    foreach ($key in @($AdditionalProperties.Keys)) { $record[$key] = $AdditionalProperties[$key] }
    return [pscustomobject]$record
}

$script:CopyMode = 'success'
$script:CopyFailureReason = ''
$script:SidecarMode = 'success'
$script:CompletionAppendMode = 'success'
function Copy-SrtAtomic {
    param([Parameter(Mandatory)] [string] $SourcePath, [Parameter(Mandatory)] [string] $DestinationPath)
    if ($script:SidecarMode -eq 'fail') {
        return [pscustomobject]@{ Ok = $false; Reason = 'simulated sidecar write failure'; CueCount = 0 }
    }
    $dir = Split-Path -Parent $DestinationPath
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    if ($script:SidecarMode -eq 'partial') {
        [System.IO.File]::WriteAllText($DestinationPath, 'partial-sidecar')
        return [pscustomobject]@{ Ok = $false; Reason = 'simulated partial sidecar write'; CueCount = 0 }
    }
    [System.IO.File]::Copy($SourcePath, $DestinationPath, $true)
    return [pscustomobject]@{ Ok = $true; Reason = ''; CueCount = 1 }
}
function Copy-FileRobocopy {
    param([string] $SourcePath, [string] $DestinationPath)
    $destinationDir = Split-Path -Parent $DestinationPath
    switch ($script:CopyMode) {
        'access_denied' { $script:CopyFailureReason = 'Access denied'; return $false }
        'disk_full' { $script:CopyFailureReason = 'There is not enough space on the disk'; return $false }
        'destination_disappeared' {
            if (Test-Path -LiteralPath $destinationDir -PathType Container) { Remove-Item -LiteralPath $destinationDir -Recurse -Force }
            $script:CopyFailureReason = 'Destination disappeared'; return $false
        }
        'partial' {
            [System.IO.Directory]::CreateDirectory($destinationDir) | Out-Null
            [System.IO.File]::WriteAllText($DestinationPath, 'part')
            $script:CopyFailureReason = 'Partial copy'; return $false
        }
        'checksum_mismatch' {
            [System.IO.Directory]::CreateDirectory($destinationDir) | Out-Null
            [System.IO.File]::WriteAllText($DestinationPath, 'wrong-media-bytes')
            return $true
        }
    }
    [System.IO.Directory]::CreateDirectory($destinationDir) | Out-Null
    [System.IO.File]::Copy($SourcePath, $DestinationPath, $true)
    return $true
}
function Get-PublishCopyFailureReason { return [string]$script:CopyFailureReason }
function Set-ProgressStage { param([string] $Stage, [string] $Status, [string] $Route, [string] $PushState, [string] $SidecarState, $Percent, [switch] $SaveNow) }
function Add-RoundFailureRecord {
    param(
        [string] $SourcePath, [string] $Stage, [string] $Reason,
        [string] $Classification, [string] $ErrorCode,
        [string] $ArtifactPath, [string] $SuggestedAction
    )
    return $null
}
function Write-OutputSummary { param([string] $FilePath, [string] $Route) }
function Write-JsonLineAppend {
    param([string] $Path, $Payload, [int] $Depth = 10, [switch] $UseLogLock)
    if ($script:CompletionAppendMode -eq 'fail') { return $false }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) { [System.IO.Directory]::CreateDirectory($dir) | Out-Null }
    [System.IO.File]::AppendAllText($Path, (($Payload | ConvertTo-Json -Compress -Depth $Depth) + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
    return $true
}
function Write-Sidecar {
    param([string] $OutputPath, [string] $Route, $Extra, [switch] $SkipCompletedManifest)
    if ($script:SidecarMode -eq 'pipeline_fail') { return $false }
    $payload = [ordered]@{ pipeline_version = $script:PipelineVersion; route = $Route }
    if ($Extra -is [System.Collections.IDictionary]) {
        foreach ($key in @($Extra.Keys)) { $payload[$key] = $Extra[$key] }
    }
    [System.IO.File]::WriteAllText((Get-SidecarPath $OutputPath), ($payload | ConvertTo-Json -Depth 10), [System.Text.UTF8Encoding]::new($false))
    return $true
}
function Refresh-PendingPublishIndex {
    $count = @(Get-ChildItem -LiteralPath $script:LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue).Count
    $script:PendingPublishIndex = [pscustomobject]@{ Count = $count }
    return $script:PendingPublishIndex
}

$script:Failures = [System.Collections.Generic.List[string]]::new()
function Invoke-FaultCheck {
    param(
        [Parameter(Mandatory)] [string] $Name,
        [Parameter(Mandatory)] [scriptblock] $Body
    )
    try {
        & $Body
        Write-Host "PASS: $Name"
    } catch {
        $script:Failures.Add("${Name}: $($_.Exception.Message)") | Out-Null
        Write-Host "FAIL: ${Name}: $($_.Exception.Message)"
    }
}
function Assert-True {
    param([bool] $Condition, [string] $Message)
    if (-not $Condition) { throw $Message }
}
function Assert-Equal {
    param($Actual, $Expected, [string] $Message)
    if ($Actual -ne $Expected) { throw "$Message Expected '$Expected', got '$Actual'." }
}
function Invoke-WithFaultRoots {
    param([Parameter(Mandatory)] [scriptblock] $Body)
    $root = Join-Path ([System.IO.Path]::GetTempPath()) ('mediapipeline-pending-fault-' + [guid]::NewGuid().ToString('N'))
    try {
        $script:SourceMovies = Join-Path $root 'source'
        $script:LocalBase = Join-Path $root 'state'
        $script:LocalEncoded = Join-Path $root 'scratch\encoded'
        $script:LocalPendingPush = Join-Path $root 'pending'
        $script:Outsource = Join-Path $root 'destination'
        $script:LocalCompleted = Join-Path $script:LocalBase 'completed'
        $script:CompletedJobsManifest = Join-Path $script:LocalCompleted 'completed_jobs.jsonl'
        $script:LibraryProfiles = @([pscustomobject]@{
            source_path = $script:SourceMovies
            output_path = $script:Outsource
            enabled = $true
        })
        foreach ($path in @($script:SourceMovies, $script:LocalBase, $script:LocalEncoded, $script:LocalPendingPush, $script:Outsource, $script:LocalCompleted)) {
            [System.IO.Directory]::CreateDirectory($path) | Out-Null
        }
        & $Body ([System.IO.DirectoryInfo]::new($root))
    } finally {
        Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
    }
}

function Reset-PendingFaultHarness {
    $script:PendingPublishFaultInjector = $null
    $script:CopyMode = 'success'
    $script:CopyFailureReason = ''
    $script:SidecarMode = 'success'
    $script:CompletionAppendMode = 'success'
}

function Set-PendingFaultTarget {
    param(
        [Parameter(Mandatory)] [string] $Boundary,
        [Parameter(Mandatory)] [string] $Moment,
        [Parameter(Mandatory)] [string] $Action,
        [Parameter(Mandatory)] [string] $Scope
    )
    $script:FaultTargetBoundary = $Boundary
    $script:FaultTargetMoment = $Moment
    $script:FaultTargetAction = $Action
    $script:FaultTargetScope = $Scope
    $script:PendingPublishFaultInjector = {
        param($SeenBoundary, $SeenMoment, $Context)
        if ($SeenBoundary -eq $script:FaultTargetBoundary -and
            $SeenMoment -eq $script:FaultTargetMoment -and
            [string]$Context.scope -eq $script:FaultTargetScope) {
            return $script:FaultTargetAction
        }
        return ''
    }
}

function New-PendingFaultFixture {
    param(
        [Parameter(Mandatory)] [System.IO.DirectoryInfo] $Root,
        [int] $SidecarCount = 1
    )

    Reset-PendingFaultHarness
    $source = Join-Path $script:SourceMovies 'movie-source.mkv'
    $scratch = Join-Path $Root.FullName 'scratch\input\movie-source.mkv'
    $localOut = Join-Path $script:LocalEncoded 'movie-output.mkv'
    $serverOut = Join-Path $script:Outsource 'library\movie-output.mkv'
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $scratch)) | Out-Null
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $serverOut)) | Out-Null
    [System.IO.File]::WriteAllText($source, 'immutable-source-bytes')
    [System.IO.File]::WriteAllText($scratch, 'scratch-copy-bytes')
    [System.IO.File]::WriteAllText($localOut, 'verified-media-output-bytes')
    $sidecars = [System.Collections.Generic.List[object]]::new()
    for ($index = 0; $index -lt $SidecarCount; $index++) {
        $language = @('eng', 'spa', 'fra')[$index % 3]
        $localSrt = Join-Path $script:LocalEncoded "movie-output.$language.srt"
        $serverSrt = "$serverOut.$language.srt"
        [System.IO.File]::WriteAllText($localSrt, "1`n00:00:00,000 --> 00:00:01,000`n$language caption`n")
        $sidecars.Add([pscustomobject]@{
            LocalPath = $localSrt
            DestinationPath = $serverSrt
            Kind = 'tx3g_srt'
            PreserveExisting = $false
            Record = [pscustomobject]@{ source_stream_index = $index + 2; language = $language; status = 'pending'; path = $serverSrt }
        }) | Out-Null
    }
    $transaction = Invoke-PendingParkTransaction `
        -LocalOut $localOut `
        -ServerOut $serverOut `
        -Route 'encode' `
        -SourceIdentity 'source-v1' `
        -SourceIdentityV2 'source-v2' `
        -SourcePath $source `
        -SourceSize (Get-Item -LiteralPath $source).Length `
        -SourceMTimeUtc '2026-07-20T00:00:00Z' `
        -PublishTransactionId ('tx-' + [guid]::NewGuid().ToString('N')) `
        -PublishMode 'deferred' `
        -SidecarFiles @($sidecars)
    if (-not $transaction.Ok) { throw "Fixture park failed: $($transaction.Error)" }
    return [pscustomobject]@{
        SourcePath = $source
        SourceHash = Get-PendingFileSha256OrNull -Path $source
        ScratchPath = $scratch
        ScratchHash = Get-PendingFileSha256OrNull -Path $scratch
        ServerOut = $serverOut
        ManifestPath = [string]$transaction.ManifestPath
        PendingPath = [string]$transaction.LocalFile
        MediaHash = Get-PendingFileSha256OrNull -Path ([string]$transaction.LocalFile)
        SidecarEntries = @($transaction.SidecarEntries)
        Transaction = $transaction
    }
}

function Complete-PendingFaultFixture {
    param([Parameter(Mandatory)] $Fixture)

    $script:PendingPublishFaultInjector = $null
    [void](Invoke-PendingPublishRecovery -Reason 'fault-test-restart')
    if (Test-Path -LiteralPath $Fixture.ManifestPath -PathType Leaf -ErrorAction SilentlyContinue) {
        $manifest = Read-PendingManifestFile -Path $Fixture.ManifestPath
        if (-not ([string]$manifest.manifest_state).StartsWith('review_', [System.StringComparison]::OrdinalIgnoreCase)) {
            [void](Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $Fixture.ManifestPath) -Manifest $manifest)
        }
    }
}

function Assert-PendingFaultFixtureCompleted {
    param([Parameter(Mandatory)] $Fixture)

    Assert-True (Test-Path -LiteralPath $Fixture.ServerOut -PathType Leaf) 'Final output is missing after recovery and retry.'
    Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.ServerOut) $Fixture.MediaHash 'Final output hash differs from the parked verified artifact.'
    foreach ($sidecar in @($Fixture.SidecarEntries)) {
        $serverSidecar = [string]$sidecar.server_out
        Assert-True (Test-Path -LiteralPath $serverSidecar -PathType Leaf) "Required final sidecar is missing: $serverSidecar"
        Assert-Equal (Get-PendingFileSha256OrNull -Path $serverSidecar) ([string]$sidecar.output_sha256) "Final sidecar hash mismatch: $serverSidecar"
    }
    Assert-True (Test-Path -LiteralPath (Get-SidecarPath $Fixture.ServerOut) -PathType Leaf) 'Pipeline completion sidecar is missing.'
    Assert-True (-not (Test-Path -LiteralPath $Fixture.ManifestPath -PathType Leaf)) 'Completed drain left its pending manifest behind.'
    Assert-True (-not (Test-Path -LiteralPath $Fixture.PendingPath -PathType Leaf)) 'Completed drain left its parked media behind.'
    Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.SourcePath) $Fixture.SourceHash 'Source media changed during fault recovery.'
    Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.ScratchPath) $Fixture.ScratchHash 'Scratch input changed during fault recovery.'
    $completionRows = if (Test-Path -LiteralPath $script:CompletedJobsManifest -PathType Leaf) { @(Get-Content -LiteralPath $script:CompletedJobsManifest | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) } else { @() }
    Assert-Equal $completionRows.Count 1 'Ambiguous retry duplicated or omitted the completed-manifest result.'
    $artifactPatterns = @('*.mp-publish-partial.*', '*.mp-publish-backup.*', '*.mp-pending-sidecar-backup.*', '*.mp-publish-sidecar-backup.*')
    foreach ($pattern in $artifactPatterns) {
        Assert-Equal @(Get-ChildItem -LiteralPath $script:Outsource -Recurse -Force -File -Filter $pattern -ErrorAction SilentlyContinue).Count 0 "Stale transaction artifact remains: $pattern"
    }
}

function Assert-InterruptedDrainStateConservative {
    param([Parameter(Mandatory)] $Fixture)

    Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.SourcePath) $Fixture.SourceHash 'Interrupted drain changed source media.'
    Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.ScratchPath) $Fixture.ScratchHash 'Interrupted drain changed scratch input.'
    if (Test-Path -LiteralPath $Fixture.ServerOut -PathType Leaf -ErrorAction SilentlyContinue) {
        Assert-Equal (Get-PendingFileSha256OrNull -Path $Fixture.ServerOut) $Fixture.MediaHash 'Interrupted drain exposed incorrect final media bytes.'
        foreach ($sidecar in @($Fixture.SidecarEntries)) {
            Assert-True (Test-Path -LiteralPath ([string]$sidecar.server_out) -PathType Leaf) 'Revealed final media lacks a required sidecar.'
            Assert-Equal (Get-PendingFileSha256OrNull -Path ([string]$sidecar.server_out)) ([string]$sidecar.output_sha256) 'Revealed final media has mismatched sidecar bytes.'
        }
        Assert-True (Test-Path -LiteralPath (Get-SidecarPath $Fixture.ServerOut) -PathType Leaf) 'Revealed final media lacks pipeline sidecar proof.'
    } else {
        Assert-True (Test-Path -LiteralPath $Fixture.ManifestPath -PathType Leaf) 'Interrupted pre-reveal drain lost its manifest.'
        Assert-True (Test-Path -LiteralPath $Fixture.PendingPath -PathType Leaf) 'Interrupted pre-reveal drain lost its only parked media artifact.'
        $prematureRows = if (Test-Path -LiteralPath $script:CompletedJobsManifest -PathType Leaf) { @(Get-Content -LiteralPath $script:CompletedJobsManifest | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) } else { @() }
        Assert-Equal $prematureRows.Count 0 'Interrupted pre-reveal drain falsely wrote completion evidence.'
    }
}

function Invoke-ParkFaultScenario {
    param(
        [Parameter(Mandatory)] [System.IO.DirectoryInfo] $Root,
        [Parameter(Mandatory)] [string] $Boundary,
        [Parameter(Mandatory)] [string] $Moment,
        [Parameter(Mandatory)] [string] $Action,
        [Parameter(Mandatory)] [string] $Scope
    )

    Reset-PendingFaultHarness
    $source = Join-Path $script:SourceMovies 'park-source.mkv'
    $scratch = Join-Path $Root.FullName 'scratch\input\park-source.mkv'
    $localOut = Join-Path $script:LocalEncoded 'park-output.mkv'
    $localSrt = Join-Path $script:LocalEncoded 'park-output.eng.srt'
    $serverOut = Join-Path $script:Outsource 'library\park-output.mkv'
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $scratch)) | Out-Null
    [System.IO.Directory]::CreateDirectory((Split-Path -Parent $serverOut)) | Out-Null
    [System.IO.File]::WriteAllText($source, 'immutable-park-source')
    [System.IO.File]::WriteAllText($scratch, 'immutable-park-scratch')
    [System.IO.File]::WriteAllText($localOut, 'park-media-output')
    [System.IO.File]::WriteAllText($localSrt, "1`n00:00:00,000 --> 00:00:01,000`nPark caption`n")
    $sourceHash = Get-PendingFileSha256OrNull -Path $source
    $scratchHash = Get-PendingFileSha256OrNull -Path $scratch
    $sidecar = [pscustomobject]@{
        LocalPath = $localSrt
        DestinationPath = "$serverOut.eng.srt"
        Kind = 'tx3g_srt'
        PreserveExisting = $false
        Record = [pscustomobject]@{ source_stream_index = 2; language = 'eng'; status = 'pending'; path = "$serverOut.eng.srt" }
    }
    Set-PendingFaultTarget -Boundary $Boundary -Moment $Moment -Action $Action -Scope $Scope
    try {
        if ($Boundary -eq 'index_update') {
            [void](Invoke-ParkPendingPush -LocalOut $localOut -ServerOut $serverOut -Route 'encode' -SourceIdentity 'source-v1' -SourceIdentityV2 'source-v2' -SourcePath $source -SourceSize (Get-Item -LiteralPath $source).Length -SourceMTimeUtc '2026-07-20T00:00:00Z' -PublishTransactionId ('tx-' + [guid]::NewGuid().ToString('N')) -PublishMode 'deferred' -SidecarFiles @($sidecar))
        } else {
            [void](Invoke-PendingParkTransaction -LocalOut $localOut -ServerOut $serverOut -Route 'encode' -SourceIdentity 'source-v1' -SourceIdentityV2 'source-v2' -SourcePath $source -SourceSize (Get-Item -LiteralPath $source).Length -SourceMTimeUtc '2026-07-20T00:00:00Z' -PublishTransactionId ('tx-' + [guid]::NewGuid().ToString('N')) -PublishMode 'deferred' -SidecarFiles @($sidecar))
        }
    } catch {
        # Both injected exception and termination are expected campaign inputs.
    } finally {
        $script:PendingPublishFaultInjector = $null
    }

    [void](Invoke-PendingPublishRecovery -Reason 'park-fault-restart')
    Assert-Equal (Get-PendingFileSha256OrNull -Path $source) $sourceHash 'Source media changed during park fault recovery.'
    Assert-Equal (Get-PendingFileSha256OrNull -Path $scratch) $scratchHash 'Scratch input changed during park fault recovery.'
    Assert-True (-not (Test-Path -LiteralPath $serverOut -PathType Leaf)) 'A park interruption exposed final output.'
    Assert-True (-not (Test-Path -LiteralPath "$serverOut.eng.srt" -PathType Leaf)) 'A park interruption exposed a final sidecar.'
    $manifestFiles = @(Get-ChildItem -LiteralPath $script:LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue)
    if ($manifestFiles.Count -gt 0) {
        Assert-Equal $manifestFiles.Count 1 'Park fault created duplicate pending manifests.'
        $manifest = Read-PendingManifestFile -Path $manifestFiles[0].FullName
        Assert-True ([string]$manifest.manifest_state -in @('parked', 'parked_recovered')) 'Park fault did not reconcile to an explicitly parked state.'
        Assert-True (Test-Path -LiteralPath ([string]$manifest.local_file) -PathType Leaf) 'Reconciled park manifest lacks its recoverable media payload.'
        Assert-Equal (Get-PendingFileSha256OrNull -Path ([string]$manifest.local_file)) ([string]$manifest.output_sha256) 'Reconciled parked media hash mismatch.'
        foreach ($entry in @(Get-PendingSidecarEntries -Manifest $manifest)) {
            Assert-True (Test-Path -LiteralPath ([string]$entry.local_file) -PathType Leaf) 'Reconciled park manifest lacks a required sidecar payload.'
            Assert-Equal (Get-PendingFileSha256OrNull -Path ([string]$entry.local_file)) ([string]$entry.output_sha256) 'Reconciled parked sidecar hash mismatch.'
        }
    } else {
        Assert-True (Test-Path -LiteralPath $localOut -PathType Leaf) 'Park fault lost the only recoverable media artifact.'
    }
}

function Invoke-RetryableCopyFailureScenario {
    param(
        [Parameter(Mandatory)] [System.IO.DirectoryInfo] $Root,
        [Parameter(Mandatory)] [string] $Mode,
        [Parameter(Mandatory)] [string] $ExpectedStatus
    )

    $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
    $script:CopyMode = $Mode
    $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
    $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest
    Assert-Equal ([string]$result.Status) $ExpectedStatus "Unexpected status for simulated $Mode failure."
    Assert-True (Test-Path -LiteralPath $fixture.ManifestPath -PathType Leaf) "$Mode failure removed the pending manifest."
    Assert-True (Test-Path -LiteralPath $fixture.PendingPath -PathType Leaf) "$Mode failure removed the only parked payload."
    Assert-True (-not (Test-Path -LiteralPath $fixture.ServerOut -PathType Leaf)) "$Mode failure exposed a final output."
    Assert-Equal (Get-PendingFileSha256OrNull -Path $fixture.SourcePath) $fixture.SourceHash "$Mode failure changed source media."
    $partialPath = New-PublishPartialMediaPath -ServerOut $fixture.ServerOut -PublishTransactionId ([string]$fixture.Transaction.PublishTransactionId)
    Assert-True (-not (Test-Path -LiteralPath $partialPath -PathType Leaf)) "$Mode failure left a partial final artifact."
    $script:CopyMode = 'success'
    $script:CopyFailureReason = ''
    Complete-PendingFaultFixture -Fixture $fixture
    Assert-PendingFaultFixtureCompleted -Fixture $fixture
}

Invoke-FaultCheck -Name 'deterministic fault seam inventory exists' -Body {
    Assert-True ([bool](Get-Command -Name Invoke-PendingPublishFaultPoint -ErrorAction SilentlyContinue)) 'Invoke-PendingPublishFaultPoint is missing.'
    $required = @(
        'manifest_preparation', 'pending_copy', 'byte_hash_verification', 'sidecar_staging',
        'destination_availability', 'final_placement', 'atomic_reveal', 'index_update',
        'completion_evidence_write', 'pending_cleanup'
    )
    foreach ($boundary in $required) {
        Assert-True (Test-PendingPublishFaultBoundary -Boundary $boundary) "Fault boundary '$boundary' is not registered."
    }
}

Invoke-FaultCheck -Name 'park manifest binds sidecar bytes by SHA-256' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $sidecarSource = Join-Path $script:LocalEncoded 'movie.eng.srt'
        $sidecarDestination = Join-Path $script:Outsource 'movie.eng.srt'
        [System.IO.File]::WriteAllText($sidecarSource, "1`n00:00:00,000 --> 00:00:01,000`nExpected`n")
        $entries = @(New-PendingParkSidecarEntries -SidecarFiles @([pscustomobject]@{
            LocalPath = $sidecarSource
            DestinationPath = $sidecarDestination
            Kind = 'tx3g_srt'
        }) -LocalPendingPushPath $script:LocalPendingPush -Timestamp '20260720_000000' -TransactionFileId 'fault')
        Assert-Equal $entries.Count 1 'Expected one sidecar manifest entry.'
        Assert-True ([string]$entries[0].output_sha256 -match '^[A-F0-9]{64}$') 'Sidecar manifest entry lacks SHA-256 proof.'
        Assert-Equal ([string]$entries[0].output_hash_algorithm) 'SHA256' 'Sidecar manifest entry lacks its hash algorithm.'
    }
}

Invoke-FaultCheck -Name 'existing destination rejects mismatched sidecar bytes' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $local = Join-Path $script:LocalPendingPush 'movie.mkv'
        $server = Join-Path $script:Outsource 'movie.mkv'
        $serverSrt = "$server.eng.srt"
        $source = Join-Path $script:SourceMovies 'movie.mkv'
        [System.IO.File]::WriteAllText($local, 'media')
        [System.IO.File]::WriteAllText($server, 'media')
        [System.IO.File]::WriteAllText($serverSrt, "1`n00:00:00,000 --> 00:00:01,000`nWrong`n")
        [System.IO.File]::WriteAllText($source, 'source')
        $manifest = [pscustomobject]@{
            output_size = 5
            publish_transaction_id = 'tx-fault'
            source_identity_v2 = 'source-v2'
            source_identity = 'source-v1'
            source_path = $source
            source_size = 6
            sidecar_files = @([pscustomobject]@{
                local_file = (Join-Path $script:LocalPendingPush 'movie.eng.srt')
                server_out = $serverSrt
                output_sha256 = ('A' * 64)
                output_hash_algorithm = 'SHA256'
            })
            tx3g_srt_tracks = @()
        }
        $pipelineSidecar = [ordered]@{
            pipeline_version = $script:PipelineVersion
            publish_transaction_id = 'tx-fault'
            source_identity_v2 = 'source-v2'
            source_identity = 'source-v1'
            source_path = $source
            source_size = 6
        }
        [System.IO.File]::WriteAllText((Get-SidecarPath $server), ($pipelineSidecar | ConvertTo-Json), [System.Text.UTF8Encoding]::new($false))
        $accepted = Test-PendingPublishedServerCopy -Manifest $manifest -LocalPath $local -ServerPath $server
        Assert-True (-not $accepted) 'Existing final was accepted even though its required sidecar bytes do not match the manifest.'
    }
}

Invoke-FaultCheck -Name 'completed manifest append failure is not reported as success' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $server = Join-Path $script:Outsource 'movie.mkv'
        [System.IO.File]::WriteAllText($server, 'media')
        [System.IO.File]::WriteAllText((Get-SidecarPath $server), (@{ pipeline_version = $script:PipelineVersion; output_path = $server } | ConvertTo-Json))
        function Write-JsonLineAppend { param(); return $false }
        $added = Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server
        Assert-True (-not $added) 'Completed manifest append failure was falsely reported as success.'
    }
}

Invoke-FaultCheck -Name 'ambiguous already-published response retains pending evidence' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $local = Join-Path $script:LocalPendingPush 'movie.mkv'
        $server = Join-Path $script:Outsource 'movie.mkv'
        $manifestPath = "$local.manifest.json"
        [System.IO.File]::WriteAllText($local, 'media')
        [System.IO.File]::WriteAllText($server, 'media')
        $hash = Get-PendingFileSha256OrNull $local
        $manifest = [pscustomobject]@{
            local_file = $local; server_out = $server; route = 'encode'; publish_mode = 'retry'
            source_path = (Join-Path $script:SourceMovies 'movie.mkv'); publish_transaction_id = 'tx-fault'
            output_sha256 = $hash; output_hash_algorithm = 'SHA256'; sidecar_files = @(); tx3g_srt_tracks = @()
        }
        [System.IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 10))
        function Test-PendingManifestTrustedForDrain { return [pscustomobject]@{ Ok = $true } }
        function Update-PendingManifestDrainAttempt { param($Manifest); return $Manifest }
        function Test-PendingPublishedServerCopy { return $true }
        function Add-CompletedJobsManifestEntryFromSidecar { return $false }
        $script:PendingCleanupCalled = $false
        function Remove-PendingDrainLocalArtifacts { $script:PendingCleanupCalled = $true }
        $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $manifestPath) -Manifest $manifest
        Assert-Equal ([string]$result.Status) 'completion_evidence_failed' 'Ambiguous completion evidence must remain a failed/pending transaction.'
        Assert-True (-not $script:PendingCleanupCalled) 'Pending cleanup ran without durable completion evidence.'
        Assert-True (Test-Path -LiteralPath $local -PathType Leaf) 'The only parked payload was removed after an ambiguous response.'
        Assert-True (Test-Path -LiteralPath $manifestPath -PathType Leaf) 'The pending manifest was removed after an ambiguous response.'
    }
}

$parkFaultBoundaries = @(
    [pscustomobject]@{ Boundary = 'manifest_preparation'; Scope = 'park' },
    [pscustomobject]@{ Boundary = 'sidecar_staging'; Scope = 'park' },
    [pscustomobject]@{ Boundary = 'pending_copy'; Scope = 'park' },
    [pscustomobject]@{ Boundary = 'byte_hash_verification'; Scope = 'park_staged' },
    [pscustomobject]@{ Boundary = 'index_update'; Scope = 'park' }
)
foreach ($faultBoundary in $parkFaultBoundaries) {
    foreach ($faultMoment in @('before', 'after')) {
        foreach ($faultAction in @('exception', 'terminate')) {
            $caseBoundary = [string]$faultBoundary.Boundary
            $caseScope = [string]$faultBoundary.Scope
            $caseMoment = [string]$faultMoment
            $caseAction = [string]$faultAction
            Invoke-FaultCheck -Name "park $caseBoundary $caseMoment $caseAction" -Body {
                Invoke-WithFaultRoots {
                    param($Root)
                    Invoke-ParkFaultScenario -Root $Root -Boundary $caseBoundary -Moment $caseMoment -Action $caseAction -Scope $caseScope
                }
            }
        }
    }
}

$drainFaultBoundaries = @(
    [pscustomobject]@{ Boundary = 'destination_availability'; Scope = 'drain' },
    [pscustomobject]@{ Boundary = 'final_placement'; Scope = 'drain_partial' },
    [pscustomobject]@{ Boundary = 'byte_hash_verification'; Scope = 'drain_partial' },
    [pscustomobject]@{ Boundary = 'sidecar_staging'; Scope = 'drain_all_sidecars' },
    [pscustomobject]@{ Boundary = 'atomic_reveal'; Scope = 'drain' },
    [pscustomobject]@{ Boundary = 'completion_evidence_write'; Scope = 'drain' },
    [pscustomobject]@{ Boundary = 'pending_cleanup'; Scope = 'drain' }
)
foreach ($faultBoundary in $drainFaultBoundaries) {
    foreach ($faultMoment in @('before', 'after')) {
        foreach ($faultAction in @('exception', 'terminate')) {
            $caseBoundary = [string]$faultBoundary.Boundary
            $caseScope = [string]$faultBoundary.Scope
            $caseMoment = [string]$faultMoment
            $caseAction = [string]$faultAction
            Invoke-FaultCheck -Name "drain $caseBoundary $caseMoment $caseAction" -Body {
                Invoke-WithFaultRoots {
                    param($Root)
                    $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
                    Set-PendingFaultTarget -Boundary $caseBoundary -Moment $caseMoment -Action $caseAction -Scope $caseScope
                    try {
                        $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
                        [void](Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest)
                    } catch {
                        # Expected for injected exception/termination.
                    } finally {
                        $script:PendingPublishFaultInjector = $null
                    }
                    Assert-InterruptedDrainStateConservative -Fixture $fixture
                    Complete-PendingFaultFixture -Fixture $fixture
                    Assert-PendingFaultFixtureCompleted -Fixture $fixture
                }
            }
        }
    }
}

foreach ($failureCase in @(
    [pscustomobject]@{ Mode = 'access_denied'; Status = 'copy_failed' },
    [pscustomobject]@{ Mode = 'disk_full'; Status = 'copy_failed' },
    [pscustomobject]@{ Mode = 'partial'; Status = 'copy_failed' },
    [pscustomobject]@{ Mode = 'checksum_mismatch'; Status = 'partial_hash_mismatch' },
    [pscustomobject]@{ Mode = 'destination_disappeared'; Status = 'copy_failed' }
)) {
    $copyMode = [string]$failureCase.Mode
    $copyStatus = [string]$failureCase.Status
    Invoke-FaultCheck -Name "drain $copyMode remains retryable" -Body {
        Invoke-WithFaultRoots {
            param($Root)
            Invoke-RetryableCopyFailureScenario -Root $Root -Mode $copyMode -ExpectedStatus $copyStatus
        }
    }
}

Invoke-FaultCheck -Name 'existing destination collision is review-bound and never overwritten' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
        [System.IO.File]::WriteAllText($fixture.ServerOut, 'unrelated-existing-final')
        $collisionHash = Get-PendingFileSha256OrNull -Path $fixture.ServerOut
        $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest
        Assert-Equal ([string]$result.Status) 'destination_collision' 'Existing destination collision did not fail closed.'
        Assert-Equal (Get-PendingFileSha256OrNull -Path $fixture.ServerOut) $collisionHash 'Existing destination was overwritten.'
        Assert-True (Test-Path -LiteralPath $fixture.PendingPath -PathType Leaf) 'Collision handling removed the parked payload.'
        $reviewManifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        Assert-Equal ([string]$reviewManifest.manifest_state) 'review_destination_collision' 'Collision was not explicitly review-bound.'
        Assert-True ([bool]$reviewManifest.review_required) 'Collision manifest does not require review.'
        Assert-Equal (Get-PendingFileSha256OrNull -Path $fixture.SourcePath) $fixture.SourceHash 'Collision handling changed source media.'
    }
}

Invoke-FaultCheck -Name 'duplicate drain request cannot mutate or duplicate output' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
        $heldLock = Enter-PendingPublishTransactionLock -ManifestPath $fixture.ManifestPath
        Assert-True ($null -ne $heldLock) 'Could not acquire the fixture manifest lock.'
        try {
            $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
            $duplicate = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest
            Assert-Equal ([string]$duplicate.Status) 'duplicate_request' 'Concurrent duplicate drain was not rejected.'
            Assert-True (-not (Test-Path -LiteralPath $fixture.ServerOut -PathType Leaf)) 'Rejected duplicate drain exposed output.'
            Assert-True (Test-Path -LiteralPath $fixture.PendingPath -PathType Leaf) 'Rejected duplicate drain removed pending media.'
        } finally {
            Exit-PendingPublishTransactionLock -Lock $heldLock
        }
        Complete-PendingFaultFixture -Fixture $fixture
        Assert-PendingFaultFixtureCompleted -Fixture $fixture
    }
}

Invoke-FaultCheck -Name 'ambiguous success retry is idempotent without restart helper' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
        Set-PendingFaultTarget -Boundary 'completion_evidence_write' -Moment 'after' -Action 'terminate' -Scope 'drain'
        try {
            $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
            [void](Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest)
        } catch {
        } finally {
            $script:PendingPublishFaultInjector = $null
        }
        Assert-True (Test-Path -LiteralPath $fixture.ManifestPath -PathType Leaf) 'Ambiguous response lost pending manifest before cleanup.'
        $retryManifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        $retry = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $retryManifest
        Assert-Equal ([string]$retry.Status) 'already_published' 'Ambiguous retry did not converge on already_published.'
        Assert-PendingFaultFixtureCompleted -Fixture $fixture
    }
}

Invoke-FaultCheck -Name 'stale in-progress attempt is reconciled on restart' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
        $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        $manifest = Update-PendingManifestDrainAttempt -ManifestPath $fixture.ManifestPath -Manifest $manifest -AttemptId 'stale-attempt' -Status 'in_progress'
        $manifest = Update-PendingManifestTransactionPhase -ManifestPath $fixture.ManifestPath -Manifest $manifest -Phase 'final_partial_copied' -AttemptId 'stale-attempt'
        $partial = New-PublishPartialMediaPath -ServerOut $fixture.ServerOut -PublishTransactionId ([string]$manifest.publish_transaction_id)
        [System.IO.File]::Copy($fixture.PendingPath, $partial, $true)
        $recovery = Invoke-PendingPublishRecovery -Reason 'stale-attempt-test'
        Assert-Equal ([int]$recovery.recovered_count) 1 'Restart recovery did not reconcile the stale attempt.'
        Assert-True (-not (Test-Path -LiteralPath $partial -PathType Leaf)) 'Restart recovery left a stale partial artifact.'
        $recoveredManifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        Assert-Equal ([string]$recoveredManifest.manifest_state) 'parked_recovered' 'Stale attempt was not returned to parked recovery posture.'
        Complete-PendingFaultFixture -Fixture $fixture
        Assert-PendingFaultFixtureCompleted -Fixture $fixture
    }
}

Invoke-FaultCheck -Name 'corrupted manifest remains explicit and does not publish' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        Reset-PendingFaultHarness
        $corruptPath = Join-Path $script:LocalPendingPush 'corrupt.manifest.json'
        $orphanPayload = Join-Path $script:LocalPendingPush 'corrupt.mkv'
        $server = Join-Path $script:Outsource 'corrupt.mkv'
        [System.IO.File]::WriteAllText($corruptPath, '{not-json')
        [System.IO.File]::WriteAllText($orphanPayload, 'recoverable-orphan-bytes')
        $payloadHash = Get-PendingFileSha256OrNull -Path $orphanPayload
        $recovery = Invoke-PendingPublishRecovery -Reason 'corrupted-manifest-test'
        Assert-Equal ([int]$recovery.failed_count) 1 'Corrupted manifest was not surfaced as failed recovery evidence.'
        Assert-True (Test-Path -LiteralPath $corruptPath -PathType Leaf) 'Corrupted manifest evidence was deleted.'
        Assert-Equal (Get-PendingFileSha256OrNull -Path $orphanPayload) $payloadHash 'Corrupted-manifest recovery changed the orphan payload.'
        Assert-True (-not (Test-Path -LiteralPath $server -PathType Leaf)) 'Corrupted manifest published output.'
    }
}

Invoke-FaultCheck -Name 'crash during sidecar placement rolls back before retry' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 2
        Set-PendingFaultTarget -Boundary 'sidecar_staging' -Moment 'after' -Action 'terminate' -Scope 'drain_sidecar'
        try {
            $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
            [void](Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest)
        } catch {
        } finally {
            $script:PendingPublishFaultInjector = $null
        }
        Assert-True (-not (Test-Path -LiteralPath $fixture.ServerOut -PathType Leaf)) 'Sidecar-placement crash revealed final media.'
        Assert-True (@($fixture.SidecarEntries | Where-Object { Test-Path -LiteralPath ([string]$_.server_out) -PathType Leaf }).Count -ge 1) 'Sidecar-placement fault did not occur after a staged sidecar.'
        $recovery = Invoke-PendingPublishRecovery -Reason 'sidecar-crash-test'
        Assert-Equal ([int]$recovery.recovered_count) 1 'Restart recovery did not reconcile the sidecar-placement crash.'
        foreach ($sidecar in @($fixture.SidecarEntries)) {
            Assert-True (-not (Test-Path -LiteralPath ([string]$sidecar.server_out) -PathType Leaf)) 'Restart recovery left a pre-reveal sidecar exposed.'
        }
        Complete-PendingFaultFixture -Fixture $fixture
        Assert-PendingFaultFixtureCompleted -Fixture $fixture
    }
}

Invoke-FaultCheck -Name 'tampered pending sidecar cannot reach completed output' -Body {
    Invoke-WithFaultRoots {
        param($Root)
        $fixture = New-PendingFaultFixture -Root $Root -SidecarCount 1
        [System.IO.File]::WriteAllText(([string]$fixture.SidecarEntries[0].local_file), 'tampered-sidecar-bytes')
        $manifest = Read-PendingManifestFile -Path $fixture.ManifestPath
        $result = Invoke-PendingDrainTransaction -ManifestFile (Get-Item -LiteralPath $fixture.ManifestPath) -Manifest $manifest
        Assert-Equal ([string]$result.Status) 'sidecar_file_failed' 'Tampered pending sidecar did not fail publication.'
        Assert-True (-not (Test-Path -LiteralPath $fixture.ServerOut -PathType Leaf)) 'Tampered sidecar transaction revealed final media.'
        Assert-True (Test-Path -LiteralPath $fixture.ManifestPath -PathType Leaf) 'Tampered sidecar transaction deleted its manifest evidence.'
        Assert-True (Test-Path -LiteralPath $fixture.PendingPath -PathType Leaf) 'Tampered sidecar transaction deleted its parked media.'
        Assert-Equal (Get-PendingFileSha256OrNull -Path $fixture.SourcePath) $fixture.SourceHash 'Tampered sidecar handling changed source media.'
    }
}

if ($script:Failures.Count -gt 0) {
    throw ("Pending publish transaction fault checks failed ({0}):`n - {1}" -f $script:Failures.Count, ($script:Failures -join "`n - "))
}

Write-Host 'Pending publish transaction fault injection checks passed.'
