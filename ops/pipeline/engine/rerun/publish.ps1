# Extracted from ops/pipeline/entrypoints/Invoke-RerunCsv.ps1. Responsibility: pending-publish and final-destination handoff policy

function Remove-RerunStagedInputs {
    param([array]$Plans)
    foreach ($plan in @($Plans)) {
        $stagePath = [string]$plan.stage_path
        if ([string]::IsNullOrWhiteSpace($stagePath)) { continue }
        try {
            if (Test-Path -LiteralPath $stagePath -PathType Leaf) {
                Remove-Item -LiteralPath $stagePath -Force
                $plan.staged_input_cleanup = 'removed'
            }
        } catch {
            $plan.staged_input_cleanup = "failed: $($_.Exception.Message)"
            Write-RerunLog "Staged input cleanup failed: $stagePath :: $($_.Exception.Message)" "WARN"
        }
    }
}

function Get-RerunNonOverlapPath {
    param([string]$Path, [string]$Suffix, $ReservedKeys = $null)
    $pathKey = Get-RerunNormalizedPathKey -Path $Path
    $reserved = ($null -ne $ReservedKeys -and -not [string]::IsNullOrWhiteSpace($pathKey) -and $ReservedKeys.Contains($pathKey))
    if (-not (Test-Path -LiteralPath $Path) -and -not $reserved) { return $Path }
    $dir = Split-Path -Parent $Path
    $leaf = [System.IO.Path]::GetFileNameWithoutExtension($Path)
    $ext = [System.IO.Path]::GetExtension($Path)
    $candidate = Join-Path $dir ("{0}.{1}{2}" -f $leaf, $Suffix, $ext)
    $counter = 1
    while ((Test-Path -LiteralPath $candidate) -or ($null -ne $ReservedKeys -and $ReservedKeys.Contains((Get-RerunNormalizedPathKey -Path $candidate)))) {
        $candidate = Join-Path $dir ("{0}.{1}.{2}{3}" -f $leaf, $Suffix, $counter, $ext)
        $counter++
    }
    return $candidate
}

function Resolve-RerunPendingPublishServerOut {
    param(
        [Parameter(Mandatory)] [string]$RequestedPath,
        [Parameter(Mandatory)] [string]$BatchId,
        $ReservedServerOutKeys
    )
    if ([string]::IsNullOrWhiteSpace($RequestedPath)) {
        throw 'final output path is unavailable'
    }
    $destinationKey = Get-RerunNormalizedPathKey -Path $RequestedPath
    $pendingDestinationInUse = ($null -ne $ReservedServerOutKeys -and $ReservedServerOutKeys.Contains($destinationKey))
    $finalExists = Test-Path -LiteralPath $RequestedPath -PathType Leaf

    if ($pendingDestinationInUse) {
        if ($CollisionPolicy -eq 'fail') {
            throw "pending publish destination is already queued: $RequestedPath"
        }
        # replace_final applies to final-file collisions. Pending queue collisions must stay unique.
        $resolved = Get-RerunNonOverlapPath -Path $RequestedPath -Suffix $BatchId -ReservedKeys $ReservedServerOutKeys
        $ReservedServerOutKeys.Add((Get-RerunNormalizedPathKey -Path $resolved)) | Out-Null
        return $resolved
    }

    if ($finalExists) {
        if ($CollisionPolicy -eq 'fail') {
            throw "final output exists and collision_policy=fail: $RequestedPath"
        }
        if ($CollisionPolicy -eq 'replace_final') {
            if (-not $ConfirmReplaceFinal) {
                throw 'collision_policy=replace_final for pending_publish requires -ConfirmReplaceFinal.'
            }
            $ReservedServerOutKeys.Add($destinationKey) | Out-Null
            return $RequestedPath
        }
        $resolved = Get-RerunNonOverlapPath -Path $RequestedPath -Suffix $BatchId -ReservedKeys $ReservedServerOutKeys
        $ReservedServerOutKeys.Add((Get-RerunNormalizedPathKey -Path $resolved)) | Out-Null
        return $resolved
    }

    $ReservedServerOutKeys.Add($destinationKey) | Out-Null
    return $RequestedPath
}

function Move-RerunVerifiedOutput {
    param([string]$Source, [string]$Destination)
    if ([string]::IsNullOrWhiteSpace($Source) -or -not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "verified output not found: $Source"
    }
    $destDir = Split-Path -Parent $Destination
    if (-not (Test-Path -LiteralPath $destDir)) { New-Item -ItemType Directory -Path $destDir -Force | Out-Null }
    Move-Item -LiteralPath $Source -Destination $Destination -Force
    return $Destination
}

function Backup-RerunFinalCompanionPath {
    param(
        [Parameter(Mandatory)] [string]$Path,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot
    )
    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return ''
    }
    $backupDir = Join-Path $FinalHoldRoot $BatchId
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
    $backup = Join-Path $backupDir (Split-Path -Leaf $Path)
    if (Test-Path -LiteralPath $backup) { $backup = Get-RerunNonOverlapPath -Path $backup -Suffix $BatchId }
    Move-Item -LiteralPath $Path -Destination $backup
    return $backup
}

function Get-RerunFinalCompanionPath {
    param(
        [Parameter(Mandatory)] [string]$SourcePath,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$FinalOutput
    )
    $verifiedDir = Split-Path -Parent $VerifiedOutput
    $finalDir = Split-Path -Parent $FinalOutput
    $relative = [System.IO.Path]::GetRelativePath([System.IO.Path]::GetFullPath($verifiedDir), [System.IO.Path]::GetFullPath($SourcePath))
    if ([string]::IsNullOrWhiteSpace($relative) -or $relative.StartsWith('..')) {
        return ''
    }
    $relativeParent = Split-Path $relative -Parent
    $relativeLeaf = Split-Path $relative -Leaf
    $sourceStem = [System.IO.Path]::GetFileNameWithoutExtension($relativeLeaf)
    $verifiedStem = [System.IO.Path]::GetFileNameWithoutExtension($VerifiedOutput)
    $finalStem = [System.IO.Path]::GetFileNameWithoutExtension($FinalOutput)
    if (-not [string]::IsNullOrWhiteSpace($verifiedStem) -and $sourceStem.StartsWith($verifiedStem, [System.StringComparison]::OrdinalIgnoreCase)) {
        $relativeLeaf = $finalStem + $sourceStem.Substring($verifiedStem.Length) + [System.IO.Path]::GetExtension($relativeLeaf)
    }
    $relativeFinalPath = if ([string]::IsNullOrWhiteSpace($relativeParent)) { $relativeLeaf } else { Join-Path $relativeParent $relativeLeaf }
    return (Join-Path $finalDir $relativeFinalPath)
}

function Copy-RerunFinalSrtSidecars {
    param(
        $PipelineSidecar,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$FinalOutput,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot,
        [string]$FinalOutputRoot = '',
        [switch]$AllowSourceOutputRoot
    )
    $tracks = [System.Collections.Generic.List[object]]::new()
    $backups = [System.Collections.Generic.List[string]]::new()
    $copied = [System.Collections.Generic.List[string]]::new()
    $verifiedDir = Split-Path -Parent $VerifiedOutput
    foreach ($record in @(Get-RerunArrayField -Object $PipelineSidecar -Name 'tx3g_srt_tracks')) {
        $recordMap = Copy-RerunRecordProperties -Record $record
        $source = Get-RerunTrackSourcePath -Record $record
        if (
            -not [string]::IsNullOrWhiteSpace($source) -and
            [System.IO.Path]::GetExtension($source).ToLowerInvariant() -eq '.srt' -and
            (Test-Path -LiteralPath $source -PathType Leaf) -and
            (Test-RerunPathUnderRoot -Path $source -Root $verifiedDir)
        ) {
            $destination = Get-RerunFinalCompanionPath -SourcePath $source -VerifiedOutput $VerifiedOutput -FinalOutput $FinalOutput
            if (-not [string]::IsNullOrWhiteSpace($destination)) {
                $finalDir = Split-Path -Parent $FinalOutput
                if (-not (Test-RerunPathUnderRoot -Path $destination -Root $finalDir)) {
                    throw "sidecar destination resolves outside final output folder: $destination"
                }
                if (-not $AllowSourceOutputRoot -and -not [string]::IsNullOrWhiteSpace($FinalOutputRoot) -and -not (Test-RerunPathUnderRoot -Path $destination -Root $FinalOutputRoot)) {
                    throw "sidecar destination resolves outside configured output root: $destination"
                }
                $destinationDir = Split-Path -Parent $destination
                if (-not (Test-Path -LiteralPath $destinationDir)) { New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null }
                $backup = Backup-RerunFinalCompanionPath -Path $destination -BatchId $BatchId -FinalHoldRoot $FinalHoldRoot
                if (-not [string]::IsNullOrWhiteSpace($backup)) { $backups.Add($backup) | Out-Null }
                Copy-Item -LiteralPath $source -Destination $destination -Force
                $copied.Add($destination) | Out-Null
                $recordMap['path'] = $destination
                $recordMap['file_name'] = Split-Path -Leaf $destination
                $recordMap['status'] = 'written'
            }
        }
        $tracks.Add([pscustomobject]$recordMap) | Out-Null
    }
    return [pscustomobject]@{
        Tracks = @($tracks)
        Backups = @($backups)
        Copied = @($copied)
    }
}

function Publish-RerunPipelineSidecarToFinal {
    param(
        $Plan,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot
    )
    $sourceSidecarPath = Get-RerunPipelineSidecarPath -OutputPath $VerifiedOutput
    if (-not (Test-Path -LiteralPath $sourceSidecarPath -PathType Leaf)) {
        $Plan.pipeline_sidecar_publish = 'missing'
        return
    }
    $pipelineSidecar = Read-RerunPipelineSidecar -OutputPath $VerifiedOutput
    if ($null -eq $pipelineSidecar) {
        $Plan.pipeline_sidecar_publish = 'unreadable'
        return
    }
    $destinationSidecarPath = Get-RerunPipelineSidecarPath -OutputPath $Destination
    $destinationSidecarDir = Split-Path -Parent $destinationSidecarPath
    if (-not (Test-Path -LiteralPath $destinationSidecarDir)) { New-Item -ItemType Directory -Path $destinationSidecarDir -Force | Out-Null }

    $sidecarCopy = Copy-RerunRecordProperties -Record $pipelineSidecar
    $sidecarCopy['output_path'] = $Destination
    $sidecarCopy['output_file'] = Split-Path -Leaf $Destination
    $sidecarCopy['publish_state'] = 'published'
    if ([string]::IsNullOrWhiteSpace([string]$sidecarCopy['publish_mode'])) {
        $sidecarCopy['publish_mode'] = 'immediate'
    }
    $sidecarCopy['rerun_destination_policy'] = $DestinationMode
    $sidecarCopy['rerun_batch_id'] = $BatchId
    $sidecarCopy['rerun_source_path'] = [string]$Plan.source_path
    $sidecarCopy['rerun_verified_output_path'] = $VerifiedOutput
    $sidecarCopy['rerun_final_replacement'] = $true

    $allowSourceOutputRoot = ([bool]$Plan.source_overwrite_confirmed -and (Test-RerunSamePath -Left $Destination -Right ([string]$Plan.source_path)))
    $srtPublish = Copy-RerunFinalSrtSidecars `
        -PipelineSidecar $pipelineSidecar `
        -VerifiedOutput $VerifiedOutput `
        -FinalOutput $Destination `
        -BatchId $BatchId `
        -FinalHoldRoot $FinalHoldRoot `
        -FinalOutputRoot ([string]$Plan.final_output_root) `
        -AllowSourceOutputRoot:$allowSourceOutputRoot
    if (@($srtPublish.Tracks).Count -gt 0) {
        $sidecarCopy['tx3g_srt_tracks'] = @($srtPublish.Tracks)
    }
    $sidecarBackup = Backup-RerunFinalCompanionPath -Path $destinationSidecarPath -BatchId $BatchId -FinalHoldRoot $FinalHoldRoot
    $sidecarBackups = @($srtPublish.Backups)
    if (-not [string]::IsNullOrWhiteSpace($sidecarBackup)) { $sidecarBackups += $sidecarBackup }
    Write-RerunManifest -Path $destinationSidecarPath -Payload ([pscustomobject]$sidecarCopy)
    $completedAppend = Add-RerunCompletedJobsManifestEntry -OutputPath $Destination -Payload $sidecarCopy
    $Plan.pipeline_sidecar_publish = 'published'
    $Plan.pipeline_sidecar_path = $destinationSidecarPath
    $Plan.published_sidecar_paths = @($destinationSidecarPath) + @($srtPublish.Copied)
    $Plan.replaced_sidecar_hold_paths = @($sidecarBackups)
    $Plan.completed_manifest_path = [string]$script:RerunCompletedJobsManifest
    $Plan.completed_manifest_append = if ($completedAppend) { 'appended' } else { 'append_failed' }
}

function New-RerunPendingPublishManifest {
    param(
        $Plan,
        [string]$PendingRoot,
        [string]$BatchId,
        [string]$ServerOut = '',
        [string]$RouteReasonCode = 'rerun_csv_pending_publish',
        [string]$RouteReason = 'CSV rerun verified output promoted into Pending Publish.'
    )
    $verified = [string]$Plan.verified_output_path
    if ([string]::IsNullOrWhiteSpace($verified)) { $verified = [string]$Plan.planned_output_path }
    $leaf = Split-Path -Leaf $verified
    $pendingFile = Join-Path $PendingRoot $leaf
    if (Test-Path -LiteralPath $pendingFile) {
        $pendingFile = Get-RerunNonOverlapPath -Path $pendingFile -Suffix $BatchId
    }
    if ([string]::IsNullOrWhiteSpace($verified) -or -not (Test-Path -LiteralPath $verified -PathType Leaf)) {
        throw "verified output not found: $verified"
    }
    if ([string]::IsNullOrWhiteSpace($ServerOut)) { $ServerOut = [string]$Plan.final_output_path }
    if ([string]::IsNullOrWhiteSpace($ServerOut)) { throw 'final output path is unavailable' }
    $serverOutViolation = Get-RerunFinalOutputRootViolation `
        -FinalOutputPath $ServerOut `
        -SourcePath ([string]$Plan.source_path) `
        -EffectiveRoot ([string]$Plan.final_output_root) `
        -SourceField ([string]$Plan.final_output_source_field) `
        -SourceOverwriteConfirmed ([bool]$Plan.source_overwrite_confirmed)
    if (-not [string]::IsNullOrWhiteSpace($serverOutViolation)) {
        throw $serverOutViolation
    }
    $verifiedOutputSize = [long](Get-Item -LiteralPath $verified -Force).Length

    $manifestPath = Join-Path $PendingRoot (([System.IO.Path]::GetFileNameWithoutExtension($pendingFile)) + '.manifest.json')
    if (Test-Path -LiteralPath $manifestPath) {
        $manifestPath = Get-RerunNonOverlapPath -Path $manifestPath -Suffix $BatchId
    }
    $sourceIdentity = [string]$Plan.source_identity_v2
    if ([string]::IsNullOrWhiteSpace($sourceIdentity)) {
        $sourceIdentity = 'rerun_csv:' + ([guid]::NewGuid().ToString('N'))
    }
    $sourceContentSha256 = [string]$Plan.planned_source_content_sha256
    if ([string]::IsNullOrWhiteSpace($sourceContentSha256)) {
        $sourceContentSha256 = [string]$Plan.source_content_sha256
    }
    $sourceContentSha256 = $sourceContentSha256.Trim().ToLowerInvariant()
    $now = Get-Date -Format 'o'
    $transactionId = ('rerun-csv-{0}-{1}' -f $BatchId, [guid]::NewGuid().ToString('N'))
    $pipelineSidecar = Read-RerunPipelineSidecar -OutputPath $verified
    $allowSourceOutputRoot = ([bool]$Plan.source_overwrite_confirmed -and (Test-RerunSamePath -Left $ServerOut -Right ([string]$Plan.source_path)))
    $pendingSidecars = New-RerunPendingSidecarEntries `
        -PipelineSidecar $pipelineSidecar `
        -VerifiedOutput $verified `
        -FinalOutput $ServerOut `
        -PendingRoot $PendingRoot `
        -TransactionId $transactionId `
        -FinalOutputRoot ([string]$Plan.final_output_root) `
        -AllowSourceOutputRoot:$allowSourceOutputRoot
    $payload = [ordered]@{
        schema_version = 'pending_push_manifest.v1'
        parked_at = $now
        product_version = [string]$script:RerunProductVersion
        pipeline_version = [string]$script:RerunPipelineVersion
        publish_transaction_id = $transactionId
        manifest_state = 'pending_move'
        created_at = $now
        route = 'csv_rerun'
        route_reason_code = $RouteReasonCode
        route_reason = $RouteReason
        media_type = [string]$Plan.media_kind
        local_file = $pendingFile
        original_local_file = $verified
        parked_file = $pendingFile
        server_out = $ServerOut
        source_path = [string]$Plan.source_path
        source_size = [long]($Plan.source_size -as [long])
        source_mtime_utc = [string]$Plan.source_mtime_utc
        source_identity = $sourceIdentity
        source_identity_v2 = $sourceIdentity
        source_identity_v2_algorithm = 'rerun_csv_v2'
        source_content_sha256 = $sourceContentSha256
        source_content_sha256_algorithm = 'sha256-full-file'
        confirm_source_overwrite = [bool]$Plan.source_overwrite_confirmed
        output_size = $verifiedOutputSize
        publish_mode = 'pending_publish'
        sidecar_files = @($pendingSidecars.Entries)
        tx3g_srt_tracks = @($pendingSidecars.Tracks)
        tx3g_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'tx3g_srt_failures')
        bdpgs_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'bdpgs_srt_failures')
        vobsub_srt_failures = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'vobsub_srt_failures')
        converted_srt_sidecar_candidates = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'converted_srt_sidecar_candidates')
        subtitle_output_reduction = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'subtitle_output_reduction')
        tx3g_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'tx3g_embedded_srt_tracks')
        bdpgs_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'bdpgs_embedded_srt_tracks')
        vobsub_embedded_srt_tracks = @(Get-RerunArrayField -Object $pipelineSidecar -Name 'vobsub_embedded_srt_tracks')
        tx3g_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'tx3g_srt_conversion_enabled')
        tx3g_external_srt_sidecars_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'tx3g_external_srt_sidecars_enabled')
        drop_tx3g_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_tx3g_after_conversion')
        bdpgs_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'bdpgs_srt_conversion_enabled')
        drop_bdpgs_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_bdpgs_after_conversion')
        vobsub_srt_conversion_enabled = (Get-RerunBoolField -Object $pipelineSidecar -Name 'vobsub_srt_conversion_enabled')
        drop_vobsub_after_conversion = (Get-RerunBoolField -Object $pipelineSidecar -Name 'drop_vobsub_after_conversion')
        original_subtitles_preserved = $true
        drop_ass_after_conversion = $false
        conversion_failed = $false
        source = @{
            rerun_batch_id = $BatchId
            rerun_audit_issue_codes = [string]$Plan.audit_issue_codes
        }
    }
    $autoIssues = @()
    if ($Plan.PSObject.Properties['auto_destination_issues']) {
        $autoIssues = @($Plan.auto_destination_issues)
    }
    if ($autoIssues.Count -gt 0) {
        $payload['rerun_auto_destination_policy'] = 'auto_replace_clean_else_pending_review'
        $payload['rerun_auto_destination_decision'] = 'pending_publish_review'
        $payload['rerun_auto_review_issues'] = @($autoIssues)
    }
    foreach ($evidenceKey in @('folder_policy','route_plan','route_explanation','library_profile','dynamic_hdr','quality_verification','audio_decisions','subtitle_decisions','encode_selected_attempt','encode_selected_encoder','encode_selected_encoder_kind','encode_selected_gpu_device')) {
        $evidenceValue = Get-RerunObjectValue -Object $pipelineSidecar -Name $evidenceKey -Default $null
        if ($null -ne $evidenceValue) {
            $payload[$evidenceKey] = $evidenceValue
        }
    }
    $manifestWritten = $false
    try {
        Assert-RerunPendingPublishManifestContract -Payload $payload
    } catch {
        foreach ($copiedSidecar in @($pendingSidecars.Copied)) {
            Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
        }
        throw
    }
    try {
        Write-RerunManifest -Path $manifestPath -Payload $payload
        $manifestWritten = $true
        $roundTrip = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json -ErrorAction Stop
        if ([string]$roundTrip.local_file -ne $pendingFile -or [string]$roundTrip.server_out -ne $ServerOut -or [string]$roundTrip.manifest_state -ne 'pending_move') {
            throw 'CSV rerun pending manifest validation failed before park.'
        }
        Move-RerunVerifiedOutput -Source $verified -Destination $pendingFile | Out-Null
        try {
            $payload['manifest_state'] = 'parked'
            $payload['parked_at'] = (Get-Date -Format 'o')
            Write-RerunManifest -Path $manifestPath -Payload $payload
        } catch {
            Write-RerunLog "CSV rerun pending manifest state update failed after moving output; pending intent remains retryable: $manifestPath : $($_.Exception.Message)" "WARN"
        }
    } catch {
        if (-not $manifestWritten) {
            foreach ($copiedSidecar in @($pendingSidecars.Copied)) {
                Remove-Item -LiteralPath $copiedSidecar -Force -ErrorAction SilentlyContinue
            }
        }
        throw
    }
    $Plan.verified_output_path = $pendingFile
    $Plan.pending_publish_payload_path = $pendingFile
    $Plan.pending_publish_manifest_path = $manifestPath
    $Plan.final_output_path = $ServerOut
    $Plan.status = 'pending_publish'
    $Plan.reason = 'verified output moved into Pending Publish manifest'
}

function Invoke-RerunOriginalPolicy {
    param($Plan, [string]$BatchId, [string]$HoldRoot)
    if ($OriginalPolicy -eq 'keep') {
        $Plan.original_action = 'kept'
        return
    }
    if (-not $ConfirmOriginalPolicy) { throw "$OriginalPolicy requires -ConfirmOriginalPolicy." }
    $sourcePath = [string]$Plan.source_path
    if ([string]::IsNullOrWhiteSpace($sourcePath) -or -not (Test-Path -LiteralPath $sourcePath -PathType Leaf)) {
        throw "original source not found for original policy: $sourcePath"
    }
    if ($OriginalPolicy -eq 'rename_after_publish') {
        $dir = Split-Path -Parent $sourcePath
        $leaf = [System.IO.Path]::GetFileNameWithoutExtension($sourcePath)
        $ext = [System.IO.Path]::GetExtension($sourcePath)
        $renamed = Join-Path $dir ("{0}.rerun-original-{1}{2}" -f $leaf, $BatchId, $ext)
        if (Test-Path -LiteralPath $renamed) { $renamed = Get-RerunNonOverlapPath -Path $renamed -Suffix $BatchId }
        Move-Item -LiteralPath $sourcePath -Destination $renamed
        $Plan.original_action = 'renamed_after_publish'
        $Plan.original_held_path = $renamed
        return
    }
    $holdDir = Join-Path $HoldRoot $BatchId
    New-Item -ItemType Directory -Path $holdDir -Force | Out-Null
    $held = Join-Path $holdDir (Split-Path -Leaf $sourcePath)
    if (Test-Path -LiteralPath $held) { $held = Get-RerunNonOverlapPath -Path $held -Suffix $BatchId }
    Move-Item -LiteralPath $sourcePath -Destination $held
    $Plan.original_action = if ($OriginalPolicy -eq 'hold_then_delete_after_publish') { 'held_cleanup_ready' } else { 'moved_to_hold_after_publish' }
    $Plan.original_held_path = $held
    if ($OriginalPolicy -eq 'hold_then_delete_after_publish') {
        $Plan.original_cleanup_ready = $true
    }
}

function Publish-RerunReplaceFinal {
    param(
        $Plan,
        [Parameter(Mandatory)] [string]$VerifiedOutput,
        [Parameter(Mandatory)] [string]$Destination,
        [Parameter(Mandatory)] [string]$BatchId,
        [Parameter(Mandatory)] [string]$FinalHoldRoot,
        [Parameter(Mandatory)] [string]$OriginalHoldRoot,
        [string]$Reason = 'verified output replaced backend-planned final output',
        $ExecutionManifest = $null,
        [string]$ExecutionManifestPath = ''
    )
    if (-not $ConfirmReplaceFinal) { throw "$DestinationMode requires -ConfirmReplaceFinal." }
    $successReason = $Reason
    if ([bool]$Plan.source_overwrite_confirmed) {
        $successReason = "$Reason at confirmed source path"
    }
    Invoke-RerunFinalPublicationTransaction `
        -Plan $Plan `
        -VerifiedOutput $VerifiedOutput `
        -Destination $Destination `
        -BatchId $BatchId `
        -FinalHoldRoot $FinalHoldRoot `
        -DestinationPolicy $DestinationMode `
        -SuccessStatus 'published_replace_final' `
        -SuccessReason $successReason `
        -IsReplacement $true `
        -ExecutionManifest $ExecutionManifest `
        -ExecutionManifestPath $ExecutionManifestPath | Out-Null
    if ([bool]$Plan.source_overwrite_confirmed) {
        $Plan.original_action = 'source_overwritten_by_confirmed_replace_final'
    } else {
        Invoke-RerunOriginalPolicy -Plan $Plan -BatchId $BatchId -HoldRoot $OriginalHoldRoot
    }
}

function Invoke-RerunDestinationPolicy {
    param(
        [array]$Plans,
        [string]$BatchId,
        [string]$PendingRoot,
        [string]$FinalHoldRoot,
        [string]$OriginalHoldRoot,
        $ExecutionManifest = $null,
        [string]$ExecutionManifestPath = ''
    )
    $reservedServerOutKeys = Get-RerunPendingServerDestinationSet -PendingRoot $PendingRoot
    foreach ($plan in @($Plans | Where-Object { $_.status -eq 'complete' })) {
        try {
            $verified = [string]$plan.verified_output_path
            if ([string]::IsNullOrWhiteSpace($verified)) { $verified = [string]$plan.planned_output_path }
            if ($DestinationMode -eq 'review_workspace') {
                $plan.status = 'review_workspace'
                $plan.reason = 'verified output left in rerun review workspace'
                $plan.verified_output_path = $verified
                $plan.original_action = 'deferred_until_final_publish'
                continue
            }
            if ($DestinationMode -eq 'pending_publish') {
                New-Item -ItemType Directory -Path $PendingRoot -Force | Out-Null
                $serverOut = Resolve-RerunPendingPublishServerOut -RequestedPath ([string]$plan.final_output_path) -BatchId $BatchId -ReservedServerOutKeys $reservedServerOutKeys
                New-RerunPendingPublishManifest -Plan $plan -PendingRoot $PendingRoot -BatchId $BatchId -ServerOut $serverOut
                $plan.original_action = 'deferred_until_pending_publish_drain'
                continue
            }
            if ($DestinationMode -eq 'auto_replace_clean_else_pending_review') {
                if (-not $ConfirmReplaceFinal) { throw 'auto_replace_clean_else_pending_review requires -ConfirmReplaceFinal.' }
                $issues = @(Get-RerunAutoReviewIssues -Plan $plan -VerifiedOutput $verified)
                $plan.auto_destination_policy = 'auto_replace_clean_else_pending_review'
                $plan.auto_destination_issue_count = [int]$issues.Count
                $plan.auto_destination_issues = @($issues)
                if ($issues.Count -gt 0) {
                    $plan.auto_destination_decision = 'pending_publish_review'
                    New-Item -ItemType Directory -Path $PendingRoot -Force | Out-Null
                    $serverOut = Resolve-RerunPendingPublishServerOut -RequestedPath ([string]$plan.final_output_path) -BatchId $BatchId -ReservedServerOutKeys $reservedServerOutKeys
                    New-RerunPendingPublishManifest `
                        -Plan $plan `
                        -PendingRoot $PendingRoot `
                        -BatchId $BatchId `
                        -ServerOut $serverOut `
                        -RouteReasonCode 'rerun_csv_auto_pending_review' `
                        -RouteReason 'CSV rerun auto-return policy found remaining issue evidence; output parked for Pending Publish review.'
                    $plan.original_action = 'deferred_until_pending_publish_review'
                    continue
                }
                $plan.auto_destination_decision = 'published_replace_final'
                $destination = [string]$plan.final_output_path
                if ([string]::IsNullOrWhiteSpace($destination)) { throw 'final output path is unavailable' }
                Publish-RerunReplaceFinal `
                    -Plan $plan `
                    -VerifiedOutput $verified `
                    -Destination $destination `
                    -BatchId $BatchId `
                    -FinalHoldRoot $FinalHoldRoot `
                    -OriginalHoldRoot $OriginalHoldRoot `
                    -Reason 'auto policy clean output replaced backend-planned final output' `
                    -ExecutionManifest $ExecutionManifest `
                    -ExecutionManifestPath $ExecutionManifestPath
                continue
            }
            $destination = [string]$plan.final_output_path
            if ([string]::IsNullOrWhiteSpace($destination)) { throw 'final output path is unavailable' }
            if ($DestinationMode -eq 'publish_non_overlap') {
                if ((Test-Path -LiteralPath $destination) -and $CollisionPolicy -eq 'fail') {
                    throw "final output exists and collision_policy=fail: $destination"
                }
                if (Test-Path -LiteralPath $destination) {
                    $destination = Get-RerunNonOverlapPath -Path $destination -Suffix $BatchId
                }
                Invoke-RerunFinalPublicationTransaction `
                    -Plan $plan `
                    -VerifiedOutput $verified `
                    -Destination $destination `
                    -BatchId $BatchId `
                    -FinalHoldRoot $FinalHoldRoot `
                    -DestinationPolicy $DestinationMode `
                    -SuccessStatus 'published_non_overlap' `
                    -SuccessReason 'verified output published without overlapping existing final output' `
                    -IsReplacement $false `
                    -ExecutionManifest $ExecutionManifest `
                    -ExecutionManifestPath $ExecutionManifestPath | Out-Null
                Invoke-RerunOriginalPolicy -Plan $plan -BatchId $BatchId -HoldRoot $OriginalHoldRoot
                continue
            }
            if ($DestinationMode -eq 'publish_replace_final') {
                Publish-RerunReplaceFinal `
                    -Plan $plan `
                    -VerifiedOutput $verified `
                    -Destination $destination `
                    -BatchId $BatchId `
                    -FinalHoldRoot $FinalHoldRoot `
                    -OriginalHoldRoot $OriginalHoldRoot `
                    -Reason 'verified output replaced backend-planned final output' `
                    -ExecutionManifest $ExecutionManifest `
                    -ExecutionManifestPath $ExecutionManifestPath
                continue
            }
        } catch {
            $plan.status = 'failed'
            $plan.reason = "destination policy failed: $($_.Exception.Message)"
            Write-RerunLog $plan.reason "ERROR"
        }
    }
}

function Reset-RerunStageRoot {
    param([string]$StageRoot)
    foreach ($child in @('Movies','TV')) {
        $path = Join-Path $StageRoot $child
        if (Test-Path -LiteralPath $path) {
            Remove-Item -LiteralPath $path -Recurse -Force
        }
        New-Item -ItemType Directory -Path $path -Force | Out-Null
    }
}
