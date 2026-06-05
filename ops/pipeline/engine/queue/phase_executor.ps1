# ==============================================================================
# ops\pipeline\engine\queue\phase_executor.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

function Invoke-MediaPipelineProcessQueueEntry {
    param(
        [Parameter(Mandatory)] $Entry,
        [Parameter(Mandatory)] $ProcessedIndex
    )

    $progressQueueIndex = Get-MediaPipelineQueueEntryProgressValue -Entry $Entry -RunProperty 'RunQueueIndex' -BucketProperty 'QueueIndex'
    $progressQueueTotal = Get-MediaPipelineQueueEntryProgressValue -Entry $Entry -RunProperty 'RunQueueTotal' -BucketProperty 'QueueTotal'
    return Process-File $Entry.File ([bool]$Entry.IsTV) $ProcessedIndex -QueueIndex $progressQueueIndex -QueueTotal $progressQueueTotal -PriorityInfo $Entry.PriorityInfo -LibraryProfileId ([string]$Entry.LibraryId)
}

function Invoke-MediaQueuePhasePlan {
    param(
        [Parameter(Mandatory)] $QueuePlan,
        [Parameter(Mandatory)] $ProcessedIndex
    )

    $runnableEntries = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    # ---- Phase 1: High-priority movies ----
    $highMovies = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_movie' })
    # ---- Phase 2: High-priority TV ----
    $highTV = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority_tv' })
    $mixedPriorityEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'priority' })
    # ---- Combined priority count for logging ----
    $totalHighCount = $highMovies.Count + $highTV.Count + $mixedPriorityEntries.Count

    if ($QueuePlan.MixPriorityPhase -and $totalHighCount -gt 0) {
        # MixPriorityPhase: run all high-priority items (movies + TV) together
        $mixedPriority = @($mixedPriorityEntries)
        $mixedMovieCount = @($mixedPriority | Where-Object { -not [bool]$_.IsTV }).Count
        $mixedTVCount = @($mixedPriority | Where-Object { [bool]$_.IsTV }).Count
        Write-Log "PRIORITY PHASE (mixed): $($mixedPriority.Count) item(s) queued first (movies: $mixedMovieCount, tv: $mixedTVCount)"
        foreach ($entry in $mixedPriority) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
        }
    } else {
        # Default: priority movies first, then priority TV
        if ($highMovies.Count -gt 0) {
            Write-Log "PRIORITY PHASE — MOVIES: $($highMovies.Count) item(s)"
            for ($i = 0; $i -lt $highMovies.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $highMovies[$i]
                Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
            }
        }
        if (-not $script:StopRequested -and $highTV.Count -gt 0) {
            Write-Log "PRIORITY PHASE — TV: $($highTV.Count) item(s)"
            for ($i = 0; $i -lt $highTV.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $highTV[$i]
                Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
            }
        }
    }

    # ---- Phase 3: Normal movies ----
    if (-not $script:StopRequested) {
        $normalMovieEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'movie' })
        for ($i = 0; $i -lt $normalMovieEntries.Count; $i++) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            $entry = $normalMovieEntries[$i]
            Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
        }
    }

    # ---- Phase 4: Normal TV ----
    if (-not $script:StopRequested) {
        $normalTvEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'tv' })
        for ($i = 0; $i -lt $normalTvEntries.Count; $i++) {
            Check-ControlFlags; if ($script:StopRequested) { break }
            $entry = $normalTvEntries[$i]
            Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
        }
    }

    # ---- Phase 5: Low-priority entries (movies and TV interleaved, already sorted) ----
    if (-not $script:StopRequested) {
        $lowEntries = @($runnableEntries | Where-Object { [string]$_.LocalWorkerPhase -eq 'low' })
        if ($lowEntries.Count -gt 0) {
            Write-Log "LOW-PRIORITY PHASE: $($lowEntries.Count) item(s) deferred"
            for ($i = 0; $i -lt $lowEntries.Count; $i++) {
                Check-ControlFlags; if ($script:StopRequested) { break }
                $entry = $lowEntries[$i]
                Invoke-MediaPipelineProcessQueueEntry -Entry $entry -ProcessedIndex $ProcessedIndex
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

