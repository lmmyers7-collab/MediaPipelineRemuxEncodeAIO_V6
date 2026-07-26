# ==============================================================================
# ops\pipeline\engine\process\pipeline_processing.ps1
# ==============================================================================
# Job-level processing orchestration extracted from MediaPipeline.ps1.
# Dot-sourced by the main script; preserves script-scope configuration and the
# legacy Process-File wrapper in the main script.
# ==============================================================================

. (Join-Path $PSScriptRoot 'pipeline_processing\preflight.ps1')

function New-MediaPipelineProcessFileResult {
    param(
        [Parameter(Mandatory)] $File,
        [Parameter(Mandatory)] [string] $Status,
        [bool] $Success = $false,
        [bool] $QueueTerminal = $false,
        [bool] $Retryable = $true,
        [string] $Reason = '',
        [string] $ErrorCode = '',
        [string] $Route = '',
        [string] $RouteReasonCode = '',
        [string] $RouteReason = '',
        [string] $PublishState = '',
        [string] $PublishMode = '',
        [string] $OutputPath = '',
        [long] $OutputSizeBytes = 0,
        $SizeGuardEvidence = $null,
        $VerificationEvidence = $null,
        $PublishEvidence = $null,
        [string] $RunId = '',
        [string] $RunMonitorJobId = ''
    )

    $publishedPath = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'published_path' -Default '') } else { '' }
    $parkedPath = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'parked_path' -Default '') } else { '' }
    $intendedFinalPath = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'intended_final_path' -Default '') } else { '' }
    $manifestPath = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'manifest_path' -Default '') } else { '' }
    $pipelineSidecarPath = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'pipeline_sidecar_path' -Default '') } else { '' }
    $sidecarPaths = if ($PublishEvidence) { @(Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'sidecar_paths' -Default @()) } else { @() }
    $publishTransactionId = if ($PublishEvidence) { [string](Get-MediaPipelineProfileProperty -Profile $PublishEvidence -Name 'publish_transaction_id' -Default '') } else { '' }

    return [pscustomobject]@{
        SchemaVersion    = 'process_file_result.v1'
        Success          = [bool]$Success
        Status           = [string]$Status
        QueueTerminal    = [bool]$QueueTerminal
        Retryable        = [bool]$Retryable
        Reason           = [string]$Reason
        ErrorCode        = [string]$ErrorCode
        SourcePath       = [string]$File.FullName
        SourceName       = [string]$File.Name
        Route            = [string]$Route
        RouteReasonCode  = [string]$RouteReasonCode
        RouteReason      = [string]$RouteReason
        PublishState     = [string]$PublishState
        PublishMode      = [string]$PublishMode
        OutputPath       = [string]$OutputPath
        OutputSizeBytes  = [long]$OutputSizeBytes
        PublishedPath    = $publishedPath
        ParkedPath       = $parkedPath
        IntendedFinalPath = $intendedFinalPath
        ManifestPath     = $manifestPath
        PipelineSidecarPath = $pipelineSidecarPath
        SidecarPaths     = @($sidecarPaths)
        PublishTransactionId = $publishTransactionId
        SizeGuardEvidence = $SizeGuardEvidence
        VerificationEvidence = $VerificationEvidence
        PublishEvidence  = $PublishEvidence
        RunId            = if ([string]::IsNullOrWhiteSpace($RunId)) { [string]$script:PipelineRunId } else { $RunId }
        RunMonitorJobId  = if ([string]::IsNullOrWhiteSpace($RunMonitorJobId)) { [string]$script:CurrentRunMonitorJobId } else { $RunMonitorJobId }
    }
}

function Write-MediaPipelineProcessCompletedEvent {
    param(
        [Parameter(Mandatory)] $Result,
        [string] $Stage = '',
        [string] $MediaType = '',
        [string] $Route = '',
        [string] $RouteReasonCode = '',
        [string] $RouteReason = ''
    )

    $eventStatus = if ([bool]$Result.Success) {
        'succeeded'
    } elseif ([string]$Result.Status -eq 'skipped') {
        'skipped'
    } elseif ([string]$Result.Status -eq 'stopped') {
        'stopped'
    } else {
        'failed'
    }
    $eventStage = if (-not [string]::IsNullOrWhiteSpace($Stage)) {
        $Stage
    } elseif ([string]$Result.Status -eq 'skipped') {
        'skipped'
    } elseif ([string]$Result.Status -eq 'stopped') {
        'stopped'
    } elseif ([bool]$Result.Success) {
        'completed'
    } else {
        'failed'
    }
    $eventRoute = if (-not [string]::IsNullOrWhiteSpace($Route)) { $Route } else { [string]$Result.Route }
    $rrCode = if (-not [string]::IsNullOrWhiteSpace($RouteReasonCode)) { $RouteReasonCode } else { [string]$Result.RouteReasonCode }
    $rrText = if (-not [string]::IsNullOrWhiteSpace($RouteReason)) { $RouteReason } else { [string]$Result.RouteReason }

    Write-PipelineEvent -EventType 'job_completed' -Stage $eventStage -Route $eventRoute -Status $eventStatus -SourcePath ([string]$Result.SourcePath) -Data @{
        schema_version     = [string]$Result.SchemaVersion
        success            = [bool]$Result.Success
        completion_status  = [string]$Result.Status
        queue_terminal     = [bool]$Result.QueueTerminal
        retryable          = [bool]$Result.Retryable
        reason             = [string]$Result.Reason
        error_code         = [string]$Result.ErrorCode
        media_type         = [string]$MediaType
        route              = [string]$eventRoute
        route_reason_code  = [string]$rrCode
        route_reason       = [string]$rrText
        publish_state      = [string]$Result.PublishState
        publish_mode       = [string]$Result.PublishMode
        output_path        = [string]$Result.OutputPath
        output_size_bytes  = [long]$Result.OutputSizeBytes
        run_id             = [string]$Result.RunId
        run_monitor_job_id = [string]$Result.RunMonitorJobId
        size_guard_evidence = $Result.SizeGuardEvidence
        verification_evidence = $Result.VerificationEvidence
        publish_evidence  = $Result.PublishEvidence
    } | Out-Null
}

function Resolve-MediaPipelineSourceProbeFailure {
    param($SourceMediaProfile)

    $probeError = if ($SourceMediaProfile -and $SourceMediaProfile.PSObject.Properties['probe_error']) {
        [string]$SourceMediaProfile.probe_error
    } else {
        ''
    }
    if ([string]::IsNullOrWhiteSpace($probeError)) { $probeError = 'probe_failed' }

    switch ($probeError) {
        'video_stream_missing' {
            return [pscustomobject]@{
                ErrorCode       = 'SOURCE_MEDIA_VIDEO_MISSING'
                RouteReasonCode = 'source_video_missing'
                Classification  = 'permanent'
                Retryable       = $false
                QueueTerminal   = $true
                Reason          = 'SOURCE_MEDIA_VIDEO_MISSING: ffprobe found no usable video stream in a source being processed by the video media pipeline.'
                SuggestedAction = 'Inspect or replace the source with media that contains a usable video stream; do not clear this marker until source health is understood.'
                LogWarningCode  = 'SOURCE_MEDIA_VIDEO_MISSING'
            }
        }
        'file_missing' {
            return [pscustomobject]@{
                ErrorCode       = 'SOURCE_FILE_MISSING'
                RouteReasonCode = 'source_probe_file_missing'
                Classification  = 'operator_required'
                Retryable       = $true
                QueueTerminal   = $false
                Reason          = 'SOURCE_FILE_MISSING: source media probe could not find the source file before route selection.'
                SuggestedAction = 'Confirm the source path is still available, then rerun after storage or library state is corrected.'
                LogWarningCode  = 'SOURCE_FILE_MISSING'
            }
        }
        'file_path_empty' {
            return [pscustomobject]@{
                ErrorCode       = 'SOURCE_FILE_PATH_EMPTY'
                RouteReasonCode = 'source_probe_file_path_empty'
                Classification  = 'operator_required'
                Retryable       = $true
                QueueTerminal   = $false
                Reason          = 'SOURCE_FILE_PATH_EMPTY: source media probe received an empty source path before route selection.'
                SuggestedAction = 'Inspect queue/source metadata and rerun after the source path is corrected.'
                LogWarningCode  = 'SOURCE_FILE_PATH_EMPTY'
            }
        }
        default {
            return [pscustomobject]@{
                ErrorCode       = 'SOURCE_MEDIA_PROBE_FAILED'
                RouteReasonCode = 'source_probe_failed'
                Classification  = 'transient'
                Retryable       = $true
                QueueTerminal   = $false
                Reason          = "SOURCE_MEDIA_PROBE_FAILED: source media probe failed before route selection ($probeError)."
                SuggestedAction = 'Inspect ffprobe/tool output and source accessibility, then rerun after the probe problem is corrected.'
                LogWarningCode  = 'SOURCE_MEDIA_PROBE_FAILED'
            }
        }
    }
}

function Invoke-MediaPipelineProcessPreflightDecision {
    param(
        [Parameter(Mandatory)] $Decision,
        [Parameter(Mandatory)] $File,
        [Parameter(Mandatory)] $CollectedChecks
    )

    foreach ($check in @($Decision.Checks)) {
        if ($null -ne $check) { [void]$CollectedChecks.Add($check) }
    }

    foreach ($effect in @($Decision.Effects)) {
        switch ([string]$effect.Kind) {
            'skip_stat' {
                if (-not [string]::IsNullOrWhiteSpace([string]$effect.SkipStat)) {
                    Add-SkipStat ([string]$effect.SkipStat)
                }
            }
            'retry_notice' {
                Add-RetryNotice
            }
            'register_failure' {
                $registration = $effect.FailureRegistration
                if ($registration) {
                    $params = @{
                        SourceFile     = $File
                        Classification = [string]$registration.Classification
                        Reason         = [string]$registration.Reason
                        Stage          = [string]$registration.Stage
                    }
                    if (-not [string]::IsNullOrWhiteSpace([string]$registration.SuggestedAction)) {
                        $params['SuggestedAction'] = [string]$registration.SuggestedAction
                    }
                    if (-not [string]::IsNullOrWhiteSpace([string]$registration.SuggestedRename)) {
                        $params['SuggestedRename'] = [string]$registration.SuggestedRename
                    }
                    Register-SourceFailure @params | Out-Null
                }
            }
            'clear_failure_state' {
                Clear-SourceFailureState $File
            }
            'log' {
                if (-not [string]::IsNullOrWhiteSpace([string]$effect.Message)) {
                    Write-Log ([string]$effect.Message) ([string]$effect.Level)
                }
            }
        }
    }

    if (-not [bool]$Decision.Terminal) { return $null }

    $result = New-MediaPipelineProcessFileResult `
        -File $File `
        -Status ([string]$Decision.Status) `
        -Success:([bool]$Decision.Success) `
        -QueueTerminal:([bool]$Decision.QueueTerminal) `
        -Retryable:([bool]$Decision.Retryable) `
        -Reason ([string]$Decision.Reason) `
        -ErrorCode ([string]$Decision.ErrorCode)
    Write-MediaPipelineProcessCompletedEvent -Result $result -Stage ([string]$Decision.EventStage) -MediaType ([string]$Decision.MediaType)
    return $result
}

function Invoke-MediaPipelineProcessFile {
    param(
        $file,
        [bool]$isTV,
        $idx,
        [int]$QueueIndex = 0,
        [int]$QueueTotal = 0,
        $PriorityInfo = $null,
        [string]$LibraryProfileId = ''
    )

    # Populated only after Queue naming evidence has been verified under the
    # execution-time override stack. Route fallbacks reuse the same object so
    # no later stage can silently re-plan the accepted filename.
    $script:CurrentAcceptedOutputPaths = $null

    if ($script:ProgressWriteFailures -ge 3) {
        Write-Log "Progress persistence failed $($script:ProgressWriteFailures) consecutive time(s); stopping before next file." "ERROR"
        $script:StopRequested = $true
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'stopped' -Success:$false -QueueTerminal:$false -Retryable:$true -Reason 'Progress persistence failed before processing started' -ErrorCode 'PROGRESS_PERSISTENCE_FAILED'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'stopped'
        return $result
    }

    if (-not $PriorityInfo) { $PriorityInfo = Get-SourcePriorityInfo $file }
    $queueLabel = if ($isTV) { 'TV' } else { 'Movie' }
    $queueBits = [System.Collections.Generic.List[string]]::new()
    if ($PriorityInfo.IsPriority) {
        $queueBits.Add('[PRIORITY]')
    }
    if ($QueueIndex -gt 0 -and $QueueTotal -gt 0) {
        $queueBits.Add("[${queueLabel} $QueueIndex/$QueueTotal]")
    }
    $queuePrefix = if ($queueBits.Count -gt 0) {
        ($queueBits -join '') + ' '
    } else {
        ''
    }

    $mediaType = $queueLabel.ToLowerInvariant()
    $preflightChecks = [System.Collections.Generic.List[object]]::new()

    $extensionDecision = Test-MediaPipelineExtensionPreflight -File $file -ValidExtensions $ValidExtensions
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $extensionDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }

    $failureDecision = Get-MediaPipelineFailureStatePreflight -File $file
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $failureDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }

    $tvDecision = Get-MediaPipelineTvParsePreflight -File $file -IsTV:$isTV -LibraryProfileId ([string]$LibraryProfileId)
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $tvDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }
    $tvInfo = $tvDecision.TvInfo

    # Apply ShowName canonical override NOW before Already-Processed so the
    # index key, output path, and all downstream log messages use the final name.
    # The full ActiveOverrides are re-resolved below at the standard point.
    $showNameDecision = Resolve-MediaPipelineTvShowNameOverridePreflight -IsTV:$isTV -TvInfo $tvInfo
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $showNameDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }
    $tvInfo = $showNameDecision.TvInfo

    $alreadyProcessedDecision = Test-MediaPipelineAlreadyProcessedPreflight -File $file -IsTV:$isTV -TvInfo $tvInfo -ProcessedIndex $idx -MediaType $mediaType -LibraryProfileId ([string]$LibraryProfileId)
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $alreadyProcessedDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }

    $stabilityDecision = Test-MediaPipelineStabilityPreflight -File $file -MediaType $mediaType
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $stabilityDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }

    $outputPathDecision = Test-MediaPipelineOutputPathPreflight -File $file -IsTV:$isTV -TvInfo $tvInfo -MediaType $mediaType -LibraryProfileId ([string]$LibraryProfileId)
    $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $outputPathDecision -File $file -CollectedChecks $preflightChecks
    if ($result) { return $result }

    $queuePhase = if ($PriorityInfo.IsPriority) { 'priority' } elseif ($isTV) { 'tv' } else { 'movie' }
    $displayName = "$queuePrefix$($file.Name)"
    $script:CurrentJobId = Get-SourceIdentityKeyV2 $file
    if (-not $script:CurrentJobId) { $script:CurrentJobId = Get-SourceIdentityKey $file }
    $previousLibraryProfileId = Get-Variable -Name CurrentLibraryProfileId -Scope Script -ValueOnly -ErrorAction SilentlyContinue
    $script:CurrentLibraryProfileId = [string]$LibraryProfileId
    $libraryEvidenceForJob = Get-MediaPipelineLibraryProfileEvidenceForPath -SourcePath ([string]$file.FullName) -LibraryProfileId ([string]$LibraryProfileId)
    Set-ProgressItemContext `
        -DisplayName $displayName `
        -FilePath $file.FullName `
        -MediaType $queueLabel.ToLowerInvariant() `
        -LibraryId ([string]$libraryEvidenceForJob['library_id']) `
        -LibraryName ([string]$libraryEvidenceForJob['library_name']) `
        -LibraryDesignation ([string]$libraryEvidenceForJob['designation']) `
        -LibrarySourceRoot ([string]$libraryEvidenceForJob['source_root']) `
        -LibraryOutputRoot ([string]$libraryEvidenceForJob['output_root']) `
        -QueuePhase $queuePhase `
        -QueueIndex $QueueIndex `
        -QueueTotal $QueueTotal
    Set-ProgressStage -Stage 'processing' -Status 'Processing' -Percent $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    Write-PipelineEvent -EventType 'job_started' -Stage 'processing' -Status 'started' -SourcePath $file.FullName -Data @{
        media_type   = $queueLabel.ToLowerInvariant()
        queue_phase  = $queuePhase
        queue_index  = $QueueIndex
        queue_total  = $QueueTotal
        priority     = [bool]$PriorityInfo.IsPriority
        display_name = $displayName
        library_profile = $libraryEvidenceForJob
        library_id = [string]$libraryEvidenceForJob['library_id']
        library_name = [string]$libraryEvidenceForJob['library_name']
        library_designation = [string]$libraryEvidenceForJob['designation']
        library_source_root = [string]$libraryEvidenceForJob['source_root']
        library_output_root = [string]$libraryEvidenceForJob['output_root']
        promotion_enabled = [bool]$libraryEvidenceForJob['promotion_enabled']
        promotion_destination_root = [string]$libraryEvidenceForJob['promotion_destination_root']
        promotion_rule_id = [string]$libraryEvidenceForJob['promotion_rule_id']
        promotion_rule_source = [string]$libraryEvidenceForJob['promotion_rule_source']
        library_settings_override_keys = @($libraryEvidenceForJob['settings_override_keys'])
        library_settings_overrides = $libraryEvidenceForJob['settings_overrides']
        library_effective_settings = $libraryEvidenceForJob['effective_settings']
        library_effective_settings_ref = 'library-only'
        runtime_effective_settings_available = $false
    } | Out-Null

    Write-Log "=========================================="
    Write-Log "${queuePrefix}FILE: $($file.Name)"
    if ($isTV) {
        Write-Log "${queuePrefix}TV: $($tvInfo.ShowName) S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
    } else { Write-Log "${queuePrefix}TYPE: Movie" }
    $libraryLogName = if ([string]::IsNullOrWhiteSpace([string]$libraryEvidenceForJob['library_name'])) { [string]$libraryEvidenceForJob['library_id'] } else { [string]$libraryEvidenceForJob['library_name'] }
    $libraryOverrideKeyText = (@($libraryEvidenceForJob['settings_override_keys']) | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ', '
    Write-Log "${queuePrefix}LIBRARY: $libraryLogName ($($libraryEvidenceForJob['library_id'])) source=$($libraryEvidenceForJob['source_root']) output=$($libraryEvidenceForJob['output_root']) overrides=$libraryOverrideKeyText" "INFO"
    if ([bool]$libraryEvidenceForJob['promotion_enabled'] -and -not [string]::IsNullOrWhiteSpace([string]$libraryEvidenceForJob['promotion_destination_root'])) {
        Write-Log "${queuePrefix}PROMOTION: enabled destination=$($libraryEvidenceForJob['promotion_destination_root']) rule=$($libraryEvidenceForJob['promotion_rule_id']) source=$($libraryEvidenceForJob['promotion_rule_source'])" "INFO"
    }

    # Resolve effective per-job overrides before route selection so folder
    # and library policy can influence routing, encode ladders, audio, and
    # subtitle policy from one shared source of truth. Always cleared in the
    # finally block.
    $showOverrides = if ($isTV -and $tvInfo.ShowName) { Resolve-ShowOverrides $tvInfo.ShowName } else { $null }
    $folderOverrides = Resolve-FolderPolicyOverrides -SourceFile $file
    $libraryOverrides = Resolve-MediaPipelineLibraryOverridesForPath -SourcePath $file.FullName -LibraryProfileId ([string]$LibraryProfileId)
    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $libraryOverrides -Override $showOverrides
    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $script:ActiveOverrides -Override $folderOverrides
    # Merge per-file à-la-carte overrides from file_overrides.json (Phase 3).
    # Stores the structured audio/subtitle override under '_FileOverride' and
    # promotes flat audio config fields so existing Get-Effective* functions
    # pick them up without modification. No-op if no entry exists for this file.
    try {
        Merge-FileOverrideIntoActiveOverrides -SourcePath $file.FullName
    } catch {
        $reason = "Invalid file override for '$($file.FullName)': $($_.Exception.Message)"
        Write-Log $reason "ERROR"
        try {
            Register-SourceFailure `
                -SourceFile $file `
                -Classification 'operator_required' `
                -Reason $reason `
                -Stage 'file-override' `
                -ErrorCode 'FILE_OVERRIDE_INVALID' `
                -SuggestedAction 'Inspect LocalBase\State\file_overrides.json or clear the per-file override from the Queue drawer, then retry.' | Out-Null
        } catch {}
        $result = New-MediaPipelineProcessFileResult `
            -File $file `
            -Status 'failed' `
            -Success:$false `
            -QueueTerminal:$false `
            -Retryable:$true `
            -Reason $reason `
            -ErrorCode 'FILE_OVERRIDE_INVALID'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'file_override' -MediaType $queueLabel.ToLowerInvariant()
        $script:ActiveOverrides = $null
        $script:LastFileOverrideConfigMap = $null
        $script:LastFileOverrideMatch = $null
        $script:CurrentRuntimeEffectiveSettings = $null
        $script:CurrentJobId = $null
        if ($null -ne $previousLibraryProfileId) {
            $script:CurrentLibraryProfileId = $previousLibraryProfileId
        } else {
            Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
        }
        if (Get-Command -Name Reset-ProgressItemContext -ErrorAction SilentlyContinue) {
            Reset-ProgressItemContext
        }
        return $result
    }
    $fileOverrides = ConvertTo-MediaPipelineProfileMap (Get-Variable -Name LastFileOverrideConfigMap -Scope Script -ValueOnly -ErrorAction SilentlyContinue)
    $libraryEffectiveSettings = Resolve-MediaPipelineLibraryEffectiveSettings -Overrides $libraryOverrides
    $runtimeSettingsLayers = @(
        (Get-MediaPipelineRuntimeGlobalSettingsLayer),
        (New-MediaPipelineRuntimeSettingsLayer -Name 'library' -Source 'LibraryProfiles[*].overrides' -Keys $libraryOverrides),
        (New-MediaPipelineRuntimeSettingsLayer -Name 'show' -Source 'ShowOverrides' -Keys $showOverrides),
        (New-MediaPipelineRuntimeSettingsLayer -Name 'folder' -Source 'mediapipeline.folder.json' -Keys $folderOverrides -ExcludeKeys @('FolderPolicyPath','FolderPolicyFolder','FolderPolicyKeys')),
        (New-MediaPipelineRuntimeSettingsLayer -Name 'file' -Source 'file_overrides.json' -Keys $fileOverrides)
    )
    $activeConfigOverrideSnapshot = Push-MediaPipelineActiveConfigOverrides -Overrides $script:ActiveOverrides
    try {
        # Queue acceptance already froze the production filename under the
        # accepted override stack. Recompute it only after the execution-time
        # stack is active, then fail closed before probe, scratch copy, or any
        # encode/remux work if the immutable accepted name no longer matches.
        $destinationNameDecision = Test-MediaPipelineAcceptedDestinationNamePreflight `
            -File $file `
            -IsTV:$isTV `
            -TvInfo $tvInfo `
            -MediaType $mediaType
        $result = Invoke-MediaPipelineProcessPreflightDecision -Decision $destinationNameDecision -File $file -CollectedChecks $preflightChecks
        if ($result) { return $result }
        $script:CurrentAcceptedOutputPaths = $destinationNameDecision.OutputPaths

        $script:CurrentSizePolicyResult = $null
        $script:LastQualityVerification = $null
        $routeHints = Get-ActiveMediaRouteHints
        if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
            Set-MediaPipelineCurrentRunMonitorStage -StageId 'probe' -State 'active' -Detail 'Probing source media streams and codec facts.' -EvidenceSource 'media_probe' -Indeterminate | Out-Null
        }
        Set-ProgressStage -Stage 'probe' -Status 'Probing source media streams and codec facts' -Percent $null -SaveNow
        $sourceProbePollHandler = if (Get-Command -Name New-MediaPipelineCurrentStageNativePollHandler -ErrorAction SilentlyContinue) {
            New-MediaPipelineCurrentStageNativePollHandler `
                -Stage 'probe' `
                -Status 'Probing source media streams and codec facts' `
                -MinimumIntervalSeconds 15 `
                -EvidenceSource 'media_probe_heartbeat'
        } else {
            $null
        }
        $sourceMediaProfile = Get-SourceMediaRouteProfile `
            -FilePath $file.FullName `
            -FileSizeBytes ([long]$file.Length) `
            -PollHandler $sourceProbePollHandler `
            -PollMilliseconds 1000
        if ($sourceMediaProfile -and $sourceMediaProfile.PSObject.Properties['probe_ok'] -and -not [bool]$sourceMediaProfile.probe_ok) {
            $probeFailure = Resolve-MediaPipelineSourceProbeFailure -SourceMediaProfile $sourceMediaProfile
            $reason = [string]$probeFailure.Reason
            $suggestedAction = [string]$probeFailure.SuggestedAction
            $errorCode = [string]$probeFailure.ErrorCode
            if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
                Set-MediaPipelineCurrentRunMonitorStage -StageId 'probe' -State 'failed' -Detail $reason -ReasonCode $errorCode -EvidenceSource 'media_probe' | Out-Null
            }
            Write-Log "${queuePrefix}$reason" "ERROR"
            try {
                Register-SourceFailure `
                    -SourceFile $file `
                    -Classification ([string]$probeFailure.Classification) `
                    -Reason $reason `
                    -Stage 'source-probe' `
                    -ErrorCode $errorCode `
                    -SuggestedAction $suggestedAction | Out-Null
            } catch {
                Write-Log "${queuePrefix}Failed to record $([string]$probeFailure.LogWarningCode) failure state: $($_.Exception.Message)" "WARN"
            }
            $result = New-MediaPipelineProcessFileResult `
                -File $file `
                -Status 'failed' `
                -Success:$false `
                -QueueTerminal:([bool]$probeFailure.QueueTerminal) `
                -Retryable:([bool]$probeFailure.Retryable) `
                -Reason $reason `
                -ErrorCode $errorCode `
                -RouteReasonCode ([string]$probeFailure.RouteReasonCode) `
                -RouteReason $reason
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'source-probe' -MediaType $queueLabel.ToLowerInvariant()
            return $result
        }
        if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
            Set-MediaPipelineCurrentRunMonitorStage -StageId 'probe' -State 'completed' -Detail 'Source media probe completed.' -EvidenceSource 'media_probe' | Out-Null
            Set-MediaPipelineCurrentRunMonitorStage -StageId 'route_decision' -State 'active' -Detail 'Applying backend route policy.' -EvidenceSource 'route_policy' -Indeterminate | Out-Null
        }
        $routePlan = Resolve-InitialMediaRoutePlan -File $file -IsTV:$isTV -MediaProfile $sourceMediaProfile -RouteHints $routeHints
        $encode    = [bool]$routePlan.ShouldEncode
        $script:CurrentRoutePlan = $routePlan
        $script:CurrentRouteReasonCode = [string]$routePlan.ReasonCode
        $script:CurrentRouteReason = [string]$routePlan.Reason
        $script:CurrentExecutedRoute = [string]$routePlan.Route
        $script:CurrentExecutedRouteReasonCode = [string]$routePlan.ReasonCode
        $script:CurrentExecutedRouteReason = [string]$routePlan.Reason
        if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
            Set-MediaPipelineCurrentRunMonitorStage -StageId 'route_decision' -State 'completed' -Detail ([string]$routePlan.Reason) -ReasonCode ([string]$routePlan.ReasonCode) -EvidenceSource 'route_policy' | Out-Null
        }
        if (Get-Command -Name Set-MediaPipelineRunMonitorExecutedRoute -ErrorAction SilentlyContinue) {
            try {
                Set-MediaPipelineRunMonitorExecutedRoute -RunId ([string]$script:PipelineRunId) -JobId ([string]$script:CurrentRunMonitorJobId) -Route ([string]$routePlan.Route) -ReasonCode ([string]$routePlan.ReasonCode) -Reason ([string]$routePlan.Reason) | Out-Null
            } catch {
                $script:RunMonitorPersistenceHealthy = $false
                Write-Log "Run Monitor executed-route evidence failed: $($_.Exception.Message)" 'WARN'
            }
        }
        Write-Log "${queuePrefix}SIZE: $([math]::Round([double]$routePlan.SizeGB,2)) GB | Route: $($routePlan.DisplayRoute)"
        DebugLog "${queuePrefix}ROUTE REASON: $($routePlan.ReasonCode) - $($routePlan.Reason)"
        $sourceRuntimeFacts = [ordered]@{
            source_media_profile = $routePlan.SourceMediaProfile
            source_codec = [string]$routePlan.SourceCodec
            size_gb = [double]$routePlan.SizeGB
            estimated_bitrate_mbps = [double]$routePlan.EstimatedBitrateMbps
            plex_compatibility_score = [double]$routePlan.PlexCompatibilityScore
        }
        $runtimeEffectiveSettings = New-MediaPipelineRuntimeEffectiveSettingsEvidence -Layers @(
            $runtimeSettingsLayers +
            (New-MediaPipelineRuntimeSettingsLayer -Name 'source' -Source 'ffprobe/probe' -Keys $sourceRuntimeFacts -SavedConfig:$false)
        )
        $script:CurrentRuntimeEffectiveSettings = $runtimeEffectiveSettings
        $routingKeySources = Get-MediaPipelineRuntimeEffectiveSettingSources -RuntimeEffectiveSettings $runtimeEffectiveSettings -Keys (Get-MediaPipelineRuntimeRoutingConsumerKeys)
        $runtimeOverrideLayers = Get-MediaPipelineRuntimeLayerNames -RuntimeEffectiveSettings $runtimeEffectiveSettings
        $runtimeUnsupportedKeys = @($runtimeEffectiveSettings['unsupported_keys'])
        $runtimeIgnoredKeys = @($runtimeEffectiveSettings['ignored_keys'])
        $routeRuleOutcomes = Get-MediaRouteRuleOutcomeEvidence -RoutePlan $routePlan
        $routingDecisionImpact = [ordered]@{}
        foreach ($routingKey in Get-MediaPipelineRuntimeRoutingConsumerKeys) {
            $routingDecisionImpact[$routingKey] = 'copy_remux_encode_decision_input'
        }
        $routingDecisionImpact['SizeGuardMode'] = 'post_encode_size_guard'
        $routingDecisionImpact['OutputContainer'] = 'container_policy_input'
        $routingDecisionImpact['MaxEncodeGrowthPercent'] = 'size_guard_budget'
        $routingDecisionImpact['CompatibilityEncodeGrowthPercent'] = 'size_guard_budget'
        $routingConsumerSettings = New-MediaPipelineRuntimeConsumerSettingsEvidence `
            -RuntimeEffectiveSettings $runtimeEffectiveSettings `
            -Consumer 'routing' `
            -Keys (Get-MediaPipelineRuntimeRoutingConsumerKeys) `
            -DecisionScope 'copy_remux_encode' `
            -ActionSelected ([string]$routePlan.Route) `
            -ActionEvidence ([string]$routePlan.ReasonCode) `
            -DecisionImpact $routingDecisionImpact
        $audioConsumerSettings = New-MediaPipelineRuntimeConsumerSettingsEvidence `
            -RuntimeEffectiveSettings $runtimeEffectiveSettings `
            -Consumer 'audio' `
            -Keys (Get-MediaPipelineRuntimeAudioConsumerKeys) `
            -DecisionScope 'audio_policy' `
            -ActionEvidence 'audio action is selected when the audio consumer builds ffmpeg args' `
            -Consequences ([ordered]@{
                AudioPassthroughProfile = 'passthrough eligibility'
                CompatibleAudioCodecs = 'copy compatibility allowlist'
                PreferredDefaultAudioLanguages = 'default audio language preference'
                AudioTranscodeCodec = 'transcode codec selection'
                AudioTranscodeBitrate = 'transcode bitrate selection'
                AudioTranscodeAutoBitrateByChannels = 'channel-aware bitrate selection'
                AudioDownmixMode = 'downmix policy'
                AudioMaxChannels = 'channel cap policy'
                AllowNoAudio = 'no-audio fallback policy'
            })
        $subtitleConsumerSettings = New-MediaPipelineRuntimeConsumerSettingsEvidence `
            -RuntimeEffectiveSettings $runtimeEffectiveSettings `
            -Consumer 'subtitles' `
            -Keys (Get-MediaPipelineRuntimeSubtitleConsumerKeys) `
            -DecisionScope 'subtitle_policy' `
            -ActionEvidence 'subtitle actions are selected when subtitle streams are filtered and converted' `
            -Consequences ([ordered]@{
                SubKeepLanguages = 'subtitle language keep policy'
                ConvertTx3gToSrt = 'TX3G conversion policy'
                DropTx3gAfterConversion = 'TX3G cleanup policy'
                ConvertBdpgsToSrt = 'BDPGS OCR conversion policy'
                DropBdpgsAfterConversion = 'BDPGS cleanup policy'
                ConvertVobSubToSrt = 'VobSub OCR conversion policy'
                DropVobSubAfterConversion = 'VobSub cleanup policy'
                VobSubOcrToolPath = 'VobSub OCR tool selection'
                VobSubOcrTimeoutSeconds = 'VobSub OCR timeout policy'
                TreatVobSubSignsSongsAsForced = 'VobSub forced/signs/songs classification'
                DropAssAfterConversion = 'ASS cleanup policy'
                StripFormatting = 'ASS/text subtitle cleanup policy'
                RemoveKaraoke = 'ASS karaoke cleanup policy'
            })
        $containerPathPlanningEvidence = Get-MediaPipelineOutputContainerPlanningEvidence `
            -LibraryOverrides $libraryOverrides `
            -RuntimeEffectiveSettings $runtimeEffectiveSettings `
            -LibraryOutputRoot ([string]$libraryEvidenceForJob['output_root']) `
            -LibrarySourceRoot ([string]$libraryEvidenceForJob['source_root']) `
            -DefaultOutputContainer ([string]$OutputContainer)
        $runtimeConsumerEvidence = [ordered]@{
            routing = $routingConsumerSettings
            audio = $audioConsumerSettings
            subtitles = $subtitleConsumerSettings
            container_path = $containerPathPlanningEvidence
        }
        $routingSourceText = (@($routingKeySources.Keys) | ForEach-Object {
            "{0}:{1}" -f $_, [string]$routingKeySources[$_]['source_layer']
        }) -join ', '
        if (-not [string]::IsNullOrWhiteSpace($routingSourceText)) {
            DebugLog "${queuePrefix}RUNTIME EVIDENCE: layers=$($runtimeOverrideLayers -join '>') routing_sources=$routingSourceText"
        }
        Write-PipelineEvent -EventType 'route_selected' -Stage 'route' -Route $routePlan.Route -Status 'selected' -SourcePath $file.FullName -Data @{
            route              = $routePlan.Route
            reason_code        = $routePlan.ReasonCode
            reason             = $routePlan.Reason
            size_gb            = [double]$routePlan.SizeGB
            threshold_gb       = [double]$routePlan.ThresholdGB
            estimated_bitrate_mbps = [double]$routePlan.EstimatedBitrateMbps
            source_codec       = [string]$routePlan.SourceCodec
            plex_compatibility_score = [double]$routePlan.PlexCompatibilityScore
            routing_profile   = if ($routePlan.PSObject.Properties['RoutingProfile']) { [string]$routePlan.RoutingProfile } else { [string]$script:RoutingProfile }
            size_guard_mode   = if ($routePlan.PSObject.Properties['SizeGuardMode']) { [string]$routePlan.SizeGuardMode } else { [string]$script:SizeGuardMode }
            route_actions      = $routePlan.Actions
            route_hints        = $routePlan.RouteHints
            decision_trace     = @($routePlan.DecisionTrace)
            source_media_profile = $routePlan.SourceMediaProfile
            requires_probe     = [bool]$routePlan.RequiresCodecProbe
            media_type         = $queueLabel.ToLowerInvariant()
            library_profile    = $libraryEvidenceForJob
            library_id         = [string]$libraryEvidenceForJob['library_id']
            library_name       = [string]$libraryEvidenceForJob['library_name']
            library_designation = [string]$libraryEvidenceForJob['designation']
            library_source_root = [string]$libraryEvidenceForJob['source_root']
            library_output_root = [string]$libraryEvidenceForJob['output_root']
            promotion_enabled = [bool]$libraryEvidenceForJob['promotion_enabled']
            promotion_destination_root = [string]$libraryEvidenceForJob['promotion_destination_root']
            promotion_rule_id = [string]$libraryEvidenceForJob['promotion_rule_id']
            promotion_rule_source = [string]$libraryEvidenceForJob['promotion_rule_source']
            library_settings_override_keys = @($libraryOverrides.Keys)
            library_settings_overrides = $libraryOverrides
            library_effective_settings = $libraryEffectiveSettings
            runtime_effective_settings = $runtimeEffectiveSettings
            runtime_effective_settings_ref = 'runtime_effective_settings.v1'
            library_effective_settings_ref = 'library-only'
            runtime_override_layers = $runtimeOverrideLayers
            runtime_unsupported_keys = $runtimeUnsupportedKeys
            runtime_ignored_keys = $runtimeIgnoredKeys
            routing_key_sources = $routingKeySources
            route_rule_outcomes = $routeRuleOutcomes
            runtime_consumer_evidence = $runtimeConsumerEvidence
            routing_consumer_settings = $routingConsumerSettings
            audio_consumer_settings = $audioConsumerSettings
            subtitle_consumer_settings = $subtitleConsumerSettings
            container_path_planning_evidence = $containerPathPlanningEvidence
        } | Out-Null

        $ok = $false
        $routeName = if ($encode) { 'encode' } else { 'remux' }
        if ($encode) {
            $script:pipelineStatus = if ($isTV) { "Encoding TV" } else { "Encoding Movie" }
            Set-ProgressStage -Stage 'encode_prepare' -Status $script:pipelineStatus -Route $routeName -Percent 0 -SaveNow
            $ok = Do-Encode $file $isTV $tvInfo
            if ($ok) { $script:totalEncoded++; $script:totalProcessed++
                       if ($isTV) { $script:totalTVEpisodes++ } else { $script:totalMovies++ } }
            else     { $script:totalFailed++ }
        } else {
            $script:pipelineStatus = if ($isTV) { "Remuxing TV" } else { "Remuxing Movie" }
            Set-ProgressStage -Stage 'remux_prepare' -Status $script:pipelineStatus -Route $routeName -Percent 0 -SaveNow
            $ok = Do-Remux $file $isTV $tvInfo
            if ($ok) { $script:totalRemuxed++; $script:totalProcessed++
                       if ($isTV) { $script:totalTVEpisodes++ } else { $script:totalMovies++ } }
            else     { $script:totalFailed++ }
        }
        $sizeGuardEvidence = New-MediaPipelineSizeGuardEvidence `
            -RuntimeEffectiveSettings $runtimeEffectiveSettings `
            -SizePolicyResult $script:CurrentSizePolicyResult `
            -RoutePlan $routePlan
        $publishEvidence = New-MediaPipelinePublishEvidence `
            -PublishResult $script:LastPublishResult `
            -Route $routeName
        $verificationEvidence = New-MediaPipelineVerificationEvidence `
            -SizeGuardEvidence $sizeGuardEvidence `
            -PublishEvidence $publishEvidence `
            -QualityEvidence $script:LastQualityVerification
        if ($ok) {
            Set-ProgressStage -Stage 'completed' -Status 'Completed' -Route $routeName -Percent 100 -SaveNow
            $publishResult = $script:LastPublishResult
            $result = New-MediaPipelineProcessFileResult -File $file -Status 'processed' -Success:$true -QueueTerminal:$true -Retryable:$false -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -PublishState ([string]$publishResult.PublishState) -PublishMode ([string]$publishResult.PublishMode) -OutputPath ([string]$publishResult.OutputPath) -OutputSizeBytes ([long]$publishResult.OutputSizeBytes) -SizeGuardEvidence $sizeGuardEvidence -VerificationEvidence $verificationEvidence -PublishEvidence $publishEvidence
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'completed' -MediaType $queueLabel.ToLowerInvariant()
            return $result
        } elseif (-not $script:StopRequested) {
            Set-ProgressStage -Stage 'failed' -Status 'Failed' -Route $routeName -Percent $null -SaveNow
            $publishResult = $script:LastPublishResult
            $routeFailureState = Get-SourceFailureState $file
            $failureReason = if ($publishResult -and $publishResult.Reason) {
                [string]$publishResult.Reason
            } elseif ($routeFailureState -and $routeFailureState.PSObject.Properties['reason'] -and -not [string]::IsNullOrWhiteSpace([string]$routeFailureState.reason)) {
                [string]$routeFailureState.reason
            } else {
                'Processing failed'
            }
            $failureErrorCode = if ($routeFailureState -and $routeFailureState.PSObject.Properties['error_code']) {
                Normalize-FailureCode -Code ([string]$routeFailureState.error_code)
            } else {
                ''
            }
            $failureRetryable = $true
            if ($routeFailureState -and $routeFailureState.PSObject.Properties['retryable']) {
                $failureRetryable = [bool]$routeFailureState.retryable
            } elseif (-not [string]::IsNullOrWhiteSpace($failureErrorCode) -and (Get-Command -Name Get-MediaPipelineCodeRetryable -ErrorAction SilentlyContinue)) {
                $failureRetryable = Get-MediaPipelineCodeRetryable -Code $failureErrorCode -Family ''
            }
            $failureQueueTerminal = -not [bool]$failureRetryable
            $result = New-MediaPipelineProcessFileResult -File $file -Status 'failed' -Success:$false -QueueTerminal:([bool]$failureQueueTerminal) -Retryable:([bool]$failureRetryable) -Reason $failureReason -ErrorCode $failureErrorCode -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -PublishState ([string]$publishResult.PublishState) -PublishMode ([string]$publishResult.PublishMode) -OutputPath ([string]$publishResult.OutputPath) -OutputSizeBytes ([long]$publishResult.OutputSizeBytes) -SizeGuardEvidence $sizeGuardEvidence -VerificationEvidence $verificationEvidence -PublishEvidence $publishEvidence
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'failed' -MediaType $queueLabel.ToLowerInvariant()
            return $result
        }
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'stopped' -Success:$false -QueueTerminal:$false -Retryable:$true -Reason 'Processing stopped by operator' -ErrorCode 'STOP_REQUESTED' -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -SizeGuardEvidence $sizeGuardEvidence -VerificationEvidence $verificationEvidence -PublishEvidence $publishEvidence
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'stopped' -MediaType $queueLabel.ToLowerInvariant()
        return $result
    } finally {
        Pop-MediaPipelineActiveConfigOverrides -Snapshot $activeConfigOverrideSnapshot
        $script:ActiveOverrides = $null
        $script:LastFileOverrideConfigMap = $null
        $script:LastFileOverrideMatch = $null
        $script:CurrentRuntimeEffectiveSettings = $null
        $script:CurrentJobId = $null
        if ($null -ne $previousLibraryProfileId) {
            $script:CurrentLibraryProfileId = $previousLibraryProfileId
        } else {
            Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
        }
        $script:CurrentRoutePlan = $null
        $script:CurrentEncodeAttempts = $null
        $script:CurrentSizePolicyResult = $null
        $script:LastQualityVerification = $null
        $script:LastPublishResult = $null
        $script:CurrentRouteReasonCode = $null
        $script:CurrentRouteReason = $null
        $script:CurrentExecutedRoute = $null
        $script:CurrentExecutedRouteReasonCode = $null
        $script:CurrentExecutedRouteReason = $null
        $script:CurrentAcceptedOutputPaths = $null
        if (-not $script:StopRequested) {
            Reset-ProgressItemContext
        }
    }
}
