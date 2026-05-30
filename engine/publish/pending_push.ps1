# ==============================================================================
# Modules\PendingPush.ps1
# ==============================================================================
# PendingServerPush\ park-and-retry helpers extracted from
# MediaPipeline.ps1 (the FIX#10 cluster).
#
# Public facade for the state machine where "the local encode/remux succeeded
# but the network push to the outsource share failed". Durable manifest/move
# mechanics live in PendingTransactions.ps1. The invariant we protect: NEVER
# delete a completed local output while there's any chance the server copy
# isn't verified, because that's hours of GPU compute.
#
# Dot-sourced from the main script. Reads at call time:
#
#   $LocalPendingPush                  — local PendingServerPush\ directory
#   $StopFlag                          — operator-stop sentinel (file)
#   $script:StopRequested              — in-process stop sentinel
#   $script:PipelineVersion            — stamp written into manifests
#   $script:MinPipelineVersion         — server-sidecar freshness gate
#   $script:DeferredPublish            — drain-on-demand toggle
#   $script:SourceIdentityV2Algorithm  — algorithm tag for v2 keys
#   $script:PendingPublishIndex        — refreshed mirror used by main loop
#                                        to detect "this source is already
#                                        parked" before re-encoding
#
# Cross-module helpers (loaded earlier):
#   Compare-PipelineVersion            — Modules\PathHelpers.ps1
#   Get-SidecarPath, Write-Sidecar     — Modules\Sidecar.ps1
#   Write-Log, DebugLog                — Modules\Logging.ps1
#   Read/Write/Update pending manifests — Modules\PendingManifestStore.ps1
#   Invoke-PendingParkTransaction,
#   Invoke-PendingDrainTransaction,
#   Repair-PendingManifestState       — Modules\PendingTransactions.ps1
#   Refresh/Test pending publish index  — Modules\PendingPublishIndex.ps1
#                                        (resolved at call time)
#
# More cross-module helpers (loaded earlier):
#   Copy-FileRobocopy                 — Modules\Disk.ps1
#   Write-OutputSummary               — Modules\MediaProbe.ps1
#
# Additional cross-module helpers (loaded earlier):
#   Get-SourceIdentityKey, Get-SourceIdentityKeyV2 — Modules\SourceIdentity.ps1
#   Set-ProgressStage, Set-ProgressItemContext,
#   Reset-ProgressItemContext                    — Modules\ProgressState.ps1
#
# State machine (manifest_state field):
#
#   pending_move    ─→ Manifest written but the local file move hasn't
#                       happened yet. If we crash here, Repair-PendingManifestState
#                       on the next run finds original_local_file still in
#                       place and completes the move, transitioning to
#                       parked_recovered.
#
#   parked          ─→ Steady state: local file lives at local_file,
#                       manifest.json describes the intended push.
#                       Invoke-RetryPendingPushes consumes these.
#
#   parked_recovered ─→ Same as parked, but reached via crash recovery.
#                       Behaviourally identical; the tag is for forensics.
# ==============================================================================

function Get-PendingDrainSummaryPath {
    if ($script:LocalStateLayout -and $script:LocalStateLayout.Progress) {
        return (Join-Path ([string]$script:LocalStateLayout.Progress) 'pending_drain_summary.json')
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$LocalPendingPush)) {
        $stateRoot = Split-Path -Parent ([string]$LocalPendingPush)
        if (-not [string]::IsNullOrWhiteSpace([string]$stateRoot)) {
            return (Join-Path (Join-Path $stateRoot 'Progress') 'pending_drain_summary.json')
        }
    }
    return $null
}

function Write-PendingDrainSummary {
    param(
        [Parameter(Mandatory)] $Summary
    )

    $path = Get-PendingDrainSummaryPath
    if ([string]::IsNullOrWhiteSpace([string]$path)) { return $false }
    $dir = Split-Path ([string]$path) -Parent
    if (-not (Test-Path -LiteralPath $dir)) {
        [System.IO.Directory]::CreateDirectory($dir) | Out-Null
    }
    $leaf = Split-Path ([string]$path) -Leaf
    $id = [guid]::NewGuid().ToString("N")
    $tmp = Join-Path $dir ".$leaf.$id.tmp"
    $backup = Join-Path $dir ".$leaf.$id.bak"
    try {
        $json = $Summary | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        [void](ConvertFrom-Json -InputObject ([System.IO.File]::ReadAllText($tmp, [System.Text.UTF8Encoding]::new($false))))
        if ([System.IO.File]::Exists([string]$path)) {
            [System.IO.File]::Replace($tmp, [string]$path, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, [string]$path)
        }
        return $true
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        Write-Log "Pending: could not write pending drain summary: $_" "WARN"
        return $false
    }
}

function Add-PendingDrainSummaryCount {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Counts,
        [string] $Key
    )

    $safeKey = if ([string]::IsNullOrWhiteSpace($Key)) { 'unknown' } else { $Key }
    if (-not $Counts.Contains($safeKey)) { $Counts[$safeKey] = 0 }
    $Counts[$safeKey] = [int]$Counts[$safeKey] + 1
}

function New-PendingDrainSummaryItem {
    param(
        $ManifestFile,
        $Manifest = $null,
        $Transaction = $null,
        [string] $Status = '',
        [string] $ErrorMessage = ''
    )

    $localFile = ''
    $serverOut = ''
    $route = ''
    $sourcePath = ''
    $publishMode = ''
    $transactionId = ''
    $sidecarCount = 0
    $recovered = $false
    if ($null -ne $Manifest) {
        $localFile = [string](Get-PendingObjectProperty -Object $Manifest -Name 'local_file')
        $serverOut = [string](Get-PendingObjectProperty -Object $Manifest -Name 'server_out')
        $route = [string](Get-PendingObjectProperty -Object $Manifest -Name 'route')
        $sourcePath = [string](Get-PendingObjectProperty -Object $Manifest -Name 'source_path')
        $publishMode = [string](Get-PendingObjectProperty -Object $Manifest -Name 'publish_mode')
        $transactionId = [string](Get-PendingObjectProperty -Object $Manifest -Name 'publish_transaction_id')
    }
    if ($null -ne $Transaction) {
        $Status = [string](Get-PendingObjectProperty -Object $Transaction -Name 'Status')
        $localFile = [string](Get-PendingObjectProperty -Object $Transaction -Name 'LocalFile')
        $serverOut = [string](Get-PendingObjectProperty -Object $Transaction -Name 'ServerOut')
        $route = [string](Get-PendingObjectProperty -Object $Transaction -Name 'Route')
        $sourcePath = [string](Get-PendingObjectProperty -Object $Transaction -Name 'SourcePath')
        $publishMode = [string](Get-PendingObjectProperty -Object $Transaction -Name 'PublishMode')
        $transactionId = [string](Get-PendingObjectProperty -Object $Transaction -Name 'PublishTransactionId')
        $sidecarCount = [int](Get-PendingObjectProperty -Object $Transaction -Name 'SidecarCount')
        $recovered = [bool](Get-PendingObjectProperty -Object $Transaction -Name 'Recovered')
        $transactionError = [string](Get-PendingObjectProperty -Object $Transaction -Name 'Error')
        if (-not [string]::IsNullOrWhiteSpace($transactionError)) { $ErrorMessage = $transactionError }
    }
    if ([string]::IsNullOrWhiteSpace($Status)) { $Status = 'unknown' }

    return [ordered]@{
        manifest_path          = if ($ManifestFile) { [string]$ManifestFile.FullName } else { '' }
        local_file             = $localFile
        server_out             = $serverOut
        source_path            = $sourcePath
        route                  = $route
        publish_mode           = $publishMode
        status                 = $Status
        recovered              = $recovered
        publish_transaction_id = $transactionId
        sidecar_count          = $sidecarCount
        error                  = $ErrorMessage
    }
}

function Complete-PendingDrainSummary {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Summary,
        [Parameter(Mandatory)] [System.Collections.IEnumerable] $Items
    )

    $statusCounts = [ordered]@{}
    $routeCounts = [ordered]@{}
    $succeeded = 0
    $alreadyPublished = 0
    $errors = 0
    foreach ($item in @($Items)) {
        $status = [string](Get-PendingObjectProperty -Object $item -Name 'status')
        $route = [string](Get-PendingObjectProperty -Object $item -Name 'route')
        Add-PendingDrainSummaryCount -Counts $statusCounts -Key $status
        Add-PendingDrainSummaryCount -Counts $routeCounts -Key $route
        switch ($status) {
            'succeeded' { $succeeded++ }
            'already_published' { $alreadyPublished++ }
            default {
                if ($status -notin @('skipped', 'deferred')) { $errors++ }
            }
        }
    }
    $Summary['completed_at'] = Get-Date -Format 'o'
    $Summary['items'] = @($Items)
    $Summary['status_counts'] = $statusCounts
    $Summary['route_counts'] = $routeCounts
    $Summary['succeeded_count'] = $succeeded
    $Summary['already_published_count'] = $alreadyPublished
    $Summary['error_count'] = $errors
    [void](Write-PendingDrainSummary -Summary $Summary)
}

function Invoke-ParkPendingPushWithTx3gSidecars {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [string] $ScratchPath,
        [array] $Tx3gTracks,
        [array] $BdpgsTracks = @(),
        [Parameter(Mandatory)] [string] $MediaOutputPath,
        [Parameter(Mandatory)] [hashtable] $ParkArgs,
        [string] $Context = '',
        [string] $FailureStage = 'subtitle-tx3g-publish'
    )

    $plan = New-Tx3gSrtSidecarPublishPlan -Tx3gTracks @($Tx3gTracks) -MediaOutputPath $MediaOutputPath -Context $Context
    if ($plan.Failures -and @($plan.Failures).Count -gt 0) {
        Register-Tx3gSubtitleFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Failures @($plan.Failures) -Stage $FailureStage
        return $false
    }

    $ParkArgs['SidecarFiles'] = @($plan.SidecarFiles)
    $ParkArgs['Tx3gSrtTracks'] = @($plan.Tracks)
    $ParkArgs['Tx3gSrtFailures'] = @($plan.Failures)
    $ParkArgs['BdpgsSrtFailures'] = @()
    $ParkArgs['Tx3gEmbeddedSrtTracks'] = @(ConvertTo-Tx3gEmbeddedSrtTrackRecords -Tx3gTracks @($Tx3gTracks))
    $ParkArgs['BdpgsEmbeddedSrtTracks'] = @(ConvertTo-BdpgsEmbeddedSrtTrackRecords -BdpgsTracks @($BdpgsTracks))
    $ParkArgs['Tx3gSrtConversionEnabled'] = [bool]$script:ConvertTx3gToSrt
    $ParkArgs['Tx3gExternalSrtSidecarsEnabled'] = [bool]$script:CreateExternalTx3gSrtSidecars
    $ParkArgs['DropTx3gAfterConversion'] = [bool]$script:DropTx3gAfterConversion
    $ParkArgs['BdpgsSrtConversionEnabled'] = [bool]$script:ConvertBdpgsToSrt
    $ParkArgs['DropBdpgsAfterConversion'] = [bool]$script:DropBdpgsAfterConversion
    if (-not $ParkArgs.ContainsKey('FolderPolicyMetadata') -and (Get-Command -Name Get-ActiveFolderPolicyMetadata -ErrorAction SilentlyContinue)) {
        $ParkArgs['FolderPolicyMetadata'] = Get-ActiveFolderPolicyMetadata
    }
    if (-not $ParkArgs.ContainsKey('RoutePlanMetadata') -and (Get-Command -Name Get-ActiveMediaRoutePlanMetadata -ErrorAction SilentlyContinue)) {
        $ParkArgs['RoutePlanMetadata'] = Get-ActiveMediaRoutePlanMetadata
    }
    return (Invoke-ParkPendingPush @ParkArgs)
}

# Move a completed local output into PendingServerPush\ with a sidecar
# manifest describing the intended publish. The sequence:
#
#   1. Build manifest with manifest_state='pending_move' and write it.
#   2. Move-Item the local output to the parked location.
#   3. Re-write the manifest with manifest_state='parked'.
#
# A crash between steps 1 and 2 leaves a manifest pointing at a not-yet-
# moved file; Repair-PendingManifestState handles that on the next run.
# A crash between steps 2 and 3 leaves the file in place but the manifest
# stale at 'pending_move' — Repair will re-find the file at local_file
# (since it's already moved) and proceed normally.
function Invoke-ParkPendingPush {
    param(
        [Parameter(Mandatory)] [string] $LocalOut,
        [Parameter(Mandatory)] [string] $ServerOut,
        [Parameter(Mandatory)] [string] $Route,
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $SourceIdentity,
        [string] $SourceIdentityV2,
        [string] $SourcePath,
        [object] $SourceSize,
        [string] $SourceMTimeUtc,
        [string] $PublishTransactionId,
        [string] $PublishMode = 'retry',
        [array] $SidecarFiles = @(),
        [array] $Tx3gSrtTracks = @(),
        [array] $Tx3gSrtFailures = @(),
        [array] $BdpgsSrtFailures = @(),
        [array] $Tx3gEmbeddedSrtTracks = @(),
        [array] $BdpgsEmbeddedSrtTracks = @(),
        [bool] $Tx3gSrtConversionEnabled = $false,
        [bool] $Tx3gExternalSrtSidecarsEnabled = $false,
        [bool] $DropTx3gAfterConversion = $false,
        [bool] $BdpgsSrtConversionEnabled = $false,
        [bool] $DropBdpgsAfterConversion = $false,
        [object] $FolderPolicyMetadata = $null,
        [object] $RoutePlanMetadata = $null,
        [string] $MediaType = ''
    )
    if (-not (Test-Path -LiteralPath $LocalOut)) {
        Write-Log "Park: local output vanished at $LocalOut — nothing to park" "WARN"
        return $false
    }

    $transaction = Invoke-PendingParkTransaction `
        -LocalOut $LocalOut `
        -ServerOut $ServerOut `
        -Route $Route `
        -RouteReasonCode $RouteReasonCode `
        -RouteReason $RouteReason `
        -SourceIdentity $SourceIdentity `
        -SourceIdentityV2 $SourceIdentityV2 `
        -SourcePath $SourcePath `
        -SourceSize $SourceSize `
        -SourceMTimeUtc $SourceMTimeUtc `
        -PublishTransactionId $PublishTransactionId `
        -PublishMode $PublishMode `
        -SidecarFiles @($SidecarFiles) `
        -Tx3gSrtTracks @($Tx3gSrtTracks) `
        -Tx3gSrtFailures @($Tx3gSrtFailures) `
        -BdpgsSrtFailures @($BdpgsSrtFailures) `
        -Tx3gEmbeddedSrtTracks @($Tx3gEmbeddedSrtTracks) `
        -BdpgsEmbeddedSrtTracks @($BdpgsEmbeddedSrtTracks) `
        -Tx3gSrtConversionEnabled:$Tx3gSrtConversionEnabled `
        -Tx3gExternalSrtSidecarsEnabled:$Tx3gExternalSrtSidecarsEnabled `
        -DropTx3gAfterConversion:$DropTx3gAfterConversion `
        -BdpgsSrtConversionEnabled:$BdpgsSrtConversionEnabled `
        -DropBdpgsAfterConversion:$DropBdpgsAfterConversion `
        -FolderPolicyMetadata $FolderPolicyMetadata `
        -RoutePlanMetadata $RoutePlanMetadata `
        -MediaType $MediaType

    if (-not $transaction.Ok) {
        Write-Log "Invoke-ParkPendingPush failed for $LocalOut : $($transaction.Error)" "ERROR"
        return $false
    }

    Refresh-PendingPublishIndex | Out-Null
    $parkLevel = if ($PublishMode -eq 'deferred') { 'INFO' } else { 'WARN' }
    Write-Log "Parked pending-push: $($transaction.Leaf) -> $($transaction.LocalFile)" $parkLevel
    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        Write-PipelineEvent -EventType 'publish_parked' -Stage 'pending-push-park' -Route $Route -Status $PublishMode -SourcePath $SourcePath -Data @{
            local_file             = [string]$transaction.LocalFile
            original_local_file    = [string]$transaction.OriginalLocalFile
            server_out             = [string]$transaction.ServerOut
            publish_transaction_id = [string]$transaction.PublishTransactionId
            manifest_path          = [string]$transaction.ManifestPath
            sidecar_count          = @($transaction.SidecarEntries).Count
            output_size            = $transaction.OutputSize
        } | Out-Null
    }
    return $true
}

# Re-attempt every parked push. Called at the start of each main-loop
# round (and via -DrainPendingPushes for manual intervention). For each
# manifest:
#
#   1. Stop-flag check.
#   2. If the local file vanished, mark the manifest missing_payload.
#   3. If the server already has a validated published copy
#      (Test-PendingPublishedServerCopy), discard the local copy.
#   4. Otherwise, robocopy local -> server partial, write the sidecar,
#      reveal the final media, and delete both local file + manifest only
#      after all publish steps succeed.
#
# Returns the number of manifests successfully drained. When
# DeferredPublish is set without -Force, returns 0 immediately —
# operator must explicitly drain via the dedicated CLI flag.
function Invoke-RetryPendingPushes {
    param([switch]$Force)

    if (-not (Test-Path -LiteralPath $LocalPendingPush)) { return 0 }
    $manifests = @(Get-ChildItem -LiteralPath $LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue)
    if ($manifests.Count -eq 0) { return 0 }
    $summaryItems = New-Object System.Collections.Generic.List[object]
    $summary = [ordered]@{
        schema_version          = 'pending_drain_summary.v1'
        started_at              = Get-Date -Format 'o'
        completed_at            = ''
        force                   = [bool]$Force
        pending_root            = [string]$LocalPendingPush
        manifest_count_at_start = [int]$manifests.Count
        attempted_count         = 0
        recovered_count         = 0
        succeeded_count         = 0
        already_published_count = 0
        error_count             = 0
        skipped_count           = 0
        remaining_count         = [int]$manifests.Count
        stopped                 = $false
        deferred                = $false
        status_counts           = [ordered]@{}
        route_counts            = [ordered]@{}
        items                   = @()
    }
    if ($script:DeferredPublish -and -not $Force) {
        Write-Log "Deferred publish enabled — leaving $($manifests.Count) parked output(s) queued for manual drain" "DEBUG"
        $summary['deferred'] = $true
        $summary['skipped_count'] = [int]$manifests.Count
        foreach ($m in $manifests) {
            $manifest = $null
            $readError = ''
            try { $manifest = Read-PendingManifestFile -Path $m.FullName } catch { $readError = [string]$_ }
            $summaryItems.Add((New-PendingDrainSummaryItem -ManifestFile $m -Manifest $manifest -Status 'deferred' -ErrorMessage $readError)) | Out-Null
        }
        Complete-PendingDrainSummary -Summary $summary -Items $summaryItems
        return 0
    }

    $recovered = 0
    $visitedCount = 0
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -PushState 'retrying' -Percent $null -SaveNow
    Write-Log "PendingServerPush: found $($manifests.Count) parked file(s) — retrying"
    foreach ($m in $manifests) {
        $manifest = $null
        try {
            if ($script:StopRequested -or (Test-Path -LiteralPath $StopFlag -ErrorAction SilentlyContinue)) {
                Write-Log "Pending: stop requested — leaving remaining parked outputs queued" "WARN"
                $script:StopRequested = $true
                $summary['stopped'] = $true
                $remainingToSkip = $manifests.Count - $visitedCount
                $summary['skipped_count'] = [int]$summary['skipped_count'] + $remainingToSkip
                for ($skipIndex = $visitedCount; $skipIndex -lt $manifests.Count; $skipIndex++) {
                    $summaryItems.Add((New-PendingDrainSummaryItem -ManifestFile $manifests[$skipIndex] -Status 'skipped')) | Out-Null
                }
                break
            }
            $visitedCount++
            $manifest = Read-PendingManifestFile -Path $m.FullName
            $local    = [string]$manifest.local_file
            $route    = [string]$manifest.route
            Set-ProgressItemContext -DisplayName (Split-Path $local -Leaf) -FilePath $local -MediaType 'pending' -QueuePhase 'pending_push' -QueueIndex $visitedCount -QueueTotal $manifests.Count
            Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'retrying' -Percent $null -SaveNow

            $summary['attempted_count'] = [int]$summary['attempted_count'] + 1
            $transaction = Invoke-PendingDrainTransaction -ManifestFile $m -Manifest $manifest
            $summaryItems.Add((New-PendingDrainSummaryItem -ManifestFile $m -Manifest $manifest -Transaction $transaction)) | Out-Null
            if ($transaction.Status -eq 'already_published' -or $transaction.Status -eq 'succeeded') {
                if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                    Write-PipelineEvent -EventType 'publish_drained' -Stage 'retry_pending_push' -Route ([string]$transaction.Route) -Status ([string]$transaction.Status) -SourcePath ([string]$transaction.SourcePath) -Data @{
                        local_file             = [string]$transaction.LocalFile
                        server_out             = [string]$transaction.ServerOut
                        manifest_path          = [string]$transaction.ManifestPath
                        publish_transaction_id = [string]$transaction.PublishTransactionId
                        sidecar_count          = [int]$transaction.SidecarCount
                    } | Out-Null
                }
            }
            if ($transaction.Recovered) {
                $recovered++
                $summary['recovered_count'] = [int]$summary['recovered_count'] + 1
            }
        } catch {
            Write-Log "Pending: error processing $($m.Name) : $_" "WARN"
            $summaryItems.Add((New-PendingDrainSummaryItem -ManifestFile $m -Manifest $manifest -Status 'error' -ErrorMessage ([string]$_))) | Out-Null
        } finally {
            Reset-ProgressItemContext
        }
    }
    Refresh-PendingPublishIndex | Out-Null
    if ($script:PendingPublishIndex -and $script:PendingPublishIndex.PSObject.Properties['Count']) {
        $summary['remaining_count'] = [int]$script:PendingPublishIndex.Count
    } else {
        $remaining = @(Get-ChildItem -LiteralPath $LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue)
        $summary['remaining_count'] = [int]$remaining.Count
    }
    $summary['recovered_count'] = [int]$recovered
    Complete-PendingDrainSummary -Summary $summary -Items $summaryItems
    Set-ProgressStage -Stage 'processing' -Status 'Processing' -PushState $null -SidecarState $null -Percent $null -SaveNow
    return $recovered
}
