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
        [hashtable] $Manifest = $null
    )

    $strat = if ([string]::IsNullOrWhiteSpace($Strategy)) { 'Standard' } else { $Strategy }

    # Working copies (filter nulls once)
    $hm = [System.Collections.Generic.List[object]]::new()
    $ht = [System.Collections.Generic.List[object]]::new()
    $nm = [System.Collections.Generic.List[object]]::new()
    $nt = [System.Collections.Generic.List[object]]::new()
    $le = [System.Collections.Generic.List[object]]::new()
    foreach ($e in @($HighMovies))   { if ($null -ne $e) { $hm.Add($e) } }
    foreach ($e in @($HighTV))       { if ($null -ne $e) { $ht.Add($e) } }
    foreach ($e in @($NormalMovies)) { if ($null -ne $e) { $nm.Add($e) } }
    foreach ($e in @($NormalTV))     { if ($null -ne $e) { $nt.Add($e) } }
    foreach ($e in @($LowEntries))   { if ($null -ne $e) { $le.Add($e) } }

    switch ($strat) {

        # ------------------------------------------------------------------
        'FreshestFirst' {
            # Merge normal movies + TV, sorted by LastWriteUtc descending.
            # TV items end up in $nm; $nt is cleared — the engine uses
            # $entry.IsTV on each item so TV items in $nm still process correctly.
            $merged = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $nm) { $merged.Add($e) }
            foreach ($e in $nt) { $merged.Add($e) }
            $sorted = @($merged | Sort-Object { [datetime]$_.LastWriteUtc } -Descending)
            $nm = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $sorted) { $nm.Add($e) }
            $nt = [System.Collections.Generic.List[object]]::new()

            # Also re-sort low entries by freshness
            $sortedLow = @($le | Sort-Object { [datetime]$_.LastWriteUtc } -Descending)
            $le = [System.Collections.Generic.List[object]]::new()
            foreach ($e in $sortedLow) { $le.Add($e) }
        }

        # ------------------------------------------------------------------
        'ShowComplete' {
            # Find all ShowSortKey values present in the high-TV phase.
            # Pull all NormalTV entries for those shows into HighTV so that
            # each show is fully processed before moving to the next.
            $highShowKeys = @{}
            foreach ($e in $ht) {
                $k = [string]$e.ShowSortKey
                if (-not [string]::IsNullOrWhiteSpace($k)) {
                    $highShowKeys[$k.ToLowerInvariant()] = $true
                }
            }

            if ($highShowKeys.Count -gt 0) {
                $pullUp  = [System.Collections.Generic.List[object]]::new()
                $remain  = [System.Collections.Generic.List[object]]::new()
                foreach ($e in $nt) {
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
                    foreach ($e in $ht)     { $combined.Add($e) }
                    foreach ($e in $pullUp) { $combined.Add($e) }

                    $sortedCombined = @($combined | Sort-Object `
                        @{ Expression = { if ($_.EffectivePriorityLevel -eq 'high') { 0 } else { 1 } } }, `
                        @{ Expression = { [string]$_.ShowSortKey } }, `
                        @{ Expression = { if ($_.SeasonSortOrder -gt 0)  { [int]$_.SeasonSortOrder  } else { 9999   } } }, `
                        @{ Expression = { if ($_.EpisodeSortOrder -gt 0) { [int]$_.EpisodeSortOrder } else { 999999 } } }, `
                        @{ Expression = { [string]$_.RelativePathSort } }
                    )
                    $ht = [System.Collections.Generic.List[object]]::new()
                    foreach ($e in $sortedCombined) { $ht.Add($e) }
                    $nt = $remain
                }
            }
        }

        # ------------------------------------------------------------------
        'RoundRobin' {
            # Interleave NormalTV: one episode per show per cycle.
            # Movies are untouched.
            if ($nt.Count -gt 1) {
                $groups = @($nt | Group-Object ShowSortKey | Sort-Object Name)
                if ($groups.Count -gt 1) {
                    $maxLen = ($groups | ForEach-Object { $_.Group.Count } | Measure-Object -Maximum).Maximum
                    $rr = [System.Collections.Generic.List[object]]::new()
                    for ($cycle = 0; $cycle -lt $maxLen; $cycle++) {
                        foreach ($g in $groups) {
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
            $nm = _Sort-DeadlineFirst $nm $Manifest $nowTicks
            $nt = _Sort-DeadlineFirst $nt $Manifest $nowTicks
            $le = _Sort-DeadlineFirst $le $Manifest $nowTicks
        }

        # ------------------------------------------------------------------
        'SmallFirst' {
            $nm = _Sort-ByFileSize $nm $false $false
            $nt = _Sort-ByFileSize $nt $false $true   # preserve show grouping as primary key
            $le = _Sort-ByFileSize $le $false $false
        }

        # ------------------------------------------------------------------
        'LargeFirst' {
            $nm = _Sort-ByFileSize $nm $true $false
            $nt = _Sort-ByFileSize $nt $true $true
            $le = _Sort-ByFileSize $le $true $false
        }

        # ------------------------------------------------------------------
        'ManualOrder' {
            # Within each backend phase bucket, entries with a manifest "position" float
            # sort first (ascending); the remainder keep their natural order.
            $hm = _Sort-ManualPosition $hm $Manifest
            $ht = _Sort-ManualPosition $ht $Manifest
            $nm = _Sort-ManualPosition $nm $Manifest
            $nt = _Sort-ManualPosition $nt $Manifest
            $le = _Sort-ManualPosition $le $Manifest
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
        [long]      $NowTicks
    )

    $withDeadline    = [System.Collections.Generic.List[object]]::new()
    $withoutDeadline = [System.Collections.Generic.List[object]]::new()

    foreach ($e in @($EntriesList)) {
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

    $sortedDeadline = @($withDeadline | Sort-Object { [long]$_._DeadlineTicks })
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $sortedDeadline)    { $result.Add($e) }
    foreach ($e in $withoutDeadline) { $result.Add($e) }
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
        [bool] $GroupByShow
    )

    $result = [System.Collections.Generic.List[object]]::new()
    if ($GroupByShow) {
        $sortedEntries = @($EntriesList | Sort-Object `
            @{ Expression = { [string]$_.ShowSortKey } }, `
            @{ Expression = { try { if ($_.File) { [long]$_.File.Length } else { 0L } } catch { 0L } }; Descending = $Descending }
        )
    } else {
        $sortedEntries = @($EntriesList | Sort-Object `
            @{ Expression = { try { if ($_.File) { [long]$_.File.Length } else { 0L } } catch { 0L } }; Descending = $Descending }
        )
    }
    foreach ($e in $sortedEntries) { $result.Add($e) }
    return $result
}

function _Sort-ManualPosition {
    <#
    Helper: entries with a manifest "position" float sort first (ascending);
    remaining entries keep their existing order.
    #>
    param(
        $EntriesList,
        [hashtable] $Manifest
    )

    $positioned   = [System.Collections.Generic.List[object]]::new()
    $unPositioned = [System.Collections.Generic.List[object]]::new()

    foreach ($e in @($EntriesList)) {
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

    $sortedPositioned = @($positioned | Sort-Object { [double]$_._ManualPosition })
    $result = [System.Collections.Generic.List[object]]::new()
    foreach ($e in $sortedPositioned) { $result.Add($e) }
    foreach ($e in $unPositioned)     { $result.Add($e) }
    return $result
}
