# ==============================================================================
# ops\pipeline\engine\publish\pending_repair.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\publish\pending_transactions.ps1. Keep function names
# stable; pending_transactions.ps1 dot-sources this file as the public surface.
# ==============================================================================

function Repair-PendingSidecarArtifacts {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        $Manifest
    )

    foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
        $localFile = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
        $originalFile = [string](Get-PendingObjectProperty -Object $sidecar -Name 'original_local_file')
        if ([string]::IsNullOrWhiteSpace($localFile) -or
            (Test-Path -LiteralPath $localFile -ErrorAction SilentlyContinue)) {
            continue
        }
        if ([string]::IsNullOrWhiteSpace($originalFile) -or
            -not (Test-Path -LiteralPath $originalFile -ErrorAction SilentlyContinue)) {
            continue
        }
        if (Get-Command -Name Test-PendingSidecarTrustedForPublish -ErrorAction SilentlyContinue) {
            $sidecarTrust = Test-PendingSidecarTrustedForPublish -Manifest $Manifest -Sidecar $sidecar -ManifestPath $ManifestFile.FullName -AllowMissingLocal
            if (-not $sidecarTrust.Ok) {
                Write-Log "Pending publish index: refusing sidecar recovery for untrusted manifest $($ManifestFile.Name): $($sidecarTrust.Reason)" "ERROR"
                continue
            }
        }

        try {
            $localDir = Split-Path $localFile -Parent
            if ($localDir -and -not (Test-Path -LiteralPath $localDir)) {
                [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
            }
            $copy = Copy-SrtAtomic -SourcePath $originalFile -DestinationPath $localFile
            if (-not $copy.Ok) { throw $copy.Reason }
            $expectedHash = [string](Get-PendingObjectProperty -Object $sidecar -Name 'output_sha256')
            $actualHash = Get-PendingFileSha256OrNull -Path $localFile
            if ([string]::IsNullOrWhiteSpace($actualHash) -or -not $actualHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                Remove-Item -LiteralPath $localFile -Force -ErrorAction SilentlyContinue
                throw "recovered pending sidecar SHA-256 mismatch: $localFile"
            }
            Write-Log "Pending publish index: recovered parked sidecar from pending_move manifest: $($ManifestFile.Name)" "WARN"
        } catch {
            Write-Log "Pending publish index: failed to recover sidecar for $($ManifestFile.Name) : $_" "WARN"
        }
    }
    return $Manifest
}

function Repair-PendingManifestState {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $state = [string]$Manifest.manifest_state
    if ($state -eq 'pending_move' -and (Get-Command -Name Test-PendingManifestTrustedForRepair -ErrorAction SilentlyContinue)) {
        $repairTrust = Test-PendingManifestTrustedForRepair -ManifestFile $ManifestFile -Manifest $Manifest
        if (-not $repairTrust.Ok) {
            Write-Log "Pending publish index: refusing pending_move recovery for untrusted manifest $($ManifestFile.Name): $($repairTrust.Reason)" "ERROR"
            return $Manifest
        }
    }

    $Manifest = Repair-PendingSidecarArtifacts -ManifestFile $ManifestFile -Manifest $Manifest
    $localFile = [string]$Manifest.local_file
    $original = [string]$Manifest.original_local_file
    if ($state -ne 'pending_move' -or [string]::IsNullOrWhiteSpace($localFile)) {
        return $Manifest
    }

    try {
        if (-not (Test-Path -LiteralPath $localFile -ErrorAction SilentlyContinue)) {
            if ([string]::IsNullOrWhiteSpace($original) -or -not (Test-Path -LiteralPath $original -ErrorAction SilentlyContinue)) {
                return $Manifest
            }
            $localDir = Split-Path $localFile -Parent
            if ($localDir -and -not (Test-Path -LiteralPath $localDir)) {
                [System.IO.Directory]::CreateDirectory($localDir) | Out-Null
            }
            [System.IO.File]::Move($original, $localFile, $true)
        }
        $expectedHash = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256')
        $actualHash = Get-PendingFileSha256OrNull -Path $localFile
        if ([string]::IsNullOrWhiteSpace($actualHash) -or -not $actualHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
            $reason = "Recovered pending media SHA-256 mismatch: $localFile"
            Update-PendingManifestReviewState -ManifestPath $ManifestFile.FullName -Manifest $Manifest -State 'review_pending_payload_mismatch' -Reason $reason | Out-Null
            Write-Log "Pending publish index: $reason" 'ERROR'
            return (Read-PendingManifestFile -Path $ManifestFile.FullName)
        }
        foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
            $sidecarLocal = [string](Get-PendingObjectProperty -Object $sidecar -Name 'local_file')
            $sidecarExpectedHash = [string](Get-PendingObjectProperty -Object $sidecar -Name 'output_sha256')
            $sidecarActualHash = Get-PendingFileSha256OrNull -Path $sidecarLocal
            if ([string]::IsNullOrWhiteSpace($sidecarActualHash) -or -not $sidecarActualHash.Equals($sidecarExpectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                $reason = "Recovered pending sidecar SHA-256 mismatch: $sidecarLocal"
                Update-PendingManifestReviewState -ManifestPath $ManifestFile.FullName -Manifest $Manifest -State 'review_pending_sidecar_mismatch' -Reason $reason | Out-Null
                Write-Log "Pending publish index: $reason" 'ERROR'
                return (Read-PendingManifestFile -Path $ManifestFile.FullName)
            }
        }
        $map = ConvertTo-PendingManifestMap $Manifest
        $map['manifest_state'] = 'parked_recovered'
        $map['recovered_at'] = (Get-Date -Format 'o')
        $map['transaction_phase'] = 'parked_recovered'
        $map['transaction_phase_at'] = (Get-Date -Format 'o')
        Write-PendingManifestFile -Path $ManifestFile.FullName -Manifest $map | Out-Null
        Write-Log "Pending publish index: recovered parked output from pending_move manifest: $($ManifestFile.Name)" "WARN"
        return (Read-PendingManifestFile -Path $ManifestFile.FullName)
    } catch {
        Write-Log "Pending publish index: failed to recover pending_move manifest $($ManifestFile.Name) : $_" "WARN"
        return $Manifest
    }
}

function Get-PendingDrainPipelineSidecarBackupPath {
    param(
        [Parameter(Mandatory)] [string] $ServerPath,
        [Parameter(Mandatory)] [string] $TransactionId
    )

    $sidecarPath = Get-SidecarPath $ServerPath
    $dir = Split-Path -Parent $sidecarPath
    return (Join-Path $dir ('.{0}.mp-publish-sidecar-backup.{1}' -f (Split-Path -Leaf $sidecarPath), $TransactionId))
}

function Test-PendingDrainFinalProof {
    param([Parameter(Mandatory)] $Manifest)

    $local = [string](Get-PendingObjectProperty -Object $Manifest -Name 'local_file')
    $server = [string](Get-PendingObjectProperty -Object $Manifest -Name 'server_out')
    $expectedHash = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256')
    if (-not (Test-Path -LiteralPath $server -PathType Leaf -ErrorAction SilentlyContinue)) { return $false }
    $actualHash = Get-PendingFileSha256OrNull -Path $server
    if ([string]::IsNullOrWhiteSpace($actualHash) -or [string]::IsNullOrWhiteSpace($expectedHash) -or -not $actualHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    return [bool](Test-PendingPublishedServerCopy -Manifest $Manifest -LocalPath $local -ServerPath $server)
}

function Restore-PendingStaleDrainArtifacts {
    param([Parameter(Mandatory)] $Manifest)

    $server = [string](Get-PendingObjectProperty -Object $Manifest -Name 'server_out')
    $transactionId = [string](Get-PendingObjectProperty -Object $Manifest -Name 'publish_transaction_id')
    $expectedHash = [string](Get-PendingObjectProperty -Object $Manifest -Name 'output_sha256')
    try {
        $partialPath = New-PublishPartialMediaPath -ServerOut $server -PublishTransactionId $transactionId
        Remove-PublishPartialMedia -Path $partialPath
        if (Test-Path -LiteralPath $partialPath -PathType Leaf -ErrorAction SilentlyContinue) {
            throw "stale final partial could not be removed: $partialPath"
        }

        $finalBackup = Join-Path (Split-Path -Parent $server) ('.{0}.mp-publish-backup.{1}' -f (Split-Path -Leaf $server), $transactionId)
        if (Test-Path -LiteralPath $server -PathType Leaf -ErrorAction SilentlyContinue) {
            $actualHash = Get-PendingFileSha256OrNull -Path $server
            if ([string]::IsNullOrWhiteSpace($actualHash) -or -not $actualHash.Equals($expectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                return [pscustomobject]@{ Ok = $false; Reason = 'Existing final bytes do not match the pending transaction; automatic rollback is unsafe.' }
            }
            Restore-PublishMediaAfterRevealFailure -FinalPath $server -BackupPath $finalBackup -Context 'Pending recovery: '
        } elseif (Test-Path -LiteralPath $finalBackup -PathType Leaf -ErrorAction SilentlyContinue) {
            [System.IO.File]::Move($finalBackup, $server, $true)
        }

        foreach ($sidecar in @(Get-PendingSidecarEntries -Manifest $Manifest)) {
            $sidecarServer = [string](Get-PendingObjectProperty -Object $sidecar -Name 'server_out')
            $sidecarExpectedHash = [string](Get-PendingObjectProperty -Object $sidecar -Name 'output_sha256')
            $sidecarBackup = New-PendingSidecarBackupPath -SidecarPath $sidecarServer -PublishTransactionId $transactionId
            if (Test-Path -LiteralPath $sidecarBackup -PathType Leaf -ErrorAction SilentlyContinue) {
                Restore-PendingSidecarBackupIntoPlace -BackupPath $sidecarBackup -DestinationPath $sidecarServer -Context 'Pending recovery: '
                continue
            }
            if (Test-Path -LiteralPath $sidecarServer -PathType Leaf -ErrorAction SilentlyContinue) {
                $sidecarActualHash = Get-PendingFileSha256OrNull -Path $sidecarServer
                if (-not [string]::IsNullOrWhiteSpace($sidecarActualHash) -and $sidecarActualHash.Equals($sidecarExpectedHash, [System.StringComparison]::OrdinalIgnoreCase)) {
                    Remove-Item -LiteralPath $sidecarServer -Force -ErrorAction Stop
                } else {
                    return [pscustomobject]@{ Ok = $false; Reason = "Existing sidecar bytes are ambiguous; automatic rollback is unsafe: $sidecarServer" }
                }
            }
        }

        $pipelineSidecar = Get-SidecarPath $server
        $pipelineSidecarBackup = Get-PendingDrainPipelineSidecarBackupPath -ServerPath $server -TransactionId $transactionId
        if (Test-Path -LiteralPath $pipelineSidecarBackup -PathType Leaf -ErrorAction SilentlyContinue) {
            Move-PublishSidecarBackupIntoPlace -BackupPath $pipelineSidecarBackup -SidecarPath $pipelineSidecar -Context 'Pending recovery: '
        } elseif (Test-Path -LiteralPath $pipelineSidecar -PathType Leaf -ErrorAction SilentlyContinue) {
            $removePipelineSidecar = $false
            try {
                $sidecarPayload = Get-Content -LiteralPath $pipelineSidecar -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
                $removePipelineSidecar = [string]$sidecarPayload.publish_transaction_id -eq $transactionId
            } catch {}
            if ($removePipelineSidecar) {
                Remove-Item -LiteralPath $pipelineSidecar -Force -ErrorAction Stop
            } else {
                return [pscustomobject]@{ Ok = $false; Reason = "Existing pipeline sidecar is ambiguous; automatic rollback is unsafe: $pipelineSidecar" }
            }
        }
        return [pscustomobject]@{ Ok = $true; Reason = 'stale attempt artifacts rolled back' }
    } catch {
        return [pscustomobject]@{ Ok = $false; Reason = [string]$_ }
    }
}

function Repair-PendingStaleDrainAttempt {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $ManifestFile,
        [Parameter(Mandatory)] $Manifest
    )

    $lock = Enter-PendingPublishTransactionLock -ManifestPath $ManifestFile.FullName
    if ($null -eq $lock) {
        return [pscustomobject]@{ Status = 'busy'; Reason = 'A live drain transaction holds the manifest lock.'; Manifest = $Manifest; Cleaned = $false }
    }
    try {
        $contract = Test-PendingManifestCurrentContractFields -Manifest $Manifest -ManifestPath $ManifestFile.FullName
        if (-not $contract.Ok) {
            return [pscustomobject]@{ Status = 'blocked'; Reason = [string]$contract.Reason; Manifest = $Manifest; Cleaned = $false }
        }
        $destination = Test-PendingManifestDestinationTrusted -Manifest $Manifest -ManifestPath $ManifestFile.FullName
        if (-not $destination.Ok) {
            return [pscustomobject]@{ Status = 'blocked'; Reason = [string]$destination.Reason; Manifest = $Manifest; Cleaned = $false }
        }

        $server = [string](Get-PendingObjectProperty -Object $Manifest -Name 'server_out')
        $destinationLock = Enter-PendingPublishDestinationLock -ManifestPath $ManifestFile.FullName -ServerOut $server
        if ($null -eq $destinationLock) {
            return [pscustomobject]@{ Status = 'busy'; Reason = 'A live transaction holds the canonical destination lock, or the lock could not be opened.'; Manifest = $Manifest; Cleaned = $false }
        }
        try {
            $Manifest = Read-PendingManifestFile -Path $ManifestFile.FullName
            $lockedContract = Test-PendingManifestCurrentContractFields -Manifest $Manifest -ManifestPath $ManifestFile.FullName
            $lockedDestination = Test-PendingManifestDestinationTrusted -Manifest $Manifest -ManifestPath $ManifestFile.FullName
            $lockedServer = [string](Get-PendingObjectProperty -Object $Manifest -Name 'server_out')
            if (-not $lockedContract.Ok -or -not $lockedDestination.Ok -or (Get-PendingPublishDestinationIdentity -ServerOut $lockedServer) -ne [string]$destinationLock.Identity) {
                return [pscustomobject]@{ Status = 'blocked'; Reason = 'Pending manifest trust or destination identity changed while recovery locks were acquired.'; Manifest = $Manifest; Cleaned = $false }
            }
            $server = $lockedServer
            $local = [string](Get-PendingObjectProperty -Object $Manifest -Name 'local_file')
            $attemptId = [string](Get-PendingObjectProperty -Object $Manifest -Name 'drain_attempt_id')
            if (Test-PendingDrainFinalProof -Manifest $Manifest) {
                if (-not (Add-CompletedJobsManifestEntryFromSidecar -OutputPath $server)) {
                    $reason = 'Recovered final output is fully verified, but durable completion evidence could not be written.'
                    $updated = Update-PendingManifestReviewState -ManifestPath $ManifestFile.FullName -Manifest $Manifest -State 'review_completion_evidence_failed' -Reason $reason -AttemptId $attemptId
                    return [pscustomobject]@{ Status = 'review'; Reason = $reason; Manifest = $updated; Cleaned = $false }
                }
                Update-PendingManifestDrainAttempt -ManifestPath $ManifestFile.FullName -Manifest $Manifest -AttemptId $attemptId -Status 'recovered_completed' | Out-Null
                Remove-PendingDrainLocalArtifacts -Manifest $Manifest -LocalPath $local -ManifestPath $ManifestFile.FullName
                return [pscustomobject]@{ Status = 'recovered_completed'; Reason = ''; Manifest = $Manifest; Cleaned = $true }
            }

            $rollback = Restore-PendingStaleDrainArtifacts -Manifest $Manifest
            if (-not $rollback.Ok) {
                $updated = Update-PendingManifestReviewState -ManifestPath $ManifestFile.FullName -Manifest $Manifest -State 'review_ambiguous_drain' -Reason ([string]$rollback.Reason) -AttemptId $attemptId
                Update-PendingManifestDrainAttempt -ManifestPath $ManifestFile.FullName -Manifest $updated -AttemptId $attemptId -Status 'review_required' -Error ([string]$rollback.Reason) | Out-Null
                return [pscustomobject]@{ Status = 'review'; Reason = [string]$rollback.Reason; Manifest = $updated; Cleaned = $false }
            }

            $map = ConvertTo-PendingManifestMap $Manifest
            $map['manifest_state'] = 'parked_recovered'
            $map['transaction_phase'] = 'restart_recovered'
            $map['transaction_phase_at'] = (Get-Date -Format 'o')
            $map['review_required'] = $false
            $map['review_reason'] = ''
            Write-PendingManifestFile -Path $ManifestFile.FullName -Manifest $map | Out-Null
            $updated = Read-PendingManifestFile -Path $ManifestFile.FullName
            $updated = Update-PendingManifestDrainAttempt -ManifestPath $ManifestFile.FullName -Manifest $updated -AttemptId $attemptId -Status 'recovered_pending'
            return [pscustomobject]@{ Status = 'recovered_pending'; Reason = ''; Manifest = $updated; Cleaned = $false }
        } finally {
            Exit-PendingPublishDestinationLock -Lock $destinationLock
        }
    } finally {
        Exit-PendingPublishTransactionLock -Lock $lock
    }
}

# Explicit mutation-stage crash recovery. Read/index refreshes must never call
# this function or Repair-PendingManifestState. The intent and result events
# provide durable evidence that recovery, rather than inventory refresh, moved
# a payload/sidecar or rewrote a manifest.
function Invoke-PendingPublishRecovery {
    param([string] $Reason = 'pending-drain-preflight')

    $summary = [ordered]@{
        schema_version = 'pending_publish_recovery.v1'
        reason = [string]$Reason
        started_at = Get-Date -Format 'o'
        completed_at = ''
        inspected_count = 0
        candidate_count = 0
        recovered_count = 0
        blocked_count = 0
        failed_count = 0
        rows = @()
    }
    if (-not (Test-Path -LiteralPath $LocalPendingPush -PathType Container)) {
        $summary['completed_at'] = Get-Date -Format 'o'
        return [pscustomobject]$summary
    }

    $rows = [System.Collections.Generic.List[object]]::new()
    foreach ($manifestFile in @(Get-ChildItem -LiteralPath $LocalPendingPush -File -Filter '*.manifest.json' -ErrorAction SilentlyContinue | Sort-Object Name)) {
        $summary['inspected_count'] = [int]$summary['inspected_count'] + 1
        try {
            $manifest = Read-PendingManifestFile -Path $manifestFile.FullName
            $stateBefore = [string]$manifest.manifest_state
            $drainAttemptStatus = [string](Get-PendingObjectProperty -Object $manifest -Name 'drain_attempt_status')
            if ($drainAttemptStatus -in @('in_progress', 'completed_evidence_failed', 'succeeded', 'already_published', 'recovered_completed')) {
                $summary['candidate_count'] = [int]$summary['candidate_count'] + 1
                $drainRepair = Repair-PendingStaleDrainAttempt -ManifestFile $manifestFile -Manifest $manifest
                $statusAfter = [string]$drainRepair.Status
                if ($statusAfter -in @('recovered_pending', 'recovered_completed')) {
                    $summary['recovered_count'] = [int]$summary['recovered_count'] + 1
                } elseif ($statusAfter -in @('review', 'blocked', 'busy')) {
                    $summary['blocked_count'] = [int]$summary['blocked_count'] + 1
                } else {
                    $summary['failed_count'] = [int]$summary['failed_count'] + 1
                }
                $stateAfter = if ($drainRepair.Cleaned) { 'completed' } else { [string](Get-PendingObjectProperty -Object $drainRepair.Manifest -Name 'manifest_state') }
                $rows.Add([pscustomobject]@{
                    manifest_path = [string]$manifestFile.FullName
                    status = $statusAfter
                    reason = [string]$drainRepair.Reason
                    state_before = $stateBefore
                    state_after = $stateAfter
                }) | Out-Null
                if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                    Write-PipelineEvent -EventType 'pending_publish_recovery' -Stage 'pending-publish-recovery' -Status $statusAfter -Data @{
                        phase = 'stale_drain_result'; reason = [string]$Reason; manifest_path = [string]$manifestFile.FullName
                        state_before = $stateBefore; state_after = $stateAfter; drain_attempt_status = $drainAttemptStatus
                        error = [string]$drainRepair.Reason
                    } | Out-Null
                }
                continue
            }
            $sidecarCandidates = @(Get-PendingSidecarEntries -Manifest $manifest | Where-Object {
                $local = [string](Get-PendingObjectProperty -Object $_ -Name 'local_file')
                $original = [string](Get-PendingObjectProperty -Object $_ -Name 'original_local_file')
                -not [string]::IsNullOrWhiteSpace($local) -and
                -not (Test-Path -LiteralPath $local -ErrorAction SilentlyContinue) -and
                -not [string]::IsNullOrWhiteSpace($original) -and
                (Test-Path -LiteralPath $original -PathType Leaf -ErrorAction SilentlyContinue)
            })
            $candidate = $stateBefore -eq 'pending_move' -or $sidecarCandidates.Count -gt 0
            if (-not $candidate) { continue }
            $summary['candidate_count'] = [int]$summary['candidate_count'] + 1

            $trust = if ($stateBefore -eq 'pending_move') {
                Test-PendingManifestTrustedForRepair -ManifestFile $manifestFile -Manifest $manifest
            } else {
                $failedSidecarTrust = $null
                foreach ($sidecar in $sidecarCandidates) {
                    $sidecarTrust = Test-PendingSidecarTrustedForPublish -Manifest $manifest -Sidecar $sidecar -ManifestPath $manifestFile.FullName -AllowMissingLocal
                    if (-not $sidecarTrust.Ok) { $failedSidecarTrust = $sidecarTrust; break }
                }
                if ($failedSidecarTrust) { $failedSidecarTrust } else { [pscustomobject]@{ Ok = $true; Reason = 'ok' } }
            }
            if (-not $trust.Ok) {
                $summary['blocked_count'] = [int]$summary['blocked_count'] + 1
                $row = [pscustomobject]@{
                    manifest_path = [string]$manifestFile.FullName
                    status = 'blocked'
                    reason = [string]$trust.Reason
                    state_before = $stateBefore
                    state_after = $stateBefore
                }
                $rows.Add($row) | Out-Null
                if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                    Write-PipelineEvent -EventType 'pending_publish_recovery' -Stage 'pending-publish-recovery' -Status 'blocked' -Data @{
                        phase = 'result'; reason = [string]$Reason; manifest_path = [string]$manifestFile.FullName
                        state_before = $stateBefore; state_after = $stateBefore; error = [string]$trust.Reason
                    } | Out-Null
                }
                continue
            }

            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                Write-PipelineEvent -EventType 'pending_publish_recovery' -Stage 'pending-publish-recovery' -Status 'started' -Data @{
                    phase = 'intent'; reason = [string]$Reason; manifest_path = [string]$manifestFile.FullName
                    state_before = $stateBefore; sidecar_candidate_count = [int]$sidecarCandidates.Count
                } | Out-Null
            }
            $repaired = if ($stateBefore -eq 'pending_move') {
                Repair-PendingManifestState -ManifestFile $manifestFile -Manifest $manifest
            } else {
                Repair-PendingSidecarArtifacts -ManifestFile $manifestFile -Manifest $manifest
            }
            $stateAfter = [string]$repaired.manifest_state
            $wasRecovered = $stateAfter -eq 'parked_recovered' -or $sidecarCandidates.Count -gt 0
            if ($wasRecovered) {
                $summary['recovered_count'] = [int]$summary['recovered_count'] + 1
            }
            $row = [pscustomobject]@{
                manifest_path = [string]$manifestFile.FullName
                status = if ($wasRecovered) { 'recovered' } else { 'unchanged' }
                reason = ''
                state_before = $stateBefore
                state_after = $stateAfter
            }
            $rows.Add($row) | Out-Null
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                Write-PipelineEvent -EventType 'pending_publish_recovery' -Stage 'pending-publish-recovery' -Status ([string]$row.status) -Data @{
                    phase = 'result'; reason = [string]$Reason; manifest_path = [string]$manifestFile.FullName
                    state_before = $stateBefore; state_after = $stateAfter; sidecar_candidate_count = [int]$sidecarCandidates.Count
                } | Out-Null
            }
        } catch {
            $summary['failed_count'] = [int]$summary['failed_count'] + 1
            $rows.Add([pscustomobject]@{
                manifest_path = [string]$manifestFile.FullName
                status = 'failed'
                reason = [string]$_
                state_before = ''
                state_after = ''
            }) | Out-Null
            Write-Log "Pending publish recovery failed for $($manifestFile.Name): $_" 'ERROR'
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                Write-PipelineEvent -EventType 'pending_publish_recovery' -Stage 'pending-publish-recovery' -Status 'failed' -Data @{
                    phase = 'result'; reason = [string]$Reason; manifest_path = [string]$manifestFile.FullName; error = [string]$_
                } | Out-Null
            }
        }
    }
    $summary['rows'] = @($rows)
    $summary['completed_at'] = Get-Date -Format 'o'
    return [pscustomobject]$summary
}
