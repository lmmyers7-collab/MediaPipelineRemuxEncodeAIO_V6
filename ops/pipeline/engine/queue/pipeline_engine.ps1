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

    $script:BackendQueueRunMonitorSeedContext = $null
    $fingerprintGuardedRun = -not [string]::IsNullOrWhiteSpace([string]$EnginePlan.ExpectedQueuePlanFingerprint)
    $acceptedRunRows = @()
    if ([bool]$EnginePlan.Once -and $fingerprintGuardedRun) {
        if (-not (Get-Command -Name Get-MediaPipelineRunMonitorAcceptedSeedRows -ErrorAction SilentlyContinue)) {
            throw 'RUN_MONITOR_STATE_READER_UNAVAILABLE: accepted Run Once membership cannot be adopted.'
        }
        $acceptedRunRows = @(Get-MediaPipelineRunMonitorAcceptedSeedRows `
            -RunId ([string]$script:PipelineRunId) `
            -CommandId ([string]$CommandId) `
            -ExpectedFingerprint ([string]$EnginePlan.ExpectedQueuePlanFingerprint))
        $script:BackendQueueRunMonitorSeedContext = [pscustomobject]@{
            RunId = [string]$script:PipelineRunId
            QueuePlanFingerprint = [string]$EnginePlan.ExpectedQueuePlanFingerprint
        }
    }
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

    # A fingerprint-guarded Queue run must remain side-effect free until its
    # active discovery plan matches the accepted dry-run. Pending publish
    # retries are therefore left to an explicit drain or an unguarded
    # continuous round; the refreshed read-only index keeps exclusions equal
    # to the dry-run snapshot.
    $rescanRequested = Consume-RescanFlag
    if ([bool]$EnginePlan.Once -and $fingerprintGuardedRun) {
        Set-MediaPipelineRunMonitorSourceDiscoveryState `
            -RunId ([string]$script:PipelineRunId) `
            -State active `
            -RunState scanning `
            -ExpectedQueuePlanFingerprint ([string]$EnginePlan.ExpectedQueuePlanFingerprint) | Out-Null
    }
    $pendingPushesRecovered = 0
    if (-not $fingerprintGuardedRun) {
        $pendingPushesRecovered = Invoke-RetryPendingPushes
    } else {
        Write-Log 'QUEUE PLAN GUARD: deferred pending-publish retries until a separate drain or unguarded round.' 'INFO'
    }
    Refresh-PendingPublishIndex | Out-Null
    if ($pendingPushesRecovered -gt 0) {
        Invalidate-ProcessedIndexCache
    }

    Reset-ProgressItemContext
    Set-ProgressStage -Stage 'scanning' -Status 'Scanning sources' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    $discoveryPollHandler = $null
    if ([bool]$EnginePlan.Once -and $fingerprintGuardedRun) {
        if (-not (Get-Command -Name New-MediaPipelineSourceDiscoveryPollHandler -ErrorAction SilentlyContinue)) {
            throw 'RUN_MONITOR_SOURCE_DISCOVERY_HEARTBEAT_UNAVAILABLE: accepted Run Once scanning cannot publish current evidence.'
        }
        $discoveryPollHandler = New-MediaPipelineSourceDiscoveryPollHandler `
            -RunId ([string]$script:PipelineRunId) `
            -AcceptedQueueFingerprint ([string]$EnginePlan.ExpectedQueuePlanFingerprint) `
            -MinimumIntervalSeconds 15
        if (-not $discoveryPollHandler) {
            throw 'RUN_MONITOR_SOURCE_DISCOVERY_IDENTITY_MISMATCH: accepted Run Once scanning is not correlated to the active run.'
        }
    }
    Reset-RoundTracking
    $scanStartedAt = Get-Date
    $index = Get-ProcessedIndexCached -ForceRefresh:$rescanRequested -PollHandler $discoveryPollHandler

    $queuePlan = Get-MediaQueueDiscoveryPlan `
        -MovieRoot $EnginePlan.SourceMovies `
        -TVRoot $EnginePlan.SourceTV `
        -ForceRefresh:$rescanRequested `
        -PollHandler $discoveryPollHandler
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

    $expectedFingerprint = [string]$EnginePlan.ExpectedQueuePlanFingerprint
    $actualFingerprint = [string]$snapshot.queue_plan_fingerprint
    if (-not [string]::IsNullOrWhiteSpace($expectedFingerprint)) {
        if ([string]::IsNullOrWhiteSpace($actualFingerprint) -or $actualFingerprint -ne $expectedFingerprint) {
            $script:PipelineBlockedExitCode = 76
            $script:PipelineStopReason = 'queue_plan_fingerprint_mismatch'
            $script:StopRequested = $true
            Write-Log "QUEUE PLAN BLOCKED: active plan fingerprint does not match the accepted dry-run snapshot." 'ERROR'
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                try {
                    Write-PipelineEvent -EventType 'queue_plan_fingerprint_mismatch' -Stage 'queue' -Status 'blocked' -Data @{
                        error_code           = 'QUEUE_PLAN_FINGERPRINT_MISMATCH'
                        expected_fingerprint = $expectedFingerprint
                        actual_fingerprint   = $actualFingerprint
                        command_id           = [string]$CommandId
                    } | Out-Null
                } catch {}
            }
            Set-ProgressStage -Stage 'blocked' -Status 'Queue plan changed; refresh Queue before launch' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
            return [pscustomobject]@{
                Completed              = $false
                StopRequested          = $true
                RescanRequested        = [bool]$rescanRequested
                PendingPushesRecovered = [int]$pendingPushesRecovered
                QueuePlan              = $queuePlan
                ProcessedIndex         = $index
                Snapshot               = $snapshot
                RoundFailureSummary    = $null
                FingerprintBlocked     = $true
                FingerprintBlockReason = 'queue_plan_fingerprint_mismatch'
            }
        }
    }

    if ([bool]$EnginePlan.Once -and -not [string]::IsNullOrWhiteSpace($expectedFingerprint)) {
        try {
            $activeAcceptedRows = @($script:LastRunMonitorAcceptedRows)
            Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot `
                -AcceptedRows $acceptedRunRows `
                -ActiveRows $activeAcceptedRows | Out-Null
            Set-MediaPipelineRunMonitorSourceDiscoveryState `
                -RunId ([string]$script:PipelineRunId) `
                -State completed `
                -RunState running `
                -ExpectedQueuePlanFingerprint $expectedFingerprint | Out-Null
        } catch {
            $script:PipelineBlockedExitCode = 76
            $script:PipelineStopReason = 'run_monitor_active_membership_mismatch'
            $script:StopRequested = $true
            Write-Log "RUN MONITOR BLOCKED: active discovery no longer matches accepted membership: $($_.Exception.Message)" 'ERROR'
            if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
                try {
                    Write-PipelineEvent -EventType 'run_monitor_active_membership_mismatch' -Stage 'queue' -Status 'blocked' -Data @{
                        error_code           = 'RUN_MONITOR_ACTIVE_MEMBERSHIP_MISMATCH'
                        run_id              = [string]$script:PipelineRunId
                        command_id          = [string]$CommandId
                        accepted_fingerprint = $actualFingerprint
                        error                = [string]$_.Exception.Message
                    } | Out-Null
                } catch {}
            }
            Set-ProgressStage -Stage 'blocked' -Status 'Run workload evidence could not be persisted' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
            return [pscustomobject]@{
                Completed              = $false
                StopRequested          = $true
                RescanRequested        = [bool]$rescanRequested
                PendingPushesRecovered = [int]$pendingPushesRecovered
                QueuePlan              = $queuePlan
                ProcessedIndex         = $index
                Snapshot               = $snapshot
                RoundFailureSummary    = $null
                FingerprintBlocked     = $true
                FingerprintBlockReason = 'run_monitor_active_membership_mismatch'
            }
        }
    }

    $pendingBackpressure = Get-MediaPipelinePendingPublishBackpressure
    if ([bool]$pendingBackpressure.Blocked) {
        Write-MediaPipelinePendingPublishBackpressure -Backpressure $pendingBackpressure
        return [pscustomobject]@{
            Completed              = $true
            StopRequested          = [bool]$script:StopRequested
            RescanRequested        = [bool]$rescanRequested
            PendingPushesRecovered = [int]$pendingPushesRecovered
            QueuePlan              = $queuePlan
            ProcessedIndex         = $index
            Snapshot               = $snapshot
            RoundFailureSummary    = $null
            BackpressureBlocked    = $true
            BackpressureReason     = [string]$pendingBackpressure.BlockReason
        }
    }

    Set-ProgressStage -Stage 'processing' -Status 'Processing queue' -Percent $null -Route $null -CopyState $null -PushState $null -SidecarState $null -SaveNow
    $executionPlan = if ([bool]$EnginePlan.Once -and $fingerprintGuardedRun) {
        # A Backend Queue Run Once accepts the complete fingerprinted workload.
        # A per-round execution window must never silently truncate that scope.
        $queuePlan
    } else {
        Select-MediaPipelineQueuePlanExecutionWindow -QueuePlan $queuePlan
    }
    $script:LastQueueExecutionTruncated = [bool]($executionPlan.PSObject.Properties['RowsTruncatedForExecution'] -and [bool]$executionPlan.RowsTruncatedForExecution)
    if ($script:LastQueueExecutionTruncated) {
        $script:LastQueueCandidateCount = [int]$executionPlan.RunnableTotalBeforeCap
    }
    $useLocalWorkerSlots = ([string]$EnginePlan.ParallelEncodeMode -eq 'local_worker_slots' -and [int]$EnginePlan.MaxParallelEncodes -gt 1)
    $phaseResult = $null
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
        $phaseResult = Invoke-MediaQueuePhasePlanLocalWorkerSlots `
            -QueuePlan $executionPlan `
            -ProcessedIndex $index `
            -ScriptPath ([string]$EnginePlan.ScriptPath) `
            -ConfigPath ([string]$EnginePlan.ConfigPath) `
            -PowerShellPath ([string]$EnginePlan.PowerShellPath) `
            -MaxParallelEncodes ([int]$EnginePlan.MaxParallelEncodes)
    } else {
        $phaseResult = Invoke-MediaQueuePhasePlan -QueuePlan $executionPlan -ProcessedIndex $index -StopOnUnexpectedFailure:([bool]$EnginePlan.Once)
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

    $stoppedAfterCurrent = $null -ne $phaseResult -and
        $phaseResult.PSObject.Properties['StoppedAfterCurrent'] -and
        [bool]$phaseResult.StoppedAfterCurrent
    if ($stoppedAfterCurrent) {
        return [pscustomobject]@{
            Completed                 = $false
            StopRequested             = $false
            StopAfterCurrentRequested = $true
            RescanRequested           = [bool]$rescanRequested
            PendingPushesRecovered    = [int]$pendingPushesRecovered
            QueuePlan                 = $queuePlan
            ProcessedIndex            = $index
            Snapshot                  = $snapshot
            RoundFailureSummary       = $null
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

function Complete-MediaPipelineBackendQueueRunOnceMonitor {
    param(
        [Parameter(Mandatory)] $EnginePlan,
        $RoundResult = $null,
        $RoundError = $null
    )

    $expectedFingerprint = [string]$EnginePlan.ExpectedQueuePlanFingerprint
    if (-not [bool]$EnginePlan.Once -or [string]::IsNullOrWhiteSpace($expectedFingerprint)) {
        return $null
    }
    $context = $script:BackendQueueRunMonitorSeedContext
    if ($null -eq $context) { return $null }
    $runId = [string]$script:PipelineRunId
    if ([string]$context.RunId -ne $runId -or [string]$context.QueuePlanFingerprint -ne $expectedFingerprint) {
        throw 'RUN_MONITOR_SEED_CONTEXT_MISMATCH: refusing to finalize an uncorrelated Backend Queue run.'
    }
    if (-not (Get-Command -Name Complete-MediaPipelineRunMonitor -ErrorAction SilentlyContinue)) {
        throw 'RUN_MONITOR_FINALIZER_UNAVAILABLE: a confirmed Backend Queue run cannot be finalized.'
    }

    $parameters = @{
        RunId = $runId
        State = 'failed'
        RemainingItemState = 'skipped'
        Reason = 'The pipeline round ended unexpectedly after the accepted workload was persisted.'
        ReasonCode = 'UNEXPECTED_PIPELINE_ROUND_EXCEPTION'
        Retryable = $true
        RecoveryOwner = 'pipeline'
        NextAction = 'Review Reports, then start a new Backend Queue run for any item that still requires processing.'
    }
    if ($null -ne $RoundError) {
        $message = if ($RoundError.Exception -and $RoundError.Exception.Message) { [string]$RoundError.Exception.Message } else { [string]$RoundError }
        $parameters.Reason = "The pipeline round ended unexpectedly: $message"
    } else {
        $backpressureBlocked = $null -ne $RoundResult -and
            $RoundResult.PSObject.Properties['BackpressureBlocked'] -and
            [bool]$RoundResult.BackpressureBlocked
        $stopRequested = $null -ne $RoundResult -and
            $RoundResult.PSObject.Properties['StopRequested'] -and
            [bool]$RoundResult.StopRequested
        $stopAfterCurrentRequested = $null -ne $RoundResult -and
            $RoundResult.PSObject.Properties['StopAfterCurrentRequested'] -and
            [bool]$RoundResult.StopAfterCurrentRequested
        $completed = $null -ne $RoundResult -and
            $RoundResult.PSObject.Properties['Completed'] -and
            [bool]$RoundResult.Completed
        $fingerprintBlocked = $null -ne $RoundResult -and
            $RoundResult.PSObject.Properties['FingerprintBlocked'] -and
            [bool]$RoundResult.FingerprintBlocked
        if ($fingerprintBlocked) {
            $blockReason = if ($RoundResult.PSObject.Properties['FingerprintBlockReason']) { [string]$RoundResult.FingerprintBlockReason } else { 'queue_plan_fingerprint_mismatch' }
            $parameters.State = 'blocked'
            $parameters.RemainingItemState = 'blocked'
            $parameters.Reason = "The active Queue rescan no longer matched the accepted Run Once workload ($blockReason)."
            $parameters.ReasonCode = if ($blockReason -eq 'run_monitor_active_membership_mismatch') { 'RUN_MONITOR_ACTIVE_MEMBERSHIP_MISMATCH' } else { 'QUEUE_PLAN_FINGERPRINT_MISMATCH' }
            $parameters.NextAction = 'Refresh Queue, review the new plan, and start a new Run Once workload.'
        } elseif ($backpressureBlocked) {
            $backpressureReason = if ($RoundResult.PSObject.Properties['BackpressureReason']) { [string]$RoundResult.BackpressureReason } else { 'pending_publish_backpressure' }
            $parameters.State = 'blocked'
            $parameters.RemainingItemState = 'blocked'
            $parameters.Reason = "Pending Publish backpressure blocked dispatch ($backpressureReason)."
            $parameters.ReasonCode = 'PENDING_PUBLISH_BACKPRESSURE_BLOCKED'
            $parameters.NextAction = 'Resolve or drain Pending Publish, then start a new Backend Queue run.'
        } elseif ($stopRequested -or $stopAfterCurrentRequested -or [bool]$script:StopRequested) {
            $parameters.State = 'stopped'
            $parameters.RemainingItemState = 'stopped'
            $parameters.Reason = 'The run stopped at a backend-controlled queue boundary.'
            $parameters.ReasonCode = 'RUN_STOPPED_AT_QUEUE_BOUNDARY'
            $parameters.NextAction = 'Start a new Backend Queue run if any stopped item still requires processing.'
        } elseif ($completed) {
            $parameters.State = 'completed'
            $parameters.RemainingItemState = 'skipped'
            $parameters.Reason = 'Every accepted item reached backend terminal evidence.'
            $parameters.ReasonCode = 'RUN_COMPLETED'
            $parameters.Retryable = $false
            $parameters.NextAction = 'Review Completed Output, Pending Publish, or Reports for per-file proof.'
        } else {
            $parameters.RemainingItemState = 'failed'
            $parameters.Reason = 'The round returned without a terminal completion or stop classification.'
            $parameters.ReasonCode = 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE'
            $parameters.NextAction = 'Review Reports and retry the affected workload only after the missing terminal evidence is understood.'
        }
    }

    try {
        return Complete-MediaPipelineRunMonitor @parameters
    } catch {
        if ($parameters.State -eq 'completed' -and [string]$_ -match 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE') {
            $parameters.State = 'failed'
            $parameters.RemainingItemState = 'failed'
            $parameters.Reason = 'The round reported completion while one or more accepted items lacked terminal evidence.'
            $parameters.ReasonCode = 'RUN_MONITOR_TERMINAL_EVIDENCE_INCOMPLETE'
            $parameters.Retryable = $true
            $parameters.NextAction = 'Review Reports and retry only after the missing per-file terminal evidence is understood.'
            return Complete-MediaPipelineRunMonitor @parameters
        }
        throw
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
            Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $EnginePlan -RoundResult $roundResult | Out-Null
        } catch {
            $roundError = $_
            try {
                Complete-MediaPipelineBackendQueueRunOnceMonitor -EnginePlan $EnginePlan -RoundError $roundError | Out-Null
            } catch {
                Write-Log "Run Monitor finalization failed after a pipeline round exception: $($_.Exception.Message)" 'ERROR'
            }
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
                throw $roundError
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
        if ($roundResult.PSObject.Properties['StopAfterCurrentRequested'] -and [bool]$roundResult.StopAfterCurrentRequested) { break }

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
        StopAfterCurrentRequested = [bool]$script:StopAfterCurrentRequested
        UnexpectedRoundFailures  = [int]$unexpectedRoundFailures
    }
}

function Invoke-MediaPipelineEmitQueuePlan {
    param(
        [Parameter(Mandatory)] $EnginePlan
    )

    Set-ProgressStage -Stage 'scanning' -Status 'Scanning sources (dry run)' -Percent $null -SaveNow
    $discoveryPollHandler = $null
    # Refresh is read-only: Queue dry-run must see the same pending-publish
    # exclusions as active discovery without retrying or publishing payloads.
    Refresh-PendingPublishIndex | Out-Null
    $index     = Get-ProcessedIndexCached -ForceRefresh:$true -PollHandler $discoveryPollHandler
    $queuePlan = Get-MediaQueueDiscoveryPlan -MovieRoot $EnginePlan.SourceMovies -TVRoot $EnginePlan.SourceTV -ForceRefresh:$true -PollHandler $discoveryPollHandler
    $snapshot  = Invoke-MediaPipelineQueueSnapshot -QueuePlan $queuePlan -ProcessedIndex $index -Path $EnginePlan.QueueSnapshotPath
    Write-Log "QUEUE PLAN SNAPSHOT: $($snapshot.runnable_count) runnable row(s) -> $($EnginePlan.QueueSnapshotPath)"
    Set-ProgressStage -Stage 'idle' -Status 'Idle' -Percent $null -SaveNow
    return $snapshot
}

# Queue snapshot helpers are kept with the engine because snapshots are emitted
# from the same queue round boundary used by normal and dry-run execution.
