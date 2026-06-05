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
            -QueuePlan $queuePlan `
            -ProcessedIndex $index `
            -ScriptPath ([string]$EnginePlan.ScriptPath) `
            -ConfigPath ([string]$EnginePlan.ConfigPath) `
            -PowerShellPath ([string]$EnginePlan.PowerShellPath) `
            -MaxParallelEncodes ([int]$EnginePlan.MaxParallelEncodes) | Out-Null
    } else {
        Invoke-MediaQueuePhasePlan -QueuePlan $queuePlan -ProcessedIndex $index | Out-Null
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
