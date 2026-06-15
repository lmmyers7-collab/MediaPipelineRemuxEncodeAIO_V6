# ==============================================================================
# ops\pipeline\engine\queue\snapshot_rows.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\pipeline_engine.ps1. Keep function names stable;
# pipeline_engine.ps1 dot-sources this file as part of the queue engine surface.
# ==============================================================================

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
            $sourceFailureCode = if ($classification -eq 'operator_required') { 'source_failure_operator_required' } else { 'source_failure_permanent' }
            return [pscustomobject]@{
                Code   = $sourceFailureCode
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

    # Walk the same phase order used by execution. RunQueueIndex/RunQueueTotal
    # are assigned only after snapshot-time exclusion checks pass.
    $ordered = @(Get-MediaPipelineQueuePlanRunnableEntries -QueuePlan $QueuePlan)
    # Hold entries appended at end — they render in the UI but never process
    $holdOrdered = @($QueuePlan.HoldEntries)

    $rows = New-Object System.Collections.Generic.List[object]
    $runnableRows = New-Object System.Collections.Generic.List[object]
    $excludedRows = New-Object System.Collections.Generic.List[object]
    $excludedRowsTotal = 0
    $excludedRowsLimit = 500
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
        $routeEstimatedBitrateMbps = 0.0
        $routeSizeThresholdGb = 0.0
        $routeBitrateThresholdMbps = 0.0
        $routeThresholdMode = ''
        $routeSizeOverThreshold = $false
        $routeBitrateOverThreshold = $false
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
            if ($rp) {
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
        $rows.Add($row) | Out-Null
        if ($runQueueIndex -gt 0) {
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
        $rows.Add([ordered]@{
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
        runnable_count    = [int]$runnableRowCount
        excluded_count    = [int]$excludedRowsTotal
        excluded_row_limit = [int]$excludedRowsLimit
        excluded_rows_truncated = [bool]($excludedRowsTotal -gt $excludedRows.Count)
        excluded_rows     = $excludedRows
        rows              = $rows
        gpu_available     = $gpuAvailable
        gpu_unavailable_reason = $gpuReason
    }
}
