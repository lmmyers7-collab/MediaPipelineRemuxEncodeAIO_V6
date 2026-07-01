# ==============================================================================
# ops\pipeline\engine\queue\pipeline_engine.ps1
# ==============================================================================
# Small orchestration helpers for executing pipeline queue rounds.
#
# Discovery, routing, processing, verification, publish, and record creation keep
# their existing helper ownership. This module owns the scan -> queue -> process
# round boundary while preserving the current call flow.
# ==============================================================================


. (Join-Path $PSScriptRoot 'engine_plan.ps1')
. (Join-Path $PSScriptRoot 'phase_executor.ps1')
. (Join-Path $PSScriptRoot 'snapshot_rows.ps1')
. (Join-Path $PSScriptRoot 'snapshot_store.ps1')

function Get-MediaPipelinePendingPublishBackpressure {
    $pendingRoot = [string]$script:PendingPushRoot
    if ([string]::IsNullOrWhiteSpace($pendingRoot)) {
        try { $pendingRoot = [string]$script:LocalStateLayout.Paths.PendingPublish } catch {}
    }
    $manifestPaths = @()
    if (-not [string]::IsNullOrWhiteSpace($pendingRoot) -and (Test-Path -LiteralPath $pendingRoot -PathType Container)) {
        try {
            $manifestPaths = @(Get-ChildItem -LiteralPath $pendingRoot -Filter '*.manifest.json' -File -ErrorAction Stop)
        } catch {
            Write-Log "Pending publish backpressure scan failed: $_" 'WARN'
        }
    }
    $now = Get-Date
    $oldestAgeSeconds = $null
    $retryExhaustedCount = 0
    $totalBytes = [int64]0
    foreach ($manifestPath in @($manifestPaths)) {
        $manifest = $null
        try {
            $manifest = Get-Content -LiteralPath $manifestPath.FullName -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        } catch {
            continue
        }
        $parkedAtText = ''
        try {
            if ($manifest.PSObject.Properties['parked_at']) { $parkedAtText = [string]$manifest.parked_at }
            elseif ($manifest.PSObject.Properties['ParkedAt']) { $parkedAtText = [string]$manifest.ParkedAt }
        } catch {}
        if (-not [string]::IsNullOrWhiteSpace($parkedAtText)) {
            try {
                $age = [int](($now.ToUniversalTime()) - ([datetime]$parkedAtText).ToUniversalTime()).TotalSeconds
                if ($age -ge 0 -and ($null -eq $oldestAgeSeconds -or $age -gt $oldestAgeSeconds)) {
                    $oldestAgeSeconds = $age
                }
            } catch {}
        }
        try {
            $retryCount = if ($manifest.PSObject.Properties['retry_count']) { [int]$manifest.retry_count } else { 0 }
            $retryLimit = if ($manifest.PSObject.Properties['retry_limit']) { [int]$manifest.retry_limit } else { 3 }
            if ($retryCount -ge $retryLimit) { $retryExhaustedCount++ }
        } catch {}
        try {
            if ($manifest.PSObject.Properties['output_size']) { $totalBytes += [int64]$manifest.output_size }
            elseif ($manifest.PSObject.Properties['OutputSizeBytes']) { $totalBytes += [int64]$manifest.OutputSizeBytes }
        } catch {}
    }
    $count = [int]@($manifestPaths).Count
    $deferred = [bool]$script:DeferredPublish
    $normalThreshold = [int]$script:PendingPublishBacklogBlockThreshold
    if ($normalThreshold -le 0) { $normalThreshold = 100 }
    $deferredThreshold = [int]$script:PendingPublishDeferredBlockThreshold
    if ($deferredThreshold -le 0) { $deferredThreshold = 25 }
    $blockReason = ''
    if ($deferred -and $count -ge $deferredThreshold) {
        $blockReason = 'deferred_backlog_threshold'
    } elseif (-not $deferred -and $count -ge $normalThreshold) {
        $blockReason = 'backlog_threshold'
    } elseif (-not $deferred -and $null -ne $oldestAgeSeconds -and $oldestAgeSeconds -ge (72 * 60 * 60)) {
        $blockReason = 'oldest_age_threshold'
    } elseif (-not $deferred -and $retryExhaustedCount -gt 0) {
        $blockReason = 'retry_exhausted'
    }
    return [pscustomobject]@{
        Blocked             = -not [string]::IsNullOrWhiteSpace($blockReason)
        BlockReason         = $blockReason
        DeferredPublish     = $deferred
        ManifestCount       = $count
        OldestAgeSeconds    = $oldestAgeSeconds
        TotalBytes          = $totalBytes
        RetryExhaustedCount = $retryExhaustedCount
        NormalThreshold     = $normalThreshold
        DeferredThreshold   = $deferredThreshold
        PendingRoot         = $pendingRoot
    }
}

function Write-MediaPipelinePendingPublishBackpressure {
    param([Parameter(Mandatory)] $Backpressure)

    Write-Log "Pending publish backpressure blocked queue execution: reason=$($Backpressure.BlockReason); count=$($Backpressure.ManifestCount); deferred=$($Backpressure.DeferredPublish)" 'WARN'
    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        try {
            Write-PipelineEvent -EventType 'pending_publish_backpressure_blocked' -Stage 'pending_publish' -Status 'blocked' -Data @{
                error_code            = 'PENDING_PUBLISH_BACKPRESSURE_BLOCKED'
                block_reason          = [string]$Backpressure.BlockReason
                deferred_publish      = [bool]$Backpressure.DeferredPublish
                manifest_count        = [int]$Backpressure.ManifestCount
                oldest_age_seconds    = $Backpressure.OldestAgeSeconds
                total_bytes           = [int64]$Backpressure.TotalBytes
                retry_exhausted_count = [int]$Backpressure.RetryExhaustedCount
                pending_root          = [string]$Backpressure.PendingRoot
            } | Out-Null
        } catch {}
    }
    try {
        Set-ProgressStage -Stage 'pending_publish_backpressure' -Status 'Pending publish backpressure blocked new queue work' -Percent $null -Route $null -CopyState $null -PushState 'blocked' -SidecarState $null -SaveNow
    } catch {}
}

function Select-MediaPipelineQueuePlanExecutionWindow {
    param([Parameter(Mandatory)] $QueuePlan)

    $limit = [int]$script:QueueExecutionMaxRunnablePerRound
    if ($limit -le 0) { return $QueuePlan }
    $entries = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    if ($entries.Count -le $limit) { return $QueuePlan }
    $selected = @($entries | Select-Object -First $limit)
    Write-Log "QUEUE EXECUTION CAP: processing $limit of $($entries.Count) runnable item(s) this round; remaining runnable items will be reconsidered next round." 'WARN'
    if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
        try {
            Write-PipelineEvent -EventType 'queue_execution_capped' -Stage 'queue' -Status 'review' -Data @{
                runnable_total_before_cap = [int]$entries.Count
                execution_limit           = [int]$limit
                selected_count            = [int]$selected.Count
            } | Out-Null
        } catch {}
    }
    return [pscustomobject]@{
        HighPriorityMovieEntries  = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_movie' })
        HighPriorityTVEntries     = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_tv' })
        PriorityEntries           = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority' })
        NormalMovieEntries        = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'movie' })
        NormalTVEntries           = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'tv' })
        LowEntries                = @($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'low' })
        HoldEntries               = @($QueuePlan.HoldEntries)
        MixPriorityPhase          = [bool]$QueuePlan.MixPriorityPhase
        MovieCount                = [int](@($selected | Where-Object { -not [bool]$_.IsTV }).Count)
        TVCount                   = [int](@($selected | Where-Object { [bool]$_.IsTV }).Count)
        MoviePriorityCount        = [int](@($selected | Where-Object { -not [bool]$_.IsTV -and [bool]$_.IsPriority }).Count)
        TVPriorityCount           = [int](@($selected | Where-Object { [bool]$_.IsTV -and [bool]$_.IsPriority }).Count)
        LowCount                  = [int](@($selected | Where-Object { [string]$_.LocalWorkerPhase -eq 'low' }).Count)
        HoldCount                 = [int]$QueuePlan.HoldCount
        RunnableTotalBeforeCap    = [int]$entries.Count
        RunnableExecutionLimit    = [int]$limit
        RowsTruncatedForExecution = $true
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
    $pendingBackpressure = Get-MediaPipelinePendingPublishBackpressure
    if ([bool]$pendingBackpressure.Blocked) {
        Write-MediaPipelinePendingPublishBackpressure -Backpressure $pendingBackpressure
        return [pscustomobject]@{
            Completed              = $true
            StopRequested          = [bool]$script:StopRequested
            RescanRequested        = [bool]$rescanRequested
            PendingPushesRecovered = [int]$pendingPushesRecovered
            QueuePlan              = $null
            ProcessedIndex         = $null
            Snapshot               = $null
            RoundFailureSummary    = $null
            BackpressureBlocked    = $true
            BackpressureReason     = [string]$pendingBackpressure.BlockReason
        }
    }

    $scanStartedAt = Get-Date
    $index = Get-ProcessedIndexCached -ForceRefresh:$rescanRequested

    $queuePlan = Get-MediaQueueDiscoveryPlan -MovieRoot $EnginePlan.SourceMovies -TVRoot $EnginePlan.SourceTV -ForceRefresh:$rescanRequested
    $scanDurationSeconds = [math]::Round(((Get-Date) - $scanStartedAt).TotalSeconds, 3)
    $script:LastQueueScanDurationSeconds = $scanDurationSeconds
    $script:LastQueueCandidateCount = [int]($queuePlan.MovieCount + $queuePlan.TVCount + $queuePlan.HoldCount)
    $script:LastQueueScanTruncated = $false
    $script:LastQueueScanTimedOut = $false
    $script:RoundMovieFilesFound = [int]$queuePlan.MovieCount
    $script:RoundTVFilesFound = [int]$queuePlan.TVCount
    Write-Log "MOVIES FOUND: $($queuePlan.MovieCount) (priority: $($queuePlan.MoviePriorityCount))"
    Write-Log "TV FILES FOUND: $($queuePlan.TVCount) (priority: $($queuePlan.TVPriorityCount))"

    # Broadcast the post-filter plan so the desktop Queue tab can render the
    # live ordering without spawning a dry-run subprocess.
    $snapshot = Invoke-MediaPipelineQueueSnapshot -QueuePlan $queuePlan -ProcessedIndex $index -Path $EnginePlan.QueueSnapshotPath -NonFatal

    Set-ProgressStage -Stage 'processing' -Status 'Processing queue' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    $executionPlan = Select-MediaPipelineQueuePlanExecutionWindow -QueuePlan $queuePlan
    $script:LastQueueExecutionTruncated = [bool]($executionPlan.PSObject.Properties['RowsTruncatedForExecution'] -and [bool]$executionPlan.RowsTruncatedForExecution)
    if ($script:LastQueueExecutionTruncated) {
        $script:LastQueueCandidateCount = [int]$executionPlan.RunnableTotalBeforeCap
    }
    $useLocalWorkerSlots = ([string]$EnginePlan.ParallelEncodeMode -eq 'local_worker_slots' -and [int]$EnginePlan.MaxParallelEncodes -gt 1)
    if ($useLocalWorkerSlots) {
        if (-not (Get-Command -Name Invoke-MediaQueuePhasePlanLocalWorkerSlots -ErrorAction SilentlyContinue)) {
            throw "Local worker slots are enabled, but Invoke-MediaQueuePhasePlanLocalWorkerSlots is not loaded."
        }
        if ([string]::IsNullOrWhiteSpace([string]$EnginePlan.ScriptPath)) {
            throw "Local worker slots are enabled, but the pipeline script path was not supplied."
        }
        if ([string]::IsNullOrWhiteSpace([string]$EnginePlan.ConfigPath)) {
            throw "Local worker slots are enabled, but the config path was not supplied."
        }
        if ([string]::IsNullOrWhiteSpace([string]$EnginePlan.PowerShellPath)) {
            throw "Local worker slots are enabled, but the PowerShell executable path was not supplied."
        }
        Write-Log "LOCAL WORKER SLOTS: dispatching queue with $([int]$EnginePlan.MaxParallelEncodes) slot(s)"
        Invoke-MediaQueuePhasePlanLocalWorkerSlots `
            -QueuePlan $executionPlan `
            -ProcessedIndex $index `
            -ScriptPath ([string]$EnginePlan.ScriptPath) `
            -ConfigPath ([string]$EnginePlan.ConfigPath) `
            -PowerShellPath ([string]$EnginePlan.PowerShellPath) `
            -MaxParallelEncodes ([int]$EnginePlan.MaxParallelEncodes) | Out-Null
    } else {
        Invoke-MediaQueuePhasePlan -QueuePlan $executionPlan -ProcessedIndex $index -StopOnUnexpectedFailure:([bool]$EnginePlan.Once) | Out-Null
    }

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
    Invoke-PeriodicLocalEncodedDirectoryCleanup | Out-Null

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
    $unexpectedRoundFailures = 0
    $script:UnexpectedRoundFailures = 0
    $script:ConsecutiveUnexpectedRoundFailures = 0
    $script:ContinuousRoundFailuresBlocked = $false
    $script:LastUnexpectedRoundFailureAt = $null
    while (-not $script:StopRequested) {
        try {
            $roundResult = Invoke-MediaPipelineRound -EnginePlan $EnginePlan
        } catch {
            $unexpectedRoundFailures++
            $script:UnexpectedRoundFailures = [int]$unexpectedRoundFailures
            $script:ConsecutiveUnexpectedRoundFailures = [int]$script:ConsecutiveUnexpectedRoundFailures + 1
            $script:LastUnexpectedRoundFailureAt = (Get-Date).ToUniversalTime().ToString('o')
            $message = if ($_.Exception -and $_.Exception.Message) { [string]$_.Exception.Message } else { [string]$_ }
            $blockLimit = [int]$script:ConsecutiveRoundFailureBlockLimit
            if ($blockLimit -le 0) { $blockLimit = 12 }
            $probeBackoffSeconds = [int]$script:ConsecutiveRoundFailureProbeBackoffSeconds
            if ($probeBackoffSeconds -le 0) { $probeBackoffSeconds = 900 }
            $blocked = ([int]$script:ConsecutiveUnexpectedRoundFailures -ge $blockLimit)
            $script:ContinuousRoundFailuresBlocked = [bool]$blocked
            Write-Log "Unexpected pipeline round failure: $message" 'ERROR'
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                try {
                    $eventStatus = if ($blocked) { 'blocked' } else { 'failed' }
                    Write-PipelineEvent -EventType 'pipeline_round_unexpected_failure' -Stage 'round' -Status $eventStatus -Data @{
                        error_code                 = 'UNEXPECTED_PIPELINE_ROUND_EXCEPTION'
                        error                      = $message
                        once                       = [bool]$EnginePlan.Once
                        failure_count             = [int]$unexpectedRoundFailures
                        consecutive_failure_count = [int]$script:ConsecutiveUnexpectedRoundFailures
                        block_limit                = [int]$blockLimit
                        blocked                    = [bool]$blocked
                    } | Out-Null
                } catch {}
            }
            try {
                Reset-ProgressItemContext
                $failedStage = if ($blocked) { 'blocked' } else { 'failed' }
                $failedStatus = if ($blocked) { 'Unexpected round failures blocked' } else { 'Unexpected round failure' }
                Set-ProgressStage -Stage $failedStage -Status $failedStatus -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
            } catch {}
            if ($EnginePlan.Once) {
                throw
            }
            if ($blocked) {
                $script:StopRequested = $true
                $script:PipelineBlockedExitCode = 76
                $script:PipelineStopReason = 'consecutive_round_failures_blocked'
                Write-Log "Stopping continuous loop after $($script:ConsecutiveUnexpectedRoundFailures) consecutive unexpected round failure(s); blocked exit code 76." 'ERROR'
                if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                    try {
                        Write-PipelineEvent -EventType 'pipeline_round_failure_blocked' -Stage 'blocked' -Status 'blocked' -Data @{
                            error_code                 = 'CONSECUTIVE_ROUND_FAILURES_BLOCKED'
                            consecutive_failure_count = [int]$script:ConsecutiveUnexpectedRoundFailures
                            block_limit                = [int]$blockLimit
                            stop_reason                = [string]$script:PipelineStopReason
                        } | Out-Null
                    } catch {}
                }
                break
            }
            $backoffSeconds = if ($blocked) { [int]$probeBackoffSeconds } else { [math]::Min(300, [math]::Max(30, 30 * [math]::Min([int]$script:ConsecutiveUnexpectedRoundFailures, 10))) }
            Write-Log "Continuing after unexpected round failure in $backoffSeconds second(s). consecutive=$($script:ConsecutiveUnexpectedRoundFailures); blocked=$blocked" 'WARN'
            if (-not (Start-StopAwareSleep ([int]$backoffSeconds))) { break }
            continue
        }
        if ([int]$script:ConsecutiveUnexpectedRoundFailures -gt 0) {
            Write-Log "Continuous round failure counter reset after successful round." 'INFO'
        }
        $script:ConsecutiveUnexpectedRoundFailures = 0
        $script:ContinuousRoundFailuresBlocked = $false
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
        RoundsCompleted          = $roundsCompleted
        StopRequested            = [bool]$script:StopRequested
        UnexpectedRoundFailures  = [int]$unexpectedRoundFailures
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
