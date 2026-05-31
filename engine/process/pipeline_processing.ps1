# ============================================================================== 
# engine\process\pipeline_processing.ps1
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
        [long] $OutputSizeBytes = 0
    )

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
    } | Out-Null
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

    $tvDecision = Get-MediaPipelineTvParsePreflight -File $file -IsTV:$isTV
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
    } | Out-Null

    Write-Log "=========================================="
    Write-Log "${queuePrefix}FILE: $($file.Name)"
    if ($isTV) {
        Write-Log "${queuePrefix}TV: $($tvInfo.ShowName) S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
    } else { Write-Log "${queuePrefix}TYPE: Movie" }
    $libraryLogName = if ([string]::IsNullOrWhiteSpace([string]$libraryEvidenceForJob['library_name'])) { [string]$libraryEvidenceForJob['library_id'] } else { [string]$libraryEvidenceForJob['library_name'] }
    $libraryOverrideKeyText = (@($libraryEvidenceForJob['settings_override_keys']) | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ', '
    Write-Log "${queuePrefix}LIBRARY: $libraryLogName ($($libraryEvidenceForJob['library_id'])) source=$($libraryEvidenceForJob['source_root']) output=$($libraryEvidenceForJob['output_root']) overrides=$libraryOverrideKeyText" "INFO"

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
    Merge-FileOverrideIntoActiveOverrides -SourcePath $file.FullName
    $libraryEffectiveSettings = Resolve-MediaPipelineLibraryEffectiveSettings -Overrides $libraryOverrides
    $activeConfigOverrideSnapshot = Push-MediaPipelineActiveConfigOverrides -Overrides $script:ActiveOverrides
    try {
        $script:CurrentSizePolicyResult = $null
        $routeHints = Get-ActiveMediaRouteHints
        $sourceMediaProfile = Get-SourceMediaRouteProfile -FilePath $file.FullName -FileSizeBytes ([long]$file.Length)
        $routePlan = Resolve-InitialMediaRoutePlan -File $file -IsTV:$isTV -MediaProfile $sourceMediaProfile -RouteHints $routeHints
        $encode    = [bool]$routePlan.ShouldEncode
        $script:CurrentRoutePlan = $routePlan
        $script:CurrentRouteReasonCode = [string]$routePlan.ReasonCode
        $script:CurrentRouteReason = [string]$routePlan.Reason
        Write-Log "${queuePrefix}SIZE: $([math]::Round([double]$routePlan.SizeGB,2)) GB | Route: $($routePlan.DisplayRoute)"
        DebugLog "${queuePrefix}ROUTE REASON: $($routePlan.ReasonCode) - $($routePlan.Reason)"
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
            library_settings_override_keys = @($libraryOverrides.Keys)
            library_settings_overrides = $libraryOverrides
            library_effective_settings = $libraryEffectiveSettings
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
        if ($ok) {
            Set-ProgressStage -Stage 'completed' -Status 'Completed' -Route $routeName -Percent 100 -SaveNow
            $publishResult = $script:LastPublishResult
            $result = New-MediaPipelineProcessFileResult -File $file -Status 'processed' -Success:$true -QueueTerminal:$true -Retryable:$false -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -PublishState ([string]$publishResult.PublishState) -PublishMode ([string]$publishResult.PublishMode) -OutputPath ([string]$publishResult.OutputPath) -OutputSizeBytes ([long]$publishResult.OutputSizeBytes)
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'completed' -MediaType $queueLabel.ToLowerInvariant()
            return $result
        } elseif (-not $script:StopRequested) {
            Set-ProgressStage -Stage 'failed' -Status 'Failed' -Route $routeName -Percent $null -SaveNow
            $publishResult = $script:LastPublishResult
            $failureReason = if ($publishResult -and $publishResult.Reason) { [string]$publishResult.Reason } else { 'Processing failed' }
            $result = New-MediaPipelineProcessFileResult -File $file -Status 'failed' -Success:$false -QueueTerminal:$false -Retryable:$true -Reason $failureReason -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason) -PublishState ([string]$publishResult.PublishState) -PublishMode ([string]$publishResult.PublishMode) -OutputPath ([string]$publishResult.OutputPath) -OutputSizeBytes ([long]$publishResult.OutputSizeBytes)
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'failed' -MediaType $queueLabel.ToLowerInvariant()
            return $result
        }
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'stopped' -Success:$false -QueueTerminal:$false -Retryable:$true -Reason 'Processing stopped by operator' -ErrorCode 'STOP_REQUESTED' -Route $routeName -RouteReasonCode ([string]$script:CurrentRouteReasonCode) -RouteReason ([string]$script:CurrentRouteReason)
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'stopped' -MediaType $queueLabel.ToLowerInvariant()
        return $result
    } finally {
        Pop-MediaPipelineActiveConfigOverrides -Snapshot $activeConfigOverrideSnapshot
        $script:ActiveOverrides = $null
        $script:CurrentJobId = $null
        if ($null -ne $previousLibraryProfileId) {
            $script:CurrentLibraryProfileId = $previousLibraryProfileId
        } else {
            Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
        }
        $script:CurrentRoutePlan = $null
        $script:CurrentEncodeAttempts = $null
        $script:CurrentSizePolicyResult = $null
        $script:LastPublishResult = $null
        $script:CurrentRouteReasonCode = $null
        $script:CurrentRouteReason = $null
        if (-not $script:StopRequested) {
            Reset-ProgressItemContext
        }
    }
}
