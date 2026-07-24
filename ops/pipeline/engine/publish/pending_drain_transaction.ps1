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
        output_sha256          = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256')
        output_hash_algorithm  = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_hash_algorithm')
        pending_copy_proof     = if ([string]::IsNullOrWhiteSpace([string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256'))) { 'legacy_weak_copy_proof' } else { 'sha256_verified' }
        replacement_existing_final = [bool](Test-Path -LiteralPath $ServerPath -PathType Leaf -ErrorAction SilentlyContinue)
        replacement_transaction_id = $PublishTransactionId
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

    $lock = Enter-PendingPublishTransactionLock -ManifestPath $ManifestFile.FullName
    if ($null -eq $lock) {
        return [pscustomobject]([ordered]@{
            Status = 'duplicate_request'
            Recovered = $false
            LocalFile = [string]$Manifest.local_file
            ServerOut = [string]$Manifest.server_out
            Route = [string]$Manifest.route
            PublishMode = [string]$Manifest.publish_mode
            SourcePath = [string]$Manifest.source_path
            ManifestPath = [string]$ManifestFile.FullName
            PublishTransactionId = [string]$Manifest.publish_transaction_id
            SidecarCount = 0
            Error = 'Another drain transaction holds the manifest lock; no files were changed.'
        })
    }
    try {
        try {
            $lockedManifest = Read-PendingManifestFile -Path $ManifestFile.FullName
        } catch {
            return [pscustomobject]([ordered]@{
                Status = 'invalid_manifest'; Recovered = $false; LocalFile = [string]$Manifest.local_file
                ServerOut = [string]$Manifest.server_out; Route = [string]$Manifest.route
                PublishMode = [string]$Manifest.publish_mode; SourcePath = [string]$Manifest.source_path
                ManifestPath = [string]$ManifestFile.FullName; PublishTransactionId = [string]$Manifest.publish_transaction_id
                SidecarCount = 0; Error = "Pending manifest could not be re-read under its transaction lock: $_"
            })
        }
        $drainTrust = Test-PendingManifestTrustedForDrain -ManifestFile $ManifestFile -Manifest $lockedManifest
        if (-not $drainTrust.Ok) {
            return Invoke-PendingDrainTransactionCore -ManifestFile $ManifestFile -Manifest $lockedManifest
        }

        $lockedServer = [string](Get-PendingObjectProperty -Object $lockedManifest -Name 'server_out')
        $destinationLock = Enter-PendingPublishDestinationLock -ManifestPath $ManifestFile.FullName -ServerOut $lockedServer
        if ($null -eq $destinationLock) {
            return [pscustomobject]([ordered]@{
                Status = 'destination_lock_unavailable'; Recovered = $false; LocalFile = [string]$lockedManifest.local_file
                ServerOut = $lockedServer; Route = [string]$lockedManifest.route
                PublishMode = [string]$lockedManifest.publish_mode; SourcePath = [string]$lockedManifest.source_path
                ManifestPath = [string]$ManifestFile.FullName; PublishTransactionId = [string]$lockedManifest.publish_transaction_id
                SidecarCount = 0; Error = 'Another transaction holds the canonical destination lock, or the lock could not be opened; no files were changed.'
            })
        }
        try {
            $lockedManifest = Read-PendingManifestFile -Path $ManifestFile.FullName
            $reReadServer = [string](Get-PendingObjectProperty -Object $lockedManifest -Name 'server_out')
            if ((Get-PendingPublishDestinationIdentity -ServerOut $reReadServer) -ne [string]$destinationLock.Identity) {
                return [pscustomobject]([ordered]@{
                    Status = 'manifest_changed'; Recovered = $false; LocalFile = [string]$lockedManifest.local_file
                    ServerOut = $reReadServer; Route = [string]$lockedManifest.route
                    PublishMode = [string]$lockedManifest.publish_mode; SourcePath = [string]$lockedManifest.source_path
                    ManifestPath = [string]$ManifestFile.FullName; PublishTransactionId = [string]$lockedManifest.publish_transaction_id
                    SidecarCount = 0; Error = 'Pending destination identity changed while locks were acquired; no files were changed.'
                })
            }
            return Invoke-PendingDrainTransactionCore -ManifestFile $ManifestFile -Manifest $lockedManifest
        } finally {
            Exit-PendingPublishDestinationLock -Lock $destinationLock
        }
    } finally {
        Exit-PendingPublishTransactionLock -Lock $lock
    }
}

function Invoke-PendingDrainTransactionCore {
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

    $attemptId = [guid]::NewGuid().ToString('N')
    $duplicateDestinations = @(Get-PendingPublishDuplicateDestinationManifestPaths -ManifestPath $manifestPath -ServerOut $server)
    if ($duplicateDestinations.Count -gt 0) {
        $reason = "Duplicate pending manifests target the same canonical destination; reconcile before drain. Conflicts: $($duplicateDestinations -join ', ')"
        $Manifest = Update-PendingManifestReviewState -ManifestPath $manifestPath -Manifest $Manifest -State 'review_duplicate_destination' -Reason $reason -AttemptId $attemptId
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'duplicate_destination' -Error $reason | Out-Null
        Write-Log "Pending: $reason" 'ERROR'
        $result.Status = 'duplicate_destination'
        $result.Error = $reason
        return [pscustomobject]$result
    }
    try {
        $Manifest = Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'in_progress'
        $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'drain_attempt_started' -AttemptId $attemptId
    } catch {
        $result.Status = 'attempt_state_failed'
        $result.Error = "Could not persist pending drain attempt intent: $_"
        return [pscustomobject]$result
    }
    $expectedHash = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256')
    $hasStrongHashProof = -not [string]::IsNullOrWhiteSpace($expectedHash)

    if (-not (Test-Path -LiteralPath $local)) {
        $reason = "Pending parked local file is missing: $local"
        Write-Log "Pending: $reason; leaving manifest queued as missing_payload: $($ManifestFile.Name)" "ERROR"
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'missing_payload' -Reason $reason -Stage 'retry_pending_push'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'missing_payload' -Error $reason | Out-Null
        $result.Status = 'missing_payload'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    if (Test-Path -LiteralPath $server) {
        if (Test-PendingPublishedServerCopy -Manifest $Manifest -LocalPath $local -ServerPath $server) {
            Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'before' -Context @{
                scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
            }
            $existingHash = Get-PendingFileSha256OrNull $server
            $existingHashMatches = $hasStrongHashProof -and -not [string]::IsNullOrWhiteSpace($existingHash) -and $existingHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)
            Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'after' -Context @{
                scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
            }
            if ($existingHashMatches) {
                Invoke-PendingPublishFaultPoint -Boundary 'completion_evidence_write' -Moment 'before' -Context @{
                    scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
                }
                $completedEntryAdded = Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server
                if (-not $completedEntryAdded) {
                    $reason = 'Existing final output is byte/sidecar verified, but durable completion evidence could not be written; retaining pending evidence.'
                    Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'completed_evidence_failed' -Error $reason | Out-Null
                    $result.Status = 'completion_evidence_failed'
                    $result.Error = $reason
                    return [pscustomobject]$result
                }
                $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'completion_evidence_written' -AttemptId $attemptId
                Invoke-PendingPublishFaultPoint -Boundary 'completion_evidence_write' -Moment 'after' -Context @{
                    scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
                }
                Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'already_published' | Out-Null
                Write-Log "Pending: server already has a fully verified published copy for $server - cleaning pending evidence"
                Invoke-PendingPublishFaultPoint -Boundary 'pending_cleanup' -Moment 'before' -Context @{
                    scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
                }
                Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
                Invoke-PendingPublishFaultPoint -Boundary 'pending_cleanup' -Moment 'after' -Context @{
                    scope = 'drain_existing_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
                }
                $result.Status = 'already_published'
                return [pscustomobject]$result
            }
        }
        $reason = 'Destination collision: existing final output is not an exact media, sidecar, and transaction match. No overwrite was attempted.'
        Update-PendingManifestReviewState -ManifestPath $manifestPath -Manifest $Manifest -State 'review_destination_collision' -Reason $reason -AttemptId $attemptId | Out-Null
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'destination_collision' -Error $reason | Out-Null
        Write-Log "Pending: $reason Path: $server" "ERROR"
        $result.Status = 'destination_collision'
        $result.Error = $reason
        return [pscustomobject]$result
    }

    $srvDir = Split-Path $server -Parent
    Invoke-PendingPublishFaultPoint -Boundary 'destination_availability' -Moment 'before' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; destination_root = $srvDir; attempt_id = $attemptId
    }
    if ($srvDir -and -not (Test-Path -LiteralPath $srvDir)) {
        try { [System.IO.Directory]::CreateDirectory($srvDir) | Out-Null } catch {
            $reason = "Destination unavailable before final placement: $($_.Exception.Message)"
            Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_destination_unavailable' -Reason $reason -Stage 'retry_pending_push'
            Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'destination_unavailable' -Error $reason | Out-Null
            $result.Status = 'destination_unavailable'
            $result.Error = $reason
            return [pscustomobject]$result
        }
    }
    if ([string]::IsNullOrWhiteSpace($srvDir) -or -not (Test-Path -LiteralPath $srvDir -PathType Container -ErrorAction SilentlyContinue)) {
        $reason = 'Destination unavailable before final placement.'
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_destination_unavailable' -Reason $reason -Stage 'retry_pending_push'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'destination_unavailable' -Error $reason | Out-Null
        $result.Status = 'destination_unavailable'
        $result.Error = $reason
        return [pscustomobject]$result
    }
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'destination_available' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'destination_availability' -Moment 'after' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; destination_root = $srvDir; attempt_id = $attemptId
    }
    $publishTxn = if ([string]::IsNullOrWhiteSpace([string]$Manifest.publish_transaction_id)) { New-PublishTransactionId } else { [string]$Manifest.publish_transaction_id }
    $priorFinalSize = if (Test-Path -LiteralPath $server -PathType Leaf -ErrorAction SilentlyContinue) { Get-FileLengthOrNull $server } else { 0 }
    $priorFinalHash = if ($priorFinalSize -gt 0) { Get-PendingFileSha256OrNull $server } else { '' }
    $result.PublishTransactionId = $publishTxn
    $serverPartial = New-PublishPartialMediaPath -ServerOut $server -PublishTransactionId $publishTxn
    Remove-PublishPartialMedia -Path $serverPartial

    Write-Log "Pending: retrying push $(Split-Path $local -Leaf) -> $server via publish partial"
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copying' -Percent 0 -SaveNow
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'final_placement_started' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'final_placement' -Moment 'before' -Context @{
        scope = 'drain_partial'; manifest_path = $manifestPath; partial_path = $serverPartial; attempt_id = $attemptId
    }
    if (-not (Copy-FileRobocopy $local $serverPartial)) {
        Remove-PublishPartialMedia -Path $serverPartial
        $copyReason = Get-PublishCopyFailureReason
        if ([string]::IsNullOrWhiteSpace($copyReason)) { $copyReason = 'Pending media partial copy failed' }
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_copy_failed' -Reason $copyReason -Stage 'retry_pending_push'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'copy_failed' -Error $copyReason | Out-Null
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: still cannot push $(Split-Path $local -Leaf) - will retry next round" "WARN"
        $result.Status = 'copy_failed'
        $result.Error = $copyReason
        return [pscustomobject]$result
    }
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'final_partial_copied' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'final_placement' -Moment 'after' -Context @{
        scope = 'drain_partial'; manifest_path = $manifestPath; partial_path = $serverPartial; attempt_id = $attemptId
    }

    if ($hasStrongHashProof) {
        Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'before' -Context @{
            scope = 'drain_partial'; manifest_path = $manifestPath; partial_path = $serverPartial; attempt_id = $attemptId
        }
        $partialHash = Get-PendingFileSha256OrNull $serverPartial
        if ([string]::IsNullOrWhiteSpace($partialHash) -or -not $partialHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
            $reason = "Pending partial copy SHA-256 mismatch (expected $expectedHash; got $partialHash)"
            Remove-PublishPartialMedia -Path $serverPartial
            Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_copy_failed' -Reason $reason -Stage 'retry_pending_push'
            Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'partial_hash_mismatch' -Error $reason | Out-Null
            $result.Status = 'partial_hash_mismatch'
            $result.Error = $reason
            return [pscustomobject]$result
        }
        $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'final_partial_verified' -AttemptId $attemptId
        Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'after' -Context @{
            scope = 'drain_partial'; manifest_path = $manifestPath; partial_path = $serverPartial; attempt_id = $attemptId
        }
    }

    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'copied_pending_reveal' -Percent 95 -SaveNow
    $serverSize = Get-FileLengthOrNull $serverPartial
    $sidecarExtra = New-PendingDrainSidecarExtra -Manifest $Manifest -ServerPath $server -PublishMode $publishMode -PublishTransactionId $publishTxn -OutputSize $serverSize
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'sidecar_staging_started' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'sidecar_staging' -Moment 'before' -Context @{
        scope = 'drain_all_sidecars'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }
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
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'sidecar_file_failed' -Error $reason | Out-Null
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
    $sidecarExtra['subtitle_conversion_results'] = @($Manifest.subtitle_conversion_results)

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'writing' -Percent $null -SaveNow
    $publishSidecarBackup = Backup-PublishSidecarForReveal -OutputPath $server -PublishTransactionId $publishTxn -Context 'Pending: '
    if (-not (Test-PublishSidecarBackupReadyForReveal -Backup $publishSidecarBackup)) {
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_backup_failed' -Reason 'Existing final sidecar could not be backed up before pending media reveal' -Stage 'sidecar'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'sidecar_backup_failed' -Error 'Existing final sidecar could not be backed up before pending media reveal' | Out-Null
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: existing publish sidecar backup failed - removed partial and left manifest/local copy for next retry" "ERROR"
        $result.Status = 'sidecar_backup_failed'
        $result.Error = 'Existing final sidecar could not be backed up before pending media reveal'
        return [pscustomobject]$result
    }
    if (-not (Write-Sidecar -OutputPath $server -Route $route -Extra $sidecarExtra -SkipCompletedManifest)) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -Backup $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_sidecar_failed' -Reason 'Pending sidecar write failed before final media reveal' -Stage 'sidecar'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'sidecar_failed' -Error 'Pending sidecar write failed before final media reveal' | Out-Null
        Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: partial media copy ok but sidecar failed - removed partial and left manifest/local copy for next retry" "WARN"
        $result.Status = 'sidecar_failed'
        $result.Error = 'Pending sidecar write failed before final media reveal'
        return [pscustomobject]$result
    }
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'sidecars_staged' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'sidecar_staging' -Moment 'after' -Context @{
        scope = 'drain_all_sidecars'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }

    Set-ProgressStage -Stage 'sidecar' -Status 'Retrying pending push' -Route $route -SidecarState 'complete' -Percent 100 -SaveNow
    Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'revealing' -Percent 99 -SaveNow
    Invoke-PendingPublishFaultPoint -Boundary 'atomic_reveal' -Moment 'before' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; partial_path = $serverPartial; server_out = $server; attempt_id = $attemptId
    }
    if (-not (Complete-PublishMediaReveal -PartialPath $serverPartial -FinalPath $server -PublishTransactionId $publishTxn -Context 'Pending: ' -KeepBackup)) {
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -Backup $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Remove-PublishPartialMedia -Path $serverPartial
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_reveal_failed' -Reason 'Server partial copy and sidecar write succeeded but final media reveal failed' -Stage 'retry_pending_push'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'reveal_failed' -Error 'Server partial copy and sidecar write succeeded but final media reveal failed' | Out-Null
        Set-ProgressStage -Stage 'retry_pending_push' -Status 'Retrying pending push' -Route $route -PushState 'failed' -Percent $null -SaveNow
        Write-Log "Pending: reveal failed - restored/removed sidecar, removed partial, and left manifest/local copy for next retry" "WARN"
        $result.Status = 'reveal_failed'
        $result.Error = 'Server partial copy and sidecar write succeeded but final media reveal failed'
        return [pscustomobject]$result
    }
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'final_revealed' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'atomic_reveal' -Moment 'after' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }

    $revealBackup = [string]$script:LastPublishRevealBackupPath
    $replacedExisting = [bool]$script:LastPublishRevealReplacedExisting
    if ($hasStrongHashProof) {
        Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'before' -Context @{
            scope = 'drain_revealed_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
        }
        $finalHash = Get-PendingFileSha256OrNull $server
        if ([string]::IsNullOrWhiteSpace($finalHash) -or -not $finalHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
            $reason = "Pending final output SHA-256 mismatch after reveal (expected $expectedHash; got $finalHash)"
            Restore-PublishMediaAfterRevealFailure -FinalPath $server -BackupPath $revealBackup -Context 'Pending: '
            Restore-PublishSidecarAfterRevealFailure -OutputPath $server -Backup $publishSidecarBackup -Context 'Pending: '
            Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
            Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_reveal_failed' -Reason $reason -Stage 'retry_pending_push'
            Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'final_hash_mismatch' -Error $reason | Out-Null
            $result.Status = 'final_hash_mismatch'
            $result.Error = $reason
            return [pscustomobject]$result
        }
        $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'final_verified' -AttemptId $attemptId
        Invoke-PendingPublishFaultPoint -Boundary 'byte_hash_verification' -Moment 'after' -Context @{
            scope = 'drain_revealed_final'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
        }
    }

    $Manifest = Update-PendingManifestReplacementEvidence -ManifestPath $manifestPath -Manifest $Manifest -ReplacedExisting:$replacedExisting -PriorSize $priorFinalSize -PriorSha256 $priorFinalHash -TransactionId $publishTxn

    Invoke-PendingPublishFaultPoint -Boundary 'completion_evidence_write' -Moment 'before' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }
    $completedEntryAdded = Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server
    if (-not $completedEntryAdded) {
        $reason = 'Completed manifest entry failed after final media reveal; retaining pending payload for retry.'
        Restore-PublishMediaAfterRevealFailure -FinalPath $server -BackupPath $revealBackup -Context 'Pending: '
        Restore-PublishSidecarAfterRevealFailure -OutputPath $server -Backup $publishSidecarBackup -Context 'Pending: '
        Undo-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published) -Context 'Pending: '
        Update-PendingManifestRetryState -ManifestPath $manifestPath -Manifest $Manifest -State 'retry_reveal_failed' -Reason $reason -Stage 'retry_pending_push'
        Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'completed_evidence_failed' -Error $reason | Out-Null
        $result.Status = 'completed_evidence_failed'
        $result.Error = $reason
        return [pscustomobject]$result
    }
    $Manifest = Update-PendingManifestTransactionPhase -ManifestPath $manifestPath -Manifest $Manifest -Phase 'completion_evidence_written' -AttemptId $attemptId
    Invoke-PendingPublishFaultPoint -Boundary 'completion_evidence_write' -Moment 'after' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }
    Remove-PublishSidecarBackup -BackupPath $publishSidecarBackup
    if ($revealBackup -and (Test-Path -LiteralPath $revealBackup -ErrorAction SilentlyContinue)) {
        Remove-Item -LiteralPath $revealBackup -Force -ErrorAction SilentlyContinue
    }
    Complete-PendingPublishedSidecarFiles -PublishedSidecars @($pendingSidecars.Published)
    Write-OutputSummary -FilePath $server -Route $route
    Update-PendingManifestDrainAttempt -ManifestPath $manifestPath -Manifest $Manifest -AttemptId $attemptId -Status 'succeeded' | Out-Null
    Invoke-PendingPublishFaultPoint -Boundary 'pending_cleanup' -Moment 'before' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }
    Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $manifestPath
    Invoke-PendingPublishFaultPoint -Boundary 'pending_cleanup' -Moment 'after' -Context @{
        scope = 'drain'; manifest_path = $manifestPath; server_out = $server; attempt_id = $attemptId
    }
    Write-Log "Pending: successfully pushed $(Split-Path $server -Leaf)"
    $result.Status = 'succeeded'
    $result.Recovered = $true
    $result.SidecarCount = @($pendingSidecars.Tracks).Count
    return [pscustomobject]$result
}
