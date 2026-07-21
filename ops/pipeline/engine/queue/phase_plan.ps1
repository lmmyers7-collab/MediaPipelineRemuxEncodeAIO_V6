# ==============================================================================
# ops\pipeline\engine\queue\phase_plan.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\queue_plan.ps1. Keep function names stable;
# queue_plan.ps1 dot-sources this file as the compatibility import surface.
# ==============================================================================

function Copy-QueueEntriesForLegacyPriorityPhase {
    param(
        [array]$Entries,
        [scriptblock]$PollHandler
    )

    $items = @($Entries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    $copies = [System.Collections.Generic.List[object]]::new()
    $pollStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    for ($i = 0; $i -lt $items.Count; $i++) {
        Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
        $copy = [pscustomobject]@{}
        foreach ($prop in $items[$i].PSObject.Properties) {
            Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $copy | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
        }
        $copy | Add-Member -NotePropertyName QueueIndex -NotePropertyValue ($i + 1) -Force
        $copy | Add-Member -NotePropertyName QueueTotal -NotePropertyValue $items.Count -Force
        $copy | Add-Member -NotePropertyName QueuePhase -NotePropertyValue 'priority' -Force
        $copies.Add($copy)
    }
    return @($copies)
}

function Get-MediaPipelineQueuePlanRunnableEntries {
    param([Parameter(Mandatory)] $QueuePlan)

    $entries = [System.Collections.Generic.List[object]]::new()
    $highMovies = @($QueuePlan.HighPriorityMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    $highTV = @($QueuePlan.HighPriorityTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    if ($highMovies.Count -eq 0 -and $highTV.Count -eq 0 -and $QueuePlan.PriorityEntries) {
        $legacyPriorityEntries = @($QueuePlan.PriorityEntries)
        $highMovies = @($legacyPriorityEntries | Where-Object { -not [bool]$_.IsTV })
        $highTV = @($legacyPriorityEntries | Where-Object { [bool]$_.IsTV })
    }

    $phaseSets = @()
    if ($QueuePlan.MixPriorityPhase -and ($highMovies.Count + $highTV.Count) -gt 0) {
        $phaseSets += ,@('priority', @(@($highMovies) + @($highTV)))
    } else {
        $phaseSets += ,@('priority_movie', $highMovies)
        $phaseSets += ,@('priority_tv', $highTV)
    }
    $phaseSets += ,@('movie', @($QueuePlan.NormalMovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))
    $phaseSets += ,@('tv', @($QueuePlan.NormalTVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))
    $phaseSets += ,@('low', @($QueuePlan.LowEntries | Where-Object { $null -ne $_ -and $null -ne $_.File }))

    foreach ($phase in $phaseSets) {
        $phaseName = [string]$phase[0]
        foreach ($entry in @($phase[1])) {
            $entry | Add-Member -NotePropertyName LocalWorkerPhase -NotePropertyValue $phaseName -Force
            $entry | Add-Member -NotePropertyName RunQueuePhase -NotePropertyValue $phaseName -Force
            [void]$entries.Add($entry)
        }
    }
    return @($entries)
}

function New-MediaQueuePhasePlan {
    param(
        [array]$MovieEntries,
        [array]$TVEntries,
        [scriptblock]$PollHandler
    )

    $pollStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch

    # ----- Split each batch by effective priority level -----
    $movieHigh   = @($MovieEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'high' })
    $movieNormal = @($MovieEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'normal' })
    $movieLow    = @($MovieEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'low' })
    $movieHold   = @($MovieEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'hold' })

    $tvHigh      = @($TVEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'high' })
    $tvNormal    = @($TVEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'normal' })
    $tvLow       = @($TVEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'low' })
    $tvHold      = @($TVEntries | Where-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'hold' })

    # ----- Apply runtime metadata (QueueIndex, QueuePhase, etc.) -----
    $highMoviesMeta = @(Set-QueueEntryRuntimeMetadata -Entries $movieHigh   -IsTV $false -PhaseOverride 'priority_movie' -PollHandler $PollHandler)
    $highTVMeta     = @(Set-QueueEntryRuntimeMetadata -Entries $tvHigh      -IsTV $true  -PhaseOverride 'priority_tv' -PollHandler $PollHandler)
    $normalMovieMeta= @(Set-QueueEntryRuntimeMetadata -Entries $movieNormal -IsTV $false -PhaseOverride 'movie' -PollHandler $PollHandler)
    $normalTVMeta   = @(Set-QueueEntryRuntimeMetadata -Entries $tvNormal    -IsTV $true  -PhaseOverride 'tv' -PollHandler $PollHandler)
    $lowMovieMeta   = @(Set-QueueEntryRuntimeMetadata -Entries $movieLow    -IsTV $false -PhaseOverride 'low' -PollHandler $PollHandler)
    $lowTVMeta      = @(Set-QueueEntryRuntimeMetadata -Entries $tvLow       -IsTV $true  -PhaseOverride 'low' -PollHandler $PollHandler)
    $holdMovieMeta  = @(Set-QueueEntryRuntimeMetadata -Entries $movieHold   -IsTV $false -PhaseOverride 'hold' -PollHandler $PollHandler)
    $holdTVMeta     = @(Set-QueueEntryRuntimeMetadata -Entries $tvHold      -IsTV $true  -PhaseOverride 'hold' -PollHandler $PollHandler)

    # ----- Queue ordering strategy -----
    # Get the active strategy name and apply it to the normal/low/high-TV buckets.
    # Hold entries are never reordered.
    $activeStrategy = Get-EffectiveQueueStrategy
    $manifest       = Get-PriorityManifest
    $lowEntries     = @(@($lowMovieMeta) + @($lowTVMeta) | Where-Object { $null -ne $_ })

    $sorted = Invoke-QueueStrategySort `
        -Strategy     $activeStrategy `
        -HighMovies   $highMoviesMeta `
        -HighTV       $highTVMeta `
        -NormalMovies $normalMovieMeta `
        -NormalTV     $normalTVMeta `
        -LowEntries   $lowEntries `
        -Manifest     $manifest `
        -PollHandler  $PollHandler

    $highMoviesMeta  = @($sorted.HighMovies   | Where-Object { $null -ne $_ })
    $highTVMeta      = @($sorted.HighTV       | Where-Object { $null -ne $_ })
    $normalMovieMeta = @($sorted.NormalMovies | Where-Object { $null -ne $_ })
    $normalTVMeta    = @($sorted.NormalTV     | Where-Object { $null -ne $_ })
    $lowEntries      = @($sorted.LowEntries   | Where-Object { $null -ne $_ })

    # MixPriorityPhase: combine high-movie + high-TV into a single "priority" phase
    # (preserves the pre-manifest behaviour where all priority items ran together).
    $mixPhase = $false
    try { $mixPhase = [bool]$script:MixPriorityPhase } catch {}

    if ($mixPhase) {
        $priorityEntries = @(@($highMoviesMeta) + @($highTVMeta) | Where-Object { $null -ne $_ })
        $priorityEntries | ForEach-Object {
            Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $_ | Add-Member -NotePropertyName QueuePhase -NotePropertyValue 'priority' -Force
        }
    }

    $holdEntries = @(@($holdMovieMeta) + @($holdTVMeta) | Where-Object { $null -ne $_ })
    $movies  = @(@($highMoviesMeta) + @($normalMovieMeta) + @($lowMovieMeta) + @($holdMovieMeta) | Where-Object { $null -ne $_ })
    $tv      = @(@($highTVMeta) + @($normalTVMeta) + @($lowTVMeta) + @($holdTVMeta) | Where-Object { $null -ne $_ })

    # Legacy-compat: PriorityEntries combines high-movie + high-TV regardless of MixPhase
    # and keeps the original flat "priority" phase contract for downstream callers.
    $allPriorityEntries = @(Copy-QueueEntriesForLegacyPriorityPhase -Entries @(@($highMoviesMeta) + @($highTVMeta)) -PollHandler $PollHandler)
    $allQueuedEntries   = @(@($movies) + @($tv) | Where-Object { $null -ne $_ -and $null -ne $_.File })

    return [pscustomobject]@{
        # Full batches (all levels, for snapshot / stats)
        MovieEntries            = $movies
        TVEntries               = $tv
        AllQueuedEntries        = $allQueuedEntries

        # High-priority sub-batches
        HighPriorityMovieEntries = $highMoviesMeta
        HighPriorityTVEntries    = $highTVMeta

        # Normal sub-batches (backward-compat names preserved)
        NormalMovieEntries       = $normalMovieMeta
        NormalTVEntries          = $normalTVMeta

        # Low / hold batches
        LowEntries               = $lowEntries
        HoldEntries              = $holdEntries

        # Legacy flat priority list (all high items, movies first then TV)
        PriorityEntries          = $allPriorityEntries

        # Counts
        MovieCount               = @($MovieEntries | Where-Object { $null -ne $_ }).Count
        TVCount                  = @($TVEntries | Where-Object { $null -ne $_ }).Count
        MoviePriorityCount       = $movieHigh.Count
        TVPriorityCount          = $tvHigh.Count
        PriorityMovieCount       = $movieHigh.Count
        PriorityTVCount          = $tvHigh.Count
        LowCount                 = $lowEntries.Count
        HoldCount                = $holdEntries.Count

        MixPriorityPhase         = $mixPhase
        QueueOrderingStrategy    = $activeStrategy
    }
}
