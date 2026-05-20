# ============================================================================== 
# Modules\PipelineProcessing.ps1
# ============================================================================== 
# Job-level processing orchestration extracted from MediaPipeline_chatgpt.ps1.
# Dot-sourced by the main script; preserves script-scope configuration and the
# legacy Process-File wrapper in the main script.
# ============================================================================== 

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

function Invoke-MediaPipelineProcessFile {
    param(
        $file,
        [bool]$isTV,
        $idx,
        [int]$QueueIndex = 0,
        [int]$QueueTotal = 0,
        $PriorityInfo = $null
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

    if (-not ($ValidExtensions -contains $file.Extension.ToLower())) {
        Add-SkipStat 'BadExtension'
        Write-Log "SKIP (bad extension): $($file.Name)" "DEBUG"
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$false -QueueTerminal:$true -Retryable:$false -Reason 'Bad extension' -ErrorCode 'BAD_EXTENSION'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped'
        return $result
    }
    $failureState = Get-SourceFailureState $file
    if ($failureState) {
        $stateCode = if ($failureState.PSObject.Properties['error_code'] -and $failureState.error_code) {
            Normalize-FailureCode -Code ([string]$failureState.error_code)
        } else {
            Get-MediaFailureCode -Stage ([string]$failureState.stage) -Reason ([string]$failureState.reason) -Classification ([string]$failureState.classification)
        }
        $stateClassification = [string]$failureState.classification
        $retrySuffix = ''
        if ($failureState.PSObject.Properties['retry_count'] -and $failureState.PSObject.Properties['retry_limit']) {
            try {
                $retryCount = [int]$failureState.retry_count
                $retryLimit = [int]$failureState.retry_limit
                if ($retryCount -gt 0 -and $retryLimit -gt 0) { $retrySuffix = " retry=$retryCount/$retryLimit" }
            } catch {}
        }
        if ($stateClassification -eq 'permanent' -or $stateClassification -eq 'operator_required') {
            $skipKey = if ($stateClassification -eq 'operator_required') { 'OperatorRequired' } else { 'PermanentFailure' }
            Add-SkipStat $skipKey
            $label = if ($stateClassification -eq 'operator_required') { 'operator required' } else { 'permanent failure' }
            Write-Log "SKIP ($label [$stateCode]${retrySuffix}: $($failureState.reason)): $($file.Name)" "ERROR"
            $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$false -QueueTerminal:$true -Retryable:$false -Reason ([string]$failureState.reason) -ErrorCode $stateCode
            Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped'
            return $result
        }
        Add-RetryNotice
        Write-Log "RETRY after transient failure [$stateCode]$retrySuffix ($($failureState.stage)): $($file.Name)" "WARN"
    }
    $tvInfo = $null
    if ($isTV) { $tvInfo = Get-TVInfoFromFile $file }
    if ($isTV -and $tvInfo -and -not $tvInfo.IsReliable) {
        $renameSuggestion = Get-TVParseRenameSuggestion -File $file -TvInfo $tvInfo
        Register-SourceFailure -SourceFile $file -Classification 'permanent' -Reason $tvInfo.ParseError -Stage 'tv-parse' -SuggestedRename $renameSuggestion | Out-Null
        Add-SkipStat 'AmbiguousTV'
        Write-Log "SKIP (ambiguous TV filename): $($file.Name) — $($tvInfo.ParseError)" "ERROR"
        Write-Log "  Suggested rename: $renameSuggestion" "WARN"
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$false -QueueTerminal:$true -Retryable:$false -Reason ([string]$tvInfo.ParseError) -ErrorCode 'TV_PARSE_UNRELIABLE'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped' -MediaType 'tv'
        return $result
    }
    # ③ Apply ShowName canonical override NOW — before Already-Processed — so the
    #   index key, output path, and all downstream log messages use the final name.
    #   The full ActiveOverrides (audio/subtitle settings) are re-resolved below at
    #   the standard point; this early call is ShowName-only.
    if ($isTV -and $tvInfo -and $tvInfo.IsReliable -and $tvInfo.ShowName) {
        $_earlyOvr = Resolve-ShowOverrides $tvInfo.ShowName
        if (-not [string]::IsNullOrWhiteSpace([string]$_earlyOvr.ShowName)) {
            Write-Log "SHOW NAME OVERRIDE: '$($tvInfo.ShowName)' → '$($_earlyOvr.ShowName)'" "DEBUG"
            $tvInfo.ShowName = [string]$_earlyOvr.ShowName
        }
        Remove-Variable _earlyOvr -ErrorAction SilentlyContinue
    }
    if (Already-Processed $file $isTV $tvInfo $idx) {
        Add-SkipStat 'AlreadyProcessed'
        Clear-SourceFailureState $file
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$true -QueueTerminal:$true -Retryable:$false -Reason 'Already processed' -ErrorCode 'ALREADY_PROCESSED'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped' -MediaType $queueLabel.ToLowerInvariant()
        return $result
    }
    if (-not (Test-FileStable $file.FullName)) {
        Add-SkipStat 'StillWriting'
        Write-Log "SKIP (file still being written): $($file.Name)" "WARN"
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$false -QueueTerminal:$false -Retryable:$true -Reason 'File is still being written' -ErrorCode 'SOURCE_STILL_WRITING'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped' -MediaType $queueLabel.ToLowerInvariant()
        return $result
    }

    # Output path guard — test the actual filesystem/share capability instead
    # of rejecting by total string length. Long paths can be valid on modern
    # Windows/SMB; component length and write/create capability are what matter.
    $safeName  = Get-SafeLocalName $file.Name
    $testPaths = Get-OutputPaths $file $isTV $tvInfo $safeName
    $pathCheck = Test-OutputPathCapability -Paths $testPaths
    if (-not $pathCheck.Ok) {
        Add-SkipStat 'PathUnsupported'
        Register-SourceFailure -SourceFile $file -Classification 'permanent' -Reason $pathCheck.Reason -Stage 'path-capability' -SuggestedAction (Get-FailureSuggestedAction -Stage 'path-capability' -Reason $pathCheck.Reason) -SuggestedRename (Split-Path $testPaths.ServerOut -Leaf) | Out-Null
        Write-Log "SKIP (output path unsupported): $($file.Name) — $($pathCheck.Reason)" "WARN"
        if ($pathCheck.Path) { Write-Log "  Path: $($pathCheck.Path)" "DEBUG" }
        $result = New-MediaPipelineProcessFileResult -File $file -Status 'skipped' -Success:$false -QueueTerminal:$true -Retryable:$false -Reason ([string]$pathCheck.Reason) -ErrorCode 'OUTPUT_PATH_UNSUPPORTED'
        Write-MediaPipelineProcessCompletedEvent -Result $result -Stage 'skipped' -MediaType $queueLabel.ToLowerInvariant()
        return $result
    }

    $queuePhase = if ($PriorityInfo.IsPriority) { 'priority' } elseif ($isTV) { 'tv' } else { 'movie' }
    $displayName = "$queuePrefix$($file.Name)"
    $script:CurrentJobId = Get-SourceIdentityKeyV2 $file
    if (-not $script:CurrentJobId) { $script:CurrentJobId = Get-SourceIdentityKey $file }
    Set-ProgressItemContext -DisplayName $displayName -FilePath $file.FullName -MediaType $queueLabel.ToLowerInvariant() -QueuePhase $queuePhase -QueueIndex $QueueIndex -QueueTotal $QueueTotal
    Set-ProgressStage -Stage 'processing' -Status 'Processing' -Percent $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    Write-PipelineEvent -EventType 'job_started' -Stage 'processing' -Status 'started' -SourcePath $file.FullName -Data @{
        media_type   = $queueLabel.ToLowerInvariant()
        queue_phase  = $queuePhase
        queue_index  = $QueueIndex
        queue_total  = $QueueTotal
        priority     = [bool]$PriorityInfo.IsPriority
        display_name = $displayName
    } | Out-Null

    Write-Log "=========================================="
    Write-Log "${queuePrefix}FILE: $($file.Name)"
    if ($isTV) {
        Write-Log "${queuePrefix}TV: $($tvInfo.ShowName) S$($tvInfo.Season.ToString('00'))E$($tvInfo.Episode.ToString('00'))"
    } else { Write-Log "${queuePrefix}TYPE: Movie" }

    # Resolve effective per-job overrides before route selection so folder
    # policy can influence routing, encode ladders, audio, and subtitle policy
    # from one shared source of truth. Always cleared in the finally block.
    $showOverrides = if ($isTV -and $tvInfo.ShowName) { Resolve-ShowOverrides $tvInfo.ShowName } else { $null }
    $folderOverrides = Resolve-FolderPolicyOverrides -SourceFile $file
    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $showOverrides -Override $folderOverrides
    # Merge per-file à-la-carte overrides from file_overrides.json (Phase 3).
    # Stores the structured audio/subtitle override under '_FileOverride' and
    # promotes flat audio config fields so existing Get-Effective* functions
    # pick them up without modification. No-op if no entry exists for this file.
    Merge-FileOverrideIntoActiveOverrides -SourcePath $file.FullName
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
    } | Out-Null

    try {
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
        $script:ActiveOverrides = $null
        $script:CurrentJobId = $null
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
