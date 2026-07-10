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
            [System.IO.File]::Move($originalFile, $localFile, $true)
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
        $map = ConvertTo-PendingManifestMap $Manifest
        $map['manifest_state'] = 'parked_recovered'
        $map['recovered_at'] = (Get-Date -Format 'o')
        Write-PendingManifestFile -Path $ManifestFile.FullName -Manifest $map | Out-Null
        Write-Log "Pending publish index: recovered parked output from pending_move manifest: $($ManifestFile.Name)" "WARN"
        return (Read-PendingManifestFile -Path $ManifestFile.FullName)
    } catch {
        Write-Log "Pending publish index: failed to recover pending_move manifest $($ManifestFile.Name) : $_" "WARN"
        return $Manifest
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
