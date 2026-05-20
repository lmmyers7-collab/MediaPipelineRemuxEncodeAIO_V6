# ==============================================================================
# Modules\PipelineEngine.ps1
# ==============================================================================
# Small orchestration helpers for executing pipeline queue rounds.
#
# Discovery, routing, processing, verification, publish, and record creation keep
# their existing helper ownership. This module owns the scan -> queue -> process
# round boundary while preserving the current call flow.
# ==============================================================================

function New-MediaPipelineEnginePlan {
    param(
        [Parameter(Mandatory)] [string] $SourceMovies,
        [Parameter(Mandatory)] [string] $SourceTV,
        [Parameter(Mandatory)] [string] $QueueSnapshotPath,
        [bool] $Once = $false,
        [int] $SleepSeconds = 30
    )

    return [pscustomobject]@{
        EnginePlanType   = 'media_pipeline_engine_plan.v1'
        SourceMovies     = $SourceMovies
        SourceTV         = $SourceTV
        QueueSnapshotPath = $QueueSnapshotPath
        Once             = [bool]$Once
        SleepSeconds     = [int]$SleepSeconds
    }
}

function Invoke-MediaQueuePhasePlan {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex
    )

    # ---- Phase 1: High-priority movies ----
    $highMovies = @($QueuePlan.HighPriorityMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    # ---- Phase 2: High-priority TV ----
    $highTV = @($QueuePlan.HighPriorityTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    if ($highMovies.Count -eq 0 -and $highTV.Count -eq 0 -and $QueuePlan.PriorityEntries) {
        $legacyPriorityEntries = @($QueuePlan.PriorityEntries)
        $highMovies = @($legacyPriorityEntries | Where-Object { -not [bool]$_.IsTV })
        $highTV = @($legacyPriorityEntries | Where-Object { [bool]$_.IsTV })
    }
    # ---- Combined priority count for logging ----
    $totalHighCount = $highMovies.Count + $highTV.Count

    if ($QueuePlan.MixPriorityPhase -and $totalHighCount -gt 0) {
        # MixPriorityPhase: run all high-priority items (movies + TV) together
        $mixedPriority = @(@($highMovies) + @($highTV))
        Write-Log "PRIORITY PHASE (mixed): $($mixedPriority.Count) item(s) queued first (movies: $($highMovies.Count), tv: $($highTV.Count))"
        foreach ($entry in $mixedPriority) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
        }
    } else {
        # Default: priority movies first, then priority TV
        if ($highMovies.Count -gt 0) {
            Write-Log "PRIORITY PHASE — MOVIES: $($highMovies.Count) item(s)"
            for ($i = 0; $i -lt $highMovies.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $highMovies[$i]
                Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
            }
        }
        if (-not $script:StopRequested -and $highTV.Count -gt 0) {
            Write-Log "PRIORITY PHASE — TV: $($highTV.Count) item(s)"
            for ($i = 0; $i -lt $highTV.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $highTV[$i]
                Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
            }
        }
    }

    # ---- Phase 3: Normal movies ----
    if (-not $script:StopRequested) {
        $normalMovieEntries = @($QueuePlan.NormalMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
        for ($i = 0; $i -lt $normalMovieEntries.Count; $i++) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            $entry = $normalMovieEntries[$i]
            Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
        }
    }

    # ---- Phase 4: Normal TV ----
    if (-not $script:StopRequested) {
        $normalTvEntries = @($QueuePlan.NormalTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
        for ($i = 0; $i -lt $normalTvEntries.Count; $i++) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            $entry = $normalTvEntries[$i]
            Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
        }
    }

    # ---- Phase 5: Low-priority entries (movies and TV interleaved, already sorted) ----
    if (-not $script:StopRequested) {
        $lowEntries = @($QueuePlan.LowEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
        if ($lowEntries.Count -gt 0) {
            Write-Log "LOW-PRIORITY PHASE: $($lowEntries.Count) item(s) deferred"
            for ($i = 0; $i -lt $lowEntries.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $lowEntries[$i]
                Process-File $entry.File ([bool]$entry.IsTV) $ProcessedIndex -QueueIndex $entry.QueueIndex -QueueTotal $entry.QueueTotal -PriorityInfo $entry.PriorityInfo
            }
        }
    }

    # ---- Hold entries are never processed ----
    $holdCount = [int]$QueuePlan.HoldCount
    if ($holdCount -gt 0) {
        Write-Log "HOLD: $holdCount item(s) excluded from processing this round (operator hold)"
    }

    return [pscustomobject]@{
        Stopped       = [bool]$script:StopRequested
        PriorityCount = $totalHighCount
        MovieCount    = [int]$QueuePlan.MovieCount
        TVCount       = [int]$QueuePlan.TVCount
        LowCount      = $QueuePlan.LowCount
        HoldCount     = $holdCount
    }
}

function Invoke-MediaPipelineQueueSnapshot {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex,
        [Parameter(Mandatory)] [string] $Path,
        [switch] $NonFatal
    )

    try {
        $snapshot = Build-QueuePlanSnapshotRows -QueuePlan $QueuePlan -ProcessedIndex $ProcessedIndex
        Write-QueuePlanSnapshot -Plan $snapshot -Path $Path
        return $snapshot
    } catch {
        if ($NonFatal) {
            Write-Log "Queue snapshot write failed (non-fatal): $_" "WARN"
            return $null
        }
        throw
    }
}

function Invoke-MediaPipelineRound {
    param(
        [Parameter(Mandatory)] $EnginePlan
    )

    Check-ControlFlags
    if ($script:StopRequested) {
        return [pscustomobject]@{
            Completed              = $false
            StopRequested          = $true
            RescanRequested        = $false
            PendingPushesRecovered = 0
            QueuePlan              = $null
            ProcessedIndex         = $null
            Snapshot               = $null
            RoundFailureSummary    = $null
        }
    }

    # Retry parked outputs before source discovery so recovered files are not
    # treated as missing by already-processed checks in the same round.
    $rescanRequested = Consume-RescanFlag
    $pendingPushesRecovered = Invoke-RetryPendingPushes
    Refresh-PendingPublishIndex | Out-Null
    if ($pendingPushesRecovered -gt 0) {
        Invalidate-ProcessedIndexCache
    }

    Reset-ProgressItemContext
    Set-ProgressStage -Stage 'scanning' -Status 'Scanning sources' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    Reset-RoundTracking
    $index = Get-ProcessedIndexCached -ForceRefresh:$rescanRequested

    $queuePlan = Get-MediaQueueDiscoveryPlan -MovieRoot $EnginePlan.SourceMovies -TVRoot $EnginePlan.SourceTV -ForceRefresh:$rescanRequested
    $script:RoundMovieFilesFound = [int]$queuePlan.MovieCount
    $script:RoundTVFilesFound = [int]$queuePlan.TVCount
    Write-Log "MOVIES FOUND: $($queuePlan.MovieCount) (priority: $($queuePlan.MoviePriorityCount))"
    Write-Log "TV FILES FOUND: $($queuePlan.TVCount) (priority: $($queuePlan.TVPriorityCount))"

    # Broadcast the post-filter plan so the desktop Queue tab can render the
    # live ordering without spawning a dry-run subprocess.
    $snapshot = Invoke-MediaPipelineQueueSnapshot -QueuePlan $queuePlan -ProcessedIndex $index -Path $EnginePlan.QueueSnapshotPath -NonFatal

    Set-ProgressStage -Stage 'processing' -Status 'Processing queue' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    Invoke-MediaQueuePhasePlan -QueuePlan $queuePlan -ProcessedIndex $index | Out-Null

    if ($script:StopRequested) {
        return [pscustomobject]@{
            Completed              = $false
            StopRequested          = $true
            RescanRequested        = [bool]$rescanRequested
            PendingPushesRecovered = [int]$pendingPushesRecovered
            QueuePlan              = $queuePlan
            ProcessedIndex         = $index
            Snapshot               = $snapshot
            RoundFailureSummary    = $null
        }
    }

    Write-Log "===== ROUND COMPLETE ====="
    Write-Log (Get-ProcessingStats)
    $roundFailureSummary = Write-RoundFailureSummary
    if ($roundFailureSummary) {
        Write-Log "Round failure summary: $($roundFailureSummary.TextPath)"
        Write-Log "Round failure summary JSON: $($roundFailureSummary.JsonPath)" "DEBUG"
    }

    # After one complete uninterrupted round with ReprocessAll, flip the flag
    # off in memory so the operator does not accidentally reprocess forever.
    if ($script:ReprocessAll) {
        Write-Log "*******************************************************************" "WARN"
        Write-Log "ReprocessAll auto-disabled for this process. One complete pass done." "WARN"
        Write-Log "Set ReprocessAll = `$false in MediaPipeline_config.psd1 to avoid"     "WARN"
        Write-Log "this warning on the next startup."                                    "WARN"
        Write-Log "*******************************************************************" "WARN"
        $script:ReprocessAll = $false
    }

    return [pscustomobject]@{
        Completed              = $true
        StopRequested          = $false
        RescanRequested        = [bool]$rescanRequested
        PendingPushesRecovered = [int]$pendingPushesRecovered
        QueuePlan              = $queuePlan
        ProcessedIndex         = $index
        Snapshot               = $snapshot
        RoundFailureSummary    = $roundFailureSummary
    }
}

function Invoke-MediaPipelineRun {
    param(
        [Parameter(Mandatory)] $EnginePlan
    )

    $roundsCompleted = 0
    while (-not $script:StopRequested) {
        $roundResult = Invoke-MediaPipelineRound -EnginePlan $EnginePlan
        if ($roundResult.Completed) { $roundsCompleted++ }
        if ($script:StopRequested) { break }

        if ($EnginePlan.Once) {
            Write-Log "Single-pass mode complete; exiting after one full round."
            break
        }

        Reset-ProgressItemContext
        Set-ProgressStage -Stage 'sleeping' -Status 'Idle' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
        Write-Log "SLEEPING $($EnginePlan.SleepSeconds)s..."
        Start-StopAwareSleep ([int]$EnginePlan.SleepSeconds) | Out-Null
    }

    return [pscustomobject]@{
        RoundsCompleted = $roundsCompleted
        StopRequested   = [bool]$script:StopRequested
    }
}

function Invoke-MediaPipelineEmitQueuePlan {
    param(
        [Parameter(Mandatory)] $EnginePlan
    )

    Set-ProgressStage -Stage 'scanning' -Status 'Scanning sources (dry run)' -Percent $null -SaveNow
    $index     = Get-ProcessedIndexCached -ForceRefresh:$true
    $queuePlan = Get-MediaQueueDiscoveryPlan -MovieRoot $EnginePlan.SourceMovies -TVRoot $EnginePlan.SourceTV -ForceRefresh:$true
    $snapshot  = Invoke-MediaPipelineQueueSnapshot -QueuePlan $queuePlan -ProcessedIndex $index -Path $EnginePlan.QueueSnapshotPath
    Write-Log "QUEUE PLAN SNAPSHOT: $($snapshot.runnable_count) runnable row(s) -> $($EnginePlan.QueueSnapshotPath)"
    Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
    return $snapshot
}

# Queue snapshot helpers are kept with the engine because snapshots are emitted
# from the same queue round boundary used by normal and dry-run execution.
function New-QueuePlanExcludedSnapshotRow {
    param(
        [Parameter(Mandatory)] $Entry,
        [int] $SourceOrder = 0,
        [string] $ReasonCode = 'excluded',
        [string] $Reason = '',
        $TvInfo = $null
    )

    $file = $Entry.File
    $sizeGb = 0.0
    if ($file) {
        try { $sizeGb = [math]::Round([double]$file.Length / 1GB, 3) } catch {}
    }

    $seasonNumber = 0
    $episodeNumber = 0
    if ($TvInfo) {
        try { $seasonNumber = [int]$TvInfo.Season } catch {}
        try { $episodeNumber = [int]$TvInfo.Episode } catch {}
    }
    if ($seasonNumber -le 0) {
        try { $seasonNumber = [int]$Entry.SeasonSortOrder } catch {}
    }
    if ($episodeNumber -le 0) {
        try { $episodeNumber = [int]$Entry.EpisodeSortOrder } catch {}
    }

    $lastWriteUtc = ''
    try {
        if ($Entry.LastWriteUtc -and $Entry.LastWriteUtc -ne [datetime]::MinValue) {
            $lastWriteUtc = ([datetime]$Entry.LastWriteUtc).ToString('o')
        } elseif ($file) {
            $lastWriteUtc = ([datetime]$file.LastWriteTimeUtc).ToString('o')
        }
    } catch {}

    return [ordered]@{
        source_order     = [int]$SourceOrder
        reason_code      = [string]$ReasonCode
        reason           = [string]$Reason
        phase            = [string]$Entry.QueuePhase
        media_kind       = [string]$Entry.MediaKind
        queue_index      = [int]$Entry.QueueIndex
        queue_total      = [int]$Entry.QueueTotal
        is_priority      = [bool]$Entry.IsPriority
        priority_reasons = @($Entry.PriorityInfo.Reasons)
        priority_rank    = [long]$Entry.PriorityOrderTicks
        source_path      = [string]$Entry.SourcePath
        root_path        = [string]$Entry.RootPath
        relative_path    = [string]$Entry.RelativePathSort
        display_name     = [string]$Entry.SortName
        show_sort_key    = [string]$Entry.ShowSortKey
        season_sort_key  = [string]$Entry.SeasonSortKey
        season_number    = [int]$seasonNumber
        episode_number   = [int]$episodeNumber
        size_gb          = $sizeGb
        last_write_utc   = $lastWriteUtc
    }
}

function Get-QueuePlanPreflightBlock {
    param(
        [Parameter(Mandatory)] $File,
        [bool] $IsTV = $false,
        $TvInfo = $null
    )

    $extension = ''
    try { $extension = [string]$File.Extension.ToLowerInvariant() } catch {}
    if (-not ($ValidExtensions -contains $extension)) {
        return [pscustomobject]@{
            Code   = 'bad_extension'
            Reason = "bad-extension: $extension"
            TvInfo = $TvInfo
        }
    }

    $failureState = $null
    try { $failureState = Get-SourceFailureState $File } catch {}
    if ($failureState) {
        $classification = [string]$failureState.classification
        if ($classification -eq 'permanent' -or $classification -eq 'operator_required') {
            $stateCode = ''
            try {
                if ($failureState.PSObject.Properties['error_code'] -and $failureState.error_code) {
                    $stateCode = Normalize-FailureCode -Code ([string]$failureState.error_code)
                } else {
                    $stateCode = Get-MediaFailureCode -Stage ([string]$failureState.stage) -Reason ([string]$failureState.reason) -Classification $classification
                }
            } catch {
                $stateCode = 'SOURCE_FAILURE_MARKER'
            }
            $reasonText = [string]$failureState.reason
            return [pscustomobject]@{
                Code   = if ($classification -eq 'operator_required') { 'source_failure_operator_required' } else { 'source_failure_permanent' }
                Reason = "source-failure: [$stateCode] $reasonText"
                TvInfo = $TvInfo
            }
        }
    }

    if ($IsTV) {
        if (-not $TvInfo) { $TvInfo = Get-TVInfoFromFile $File }
        if ($TvInfo -and -not $TvInfo.IsReliable) {
            return [pscustomobject]@{
                Code   = 'tv_parse_unreliable'
                Reason = "tv-parse: $($TvInfo.ParseError)"
                TvInfo = $TvInfo
            }
        }
    }

    return $null
}

function Build-QueuePlanSnapshotRows {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex
    )

    # Walk the plan in the exact order Invoke-MediaQueuePhasePlan would:
    # high-priority movies -> high-priority TV -> normal movies -> normal TV
    # -> low entries. Hold entries are appended last so the UI can display
    # them with a HOLD badge, but they are marked non-runnable.
    $ordered = @()
    if ($QueuePlan.MixPriorityPhase) {
        $ordered += @(@($QueuePlan.HighPriorityMovieEntries) + @($QueuePlan.HighPriorityTVEntries))
    } else {
        $ordered += @($QueuePlan.HighPriorityMovieEntries)
        $ordered += @($QueuePlan.HighPriorityTVEntries)
    }
    $ordered += @($QueuePlan.NormalMovieEntries)
    $ordered += @($QueuePlan.NormalTVEntries)
    $ordered += @($QueuePlan.LowEntries)
    # Hold entries appended at end — they render in the UI but never process
    $holdOrdered = @($QueuePlan.HoldEntries)

    $rows = New-Object System.Collections.Generic.List[object]
    $excludedRows = New-Object System.Collections.Generic.List[object]
    $excludedRowsTotal = 0
    $excludedRowsLimit = 500
    $globalOrder = 0
    $sourceOrder = 0
    foreach ($entry in $ordered) {
        if (-not $entry -or -not $entry.File) { continue }
        $sourceOrder++
        $file  = $entry.File
        $isTV  = [bool]$entry.IsTV
        $tvInfo = $null
        if ($isTV) {
            try { $tvInfo = Get-TVInfoFromFile $file } catch {}
        }
        $blocked = $null
        $blockedCode = ''
        $blockInfo = Get-QueuePlanPreflightBlock -File $file -IsTV:$isTV -TvInfo $tvInfo
        if ($blockInfo) {
            $blocked = [string]$blockInfo.Reason
            $blockedCode = [string]$blockInfo.Code
            if ($blockInfo.PSObject.Properties['TvInfo']) { $tvInfo = $blockInfo.TvInfo }
        }
        if (-not $blocked) {
            try {
                if (Already-Processed $file $isTV $tvInfo $ProcessedIndex) {
                    $excludedRowsTotal++
                    if ($excludedRows.Count -lt $excludedRowsLimit) {
                        $excludedRows.Add((New-QueuePlanExcludedSnapshotRow `
                            -Entry $entry `
                            -SourceOrder $sourceOrder `
                            -ReasonCode 'already_processed' `
                            -Reason 'Already processed by completed history, sidecar state, or pending-publish index.' `
                            -TvInfo $tvInfo)) | Out-Null
                    }
                    continue
                }
            } catch {
                $blocked = "already-processed-check failed: $_"
                $blockedCode = 'already_processed_check_failed'
            }
        }
        $globalOrder++
        $sizeGb = 0.0
        try { $sizeGb = [math]::Round([double]$file.Length / 1GB, 3) } catch {}
        $route = $null; $routeReason = $null; $routeReasonCode = $null; $routeDecisionTrace = @()
        $runtimeChecksDeferred = $false
        $runtimeCheckCodes = @()
        $runtimeCheckNotes = @()
        if (-not $blocked) {
            $runtimeChecksDeferred = $true
            $runtimeCheckCodes = @('source_stability', 'output_path_capability')
            $runtimeCheckNotes = @(
                'Source stability is checked by Test-FileStable only when processing starts.',
                'Output path capability is checked by Test-OutputPathCapability only when processing starts.'
            )
        }
        if ($blocked) {
            $routeReason = $blocked
            $routeReasonCode = $blockedCode
        } else {
            try {
            $previousOverrides = $script:ActiveOverrides
            try {
                $showOverrides = if ($isTV -and $tvInfo -and $tvInfo.ShowName -and (Get-Command -Name Resolve-ShowOverrides -ErrorAction SilentlyContinue)) {
                    Resolve-ShowOverrides $tvInfo.ShowName
                } else {
                    $null
                }
                $folderOverrides = if (Get-Command -Name Resolve-FolderPolicyOverrides -ErrorAction SilentlyContinue) {
                    Resolve-FolderPolicyOverrides -SourceFile $file
                } else {
                    $null
                }
                if (Get-Command -Name Merge-MediaPipelineActiveOverrides -ErrorAction SilentlyContinue) {
                    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $showOverrides -Override $folderOverrides
                } else {
                    $script:ActiveOverrides = $folderOverrides
                }
                $routeHints = if (Get-Command -Name Get-ActiveMediaRouteHints -ErrorAction SilentlyContinue) {
                    Get-ActiveMediaRouteHints
                } else {
                    $null
                }
                $sourceMediaProfile = if (Get-Command -Name Get-SourceMediaRouteProfile -ErrorAction SilentlyContinue) {
                    Get-SourceMediaRouteProfile -FilePath $file.FullName -FileSizeBytes ([long]$file.Length)
                } else {
                    $null
                }
                $rp = Resolve-InitialMediaRoutePlan -File $file -IsTV:$isTV -MediaProfile $sourceMediaProfile -RouteHints $routeHints
            } finally {
                $script:ActiveOverrides = $previousOverrides
            }
            if ($rp) {
                $route       = [string]$rp.DisplayRoute
                $routeReason = [string]$rp.Reason
                $routeReasonCode = [string]$rp.ReasonCode
                $routeDecisionTrace = @($rp.DecisionTrace)
            }
        } catch {
            $routeReason = "route preview failed: $($_.Exception.Message)"
        }
        }
        $rows.Add([ordered]@{
            global_order            = $globalOrder
            phase                   = [string]$entry.QueuePhase
            manifest_priority_level = [string]$entry.EffectivePriorityLevel
            media_kind              = [string]$entry.MediaKind
            queue_index             = [int]$entry.QueueIndex
            queue_total             = [int]$entry.QueueTotal
            is_priority             = [bool]$entry.IsPriority
            priority_reasons        = @($entry.PriorityInfo.Reasons)
            priority_rank           = [long]$entry.PriorityOrderTicks
            source_path             = [string]$entry.SourcePath
            root_path               = [string]$entry.RootPath
            relative_path           = [string]$entry.RelativePathSort
            display_name            = [string]$entry.SortName
            show_sort_key           = [string]$entry.ShowSortKey
            season_sort_key         = [string]$entry.SeasonSortKey
            season_number           = [int]$entry.SeasonSortOrder
            episode_number          = [int]$entry.EpisodeSortOrder
            size_gb                 = $sizeGb
            last_write_utc          = ([datetime]$entry.LastWriteUtc).ToString('o')
            route                   = $route
            route_reason_code       = $routeReasonCode
            route_reason            = $routeReason
            route_decision_trace    = @($routeDecisionTrace)
            blocked_reason_code     = $blockedCode
            blocked_reason          = $blocked
            runtime_checks_deferred = [bool]$runtimeChecksDeferred
            runtime_check_codes     = @($runtimeCheckCodes)
            runtime_check_notes     = @($runtimeCheckNotes)
        }) | Out-Null
    }

    # Append hold entries to the runnable rows list so the UI can render them
    # with a HOLD badge. They are pre-marked with phase="hold".
    foreach ($holdEntry in $holdOrdered) {
        if (-not $holdEntry -or -not $holdEntry.File) { continue }
        $holdFile = $holdEntry.File
        $holdSizeGb = 0.0
        try { $holdSizeGb = [math]::Round([double]$holdFile.Length / 1GB, 3) } catch {}
        $holdLastWriteUtc = ''
        try { $holdLastWriteUtc = ([datetime]$holdEntry.LastWriteUtc).ToString('o') } catch {}
        $globalOrder++
        $rows.Add([ordered]@{
            global_order            = $globalOrder
            phase                   = 'hold'
            manifest_priority_level = 'hold'
            media_kind              = [string]$holdEntry.MediaKind
            queue_index             = 0
            queue_total             = 0
            is_priority             = $false
            priority_reasons        = @()
            priority_rank           = 0L
            source_path             = [string]$holdEntry.SourcePath
            root_path               = [string]$holdEntry.RootPath
            relative_path           = [string]$holdEntry.RelativePathSort
            display_name            = [string]$holdEntry.SortName
            show_sort_key           = [string]$holdEntry.ShowSortKey
            season_sort_key         = [string]$holdEntry.SeasonSortKey
            season_number           = [int]$holdEntry.SeasonSortOrder
            episode_number          = [int]$holdEntry.EpisodeSortOrder
            size_gb                 = $holdSizeGb
            last_write_utc          = $holdLastWriteUtc
            route                   = $null
            route_reason_code       = 'hold'
            route_reason            = 'Operator hold — excluded from processing this round.'
            route_decision_trace    = @()
            blocked_reason_code     = 'hold'
            blocked_reason          = 'Operator hold.'
            runtime_checks_deferred = $false
            runtime_check_codes     = @()
            runtime_check_notes     = @()
        }) | Out-Null
    }

    # F-new-2 — surface the NVENC availability probe so the desktop Queue
    # tab can render a "GPU unavailable; encodes will run on CPU and may
    # take several hours each" banner instead of the operator only seeing
    # CPU labels appear after the first GPU-failed file.
    $nvencProbe = if ($script:NvencAvailableProbe) { $script:NvencAvailableProbe } else { $null }
    $gpuAvailable = $true
    $gpuReason = ''
    if ($nvencProbe) {
        $gpuAvailable = [bool]$nvencProbe.Available
        $gpuReason = [string]$nvencProbe.Reason
    }

    return [pscustomobject]@{
        schema_version    = 'queue_plan_snapshot.v1'
        produced_at       = (Get-Date).ToUniversalTime().ToString('o')
        config_path       = [string]$configPath
        local_base        = [string]$LocalBase
        source_movies     = [string]$SourceMovies
        source_tv         = [string]$SourceTV
        outsource         = [string]$Outsource
        priority_markers  = @($script:PriorityMarkers)
        movie_count_total = [int]$QueuePlan.MovieCount
        tv_count_total    = [int]$QueuePlan.TVCount
        priority_count    = [int]$QueuePlan.PriorityEntries.Count
        low_count         = [int]$QueuePlan.LowCount
        hold_count        = [int]$QueuePlan.HoldCount
        mix_priority_phase        = [bool]$QueuePlan.MixPriorityPhase
        queue_ordering_strategy   = [string]$QueuePlan.QueueOrderingStrategy
        runnable_count    = $rows.Count
        excluded_count    = [int]$excludedRowsTotal
        excluded_row_limit = [int]$excludedRowsLimit
        excluded_rows_truncated = [bool]($excludedRowsTotal -gt $excludedRows.Count)
        excluded_rows     = $excludedRows
        rows              = $rows
        gpu_available     = $gpuAvailable
        gpu_unavailable_reason = $gpuReason
    }
}

function Write-QueuePlanSnapshot {
    param(
        [Parameter(Mandatory)] $Plan,
        [Parameter(Mandatory)] [string] $Path
    )
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $target = [System.IO.Path]::GetFullPath($Path)
    $targetDir = Split-Path -Parent $target
    $leaf = Split-Path -Leaf $target
    $id = [guid]::NewGuid().ToString("N")
    $tmp = Join-Path $targetDir (".$leaf.$id.tmp")
    $backup = Join-Path $targetDir (".$leaf.$id.bak")
    try {
        $json = $Plan | ConvertTo-Json -Depth 8
        [System.IO.File]::WriteAllText($tmp, $json, [System.Text.UTF8Encoding]::new($false))
        if ([System.IO.File]::Exists($target)) {
            [System.IO.File]::Replace($tmp, $target, $backup, $true)
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        } else {
            [System.IO.File]::Move($tmp, $target)
        }
    } catch {
        if ($tmp -and (Test-Path -LiteralPath $tmp -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
        }
        if ($backup -and (Test-Path -LiteralPath $backup -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $backup -Force -ErrorAction SilentlyContinue
        }
        throw
    }
}
