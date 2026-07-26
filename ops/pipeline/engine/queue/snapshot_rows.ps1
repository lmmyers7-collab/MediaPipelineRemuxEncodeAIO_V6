# ==============================================================================
# ops\pipeline\engine\queue\snapshot_rows.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

function Get-MediaPipelineSha256Text {
    param([Parameter(Mandatory)] [string] $Text)
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($Text)
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString($hash.ComputeHash($bytes))).Replace('-', '').ToLowerInvariant()
    } finally {
        $hash.Dispose()
    }
}

function Get-MediaPipelineQueueInputFingerprint {
    $paths = [ordered]@{
        config            = [string]$configPath
        priority_manifest = if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) { [string]$script:LocalStateLayout.Paths.PriorityManifest } else { '' }
        queue_strategy    = if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) { [string]$script:LocalStateLayout.Paths.QueueStrategy } else { '' }
        file_overrides    = if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths) { [string]$script:LocalStateLayout.Paths.FileOverrides } else { '' }
    }
    $components = [ordered]@{}
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('schema=queue_input_fingerprint.v1') | Out-Null
    $unavailable = [System.Collections.Generic.List[string]]::new()
    foreach ($name in $paths.Keys) {
        $path = [string]$paths[$name]
        $status = 'missing'
        $sha256 = 'missing'
        if (-not [string]::IsNullOrWhiteSpace($path) -and (Test-Path -LiteralPath $path -PathType Leaf)) {
            try {
                $sha256 = [string](Get-FileHash -LiteralPath $path -Algorithm SHA256 -ErrorAction Stop).Hash.ToLowerInvariant()
                $status = 'current'
            } catch {
                $sha256 = 'unavailable'
                $status = 'unavailable'
                $unavailable.Add([string]$name) | Out-Null
            }
        }
        $components[$name] = [ordered]@{ status = $status; sha256 = $sha256 }
        $lines.Add("$name=$sha256") | Out-Null
    }
    $fingerprint = Get-MediaPipelineSha256Text (($lines -join "`n") + "`n")
    return [pscustomobject]@{
        SchemaVersion         = 'queue_input_fingerprint.v1'
        Status                = if ($unavailable.Count -gt 0) { 'unavailable' } else { 'current' }
        Fingerprint           = $fingerprint
        Components            = $components
        UnavailableComponents = @($unavailable)
    }
}

function ConvertTo-MediaPipelineQueueFingerprintField {
    param($Value, [switch] $Path)
    $text = [string]$Value
    if ($Path -and -not [string]::IsNullOrWhiteSpace($text)) {
        try { $text = [System.IO.Path]::GetFullPath($text) } catch {}
        $text = $text.Replace('\', '/').ToLowerInvariant()
    }
    return $text.Replace('\', '\\').Replace('|', '\p').Replace("`r", '\r').Replace("`n", '\n')
}

function ConvertTo-MediaPipelineAcceptedRunFingerprintField {
    param($Value, [switch] $Path)
    $text = [string]$Value
    if ($Path -and -not [string]::IsNullOrWhiteSpace($text)) {
        try { $text = [System.IO.Path]::GetFullPath($text) } catch {}
        $text = $text.Replace('\', '/')
        # Fingerprint v1 folds ASCII A-Z only so Python and PowerShell produce
        # identical bytes while non-ASCII distinctions remain tamper-evident.
        $builder = [System.Text.StringBuilder]::new($text.Length)
        foreach ($character in $text.ToCharArray()) {
            $codePoint = [int][char]$character
            if ($codePoint -ge 65 -and $codePoint -le 90) {
                [void]$builder.Append([char]($codePoint + 32))
            } else {
                [void]$builder.Append($character)
            }
        }
        $text = $builder.ToString()
    }
    return $text.Replace('\', '\\').Replace('|', '\p').Replace("`r", '\r').Replace("`n", '\n')
}

function Get-MediaPipelineQueuePlanFingerprint {
    param(
        [Parameter(Mandatory)] $Rows,
        [Parameter(Mandatory)] $ExcludedRows,
        [AllowEmptyCollection()] $AcceptedRows = @(),
        [Parameter(Mandatory)] [string] $InputFingerprint,
        [string] $OrderingStrategy = '',
        $PendingBackpressure = $null,
        $PendingHealth = $null
    )
    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('schema=queue_plan_fingerprint.v1') | Out-Null
    $lines.Add("input=$(ConvertTo-MediaPipelineQueueFingerprintField $InputFingerprint)") | Out-Null
    $lines.Add("strategy=$(ConvertTo-MediaPipelineQueueFingerprintField $OrderingStrategy)") | Out-Null
    $backpressureSignature = if ($PendingBackpressure) {
        '{0}|{1}|{2}|{3}|{4}' -f `
            ([bool]$PendingBackpressure.Blocked), `
            ([string]$PendingBackpressure.BlockReason), `
            ([bool]$PendingBackpressure.DeferredPublish), `
            ([int]$PendingBackpressure.ManifestCount), `
            ([int]$PendingBackpressure.RetryExhaustedCount)
    } else { 'unavailable' }
    $lines.Add("backpressure=$(ConvertTo-MediaPipelineQueueFingerprintField $backpressureSignature)") | Out-Null
    $pendingHealthSignature = if ($PendingHealth) {
        '{0}|{1}|{2}|{3}' -f `
            ([string]$PendingHealth.status), `
            ([int]$PendingHealth.count), `
            ([int]$PendingHealth.missing_payload_count), `
            ([int]$PendingHealth.unreadable_manifest_count)
    } else { 'unavailable' }
    $lines.Add("pending_health=$(ConvertTo-MediaPipelineQueueFingerprintField $pendingHealthSignature)") | Out-Null
    foreach ($row in @($Rows)) {
        $phase = [string]$row.phase
        $blockedCode = [string]$row.blocked_reason_code
        $state = if (-not [string]::IsNullOrWhiteSpace($blockedCode)) { 'blocked' } elseif ($phase -eq 'hold') { 'held' } else { 'runnable' }
        $parts = @(
            'row', [string]$row.global_order, $state, $phase, [string]$row.media_kind,
            (ConvertTo-MediaPipelineQueueFingerprintField $row.source_path -Path),
            [string]$row.manifest_priority_level, [string]$row.route,
            [string]$row.route_reason_code, $blockedCode
        ) | ForEach-Object { ConvertTo-MediaPipelineQueueFingerprintField $_ }
        $lines.Add(($parts -join '|')) | Out-Null
    }
    foreach ($row in @($ExcludedRows)) {
        $reasonCode = [string]$row.reason_code
        $parts = @(
            'excluded', [string]$row.source_order, $reasonCode, [string]$row.phase,
            [string]$row.media_kind, (ConvertTo-MediaPipelineQueueFingerprintField $row.source_path -Path)
        ) | ForEach-Object { ConvertTo-MediaPipelineQueueFingerprintField $_ }
        $lines.Add(($parts -join '|')) | Out-Null
    }
    foreach ($row in @($AcceptedRows)) {
        $parts = @(
            'accepted', [string]$row.run_queue_index, [string]$row.run_queue_total,
            [string]$row.source_identity,
            (ConvertTo-MediaPipelineQueueFingerprintField $row.source_path -Path),
            [string]$row.planned_display_name, [string]$row.planned_display_name_source, [string]$row.route,
            [string]$row.route_reason_code, [string]$row.intended_final_path
        ) | ForEach-Object { ConvertTo-MediaPipelineQueueFingerprintField $_ }
        $lines.Add(($parts -join '|')) | Out-Null
    }
    return Get-MediaPipelineSha256Text (($lines -join "`n") + "`n")
}

function Get-MediaPipelineAcceptedRunRowsFingerprint {
    param([Parameter(Mandatory)] [AllowEmptyCollection()] $Rows)

    $lines = [System.Collections.Generic.List[string]]::new()
    $lines.Add('schema=accepted_run_rows_fingerprint.v1') | Out-Null
    foreach ($row in @($Rows)) {
        $parts = @(
            'accepted', [string]$row.run_queue_index, [string]$row.run_queue_total,
            [string]$row.source_identity, [string]$row.source_identity_algorithm,
            (ConvertTo-MediaPipelineAcceptedRunFingerprintField $row.source_path -Path),
            [string]$row.planned_display_name, [string]$row.planned_display_name_source,
            (ConvertTo-MediaPipelineAcceptedRunFingerprintField $row.parent_context -Path),
            [string]$row.route, [string]$row.route_reason_code, [string]$row.route_reason,
            (ConvertTo-MediaPipelineAcceptedRunFingerprintField $row.intended_final_path -Path)
        ) | ForEach-Object { ConvertTo-MediaPipelineAcceptedRunFingerprintField $_ }
        $lines.Add(($parts -join '|')) | Out-Null
    }
    return Get-MediaPipelineSha256Text (($lines -join "`n") + "`n")
}

function Get-MediaPipelineRunMonitorSeedRowsFromAcceptedSnapshot {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter(Mandatory)] [string] $ExpectedFingerprint,
        [Parameter(Mandatory)] [string] $RunId
    )

    if ([string]::IsNullOrWhiteSpace($ExpectedFingerprint)) {
        throw 'RUN_MONITOR_ACCEPTED_FINGERPRINT_MISSING: an accepted Queue fingerprint is required.'
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw 'RUN_MONITOR_ACCEPTED_SNAPSHOT_MISSING: refresh Queue before Run Once.'
    }
    $snapshot = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -Depth 40 -ErrorAction Stop
    if ([string]$snapshot.schema_version -ne 'queue_plan_snapshot.v1' -or
        [string]$snapshot.queue_snapshot_origin -ne 'dry_run') {
        throw 'RUN_MONITOR_ACCEPTED_SNAPSHOT_INVALID: only the authoritative backend dry-run snapshot may seed Run Once.'
    }
    if ([string]$snapshot.queue_plan_fingerprint_schema -ne 'queue_plan_fingerprint.v1' -or
        [string]$snapshot.queue_plan_fingerprint -ne $ExpectedFingerprint) {
        throw 'RUN_MONITOR_ACCEPTED_FINGERPRINT_MISMATCH: refresh Queue before Run Once.'
    }
    if (-not $snapshot.PSObject.Properties['accepted_run_rows']) {
        throw 'RUN_MONITOR_ACCEPTED_ROWS_MISSING: refresh Queue with the current backend before Run Once.'
    }
    $rows = @($snapshot.accepted_run_rows)
    $total = [int]$snapshot.runnable_count
    if ($total -le 0 -or $rows.Count -ne $total) {
        throw "RUN_MONITOR_ACCEPTED_ROWS_INVALID: accepted row count $($rows.Count) does not match runnable_count $total."
    }

    $seenIdentities = @{}
    $seenPaths = @{}
    $accepted = [System.Collections.Generic.List[object]]::new()
    for ($offset = 0; $offset -lt $rows.Count; $offset++) {
        $row = $rows[$offset]
        $position = [int]$row.run_queue_index
        $rowTotal = [int]$row.run_queue_total
        $sourceIdentity = [string]$row.source_identity
        $sourceAlgorithm = [string]$row.source_identity_algorithm
        $sourcePath = [string]$row.source_path
        $displayName = ([string]$row.planned_display_name).Trim()
        $displayNameSource = ([string]$row.planned_display_name_source).Trim()
        if ($position -ne ($offset + 1) -or $rowTotal -ne $total) {
            throw 'RUN_MONITOR_ACCEPTED_ROWS_INVALID: positions must be contiguous, ordered, one-based, and share the accepted total.'
        }
        if ([string]::IsNullOrWhiteSpace($sourceIdentity) -or
            [string]::IsNullOrWhiteSpace($sourceAlgorithm) -or
            [string]::IsNullOrWhiteSpace($sourcePath)) {
            throw 'RUN_MONITOR_ACCEPTED_ROWS_INVALID: every accepted row requires exact source identity and path evidence.'
        }
        if ([string]::IsNullOrWhiteSpace($displayName) -or $displayNameSource -ne 'plex_destination_plan.v1') {
            throw 'RUN_MONITOR_ACCEPTED_NAME_EVIDENCE_MISSING: refresh Queue with the current backend before Run Once.'
        }
        $normalizedPath = try { [System.IO.Path]::GetFullPath($sourcePath).ToLowerInvariant() } catch { $sourcePath.ToLowerInvariant() }
        if ($seenIdentities.ContainsKey($sourceIdentity) -or $seenPaths.ContainsKey($normalizedPath)) {
            throw 'RUN_MONITOR_ACCEPTED_ROWS_INVALID: duplicate source identity or path in accepted workload.'
        }
        $seenIdentities[$sourceIdentity] = $true
        $seenPaths[$normalizedPath] = $true
        $accepted.Add([ordered]@{
            job_id                    = ('{0}-item-{1:D8}' -f $RunId, $position)
            source_identity           = $sourceIdentity
            source_identity_algorithm = $sourceAlgorithm
            source_path               = $sourcePath
            display_name              = $displayName
            display_name_source       = $displayNameSource
            parent_context            = [string]$row.parent_context
            run_queue_index           = $position
            run_queue_total           = $total
            route                     = [string]$row.route
            route_reason              = [string]$row.route_reason
            route_reason_code         = [string]$row.route_reason_code
            intended_final_path       = [string]$row.intended_final_path
        }) | Out-Null
    }
    $storedAcceptedFingerprintSchema = [string]$snapshot.accepted_run_rows_fingerprint_schema
    $storedAcceptedFingerprint = [string]$snapshot.accepted_run_rows_fingerprint
    if ($storedAcceptedFingerprintSchema -ne 'accepted_run_rows_fingerprint.v1' -or
        [string]::IsNullOrWhiteSpace($storedAcceptedFingerprint)) {
        throw 'RUN_MONITOR_ACCEPTED_ROWS_FINGERPRINT_MISSING: refresh Queue with the current backend before Run Once.'
    }
    $actualAcceptedFingerprint = Get-MediaPipelineAcceptedRunRowsFingerprint -Rows $rows
    if ($actualAcceptedFingerprint -ne $storedAcceptedFingerprint) {
        throw 'RUN_MONITOR_ACCEPTED_ROWS_FINGERPRINT_MISMATCH: accepted membership or naming evidence changed after Queue acceptance.'
    }
    return @($accepted.ToArray())
}

function Assert-MediaPipelineRunMonitorActiveMembershipMatchesAcceptedSnapshot {
    param(
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $AcceptedRows,
        [Parameter(Mandatory)] [AllowEmptyCollection()] [array] $ActiveRows
    )

    if ($AcceptedRows.Count -ne $ActiveRows.Count) {
        throw 'RUN_MONITOR_ACTIVE_MEMBERSHIP_MISMATCH: active rescan count changed after launch acceptance.'
    }
    for ($index = 0; $index -lt $AcceptedRows.Count; $index++) {
        $accepted = $AcceptedRows[$index]
        $active = $ActiveRows[$index]
        $acceptedPath = try { [System.IO.Path]::GetFullPath([string]$accepted.source_path).ToLowerInvariant() } catch { ([string]$accepted.source_path).ToLowerInvariant() }
        $activePath = try { [System.IO.Path]::GetFullPath([string]$active.source_path).ToLowerInvariant() } catch { ([string]$active.source_path).ToLowerInvariant() }
        $acceptedIntendedPath = [string]$accepted.intended_final_path
        $activeIntendedPath = [string]$active.intended_final_path
        if (-not [string]::IsNullOrWhiteSpace($acceptedIntendedPath)) {
            $acceptedIntendedPath = try { [System.IO.Path]::GetFullPath($acceptedIntendedPath).ToLowerInvariant() } catch { $acceptedIntendedPath.ToLowerInvariant() }
        }
        if (-not [string]::IsNullOrWhiteSpace($activeIntendedPath)) {
            $activeIntendedPath = try { [System.IO.Path]::GetFullPath($activeIntendedPath).ToLowerInvariant() } catch { $activeIntendedPath.ToLowerInvariant() }
        }
        if ([string]$accepted.job_id -ne [string]$active.job_id -or
            [string]$accepted.source_identity -ne [string]$active.source_identity -or
            [string]$accepted.source_identity_algorithm -ne [string]$active.source_identity_algorithm -or
            $acceptedPath -ne $activePath -or
            [string]$accepted.display_name -ne [string]$active.display_name -or
            [string]$accepted.display_name_source -ne [string]$active.display_name_source -or
            [string]$accepted.parent_context -ne [string]$active.parent_context -or
            [int]$accepted.run_queue_index -ne [int]$active.run_queue_index -or
            [int]$accepted.run_queue_total -ne [int]$active.run_queue_total -or
            [string]$accepted.route -ne [string]$active.route -or
            [string]$accepted.route_reason -ne [string]$active.route_reason -or
            [string]$accepted.route_reason_code -ne [string]$active.route_reason_code -or
            $acceptedIntendedPath -ne $activeIntendedPath) {
            throw "RUN_MONITOR_ACTIVE_MEMBERSHIP_MISMATCH: active rescan changed accepted item at position $($index + 1)."
        }
    }
    return $true
}

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
        run_queue_index  = 0
        run_queue_total  = 0
        is_priority      = [bool]$Entry.IsPriority
        priority_reasons = @($Entry.PriorityInfo.Reasons)
        priority_rank    = [long]$Entry.PriorityOrderTicks
        source_path      = [string]$Entry.SourcePath
        root_path        = [string]$Entry.RootPath
        library_id       = [string]$Entry.LibraryId
        library_name     = [string]$Entry.LibraryName
        library_designation = [string]$Entry.LibraryDesignation
        library_output_root = [string]$Entry.LibraryOutputRoot
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
        $TvInfo = $null,
        [string] $SourceRootPath = '',
        [string] $LibraryName = '',
        [string] $LibraryId = '',
        [string] $LibraryDesignation = ''
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
            $sourceFailureCode = if ($classification -eq 'operator_required') { 'source_failure_operator_required' } else { 'source_failure_permanent' }
            return [pscustomobject]@{
                Code   = $sourceFailureCode
                Reason = "source-failure: [$stateCode] $reasonText"
                TvInfo = $TvInfo
            }
        }
    }

    if ($IsTV) {
        if (-not $TvInfo) {
            $TvInfo = Get-TVInfoFromFile `
                -file $File `
                -SourceRootPath $SourceRootPath `
                -LibraryName $LibraryName `
                -LibraryId $LibraryId `
                -LibraryDesignation $LibraryDesignation
        }
        if (-not $TvInfo) {
            return [pscustomobject]@{
                Code   = 'tv_parse_unreliable'
                Reason = 'tv-parse: TV identity parser returned no result.'
                TvInfo = $null
            }
        }
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

    # Walk the same phase order used by execution. RunQueueIndex/RunQueueTotal
    # are assigned only after snapshot-time exclusion checks pass.
    $ordered = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    # Hold entries appended at end — they render in the UI but never process
    $holdOrdered = @($QueuePlan.HoldEntries)

    $rows = New-Object System.Collections.Generic.List[object]
    $fingerprintRows = New-Object System.Collections.Generic.List[object]
    $runnableRows = New-Object System.Collections.Generic.List[object]
    # Full accepted workload for the run monitor. This collection is never
    # display-capped and is not derived from Queue filters or rendered rows.
    $acceptedRunRows = New-Object System.Collections.Generic.List[object]
    # Persisted pre-launch membership deliberately has no run/job identity.
    # The backend creates the job IDs only after it accepts a concrete Run ID.
    $acceptedPlanRows = New-Object System.Collections.Generic.List[object]
    # A process-local PipelineRunId exists for every pipeline mode. It is not,
    # by itself, proof that this round owns a durable Backend Queue Run Once
    # monitor. Only the exact seed-adoption context established before the
    # active rescan authorizes per-entry monitor identities and writes.
    $runMonitorContext = $null
    try { $runMonitorContext = $script:BackendQueueRunMonitorSeedContext } catch {}
    $activeRunMonitorId = ''
    $activeRunMonitorFingerprint = ''
    if ($null -ne $runMonitorContext) {
        try { $activeRunMonitorId = [string]$runMonitorContext.RunId } catch {}
        try { $activeRunMonitorFingerprint = [string]$runMonitorContext.QueuePlanFingerprint } catch {}
    }
    $runMonitorAdopted = (
        -not [string]::IsNullOrWhiteSpace($activeRunMonitorId) -and
        -not [string]::IsNullOrWhiteSpace($activeRunMonitorFingerprint) -and
        [string]::Equals(
            $activeRunMonitorId,
            [string]$script:PipelineRunId,
            [System.StringComparison]::Ordinal
        )
    )
    $excludedRows = New-Object System.Collections.Generic.List[object]
    $fingerprintExcludedRows = New-Object System.Collections.Generic.List[object]
    $excludedRowsTotal = 0
    $excludedRowsLimit = 500
    $rowLimit = 500
    try {
        if ($script:QueueSnapshotRowLimit) {
            $rowLimit = [math]::Max(1, [int]$script:QueueSnapshotRowLimit)
        }
    } catch {
        $rowLimit = 500
    }
    $totalRowCount = 0
    $runnableRowCount = 0
    $globalOrder = 0
    $sourceOrder = 0
    foreach ($entry in $ordered) {
        if (-not $entry -or -not $entry.File) { continue }
        $sourceOrder++
        $entry | Add-Member -NotePropertyName RunQueueIndex -NotePropertyValue 0 -Force
        $entry | Add-Member -NotePropertyName RunQueueTotal -NotePropertyValue 0 -Force
        $file  = $entry.File
        $isTV  = [bool]$entry.IsTV
        $tvInfo = $null
        if ($isTV) {
            $hasCachedIdentity = $entry.PSObject.Properties['TVIdentityParsed'] -and [bool]$entry.TVIdentityParsed
            if ($hasCachedIdentity) {
                $tvInfo = $entry.TVInfo
            } else {
                try {
                    $tvInfo = Get-TVInfoFromFile `
                        -file $file `
                        -SourceRootPath ([string]$entry.RootPath) `
                        -LibraryName ([string]$entry.LibraryName) `
                        -LibraryId ([string]$entry.LibraryId) `
                        -LibraryDesignation ([string]$entry.LibraryDesignation)
                } catch {}
            }
        }
        $blocked = $null
        $blockedCode = ''
        $blockInfo = Get-QueuePlanPreflightBlock `
            -File $file `
            -IsTV:$isTV `
            -TvInfo $tvInfo `
            -SourceRootPath ([string]$entry.RootPath) `
            -LibraryName ([string]$entry.LibraryName) `
            -LibraryId ([string]$entry.LibraryId) `
            -LibraryDesignation ([string]$entry.LibraryDesignation)
        if ($blockInfo) {
            $blocked = [string]$blockInfo.Reason
            $blockedCode = [string]$blockInfo.Code
            if ($blockInfo.PSObject.Properties['TvInfo']) { $tvInfo = $blockInfo.TvInfo }
        }
        if (-not $blocked) {
            try {
                $previousLibraryProfileId = Get-Variable -Name CurrentLibraryProfileId -Scope Script -ValueOnly -ErrorAction SilentlyContinue
                $script:CurrentLibraryProfileId = [string]$entry.LibraryId
                try {
                    $alreadyProcessed = Already-Processed $file $isTV $tvInfo $ProcessedIndex
                } finally {
                    if ($null -ne $previousLibraryProfileId) {
                        $script:CurrentLibraryProfileId = $previousLibraryProfileId
                    } else {
                        Remove-Variable -Name CurrentLibraryProfileId -Scope Script -ErrorAction SilentlyContinue
                    }
                }
                if ($alreadyProcessed) {
                    $excludedRowsTotal++
                    $excludedRow = New-QueuePlanExcludedSnapshotRow `
                        -Entry $entry `
                        -SourceOrder $sourceOrder `
                        -ReasonCode 'already_processed' `
                        -Reason 'Already processed by completed history, sidecar state, or pending-publish index.' `
                        -TvInfo $tvInfo
                    $fingerprintExcludedRows.Add($excludedRow) | Out-Null
                    if ($excludedRows.Count -lt $excludedRowsLimit) {
                        $excludedRows.Add($excludedRow) | Out-Null
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
        $route = $null; $routeReason = $null; $routeReasonCode = $null; $routeDecisionTrace = @(); $rp = $null
        $routeEstimatedBitrateMbps = 0.0
        $routeSizeThresholdGb = 0.0
        $routeBitrateThresholdMbps = 0.0
        $routeThresholdMode = ''
        $routeSizeOverThreshold = $false
        $routeBitrateOverThreshold = $false
        # This is immutable backend-authored naming evidence carried into the
        # accepted Run Once workload. Keep the raw source path separately for
        # identity, and never pass a raw-name fallback off as a planned rename.
        $acceptedDisplayName = ''
        $routeLibraryOverrideKeys = if ($entry.Metadata -and $entry.Metadata.ContainsKey('settings_override_keys')) { @($entry.Metadata['settings_override_keys']) } else { @() }
        $routeLibrarySettingsOverrides = if ($entry.Metadata -and $entry.Metadata.ContainsKey('settings_overrides')) { $entry.Metadata['settings_overrides'] } else { [ordered]@{} }
        $routeLibraryEffectiveSettings = if ($entry.Metadata -and $entry.Metadata.ContainsKey('effective_settings')) { $entry.Metadata['effective_settings'] } else { [ordered]@{} }
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
            $previousFileOverrideConfigMap = Get-Variable -Name LastFileOverrideConfigMap -Scope Script -ValueOnly -ErrorAction SilentlyContinue
            $previousFileOverrideMatch = Get-Variable -Name LastFileOverrideMatch -Scope Script -ValueOnly -ErrorAction SilentlyContinue
            $activeConfigOverrideSnapshot = $null
            try {
                $libraryOverrides = if (Get-Command -Name Resolve-MediaPipelineLibraryOverridesForPath -ErrorAction SilentlyContinue) {
                    Resolve-MediaPipelineLibraryOverridesForPath -SourcePath $file.FullName -LibraryProfileId ([string]$entry.LibraryId)
                } else {
                    $null
                }
                $showOverrides = if ($isTV -and $tvInfo -and [bool]$tvInfo.IsReliable -and $tvInfo.ShowName -and (Get-Command -Name Resolve-ShowOverrides -ErrorAction SilentlyContinue)) {
                    Resolve-ShowOverrides $tvInfo.ShowName
                } else {
                    $null
                }
                # Process-File applies a reliable ShowName override to TvInfo
                # before Get-OutputPaths. Plan accepted Queue names against an
                # isolated copy with that same canonical identity so acceptance
                # and execution cannot disagree while the cached parse remains
                # immutable for ordering and evidence.
                $planningTvInfo = $tvInfo
                if (
                    $isTV -and
                    $tvInfo -and
                    [bool]$tvInfo.IsReliable -and
                    $showOverrides -and
                    -not [string]::IsNullOrWhiteSpace([string]$showOverrides.ShowName)
                ) {
                    $planningTvInfo = $tvInfo.PSObject.Copy()
                    $planningTvInfo.ShowName = [string]$showOverrides.ShowName
                }
                $folderOverrides = if (Get-Command -Name Resolve-FolderPolicyOverrides -ErrorAction SilentlyContinue) {
                    Resolve-FolderPolicyOverrides -SourceFile $file
                } else {
                    $null
                }
                if (Get-Command -Name Merge-MediaPipelineActiveOverrides -ErrorAction SilentlyContinue) {
                    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $libraryOverrides -Override $showOverrides
                    $script:ActiveOverrides = Merge-MediaPipelineActiveOverrides -Base $script:ActiveOverrides -Override $folderOverrides
                } else {
                    $script:ActiveOverrides = $folderOverrides
                }
                if (Get-Command -Name Merge-FileOverrideIntoActiveOverrides -ErrorAction SilentlyContinue) {
                    Merge-FileOverrideIntoActiveOverrides -SourcePath $file.FullName
                }
                if (Get-Command -Name Push-MediaPipelineActiveConfigOverrides -ErrorAction SilentlyContinue) {
                    $activeConfigOverrideSnapshot = Push-MediaPipelineActiveConfigOverrides -Overrides $script:ActiveOverrides
                }
                if ($libraryOverrides) {
                    $routeLibraryOverrideKeys = @($libraryOverrides.Keys)
                    $routeLibrarySettingsOverrides = $libraryOverrides
                }
                if (Get-Command -Name Resolve-MediaPipelineLibraryEffectiveSettings -ErrorAction SilentlyContinue) {
                    $routeLibraryEffectiveSettings = Resolve-MediaPipelineLibraryEffectiveSettings -Overrides $libraryOverrides
                }
                $destinationPlanner = Get-Command -Name New-PlexDestinationPlan -ErrorAction SilentlyContinue
                if ($destinationPlanner) {
                    try {
                        $plannedDisplay = if ($isTV) {
                            New-PlexDestinationPlan `
                                -MediaKind 'TV' `
                                -File $file `
                                -TvInfo $planningTvInfo `
                                -OriginalName ([string]$planningTvInfo.OriginalName) `
                                -Extension ([string]$OutputContainer)
                        } else {
                            New-PlexDestinationPlan `
                                -MediaKind 'Movie' `
                                -File $file `
                                -OriginalName ([string]$file.Name) `
                                -Extension ([string]$OutputContainer)
                        }
                        if ($plannedDisplay -and -not [string]::IsNullOrWhiteSpace([string]$plannedDisplay.FileName)) {
                            $acceptedDisplayName = [string]$plannedDisplay.FileName
                        } else {
                            throw 'backend destination planner returned no filename'
                        }
                    } catch {
                        $blocked = "destination naming plan failed: $($_.Exception.Message)"
                        $blockedCode = 'destination_naming_plan_failed'
                    }
                } else {
                    $blocked = 'destination naming plan failed: backend destination planner is unavailable'
                    $blockedCode = 'destination_naming_plan_failed'
                }
                if ($blocked) {
                    $routeReason = $blocked
                    $routeReasonCode = $blockedCode
                    $runtimeChecksDeferred = $false
                    $runtimeCheckCodes = @()
                    $runtimeCheckNotes = @()
                } else {
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
                }
            } finally {
                if (Get-Command -Name Pop-MediaPipelineActiveConfigOverrides -ErrorAction SilentlyContinue) {
                    Pop-MediaPipelineActiveConfigOverrides -Snapshot $activeConfigOverrideSnapshot
                }
                $script:ActiveOverrides = $previousOverrides
                if ($null -ne $previousFileOverrideConfigMap) {
                    $script:LastFileOverrideConfigMap = $previousFileOverrideConfigMap
                } else {
                    Remove-Variable -Name LastFileOverrideConfigMap -Scope Script -ErrorAction SilentlyContinue
                }
                if ($null -ne $previousFileOverrideMatch) {
                    $script:LastFileOverrideMatch = $previousFileOverrideMatch
                } else {
                    Remove-Variable -Name LastFileOverrideMatch -Scope Script -ErrorAction SilentlyContinue
                }
            }
            if (-not $blocked -and $rp) {
                $route       = [string]$rp.DisplayRoute
                $routeReason = [string]$rp.Reason
                $routeReasonCode = [string]$rp.ReasonCode
                $routeDecisionTrace = @($rp.DecisionTrace)
                if ($rp.PSObject.Properties['EstimatedBitrateMbps']) { $routeEstimatedBitrateMbps = [double]$rp.EstimatedBitrateMbps }
                if ($rp.PSObject.Properties['ThresholdGB']) { $routeSizeThresholdGb = [double]$rp.ThresholdGB }
                if ($rp.PSObject.Properties['BitrateThresholdMbps']) { $routeBitrateThresholdMbps = [double]$rp.BitrateThresholdMbps }
                if ($rp.PSObject.Properties['RouteThresholdMode']) { $routeThresholdMode = [string]$rp.RouteThresholdMode }
                if ($rp.PSObject.Properties['SizeOverThreshold']) { $routeSizeOverThreshold = [bool]$rp.SizeOverThreshold }
                if ($rp.PSObject.Properties['BitrateOverThreshold']) { $routeBitrateOverThreshold = [bool]$rp.BitrateOverThreshold }
            }
        } catch {
            $routeReason = "route preview failed: $($_.Exception.Message)"
        }
        }
        if (-not $blocked -and [string]::IsNullOrWhiteSpace($acceptedDisplayName)) {
            $namingFailureDetail = if ([string]::IsNullOrWhiteSpace($routeReason)) {
                'backend naming evidence is unavailable'
            } else {
                [string]$routeReason
            }
            $blocked = "destination naming plan failed: $namingFailureDetail"
            $blockedCode = 'destination_naming_plan_failed'
            $routeReason = $blocked
            $routeReasonCode = $blockedCode
            $runtimeChecksDeferred = $false
            $runtimeCheckCodes = @()
            $runtimeCheckNotes = @()
        }
        if (-not $blocked) {
            $routePlanRoute = if ($rp -and $rp.PSObject.Properties['Route']) { ([string]$rp.Route).Trim().ToLowerInvariant() } else { '' }
            $routePlanDisplay = if ($rp -and $rp.PSObject.Properties['DisplayRoute']) { [string]$rp.DisplayRoute } else { '' }
            $routePlanReason = if ($rp -and $rp.PSObject.Properties['Reason']) { [string]$rp.Reason } else { '' }
            $routePlanReasonCode = if ($rp -and $rp.PSObject.Properties['ReasonCode']) { [string]$rp.ReasonCode } else { '' }
            $routePlanComplete = (
                $routePlanRoute -in @('encode','remux') -and
                -not [string]::IsNullOrWhiteSpace($routePlanDisplay) -and
                -not [string]::IsNullOrWhiteSpace($routePlanReason) -and
                -not [string]::IsNullOrWhiteSpace($routePlanReasonCode)
            )
            if (-not $routePlanComplete) {
                $routeFailureDetail = if ([string]::IsNullOrWhiteSpace([string]$routeReason)) {
                    'backend route resolver returned incomplete or noncanonical route evidence'
                } else {
                    [string]$routeReason
                }
                $blocked = if ($routeFailureDetail -like 'route preview failed:*') {
                    $routeFailureDetail
                } else {
                    "route preview failed: $routeFailureDetail"
                }
                $blockedCode = 'route_preview_failed'
                $route = $null
                $routeReason = $blocked
                $routeReasonCode = $blockedCode
                $routeDecisionTrace = @()
                $routeEstimatedBitrateMbps = 0.0
                $routeSizeThresholdGb = 0.0
                $routeBitrateThresholdMbps = 0.0
                $routeThresholdMode = ''
                $routeSizeOverThreshold = $false
                $routeBitrateOverThreshold = $false
                $runtimeChecksDeferred = $false
                $runtimeCheckCodes = @()
                $runtimeCheckNotes = @()
            }
        }
        $runQueueIndex = 0
        if (-not $blocked) {
            $runnableRowCount++
            $runQueueIndex = [int]$runnableRowCount
            $entry | Add-Member -NotePropertyName RunQueueIndex -NotePropertyValue $runQueueIndex -Force
        }
        $row = [ordered]@{
            global_order            = $globalOrder
            phase                   = [string]$entry.QueuePhase
            manifest_priority_level = [string]$entry.EffectivePriorityLevel
            manifest_priority_explicit = [bool]$entry.ManifestPriorityExplicit
            media_kind              = [string]$entry.MediaKind
            queue_index             = [int]$entry.QueueIndex
            queue_total             = [int]$entry.QueueTotal
            run_queue_index         = [int]$runQueueIndex
            run_queue_total         = 0
            is_priority             = [bool]$entry.IsPriority
            priority_reasons        = @($entry.PriorityInfo.Reasons)
            priority_rank           = [long]$entry.PriorityOrderTicks
            source_path             = [string]$entry.SourcePath
            root_path               = [string]$entry.RootPath
            library_id              = [string]$entry.LibraryId
            library_name            = [string]$entry.LibraryName
            library_designation     = [string]$entry.LibraryDesignation
            library_output_root     = [string]$entry.LibraryOutputRoot
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
            estimated_bitrate_mbps  = [double]$routeEstimatedBitrateMbps
            route_size_threshold_gb = [double]$routeSizeThresholdGb
            route_bitrate_threshold_mbps = [double]$routeBitrateThresholdMbps
            route_threshold_mode    = [string]$routeThresholdMode
            size_over_threshold     = [bool]$routeSizeOverThreshold
            bitrate_over_threshold  = [bool]$routeBitrateOverThreshold
            library_settings_override_keys = @($routeLibraryOverrideKeys)
            library_settings_overrides = $routeLibrarySettingsOverrides
            library_effective_settings = $routeLibraryEffectiveSettings
            blocked_reason_code     = $blockedCode
            blocked_reason          = $blocked
            runtime_checks_deferred = [bool]$runtimeChecksDeferred
            runtime_check_codes     = @($runtimeCheckCodes)
            runtime_check_notes     = @($runtimeCheckNotes)
        }
        if ($runQueueIndex -gt 0) {
            $normalizedSourcePath = [System.IO.Path]::GetFullPath([string]$file.FullName).ToLowerInvariant()
            $sourceIdentityMaterial = '{0}|{1}|{2}' -f $normalizedSourcePath, [int64]$file.Length, ([datetime]$file.LastWriteTimeUtc).Ticks
            $runMonitorSourceIdentity = Get-MediaPipelineSha256Text $sourceIdentityMaterial
            $acceptedPlanRow = [ordered]@{
                source_identity          = $runMonitorSourceIdentity
                source_identity_algorithm = 'path_size_mtime_sha256.v1'
                source_path              = [string]$file.FullName
                display_name             = [string]$acceptedDisplayName
                planned_display_name     = [string]$acceptedDisplayName
                planned_display_name_source = 'plex_destination_plan.v1'
                display_name_source      = 'plex_destination_plan.v1'
                parent_context           = [string]$file.DirectoryName
                run_queue_index          = [int]$runQueueIndex
                run_queue_total          = 0
                route                    = [string]$route
                route_reason             = [string]$routeReason
                route_reason_code        = [string]$routeReasonCode
            }
            $acceptedPlanRows.Add($acceptedPlanRow) | Out-Null
            if ($runMonitorAdopted) {
                $runMonitorJobId = '{0}-item-{1:D8}' -f $activeRunMonitorId, [int]$runQueueIndex
                $entry | Add-Member -NotePropertyName RunMonitorJobId -NotePropertyValue $runMonitorJobId -Force
                $entry | Add-Member -NotePropertyName RunMonitorSourceIdentity -NotePropertyValue $runMonitorSourceIdentity -Force
                $entry | Add-Member -NotePropertyName RunMonitorSourceIdentityAlgorithm -NotePropertyValue 'path_size_mtime_sha256.v1' -Force
                $entry | Add-Member -NotePropertyName RunMonitorPlannedRoute -NotePropertyValue ([string]$route) -Force
                $entry | Add-Member -NotePropertyName RunMonitorPlannedReason -NotePropertyValue ([string]$routeReason) -Force
                $entry | Add-Member -NotePropertyName RunMonitorPlannedReasonCode -NotePropertyValue ([string]$routeReasonCode) -Force
                $acceptedMonitorRow = [ordered]@{ job_id = $runMonitorJobId }
                foreach ($key in $acceptedPlanRow.Keys) { $acceptedMonitorRow[$key] = $acceptedPlanRow[$key] }
                $acceptedRunRows.Add($acceptedMonitorRow) | Out-Null
            }
        }
        $totalRowCount++
        $fingerprintRows.Add($row) | Out-Null
        if ($rows.Count -lt $rowLimit) {
            $rows.Add($row) | Out-Null
        }
        if ($runQueueIndex -gt 0 -and $rows.Contains($row)) {
            $runnableRows.Add($row) | Out-Null
        }
    }

    foreach ($entry in $ordered) {
        if (-not $entry -or -not $entry.PSObject.Properties['RunQueueIndex']) { continue }
        if ([int]$entry.RunQueueIndex -gt 0) {
            $entry | Add-Member -NotePropertyName RunQueueTotal -NotePropertyValue ([int]$runnableRowCount) -Force
        }
    }
    foreach ($row in $runnableRows) {
        $row['run_queue_total'] = [int]$runnableRowCount
    }
    foreach ($acceptedRow in $acceptedRunRows) {
        $acceptedRow['run_queue_total'] = [int]$runnableRowCount
    }
    foreach ($acceptedRow in $acceptedPlanRows) {
        $acceptedRow['run_queue_total'] = [int]$runnableRowCount
    }
    $script:LastRunMonitorAcceptedRows = @($acceptedRunRows.ToArray())

    # Append hold entries to the display rows so the UI can render them with a
    # HOLD badge. They are not included in runnable_count and never process.
    foreach ($holdEntry in $holdOrdered) {
        if (-not $holdEntry -or -not $holdEntry.File) { continue }
        $holdFile = $holdEntry.File
        $holdSizeGb = 0.0
        try { $holdSizeGb = [math]::Round([double]$holdFile.Length / 1GB, 3) } catch {}
        $holdLastWriteUtc = ''
        try { $holdLastWriteUtc = ([datetime]$holdEntry.LastWriteUtc).ToString('o') } catch {}
        $holdLibraryOverrideKeys = if ($holdEntry.Metadata -and $holdEntry.Metadata.ContainsKey('settings_override_keys')) { @($holdEntry.Metadata['settings_override_keys']) } else { @() }
        $holdLibrarySettingsOverrides = if ($holdEntry.Metadata -and $holdEntry.Metadata.ContainsKey('settings_overrides')) { $holdEntry.Metadata['settings_overrides'] } else { [ordered]@{} }
        $holdLibraryEffectiveSettings = if ($holdEntry.Metadata -and $holdEntry.Metadata.ContainsKey('effective_settings')) { $holdEntry.Metadata['effective_settings'] } else { [ordered]@{} }
        $globalOrder++
        $totalRowCount++
        $holdRow = [ordered]@{
            global_order            = $globalOrder
            phase                   = 'hold'
            manifest_priority_level = 'hold'
            media_kind              = [string]$holdEntry.MediaKind
            queue_index             = 0
            queue_total             = 0
            run_queue_index         = 0
            run_queue_total         = 0
            is_priority             = $false
            priority_reasons        = @()
            priority_rank           = 0L
            source_path             = [string]$holdEntry.SourcePath
            root_path               = [string]$holdEntry.RootPath
            library_id              = [string]$holdEntry.LibraryId
            library_name            = [string]$holdEntry.LibraryName
            library_designation     = [string]$holdEntry.LibraryDesignation
            library_output_root     = [string]$holdEntry.LibraryOutputRoot
            library_settings_override_keys = @($holdLibraryOverrideKeys)
            library_settings_overrides = $holdLibrarySettingsOverrides
            library_effective_settings = $holdLibraryEffectiveSettings
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
            estimated_bitrate_mbps  = 0.0
            route_size_threshold_gb = 0.0
            route_bitrate_threshold_mbps = 0.0
            route_threshold_mode    = ''
            size_over_threshold     = $false
            bitrate_over_threshold  = $false
            blocked_reason_code     = 'hold'
            blocked_reason          = 'Operator hold.'
            runtime_checks_deferred = $false
            runtime_check_codes     = @()
            runtime_check_notes     = @()
        }
        $fingerprintRows.Add($holdRow) | Out-Null
        if ($rows.Count -lt $rowLimit) {
            $rows.Add($holdRow) | Out-Null
        }
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

    $inputFingerprint = Get-MediaPipelineQueueInputFingerprint
    $pendingBackpressure = Get-MediaPipelinePendingPublishBackpressure
    $pendingIndex = $script:PendingPublishIndex
    $pendingHealth = [ordered]@{
        status = if ($pendingIndex -and ([int]$pendingIndex.MissingPayloadCount -gt 0 -or [int]$pendingIndex.UnreadableManifestCount -gt 0)) { 'blocked' } else { 'ready' }
        count = if ($pendingIndex) { [int]$pendingIndex.Count } else { 0 }
        missing_payload_count = if ($pendingIndex) { [int]$pendingIndex.MissingPayloadCount } else { 0 }
        unreadable_manifest_count = if ($pendingIndex) { [int]$pendingIndex.UnreadableManifestCount } else { 0 }
    }
    $planFingerprint = Get-MediaPipelineQueuePlanFingerprint `
        -Rows $fingerprintRows.ToArray() `
        -ExcludedRows $fingerprintExcludedRows.ToArray() `
        -AcceptedRows $acceptedPlanRows.ToArray() `
        -InputFingerprint ([string]$inputFingerprint.Fingerprint) `
        -OrderingStrategy ([string]$QueuePlan.QueueOrderingStrategy) `
        -PendingBackpressure $pendingBackpressure `
        -PendingHealth $pendingHealth
    $acceptedRunRowsFingerprint = Get-MediaPipelineAcceptedRunRowsFingerprint -Rows $acceptedPlanRows.ToArray()
    $priorityOnlyScope = $false
    if ($QueuePlan.PSObject.Properties['PriorityOnly']) {
        $priorityOnlyScope = [bool]$QueuePlan.PriorityOnly
    }

    return [pscustomobject]@{
        schema_version    = 'queue_plan_snapshot.v1'
        queue_snapshot_origin = 'active_run'
        priority_only_scope = [bool]$priorityOnlyScope
        queue_input_fingerprint_schema = [string]$inputFingerprint.SchemaVersion
        queue_input_fingerprint = [string]$inputFingerprint.Fingerprint
        queue_input_components = $inputFingerprint.Components
        queue_plan_fingerprint_schema = 'queue_plan_fingerprint.v1'
        queue_plan_fingerprint = [string]$planFingerprint
        accepted_run_rows_fingerprint_schema = 'accepted_run_rows_fingerprint.v1'
        accepted_run_rows_fingerprint = [string]$acceptedRunRowsFingerprint
        pending_publish_index_health = $pendingHealth
        pending_publish_backpressure = [ordered]@{
            blocked = [bool]$pendingBackpressure.Blocked
            block_reason = [string]$pendingBackpressure.BlockReason
            deferred_publish = [bool]$pendingBackpressure.DeferredPublish
            manifest_count = [int]$pendingBackpressure.ManifestCount
            oldest_age_seconds = $pendingBackpressure.OldestAgeSeconds
            total_bytes = [int64]$pendingBackpressure.TotalBytes
            retry_exhausted_count = [int]$pendingBackpressure.RetryExhaustedCount
            normal_threshold = [int]$pendingBackpressure.NormalThreshold
            deferred_threshold = [int]$pendingBackpressure.DeferredThreshold
        }
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
        runnable_count    = [int]$runnableRowCount
        total_row_count   = [int]$totalRowCount
        shown_row_count   = [int]$rows.Count
        row_limit         = [int]$rowLimit
        rows_truncated    = [bool]($totalRowCount -gt $rows.Count)
        excluded_count    = [int]$excludedRowsTotal
        excluded_row_limit = [int]$excludedRowsLimit
        excluded_rows_truncated = [bool]($excludedRowsTotal -gt $excludedRows.Count)
        excluded_rows     = $excludedRows
        accepted_run_rows = @($acceptedPlanRows.ToArray())
        rows              = $rows
        gpu_available     = $gpuAvailable
        gpu_unavailable_reason = $gpuReason
    }
}
