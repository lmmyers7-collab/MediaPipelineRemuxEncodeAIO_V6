# ==============================================================================
# ops\pipeline\engine\queue\queue_entries.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\queue\queue_plan.ps1. Keep function names stable;
# queue_plan.ps1 dot-sources this file as the compatibility import surface.
# ==============================================================================

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
    $match = [regex]::Match($Text, '(?i)(?<![A-Za-z0-9])(?:season\s*|s)(\d{1,2})(?!\d)')
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
    $match = [regex]::Match($Text, '(?i)\bs\d{1,2}[ ._-]*e(\d{1,3})(?:v\d+)?\b')
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\b\d{1,2}x(\d{1,3})(?:v\d+)?\b') }
    # Fansub-style explicit tokens
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\bEpisode[\s._-]*(\d{1,3})(?:v\d+)?\b') }
    if (-not $match.Success) { $match = [regex]::Match($Text, '(?i)\bEp[\s._-]*(\d{1,3})(?:v\d+)?\b') }
    if ($match.Success) {
        try { return [int]$match.Groups[1].Value } catch { return 0 }
    }
    # Bare trailing number: strip brackets + quality tags then match "- 12" or " 12" at end.
    # Used for fansub layout like "[Group] Show 3rd Season - 12 (BD 1080p)".
    $stripped = $Text -replace '\([^()]*\)', '' -replace '\[[^\[\]]*\]', ''
    $stripped = $stripped -replace '(?i)\b(?:2160p|1080p|720p|480p|uhd|hdr|hdr10|hevc|h264|h265|x264|x265|av1|bluray|blu-ray|web-dl|webdl|webrip|remux|flac|aac|opus|ac3|dts|truehd|eac3|ddp)\b', ' '
    $stripped = ($stripped -replace '\s+', ' ').Trim()
    $match = [regex]::Match($stripped, '(?i)[\s._-]+(\d{1,3})(?:v\d+)?\s*$')
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
        $TVInfo = $null,
        [bool] $TVIdentityParsed = $false,
        [string] $RelativePathSort = '',
        [datetime] $LastWriteUtc = [datetime]::MinValue,
        [string] $LibraryId = '',
        [string] $LibraryName = '',
        [string] $LibraryDesignation = '',
        [string] $LibraryOutputRoot = '',
        [hashtable] $Metadata = @{},
        # Manifest-derived priority level: "high" | "normal" | "low" | "hold"
        [string] $ManifestPriority = 'normal',
        [bool] $ManifestPriorityExplicit = $false
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
    $metadataValue = if ($Metadata) { $Metadata } else { @{} }

    # Effective priority: manifest wins over filesystem marker when set.
    # FS marker alone → "high" (backward compat). No marker, no manifest → "normal".
    $effectiveLevel = if ($ManifestPriorityExplicit) {
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
        ManifestPriorityExplicit = [bool]$ManifestPriorityExplicit
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
        TVInfo                  = $TVInfo
        TVIdentityParsed        = [bool]$TVIdentityParsed
        TVParseReliable         = [bool]($TVIdentityParsed -and $TVInfo -and $TVInfo.IsReliable)
        TVParseError            = if ($TVIdentityParsed -and $TVInfo) { [string]$TVInfo.ParseError } elseif ($TVIdentityParsed) { 'TV identity parser returned no result.' } else { '' }
        RelativePathSort       = $RelativePathSort
        LibraryId              = $LibraryId
        LibraryName            = $LibraryName
        LibraryDesignation     = $LibraryDesignation
        LibraryOutputRoot      = $LibraryOutputRoot
        LastWriteUtc           = $LastWriteUtc
        FullName               = $SourcePath
        Metadata               = $metadataValue
    }
}

function ConvertTo-MediaQueueItemRecord {
    param($QueueItem)

    if ($null -eq $QueueItem) { return $null }
    $metadataValue = if ($QueueItem.Metadata) { $QueueItem.Metadata } else { @{} }

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
        manifest_priority_explicit = [bool]$QueueItem.ManifestPriorityExplicit
        queue_index             = [int]$QueueItem.QueueIndex
        queue_total             = [int]$QueueItem.QueueTotal
        sort_name               = [string]$QueueItem.SortName
        relative_path_sort      = [string]$QueueItem.RelativePathSort
        library_id              = [string]$QueueItem.LibraryId
        library_name            = [string]$QueueItem.LibraryName
        library_designation     = [string]$QueueItem.LibraryDesignation
        library_output_root     = [string]$QueueItem.LibraryOutputRoot
        metadata                = $metadataValue
    }
}

function Get-QueuedEntries {
    param(
        [array]$Files,
        [string]$RootPath,
        [switch]$IsTV,
        [hashtable]$LibraryProfileMetadata = $null,
        # Caller may pass a pre-loaded manifest to avoid re-reading it per-batch.
        [hashtable]$PriorityManifest = $null
    )

    # Load manifest once per call (caller may pass it in for efficiency)
    if ($null -eq $PriorityManifest) {
        $PriorityManifest = Get-PriorityManifest -FailClosed
    }
    if ($null -eq $LibraryProfileMetadata) {
        $LibraryProfileMetadata = @{}
    }

    $entries = foreach ($file in @($Files)) {
        if ($null -eq $file) { continue }
        $priorityInfo = Get-SourcePriorityInfo $file
        $manifestLevel = Get-ManifestPriorityLevel -Manifest $PriorityManifest -SourcePath ([string]$file.FullName)
        $manifestExplicit = Test-ManifestPriorityEntryApplies -Manifest $PriorityManifest -SourcePath ([string]$file.FullName)
        $sortName = Remove-PriorityMarkersFromName ([System.IO.Path]::GetFileNameWithoutExtension($file.Name))
        $relativePath = Get-QueueRelativePath -FileInfo $file -RootPath $RootPath
        $showSortKey = $sortName
        $seasonSortOrder = 0
        $seasonSortKey = ''
        $episodeSortOrder = 0
        $relativePathSort = [string]$file.FullName
        $tvInfo = $null
        $tvIdentityParsed = $false
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
            try {
                $tvInfo = Get-TVInfoFromFile `
                    -file $file `
                    -SourceRootPath $RootPath `
                    -LibraryName ([string]($LibraryProfileMetadata['library_name'])) `
                    -LibraryId ([string]($LibraryProfileMetadata['library_id'])) `
                    -LibraryDesignation ([string]($LibraryProfileMetadata['designation']))
                $tvIdentityParsed = $true
            } catch {
                $tvIdentityParsed = $true
                $tvInfo = $null
            }
            if ($tvInfo -and $tvInfo.IsReliable) {
                $showSortKey = [string]$tvInfo.ShowName
                $seasonSortOrder = [int]$tvInfo.Season
                $seasonSortKey = if ($seasonSortOrder -eq 0) { 'Specials' } else { "Season $($seasonSortOrder.ToString('00'))" }
                $episodeSortOrder = [int]$tvInfo.Episode
            } else {
                $seasonSortOrder = Get-QueueSeasonNumber $seasonSortKey
                if ($seasonSortOrder -le 0) {
                    $seasonSortOrder = Get-QueueSeasonNumber $file.BaseName
                }
                $episodeSortOrder = Get-QueueEpisodeNumber $file.BaseName
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
            -TVInfo $tvInfo `
            -TVIdentityParsed:$tvIdentityParsed `
            -RelativePathSort $relativePathSort `
            -LastWriteUtc $file.LastWriteTimeUtc `
            -LibraryId ([string]($LibraryProfileMetadata['library_id'])) `
            -LibraryName ([string]($LibraryProfileMetadata['library_name'])) `
            -LibraryDesignation ([string]($LibraryProfileMetadata['designation'])) `
            -LibraryOutputRoot ([string]($LibraryProfileMetadata['output_root'])) `
            -Metadata $(if ($LibraryProfileMetadata) { $LibraryProfileMetadata } else { @{} }) `
            -ManifestPriority $manifestLevel `
            -ManifestPriorityExplicit $manifestExplicit
    }

    if ($null -eq $entries) { return @() }

    # Priority sort integer: high=0, normal=1, low=2; hold items sorted last
    # but kept in the array so callers can split them into a hold bucket.
    return @(
        $entries | Sort-Object `
            @{ Expression = { switch ($_.EffectivePriorityLevel) { 'high' { 0 } 'low' { 2 } 'hold' { 3 } default { 1 } } } }, `
            @{ Descending = $true; Expression = { if ($_.EffectivePriorityLevel -eq 'high') { $_.PriorityOrderTicks } else { 0L } } }, `
            @{ Expression = { if (-not $_.IsTV -or $_.TVParseReliable) { 0 } else { 1 } } }, `
            @{ Expression = { $_.ShowSortKey } }, `
            @{ Expression = { if ($_.IsTV -and $_.TVParseReliable) { $_.SeasonSortOrder } elseif ($_.SeasonSortOrder -gt 0) { $_.SeasonSortOrder } else { 9999 } } }, `
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
