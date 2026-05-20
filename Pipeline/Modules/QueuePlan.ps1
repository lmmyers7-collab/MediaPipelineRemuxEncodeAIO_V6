# ==============================================================================
# Modules\QueuePlan.ps1
# ==============================================================================
# Priority-marker detection, queue entry construction, and queue sort-key
# helpers.  Split from Naming.ps1; must be dot-sourced BEFORE Naming.ps1
# because Naming.ps1 functions call Remove-PriorityMarkersFromName.
#
# Dot-sourced from MediaPipeline_chatgpt.ps1. Reads at call time:
#   $script:PriorityMarkers
#   $script:AggressiveEpisodeParsing
#   $script:ValidExtensions
#   $script:LocalStateLayout     (optional — used for priority manifest + strategy paths)
#   $script:MixPriorityPhase     (optional bool — merge priority movies+TV into one phase)
#   $script:QueueOrderingStrategy (optional string — config-file default strategy)
#
# Cross-module helpers (loaded before this module):
#   Write-Log
#
# Functions exported:
#   Test-StartsWithPriorityMarker
#   Remove-PriorityMarkersFromName
#   Get-SourcePriorityInfo
#   Get-PriorityManifest
#   Get-ManifestPriorityLevel
#   Get-ManifestEntryField
#   Get-QueueRelativePath
#   Get-QueueSeasonNumber
#   Get-QueueEpisodeNumber
#   New-MediaQueueItem
#   ConvertTo-MediaQueueItemRecord
#   Get-QueuedEntries
#   Set-QueueEntryRuntimeMetadata
#   Get-EffectiveQueueStrategy
#   Invoke-QueueStrategySort
#   New-MediaQueuePhasePlan
# ==============================================================================
function Test-StartsWithPriorityMarker {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $false }
    $trimmed = $Text.TrimStart()
    foreach ($marker in ($script:PriorityMarkers | Sort-Object Length -Descending)) {
        if ($trimmed.StartsWith($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Remove-PriorityMarkersFromName {
    param([string]$Text)
    if ([string]::IsNullOrWhiteSpace($Text)) { return $Text }

    $result = $Text
    for ($pass = 0; $pass -lt 6; $pass++) {
        $trimmed = $result.TrimStart()
        $matched = $false
        foreach ($marker in ($script:PriorityMarkers | Sort-Object Length -Descending)) {
            if ($trimmed.StartsWith($marker, [System.StringComparison]::OrdinalIgnoreCase)) {
                $trimmed = $trimmed.Substring($marker.Length).TrimStart(' ', '-', '_', '.')
                $result = $trimmed
                $matched = $true
                break
            }
        }
        if (-not $matched) { break }
    }

    return $result.Trim()
}

function Get-SourcePriorityInfo {
    param($FileInfo)

    $reasons = [System.Collections.Generic.List[string]]::new()
    $priorityTicks = 0L
    if (Test-StartsWithPriorityMarker $FileInfo.Name) {
        $reasons.Add('file')
        $priorityTicks = [Math]::Max($priorityTicks, [long]$FileInfo.LastWriteTimeUtc.Ticks)
    }

    $current = $FileInfo.DirectoryName
    for ($depth = 0; $depth -lt 4 -and $current; $depth++) {
        $leaf = Split-Path $current -Leaf
        if ($leaf -and (Test-StartsWithPriorityMarker $leaf)) {
            $reasons.Add("folder:$leaf")
            try {
                $folderInfo = Get-Item -LiteralPath $current -Force -ErrorAction Stop
                $priorityTicks = [Math]::Max($priorityTicks, [long]$folderInfo.LastWriteTimeUtc.Ticks)
            } catch {
            }
        }
        $current = Split-Path $current -Parent
    }

    return @{
        IsPriority         = ($reasons.Count -gt 0)
        Reasons            = @($reasons)
        PriorityOrderTicks = $priorityTicks
    }
}

# ==============================================================================
# Priority manifest — non-destructive UI-driven priority levels
# ==============================================================================

function Get-PriorityManifest {
    <#
    .SYNOPSIS
        Load priority_manifest.json from the state root.
        Returns an empty manifest hashtable on any error.
    .DESCRIPTION
        The manifest is a JSON file written by the DesktopApp API at:
          state_root / priority_manifest.json
        Format:
          { "version": 1, "entries": { "<norm-path>": { "level": "high"|"normal"|"low"|"hold", ... } } }
    #>
    $manifestPath = $null
    try {
        if ($script:LocalStateLayout -and $script:LocalStateLayout.Paths -and $script:LocalStateLayout.Paths.PriorityManifest) {
            $manifestPath = [string]$script:LocalStateLayout.Paths.PriorityManifest
        }
    } catch {}

    $empty = @{ version = 1; entries = @{} }

    if ([string]::IsNullOrWhiteSpace($manifestPath) -or -not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) {
        return $empty
    }

    try {
        $text = [System.IO.File]::ReadAllText($manifestPath, [System.Text.Encoding]::UTF8)
        $obj  = $text | ConvertFrom-Json
        if (-not $obj -or $obj.version -ne 1 -or -not $obj.entries) { return $empty }
        # Convert PSObject entries to a plain hashtable for fast lookup
        $ht = @{}
        foreach ($prop in $obj.entries.PSObject.Properties) {
            $ht[$prop.Name] = $prop.Value
        }
        return @{ version = 1; entries = $ht }
    } catch {
        Write-Log "Get-PriorityManifest: failed to read manifest at '$manifestPath': $_" "WARN"
        return $empty
    }
}

function Get-ManifestPriorityLevel {
    <#
    .SYNOPSIS
        Resolve the effective manifest priority level for a source path.
    .PARAMETER Manifest
        The hashtable returned by Get-PriorityManifest.
    .PARAMETER SourcePath
        The full source file path (string).
    .OUTPUTS
        "high" | "normal" | "low" | "hold"
    .DESCRIPTION
        Resolution order (first match wins):
          1. Exact file-level entry
          2. Deepest ancestor folder entry
          3. "normal" (default — no manifest entry)
    #>
    param(
        [hashtable] $Manifest,
        [string]    $SourcePath
    )

    $validLevels = @('high', 'normal', 'low', 'hold')
    $default = 'normal'

    if (-not $Manifest -or -not $Manifest.entries -or $Manifest.entries.Count -eq 0) {
        return $default
    }

    # Normalise: lowercase, forward slashes, no trailing slash
    $norm = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')

    $entries = $Manifest.entries

    # 1. Exact match
    if ($entries.ContainsKey($norm)) {
        $level = ([string]$entries[$norm].level).ToLowerInvariant()
        return if ($level -in $validLevels) { $level } else { $default }
    }

    # 2. Folder prefix match — deepest ancestor wins
    $bestLen = -1
    $bestLevel = $default
    foreach ($key in $entries.Keys) {
        $candidate = $norm + '/'
        if ($candidate.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $level = ([string]$entries[$key].level).ToLowerInvariant()
            if ($level -in $validLevels) {
                $bestLen   = $key.Length
                $bestLevel = $level
            }
        }
    }

    return $bestLevel
}

function Get-QueueRelativePath {
    param(
        $FileInfo,
        [string]$RootPath
    )

    if ($null -eq $FileInfo) { return '' }
    if ([string]::IsNullOrWhiteSpace($RootPath)) { return [string]$FileInfo.FullName }
    try {
        $fileFull = [System.IO.Path]::GetFullPath($FileInfo.FullName)
        $rootFull = [System.IO.Path]::GetFullPath($RootPath)
        if (Get-Command -Name Get-MediaPipelineRelativePath -ErrorAction SilentlyContinue) {
            $relative = Get-MediaPipelineRelativePath -Path $fileFull -Root $rootFull
            if (-not [string]::IsNullOrWhiteSpace($relative)) {
                return [string]$relative
            }
        } elseif ($fileFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or $fileFull.StartsWith(($rootFull.TrimEnd('\','/') + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)) {
            $relative = $fileFull.Substring($rootFull.Length).TrimStart('\', '/')
            if (-not [string]::IsNullOrWhiteSpace($relative)) {
                return [string]$relative
            }
        }
    } catch {
    }
    return [string]$FileInfo.FullName
}

function Get-QueueSeasonNumber {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) { return 0 }
    $match = [regex]::Match($Text, '(?i)\b(?:season\s*|s)(\d{1,2})\b')
    if (-not $match.Success) { return 0 }
    try {
        return [int]$match.Groups[1].Value
    } catch {
        return 0
    }
}

function Get-QueueEpisodeNumber {
    param([string]$Text)

    if ([string]::IsNullOrWhiteSpace($Text)) { return 0 }
    # Strong SxxExx / NxM patterns
    $match = [regex]::Match($Text, '(?i)\bs\d{1,2}[ ._-]*e(\d{1,3})\b')
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\b\d{1,2}x(\d{1,3})\b') }
    # Fansub-style explicit tokens
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\bEpisode[\s._-]*(\d{1,3})\b') }
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\bEp[\s._-]*(\d{1,3})\b') }
    if ($match.Success) {
        try { return [int]$match.Groups[1].Value } catch { return 0 }
    }
    # Bare trailing number: strip brackets + quality tags then match "- 12" or " 12" at end.
    # Used for fansub layout like "[Group] Show 3rd Season - 12 (BD 1080p)".
    $stripped = $Text -replace '\([^()]*\)', '' -replace '\[[^\[\]]*\]', ''
    $stripped = $stripped -replace '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10|hevc|h264|h265|x264|x265|av1|bluray|blu-ray|web-dl|webdl|webrip|remux|flac|aac|opus|ac3|dts|truehd|eac3|ddp)\b', ' '
    $stripped = ($stripped -replace '\s+', ' ').Trim()
    $match = [regex]::Match($stripped, '[\s._-]+(\d{1,3})\s*$')
    if ($match.Success) {
        try {
            $ep = [int]$match.Groups[1].Value
            if ($ep -ge 1 -and $ep -le 500) { return $ep }
        } catch {}
    }
    if ($script:AggressiveEpisodeParsing) {
        $loose = Get-TVLooseSeasonEpisodeFromName $Text
        if ($loose) { return [int]$loose.Episode }
        $bare = Get-TVLooseBareEpisodeNumber $Text
        if ($bare) { return [int]$bare.Episode }
    }
    return 0
}

function New-MediaQueueItem {
    param(
        $File = $null,
        [ValidateSet('movie', 'tv', 'unknown')] [string] $MediaKind = 'unknown',
        [ValidateSet('discovery', 'csv_rerun')] [string] $QueueSource = 'discovery',
        [string] $QueuePhase = '',
        [string] $SourcePath = '',
        [string] $RootPath = '',
        $PriorityInfo = $null,
        [string] $SortName = '',
        [string] $ShowSortKey = '',
        [int] $SeasonSortOrder = 0,
        [string] $SeasonSortKey = '',
        [int] $EpisodeSortOrder = 0,
        [string] $RelativePathSort = '',
        [datetime] $LastWriteUtc = [datetime]::MinValue,
        [hashtable] $Metadata = @{},
        # Manifest-derived priority level: "high" | "normal" | "low" | "hold"
        [string] $ManifestPriority = 'normal'
    )

    if ($null -eq $PriorityInfo) {
        if ($null -ne $File) {
            $PriorityInfo = Get-SourcePriorityInfo $File
        } else {
            $PriorityInfo = @{
                IsPriority         = $false
                Reasons            = @()
                PriorityOrderTicks = 0L
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($SourcePath) -and $null -ne $File) {
        $SourcePath = [string]$File.FullName
    }
    if ([string]::IsNullOrWhiteSpace($SortName) -and $null -ne $File) {
        $SortName = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($File.Name))
    }
    if ([string]::IsNullOrWhiteSpace($ShowSortKey)) { $ShowSortKey = $SortName }
    if ([string]::IsNullOrWhiteSpace($RelativePathSort) -and $null -ne $File) { $RelativePathSort = [string]$File.FullName }
    if ($LastWriteUtc -eq [datetime]::MinValue -and $null -ne $File -and $File.PSObject.Properties['LastWriteTimeUtc']) {
        $LastWriteUtc = $File.LastWriteTimeUtc
    }
    if ([string]::IsNullOrWhiteSpace($QueuePhase) -and $QueueSource -eq 'csv_rerun') { $QueuePhase = 'csv_rerun' }

    $priorityTicks = 0L
    try { $priorityTicks = [long]$PriorityInfo.PriorityOrderTicks } catch {}

    # Effective priority: manifest wins over filesystem marker when set.
    # FS marker alone → "high" (backward compat). No marker, no manifest → "normal".
    $effectiveLevel = if ($ManifestPriority -ne 'normal') {
        $ManifestPriority
    } elseif ([bool]$PriorityInfo.IsPriority) {
        'high'
    } else {
        'normal'
    }

    return [pscustomobject]@{
        QueueItemType          = 'media_queue_item.v1'
        QueueSource            = $QueueSource
        QueuePhase             = $QueuePhase
        MediaKind              = $MediaKind
        IsTV                   = ($MediaKind -eq 'tv')
        File                   = $File
        SourcePath             = $SourcePath
        RootPath               = $RootPath
        PriorityInfo           = $PriorityInfo
        IsPriority             = [bool]$PriorityInfo.IsPriority
        PriorityOrderTicks     = $priorityTicks
        ManifestPriority       = $ManifestPriority
        EffectivePriorityLevel = $effectiveLevel
        IsHold                 = ($effectiveLevel -eq 'hold')
        IsLowPriority          = ($effectiveLevel -eq 'low')
        QueueIndex             = 0
        QueueTotal             = 0
        SortName               = $SortName
        ShowSortKey            = $ShowSortKey
        SeasonSortOrder        = $SeasonSortOrder
        SeasonSortKey          = $SeasonSortKey
        EpisodeSortOrder       = $EpisodeSortOrder
        RelativePathSort       = $RelativePathSort
        LastWriteUtc           = $LastWriteUtc
        FullName               = $SourcePath
        Metadata               = if ($Metadata) { $Metadata } else { @{} }
    }
}

function ConvertTo-MediaQueueItemRecord {
    param($QueueItem)

    if ($null -eq $QueueItem) { return $null }

    return [pscustomobject][ordered]@{
        schema_version          = [string]$QueueItem.QueueItemType
        queue_source            = [string]$QueueItem.QueueSource
        queue_phase             = [string]$QueueItem.QueuePhase
        media_kind              = [string]$QueueItem.MediaKind
        source_path             = [string]$QueueItem.SourcePath
        root_path               = [string]$QueueItem.RootPath
        is_tv                   = [bool]$QueueItem.IsTV
        is_priority             = [bool]$QueueItem.IsPriority
        manifest_priority_level = [string]$QueueItem.EffectivePriorityLevel
        queue_index             = [int]$QueueItem.QueueIndex
        queue_total             = [int]$QueueItem.QueueTotal
        sort_name               = [string]$QueueItem.SortName
        relative_path_sort      = [string]$QueueItem.RelativePathSort
        metadata                = if ($QueueItem.Metadata) { $QueueItem.Metadata } else { @{} }
    }
}

function Get-QueuedEntries {
    param(
        [array]$Files,
        [string]$RootPath,
        [switch]$IsTV,
        # Caller may pass a pre-loaded manifest to avoid re-reading it per-batch.
        [hashtable]$PriorityManifest = $null
    )

    # Load manifest once per call (caller may pass it in for efficiency)
    if ($null -eq $PriorityManifest) {
        $PriorityManifest = Get-PriorityManifest
    }

    $entries = foreach ($file in @($Files)) {
        if ($null -eq $file) { continue }
        $priorityInfo = Get-SourcePriorityInfo $file
        $manifestLevel = Get-ManifestPriorityLevel -Manifest $PriorityManifest -SourcePath ([string]$file.FullName)
        $sortName = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($file.Name))
        $relativePath = Get-QueueRelativePath -FileInfo $file -RootPath $RootPath
        $showSortKey = $sortName
        $seasonSortOrder = 0
        $seasonSortKey = ''
        $episodeSortOrder = 0
        $relativePathSort = [string]$file.FullName
        if ($IsTV) {
            $relativeParts = @($relativePath -split '[\\/]') | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
            $showSortKey = if ($relativeParts.Count -ge 1) {
                [string]$relativeParts[0]
            } elseif ($file.Directory -and $file.Directory.Parent) {
                [string]$file.Directory.Parent.Name
            } elseif ($file.Directory) {
                [string]$file.Directory.Name
            } else {
                $sortName
            }
            $seasonSortKey = if ($relativeParts.Count -ge 2) { [string]$relativeParts[1] } else { '' }
            $seasonSortOrder = Get-QueueSeasonNumber $seasonSortKey
            if ($seasonSortOrder -le 0) {
                $seasonSortOrder = Get-QueueSeasonNumber $file.BaseName
            }
            $episodeSortOrder = Get-QueueEpisodeNumber $file.BaseName
            if ($seasonSortOrder -le 0 -or $episodeSortOrder -le 0) {
                $tvInfo = Get-TVInfoFromFile $file
                if ($tvInfo -and $tvInfo.IsReliable) {
                    if ($seasonSortOrder -le 0) { $seasonSortOrder = [int]$tvInfo.Season }
                    if ($episodeSortOrder -le 0) { $episodeSortOrder = [int]$tvInfo.Episode }
                }
            }
            $relativePathSort = $relativePath
        }
        New-MediaQueueItem `
            -File $file `
            -MediaKind $(if ($IsTV) { 'tv' } else { 'movie' }) `
            -QueueSource 'discovery' `
            -RootPath $RootPath `
            -PriorityInfo $priorityInfo `
            -SortName $sortName `
            -ShowSortKey $showSortKey `
            -SeasonSortOrder $seasonSortOrder `
            -SeasonSortKey $seasonSortKey `
            -EpisodeSortOrder $episodeSortOrder `
            -RelativePathSort $relativePathSort `
            -LastWriteUtc $file.LastWriteTimeUtc `
            -ManifestPriority $manifestLevel
    }

    if ($null -eq $entries) { return @() }

    # Priority sort integer: high=0, normal=1, low=2; hold items sorted last
    # but kept in the array so callers can split them into a hold bucket.
    return @(
        $entries | Sort-Object `
            @{ Expression = { switch ($_.EffectivePriorityLevel) { 'high' { 0 } 'low' { 2 } 'hold' { 3 } default { 1 } } } }, `
            @{ Descending = $true; Expression = { if ($_.EffectivePriorityLevel -eq 'high') { $_.PriorityOrderTicks } else { 0L } } }, `
            @{ Expression = { $_.ShowSortKey } }, `
            @{ Expression = { if ($_.SeasonSortOrder -gt 0) { $_.SeasonSortOrder } else { 9999 } } }, `
            @{ Expression = { $_.SeasonSortKey } }, `
            @{ Expression = { if ($_.EpisodeSortOrder -gt 0) { $_.EpisodeSortOrder } else { 999999 } } }, `
            @{ Expression = { $_.RelativePathSort } }, `
            @{ Expression = { $_.SortName } }, `
            @{ Expression = { $_.LastWriteUtc } }, `
            @{ Expression = { $_.FullName } }
    )
}

function Set-QueueEntryRuntimeMetadata {
    param(
        [array]$Entries,
        [bool]$IsTV,
        # When supplied, overrides the phase label for all entries in this batch.
        [string]$PhaseOverride = ''
    )

    $items = @($Entries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    for ($i = 0; $i -lt $items.Count; $i++) {
        $items[$i] | Add-Member -NotePropertyName QueueIndex -NotePropertyValue ($i + 1) -Force
        $items[$i] | Add-Member -NotePropertyName QueueTotal -NotePropertyValue $items.Count -Force
        $items[$i] | Add-Member -NotePropertyName IsTV -NotePropertyValue $IsTV -Force
        $items[$i] | Add-Member -NotePropertyName MediaKind -NotePropertyValue $(if ($IsTV) { 'tv' } else { 'movie' }) -Force
        $phase = if (-not [string]::IsNullOrWhiteSpace($PhaseOverride)) {
            $PhaseOverride
        } elseif ($items[$i].EffectivePriorityLevel -eq 'hold') {
            'hold'
        } elseif ($items[$i].EffectivePriorityLevel -eq 'low') {
            'low'
        } elseif ($items[$i].EffectivePriorityLevel -eq 'high' -or [bool]$items[$i].IsPriority) {
            if ($IsTV) { 'priority_tv' } else { 'priority_movie' }
        } elseif ($IsTV) {
            'tv'
        } else {
            'movie'
        }
        $items[$i] | Add-Member -NotePropertyName QueuePhase -NotePropertyValue $phase -Force
    }
    return @($items)
}

function Copy-QueueEntriesForLegacyPriorityPhase {
    param([array]$Entries)

    $items = @($Entries | Where-Object { $null -ne $_ -and $null -ne $_.File })
    $copies = [System.Collections.Generic.List[object]]::new()
    for ($i = 0; $i -lt $items.Count; $i++) {
        $copy = [pscustomobject]@{}
        foreach ($prop in $items[$i].PSObject.Properties) {
            $copy | Add-Member -NotePropertyName $prop.Name -NotePropertyValue $prop.Value -Force
        }
        $copy | Add-Member -NotePropertyName QueueIndex -NotePropertyValue ($i + 1) -Force
        $copy | Add-Member -NotePropertyName QueueTotal -NotePropertyValue $items.Count -Force
        $copy | Add-Member -NotePropertyName QueuePhase -NotePropertyValue 'priority' -Force
        $copies.Add($copy)
    }
    return @($copies)
}

# ==============================================================================
# Queue ordering strategy — Get-EffectiveQueueStrategy / Invoke-QueueStrategySort
# ==============================================================================

# Valid strategy names used both for validation and UI display.
$script:ValidQueueStrategies = @(
    'Standard', 'FreshestFirst', 'ShowComplete', 'RoundRobin',
    'DeadlineAware', 'SmallFirst', 'LargeFirst', 'ManualOrder'
)

function Get-ManifestEntryField {
    <#
    .SYNOPSIS
        Return a specific field from the manifest entry that applies to a source path.
    .DESCRIPTION
        Performs the same two-step lookup as Get-ManifestPriorityLevel (exact match then
        deepest ancestor folder) but returns an arbitrary named field from the entry
        object rather than just the "level" field.  Returns $null if the entry or field
        does not exist.
    .PARAMETER Manifest
        The hashtable returned by Get-PriorityManifest.
    .PARAMETER SourcePath
        The full source file path (string).
    .PARAMETER FieldName
        The name of the field to retrieve (e.g. "wanted_by", "position").
    #>
    param(
        [hashtable] $Manifest,
        [string]    $SourcePath,
        [string]    $FieldName
    )

    if (-not $Manifest -or -not $Manifest.entries -or $Manifest.entries.Count -eq 0) { return $null }
    if ([string]::IsNullOrWhiteSpace($SourcePath) -or [string]::IsNullOrWhiteSpace($FieldName)) { return $null }

    $norm    = $SourcePath.Replace('\', '/').ToLowerInvariant().TrimEnd('/')
    $entries = $Manifest.entries

    # Helper: extract named field from a PSObject or hashtable entry value
    $getField = {
        param($entry)
        if ($null -eq $entry) { return $null }
        try {
            # PSObject (from ConvertFrom-Json)
            $prop = $entry.PSObject.Properties[$FieldName]
            if ($prop) { return $prop.Value }
        } catch {}
        try {
            # Hashtable
            if ($entry -is [hashtable] -and $entry.ContainsKey($FieldName)) {
                return $entry[$FieldName]
            }
        } catch {}
        return $null
    }

    # 1. Exact match
    if ($entries.ContainsKey($norm)) {
        return (& $getField $entries[$norm])
    }

    # 2. Folder prefix match — deepest ancestor wins
    $bestLen   = -1
    $bestEntry = $null
    foreach ($key in $entries.Keys) {
        if ($norm.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -and $key.Length -gt $bestLen) {
            $bestLen   = $key.Length
            $bestEntry = $entries[$key]
        }
    }
    if ($null -ne $bestEntry) { return (& $getField $bestEntry) }
    return $null
}

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
          ManualOrder   — within each normal/low bucket, entries with a manifest
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
            # Within each bucket, entries with a manifest "position" float
            # sort first (ascending); the remainder keep their natural order.
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

function New-MediaQueuePhasePlan {
    param(
        [array]$MovieEntries,
        [array]$TVEntries
    )

    # ----- Split each batch by effective priority level -----
    $movieHigh   = @($MovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'high' })
    $movieNormal = @($MovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'normal' })
    $movieLow    = @($MovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'low' })
    $movieHold   = @($MovieEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'hold' })

    $tvHigh      = @($TVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'high' })
    $tvNormal    = @($TVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'normal' })
    $tvLow       = @($TVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'low' })
    $tvHold      = @($TVEntries | Where-Object { $null -ne $_ -and $null -ne $_.File -and $_.EffectivePriorityLevel -eq 'hold' })

    # ----- Apply runtime metadata (QueueIndex, QueuePhase, etc.) -----
    $highMoviesMeta = @(Set-QueueEntryRuntimeMetadata -Entries $movieHigh   -IsTV $false -PhaseOverride 'priority_movie')
    $highTVMeta     = @(Set-QueueEntryRuntimeMetadata -Entries $tvHigh      -IsTV $true  -PhaseOverride 'priority_tv')
    $normalMovieMeta= @(Set-QueueEntryRuntimeMetadata -Entries $movieNormal -IsTV $false -PhaseOverride 'movie')
    $normalTVMeta   = @(Set-QueueEntryRuntimeMetadata -Entries $tvNormal    -IsTV $true  -PhaseOverride 'tv')
    $lowMovieMeta   = @(Set-QueueEntryRuntimeMetadata -Entries $movieLow    -IsTV $false -PhaseOverride 'low')
    $lowTVMeta      = @(Set-QueueEntryRuntimeMetadata -Entries $tvLow       -IsTV $true  -PhaseOverride 'low')
    $holdMovieMeta  = @(Set-QueueEntryRuntimeMetadata -Entries $movieHold   -IsTV $false -PhaseOverride 'hold')
    $holdTVMeta     = @(Set-QueueEntryRuntimeMetadata -Entries $tvHold      -IsTV $true  -PhaseOverride 'hold')

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
        -Manifest     $manifest

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
        $priorityEntries | ForEach-Object { $_ | Add-Member -NotePropertyName QueuePhase -NotePropertyValue 'priority' -Force }
    }

    $holdEntries = @(@($holdMovieMeta) + @($holdTVMeta) | Where-Object { $null -ne $_ })
    $movies  = @(@($highMoviesMeta) + @($normalMovieMeta) + @($lowMovieMeta) + @($holdMovieMeta) | Where-Object { $null -ne $_ })
    $tv      = @(@($highTVMeta) + @($normalTVMeta) + @($lowTVMeta) + @($holdTVMeta) | Where-Object { $null -ne $_ })

    # Legacy-compat: PriorityEntries combines high-movie + high-TV regardless of MixPhase
    # and keeps the original flat "priority" phase contract for downstream callers.
    $allPriorityEntries = @(Copy-QueueEntriesForLegacyPriorityPhase -Entries @(@($highMoviesMeta) + @($highTVMeta)))
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
