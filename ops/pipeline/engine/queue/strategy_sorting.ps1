# ==============================================================================
# ops\pipeline\engine\queue\strategy_sorting.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\queue_plan.ps1. Keep function names stable;
# queue_plan.ps1 dot-sources this file as the compatibility import surface.
# ==============================================================================


# ==============================================================================
# Queue ordering strategy — Get-EffectiveQueueStrategy / Invoke-QueueStrategySort
# ==============================================================================

# Valid strategy names used both for validation and UI display.
$script:ValidQueueStrategies = @(
    'Standard', 'FreshestFirst', 'ShowComplete', 'RoundRobin',
    'DeadlineAware', 'SmallFirst', 'LargeFirst', 'ManualOrder'
)

function Get-EffectiveQueueStrategy {
    <#
    .SYNOPSIS
        Determine the active queue ordering strategy name.
    .DESCRIPTION
        Resolution order (first valid match wins):
          1. queue_strategy.json at state root   — set by the DesktopApp UI
          2. $script:QueueOrderingStrategy       — from config file
          3. "Standard"                          — hard default
    .OUTPUTS
        One of: Standard | FreshestFirst | ShowComplete | RoundRobin |
                DeadlineAware | SmallFirst | LargeFirst | ManualOrder
    #>

    # 1. UI-set state file
    try {
        $stratFile = $null
        if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) {
            $p = $script:LocalStateLayout.Paths
            if ($p.PSObject.Properties['QueueStrategy']) {
                $stratFile = [string]$p.QueueStrategy
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($stratFile) -and (Test-Path -LiteralPath $stratFile -PathType Leaf)) {
            $text = [System.IO.File]::ReadAllText($stratFile, [System.Text.Encoding]::UTF8)
            $obj  = $text | ConvertFrom-Json
            if ($obj -and $obj.version -eq 1) {
                $s = [string]$obj.strategy
                if ($s -in $script:ValidQueueStrategies) { return $s }
            }
        }
    } catch {}

    # 2. Config-file default
    try {
        $fromConfig = [string]$script:QueueOrderingStrategy
        if (-not [string]::IsNullOrWhiteSpace($fromConfig) -and $fromConfig -in $script:ValidQueueStrategies) {
            return $fromConfig
        }
    } catch {}

    # 3. Hard default
    return 'Standard'
}

function Invoke-QueueStrategySort {
    <#
    .SYNOPSIS
        Apply a queue ordering strategy to the phase-plan buckets.
    .DESCRIPTION
        Takes the five mutable buckets (HighMovies, HighTV, NormalMovies, NormalTV,
        LowEntries) that have already had Set-QueueEntryRuntimeMetadata applied and
        returns a hashtable with the same five keys, re-ordered according to the
        requested strategy.

        HoldEntries are never touched — they are always excluded from processing.

        Strategies:
          Standard      — no change; movies alpha, TV by show/season/episode.
          FreshestFirst — merge NormalMovies + NormalTV, sort by LastWriteUtc desc.
                          LowEntries also re-sorted by freshness.
          ShowComplete  — TV episodes of any show that has a high-priority episode
                          are pulled from NormalTV into HighTV so that each show
                          fully processes before the pipeline moves on.
          RoundRobin    — NormalTV interleaved one-episode-per-show per cycle.
          DeadlineAware — within NormalMovies and NormalTV, entries whose
                          manifest "wanted_by" field has a future UTC timestamp
                          sort before entries without a deadline (nearest first).
          SmallFirst    — within each normal/low bucket, sort by file size asc.
          LargeFirst    — within each normal/low bucket, sort by file size desc.
          ManualOrder   — within each backend phase bucket, entries with a manifest
                          "position" float sort first (ascending); the remainder
                          keep their natural order.

    .PARAMETER Strategy
        The strategy name (see list above).  Unknown names fall through to Standard.
    .PARAMETER HighMovies / HighTV / NormalMovies / NormalTV / LowEntries
        Phase-plan bucket arrays (already have runtime metadata applied).
    .PARAMETER Manifest
        The hashtable returned by Get-PriorityManifest.  Required for
        DeadlineAware and ManualOrder; ignored by the other strategies.
    .OUTPUTS
        Hashtable:  @{ HighMovies=...; HighTV=...; NormalMovies=...; NormalTV=...; LowEntries=... }
    #>
    param(
        [string]    $Strategy,
        [array]     $HighMovies,
        [array]     $HighTV,
        [array]     $NormalMovies,
        [array]     $NormalTV,
        [array]     $LowEntries,
        [hashtable] $Manifest = $null,
        [scriptblock] $PollHandler
    )

    $strat = if ([string]::IsNullOrWhiteSpace($Strategy)) { 'Standard' } else { $Strategy }
    $pollStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch

    # Working copies (filter nulls once)
    $hm = [System.Collections.Generic.List[object]]::new()
    $ht = [System.Collections.Generic.List[object]]::new()
    $nm = [System.Collections.Generic.List[object]]::new()
    $nt = [System.Collections.Generic.List[object]]::new()
    $le = [System.Collections.Generic.List[object]]::new()
    foreach ($e in @($HighMovies))   { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($null -ne $e) { $hm.Add($e) } }
    foreach ($e in @($HighTV))       { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($null -ne $e) { $ht.Add($e) } }
    foreach ($e in @($NormalMovies)) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($null -ne $e) { $nm.Add($e) } }
    foreach ($e in @($NormalTV))     { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($null -ne $e) { $nt.Add($e) } }
    foreach ($e in @($LowEntries))   { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($null -ne $e) { $le.Add($e) } }

    switch ($strat) {

        # ------------------------------------------------------------------
        'FreshestFirst' {
            # Merge normal movies + TV, sorted by LastWriteUtc descending.
            # TV items end up in $nm; $nt is cleared — the engine uses
            # $entry.IsTV on each item so TV items in $nm still process correctly.
            $merged = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $nm) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $merged.Add($e) }
            foreach ($e in $nt) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $merged.Add($e) }
            $sorted = @($merged | Sort-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; [datetime]$_.LastWriteUtc } -Descending)
            $nm = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $sorted) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $nm.Add($e) }
            $nt = [System.Collections.Generic.List[object]]::new()

            # Also re-sort low entries by freshness
            $sortedLow = @($le | Sort-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; [datetime]$_.LastWriteUtc } -Descending)
            $le = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $sortedLow) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $le.Add($e) }
        }

        # ------------------------------------------------------------------
        'ShowComplete' {
            # Find all ShowSortKey values present in the high-TV phase.
            # Pull all NormalTV entries for those shows into HighTV so that
            # each show is fully processed before moving to the next.
            $highShowKeys = @{}
            foreach ($e in $ht) {
                Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                $k = [string]$e.ShowSortKey
                if (-not [string]::IsNullOrWhiteSpace($k)) {
                    $highShowKeys[$k.ToLowerInvariant()] = $true
                }
            }

            if ($highShowKeys.Count -gt 0) {
                $pullUp  = [System.Collections.Generic.List[object]]::new()
                $remain  = [System.Collections.Generic.List[object]]::new()
                foreach ($e in $nt) {
                    Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                    $k = [string]$e.ShowSortKey
                    if (-not [string]::IsNullOrWhiteSpace($k) -and $highShowKeys.ContainsKey($k.ToLowerInvariant())) {
                        $pullUp.Add($e)
                    } else {
                        $remain.Add($e)
                    }
                }

                if ($pullUp.Count -gt 0) {
                    # Merge HighTV + pulled-up normals; sort by show → season → episode
                    $combined = [System.Collections.Generic.List[object]]::new()
                    foreach ($e in $ht)     { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $combined.Add($e) }
                    foreach ($e in $pullUp) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $combined.Add($e) }

                    $sortedCombined = @($combined | Sort-Object `
                        @{ Expression = { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; if ($_.EffectivePriorityLevel -eq 'high') { 0 } else { 1 } } }, `
                        @{ Expression = { [string]$_.ShowSortKey } }, `
                        @{ Expression = { if ($_.SeasonSortOrder -gt 0)  { [int]$_.SeasonSortOrder  } else { 9999   } } }, `
                        @{ Expression = { if ($_.EpisodeSortOrder -gt 0) { [int]$_.EpisodeSortOrder } else { 999999 } } }, `
                        @{ Expression = { [string]$_.RelativePathSort } }
                    )
                    $ht = [System.Collections.Generic.List[object]]::new()
                    foreach ($e in $sortedCombined) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; $ht.Add($e) }
                    $nt = $remain
                }
            }
        }

        # ------------------------------------------------------------------
        'RoundRobin' {
            # Interleave NormalTV: one episode per show per cycle.
            # Movies are untouched.
            if ($nt.Count -gt 1) {
                $groupMap = [ordered]@{}
                foreach ($entry in $nt) {
                    Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                    $groupKey = [string]$entry.ShowSortKey
                    if (-not $groupMap.Contains($groupKey)) { $groupMap[$groupKey] = [System.Collections.Generic.List[object]]::new() }
                    [void]$groupMap[$groupKey].Add($entry)
                }
                $groups = @($groupMap.GetEnumerator() | ForEach-Object {
                    Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                    [pscustomobject]@{ Name = [string]$_.Key; Group = @($_.Value.ToArray()) }
                } | Sort-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch; [string]$_.Name })
                if ($groups.Count -gt 1) {
                    $maxLen = 0
                    foreach ($group in $groups) {
                        Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                        if ([int]$group.Group.Count -gt $maxLen) { $maxLen = [int]$group.Group.Count }
                    }
                    $rr = [System.Collections.Generic.List[object]]::new()
                    for ($cycle = 0; $cycle -lt $maxLen; $cycle++) {
                        foreach ($g in $groups) {
                            Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $pollStopwatch
                            if ($cycle -lt $g.Group.Count) {
                                $rr.Add($g.Group[$cycle])
                            }
                        }
                    }
                    $nt = $rr
                }
            }
        }

        # ------------------------------------------------------------------
        'DeadlineAware' {
            # Within each bucket, entries whose manifest "wanted_by" field has
            # a future UTC timestamp sort before entries without a deadline
            # (nearest deadline first).  Natural ordering is preserved within
            # each group.
            $nowTicks = [datetime]::UtcNow.Ticks
            $nm = _Sort-DeadlineFirst $nm $Manifest $nowTicks -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $nt = _Sort-DeadlineFirst $nt $Manifest $nowTicks -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $le = _Sort-DeadlineFirst $le $Manifest $nowTicks -PollHandler $PollHandler -Stopwatch $pollStopwatch
        }

        # ------------------------------------------------------------------
        'SmallFirst' {
            $nm = _Sort-ByFileSize $nm $false $false -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $nt = _Sort-ByFileSize $nt $false $true -PollHandler $PollHandler -Stopwatch $pollStopwatch   # preserve show grouping as primary key
            $le = _Sort-ByFileSize $le $false $false -PollHandler $PollHandler -Stopwatch $pollStopwatch
        }

        # ------------------------------------------------------------------
        'LargeFirst' {
            $nm = _Sort-ByFileSize $nm $true $false -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $nt = _Sort-ByFileSize $nt $true $true -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $le = _Sort-ByFileSize $le $true $false -PollHandler $PollHandler -Stopwatch $pollStopwatch
        }

        # ------------------------------------------------------------------
        'ManualOrder' {
            # Within each backend phase bucket, entries with a manifest "position" float
            # sort first (ascending); the remainder keep their natural order.
            $hm = _Sort-ManualPosition $hm $Manifest -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $ht = _Sort-ManualPosition $ht $Manifest -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $nm = _Sort-ManualPosition $nm $Manifest -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $nt = _Sort-ManualPosition $nt $Manifest -PollHandler $PollHandler -Stopwatch $pollStopwatch
            $le = _Sort-ManualPosition $le $Manifest -PollHandler $PollHandler -Stopwatch $pollStopwatch
        }

        # Standard (and any unrecognised value) — no change
    }

    return @{
        HighMovies   = @($hm)
        HighTV       = @($ht)
        NormalMovies = @($nm)
        NormalTV     = @($nt)
        LowEntries   = @($le)
    }
}

# ------------------------------------------------------------------------------
# Internal sort helpers (prefixed with _ to signal they are not public API)
# ------------------------------------------------------------------------------

function _Sort-DeadlineFirst {
    <#
    Helper: partition $Entries into future-deadline vs no-deadline, sort the
    deadline subset by ascending deadline ticks, return the concatenation.
    #>
    param(
        $EntriesList,           # List[object] or array
        [hashtable] $Manifest,
        [long]      $NowTicks,
        [scriptblock] $PollHandler,
        [System.Diagnostics.Stopwatch] $Stopwatch
    )

    $withDeadline    = [System.Collections.Generic.List[object]]::new()
    $withoutDeadline = [System.Collections.Generic.List[object]]::new()

    foreach ($e in @($EntriesList)) {
        Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch
        if ($null -eq $e) { continue }
        $wantedBy   = Get-ManifestEntryField -Manifest $Manifest -SourcePath ([string]$e.SourcePath) -FieldName 'wanted_by'
        $hasDeadline = $false
        $deadlineTicks = [long]::MaxValue
        if ($wantedBy) {
            try {
                $styles = [System.Globalization.DateTimeStyles]::AdjustToUniversal -bor `
                          [System.Globalization.DateTimeStyles]::AssumeUniversal
                $dt = [datetime]::Parse([string]$wantedBy, $null, $styles)
                if ($dt.Ticks -gt $NowTicks) {
                    $deadlineTicks = $dt.Ticks
                    $hasDeadline   = $true
                }
            } catch {}
        }
        if ($hasDeadline) {
            try { $e | Add-Member -NotePropertyName _DeadlineTicks -NotePropertyValue $deadlineTicks -Force } catch {}
            $withDeadline.Add($e)
        } else {
            $withoutDeadline.Add($e)
        }
    }

    $sortedDeadline = @($withDeadline | Sort-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; [long]$_._DeadlineTicks })
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $sortedDeadline)  { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; $result.Add($e) }
    foreach ($e in $withoutDeadline) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; $result.Add($e) }
    return $result
}

function _Sort-ByFileSize {
    <#
    Helper: sort entries by file size (File.Length).
    $Descending = $true for LargeFirst.
    $GroupByShow = $true keeps show grouping as primary key (for TV buckets).
    #>
    param(
        $EntriesList,
        [bool] $Descending,
        [bool] $GroupByShow,
        [scriptblock] $PollHandler,
        [System.Diagnostics.Stopwatch] $Stopwatch
    )

    $result = [System.Collections.Generic.List[object]]::new()
    if ($GroupByShow) {
        $sortedEntries = @($EntriesList | Sort-Object `
            @{ Expression = { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; [string]$_.ShowSortKey } }, `
            @{ Expression = { try { if ($_.File) { [long]$_.File.Length } else { 0L } } catch { 0L } }; Descending = $Descending }
        )
    } else {
        $sortedEntries = @($EntriesList | Sort-Object `
            @{ Expression = { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; try { if ($_.File) { [long]$_.File.Length } else { 0L } } catch { 0L } }; Descending = $Descending }
        )
    }
    foreach ($e in $sortedEntries) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; $result.Add($e) }
    return $result
}

function _Sort-ManualPosition {
    <#
    Helper: entries with a manifest "position" float sort first (ascending);
    remaining entries keep their existing order.
    #>
    param(
        $EntriesList,
        [hashtable] $Manifest,
        [scriptblock] $PollHandler,
        [System.Diagnostics.Stopwatch] $Stopwatch
    )

    $positioned   = [System.Collections.Generic.List[object]]::new()
    $unPositioned = [System.Collections.Generic.List[object]]::new()

    foreach ($e in @($EntriesList)) {
        Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch
        if ($null -eq $e) { continue }
        $posRaw  = Get-ManifestEntryField -Manifest $Manifest -SourcePath ([string]$e.SourcePath) -FieldName 'position'
        $posVal  = $null
        if ($null -ne $posRaw) {
            try { $posVal = [double]$posRaw } catch {}
        }
        if ($null -ne $posVal) {
            try { $e | Add-Member -NotePropertyName _ManualPosition -NotePropertyValue $posVal -Force } catch {}
            $positioned.Add($e)
        } else {
            $unPositioned.Add($e)
        }
    }

    $sortedPositioned = @($positioned | Sort-Object { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; [double]$_._ManualPosition })
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $sortedPositioned) { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; $result.Add($e) }
    foreach ($e in $unPositioned)     { Invoke-MediaPipelineElapsedPollHandler -PollHandler $PollHandler -Stopwatch $Stopwatch; $result.Add($e) }
    return $result
}
