# ==============================================================================
# ops\pipeline\engine\publish\pending_drain_transaction.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\publish\pending_transactions.ps1. Keep function names
# stable; pending_transactions.ps1 dot-sources this file as the public surface.
# ==============================================================================

function New-PendingDrainSidecarExtra {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $ServerPath,
        [Parameter(Mandatory)] [string] $PublishMode,
        [Parameter(Mandatory)] [string] $PublishTransactionId,
        $OutputSize
    )

    # S9 — propagate media_type from the parked manifest to the
    # deferred-publish sidecar so movies parked-and-drained match
    # the immediate-publish path. Defaults to '' for legacy manifests
    # parked before this fix; the desktop's CompletedJobRecord falls
    # back to path heuristics in that case.
    $manifestMediaType = ''
    $mediaTypeProp = $Manifest.PSObject.Properties['media_type']
    if ($mediaTypeProp -and -not [string]::IsNullOrWhiteSpace([string]$mediaTypeProp.Value)) {
        $manifestMediaType = [string]$mediaTypeProp.Value
    }

    $sidecarExtra = [ordered]@{
        output_path            = $ServerPath
        media_type             = $manifestMediaType
        route_reason_code      = if ($Manifest.PSObject.Properties['route_reason_code']) { [string]$Manifest.route_reason_code } else { '' }
        route_reason           = if ($Manifest.PSObject.Properties['route_reason']) { [string]$Manifest.route_reason } else { '' }
        publish_state          = 'published'
        publish_mode           = $PublishMode
        publish_transaction_id = $PublishTransactionId
        source_identity        = [string]$Manifest.source_identity
        source_identity_v2     = [string]$Manifest.source_identity_v2
        source_identity_v2_algorithm = if ([string]::IsNullOrWhiteSpace([string]$Manifest.source_identity_v2_algorithm)) { $script:SourceIdentityV2Algorithm } else { [string]$Manifest.source_identity_v2_algorithm }
        source_path            = [string]$Manifest.source_path
        source_size            = $Manifest.source_size
        source_mtime_utc       = [string]$Manifest.source_mtime_utc
        output_size            = $OutputSize
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$Manifest.parked_at)) {
        $sidecarExtra['encoded_at'] = [string]$Manifest.parked_at
    }
    $bdpgsFailureProp = $Manifest.PSObject.Properties['bdpgs_srt_failures']
    if ($bdpgsFailureProp) {
        $sidecarExtra['bdpgs_srt_failures'] = @($bdpgsFailureProp.Value)
    }
    $vobSubFailureProp = $Manifest.PSObject.Properties['vobsub_srt_failures']
    if ($vobSubFailureProp) {
        $sidecarExtra['vobsub_srt_failures'] = @($vobSubFailureProp.Value)
    }
    $embeddedTx3gProp = $Manifest.PSObject.Properties['tx3g_embedded_srt_tracks']
    if ($embeddedTx3gProp) {
        $sidecarExtra['tx3g_embedded_srt_tracks'] = @($embeddedTx3gProp.Value)
    }
    $embeddedBdpgsProp = $Manifest.PSObject.Properties['bdpgs_embedded_srt_tracks']
    if ($embeddedBdpgsProp) {
        $sidecarExtra['bdpgs_embedded_srt_tracks'] = @($embeddedBdpgsProp.Value)
    }
    $embeddedVobSubProp = $Manifest.PSObject.Properties['vobsub_embedded_srt_tracks']
    if ($embeddedVobSubProp) {
        $sidecarExtra['vobsub_embedded_srt_tracks'] = @($embeddedVobSubProp.Value)
    }
    foreach ($policyKey in @('tx3g_srt_conversion_enabled', 'tx3g_external_srt_sidecars_enabled', 'drop_tx3g_after_conversion', 'bdpgs_srt_conversion_enabled', 'drop_bdpgs_after_conversion', 'vobsub_srt_conversion_enabled', 'drop_vobsub_after_conversion')) {
        $policyProp = $Manifest.PSObject.Properties[$policyKey]
        if ($policyProp) {
            $sidecarExtra[$policyKey] = [bool]$policyProp.Value
        }
    }
    $folderPolicyProp = $Manifest.PSObject.Properties['folder_policy']
    if ($folderPolicyProp) {
        $sidecarExtra['folder_policy'] = $folderPolicyProp.Value
    }
    $routePlanProp = $Manifest.PSObject.Properties['route_plan']
    if ($routePlanProp) {
        if (Get-Command -Name Add-MediaRoutePlanMetadataToMap -ErrorAction SilentlyContinue) {
            Add-MediaRoutePlanMetadataToMap -Map $sidecarExtra -Metadata $routePlanProp.Value | Out-Null
        } else {
            $sidecarExtra['route_plan'] = $routePlanProp.Value
        }
    }
    return $sidecarExtra
}

function Remove-PendingDrainLocalArtifacts {
    param(
        [Parameter(Mandatory)] $Manifest,
        [Parameter(Mandatory)] [string] $LocalPath,
        [Parameter(Mandatory)] [string] $ManifestPath
    )

    $artifactRoot = Split-Path -Parent $ManifestPath
    if ([string]::IsNullOrWhiteSpace($artifactRoot)) {
        Write-Log "Pending: refusing local cleanup because manifest root is empty: $ManifestPath" "ERROR"
        return
    }

    $removeIfSafe = {
        param([string]$Path, [string]$Label)
        if ([string]::IsNullOrWhiteSpace($Path)) { return }
        $boundary = Test-MediaPipelinePathBoundarySafe -Path $Path -Root $artifactRoot
        if (-not $boundary.Ok) {
            Write-Log "Pending: refusing cleanup for unsafe $Label path ($($boundary.ReasonCode)): $Path" "ERROR"
            return
        }
        Remove-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    }

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $sidecarLocal = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
        if ($sidecarLocal) {
            & $removeIfSafe $sidecarLocal 'sidecar'
        }
    }
    & $removeIfSafe $LocalPath 'local media'
    & $removeIfSafe $ManifestPath 'manifest'
}

function Invoke-PendingDrainTransaction {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $local = [string]$Manifest.local_file
    $server = [string]$Manifest.server_out
    $route = [string]$Manifest.route
    $publishMode = if ([string]::IsNullOrWhiteSpace([string]$Manifest.publish_mode)) { 'retry' } else { [string]$Manifest.publish_mode }
    $manifestPath = $ManifestFile.FullName

    $result = [ordered]@{
        Status = 'failed'
        Recovered = $false
        LocalFile = $local
        ServerOut = $server
        Route = $route
        PublishMode = $publishMode
        SourcePath = [string]$Manifest.source_path
        ManifestPath = $manifestPath
        PublishTransactionId = [string]$Manifest.publish_transaction_id
        SidecarCount = 0
        Error = ''
    }

    if (Get-Command -Name Test-PendingManifestTrustedForDrain -ErrorAction SilentlyContinue) {
        $drainTrust = Test-PendingManifestTrustedForDrain -ManifestFile $ManifestFile -Manifest $Manifest
        if (-not $drainTrust.Ok) {
            Write-Log "Pending: refusing drain for untrusted manifest $($ManifestFile.Name): $($drainTrust.Reason)" "ERROR"
            $result.Status = $drainTrust.Status
            $result.Error = $drainTrust.Reason
            return [pscustomobject]$result
        }
    }

    if (-not (Test-Path -LiteralPath $local)) {
        $reason = "Pending parked local file is missing: $local"
        Write-Log "Pending: $reason; leaving manifest queued as missing_payload: $($ManifestFile.Name)" "ERROR"
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'missing_payload' -Reason $reason -Stage 'retry_pending_push'
        $result.Status = 'missing_payload'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    if (Test-Path -LiteralPath $server) {
        if (Test-PendingPublishedServerCopy -Manifest $Manifest -LocalPath $local -ServerPath $server) {
            Write-Log "Pending: server already has a validated published copy for $server - discarding local parked copy"
            Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
            $result.Status = 'already_published'
            return [pscustomobject]$result
        }
        Write-Log "Pending: server path exists but is not a validated publish; replacing via transactional copy" "WARN"
    }

    $srvDir = Split-Path $server -Parent
    if ($srvDir -and -not (Test-Path -LiteralPath $srvDir)) {
        try { [System.IO.Directory]::CreateDirectory($srvDir) | Out-Null } catch {}
    }
    $publishTxn = if ([string]::IsNullOrWhiteSpace([string]$Manifest.publish_transaction_id)) { New-PublishTransactionId } else { [string]$Manifest.publish_transaction_id }
    $result.PublishTransactionId = $publishTxn
    $serverPartial = New-PublishPartialMediaPath -ServerOut $server -PublishTransactionId $publishTxn
    Remove-PublishPartialMedia -Path $serverPartial

    Write-Log "Pending: retrying push $(Split-Path $local -Leaf) -> $server via publish partial"
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copying' -Percent 0 -SaveNow
    if (-not (Copy-FileRobocopy $local $serverPartial)) {
        Remove-PublishPartialMedia -Path $serverPartial
        $copyReason = Get-PublishCopyFailureReason
        if ([string]::IsNullOrWhiteSpace($copyReason)) { $copyReason = 'Pending media partial copy failed' }
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_copy_failed' -Reason $copyReason -Stage 'retry_pending_push'
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: still cannot push $(Split-Path $local -Leaf) - will retry next round" "WARN"
        $result.Status = 'copy_failed'
        $result.Error = $copyReason
        return [pscustomobject]$result
    }

    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copied_pending_reveal' -Percent 95 -SaveNow
    $serverSize = Get-FileLengthOrNull $serverPartial
    $sidecarExtra = New-PendingDrainSidecarExtra -Manifest $Manifest -ServerPath $server -PublishMode $publishMode -PublishTransactionId $publishTxn -OutputSize $serverSize
    $pendingSidecars = Publish-PendingSidecarFiles -Manifest $Manifest -PublishTransactionId $publishTxn
    if ($pendingSidecars.Failures -and @($pendingSidecars.Failures).Count -gt 0) {
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        $failureList = @($pendingSidecars.Failures | Where-Object { $null -ne $_ })
        $firstFailure = $failureList[0]
        $reason = if ($firstFailure -and $firstFailure.Reason) {
            "Pending tx3g SRT sidecar publish failed: $($firstFailure.Reason)"
        } else {
            'Pending tx3g SRT sidecar publish failed'
        }
        $failureSourcePath = if ([string]::IsNullOrWhiteSpace([string]$Manifest.source_path)) { $local } else { [string]$Manifest.source_path }
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_file_failed' -Reason $reason -Stage 'pending-tx3g-sidecar' -Tx3gFailures $failureList
        Add-RoundFailureRecord -SourcePath $failureSourcePath -Stage 'pending-tx3g-sidecar' -Reason $reason -Classification 'transient' -ErrorCode 'SUBTITLE_TX3G_SRT_PUBLISH_FAILED' -ArtifactPath $local -SuggestedAction 'Inspect the PendingServerPush manifest and parked tx3g SRT files. Restore missing sidecar files or rerun the source so tx3g extraction can recreate them.'
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Remove-PublishPartialMedia -Path $serverPartial
        Write-Log "Pending: partial media copy ok but tx3g sidecar publish failed - removed partial and left manifest/local copy for next retry" "WARN"
        $result.Status = 'sidecar_file_failed'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    $sidecarExtra['tx3g_srt_tracks'] = @($pendingSidecars.Tracks)
    $sidecarExtra['tx3g_srt_failures'] = @($pendingSidecars.Failures)

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'writing' -Percent $null -SaveNow
    $publishSidecarBackup = Backup-PublishSidecarForReveal -OutputPath $server -PublishTransactionId $publishTxn -Context 'Pending: '
    if (-not (Write-Sidecar -OutputPath $server -Route $route -Extra $sidecarExtra -SkipCompletedManifest)) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -BackupPath $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_failed' -Reason 'Pending sidecar write failed before final media reveal' -Stage 'sidecar'
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: partial media copy ok but sidecar failed - removed partial and left manifest/local copy for next retry" "WARN"
        $result.Status = 'sidecar_failed'
        $result.Error = 'Pending sidecar write failed before final media reveal'
        return [pscustomobject]$result
    }

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'complete' -Percent 100 -SaveNow
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'revealing' -Percent 99 -SaveNow
    if (-not (Complete-PublishMediaReveal -PartialPath $serverPartial -FinalPath $server -PublishTransactionId $publishTxn -Context 'Pending: ')) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -BackupPath $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_reveal_failed' -Reason 'Server partial copy and sidecar write succeeded but final media reveal failed' -Stage 'retry_pending_push'
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: reveal failed - restored/removed sidecar, removed partial, and left manifest/local copy for next retry" "WARN"
        $result.Status = 'reveal_failed'
        $result.Error = 'Server partial copy and sidecar write succeeded but final media reveal failed'
        return [pscustomobject]$result
    }

    Remove-PublishSidecarBackup -BackupPath $publishSidecarBackup
    Complete-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published)
    Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server | Out-Null
    Write-OutputSummary -FilePath $server -Route $route
    Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
    Write-Log "Pending: successfully pushed $(Split-Path $server -Leaf)"
    $result.Status = 'succeeded'
    $result.Recovered = $true
    $result.SidecarCount = @($pendingSidecars.Tracks).Count
    return [pscustomobject]$result
}
