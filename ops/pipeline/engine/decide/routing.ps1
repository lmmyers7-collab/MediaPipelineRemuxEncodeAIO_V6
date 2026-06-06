# ==============================================================================
# ops\pipeline\engine\decide\routing.ps1
# ==============================================================================
# Route decision orchestrators. Pure policy helpers are split into child modules
# and dot-sourced here to preserve the historical routing export surface.
# ==============================================================================

. (Join-Path $PSScriptRoot 'codec_policy.ps1')
. (Join-Path $PSScriptRoot 'profile_selection.ps1')
. (Join-Path $PSScriptRoot 'size_policy.ps1')
. (Join-Path $PSScriptRoot 'route_plan.ps1')

function Resolve-MediaRouteBySize {
    param(
        [Parameter(Mandatory)] [long] $FileSizeBytes,
        [bool] $IsTV = $false,
        [double] $MovieRoute1080pTargetSizeGB = 0.0,
        [double] $MovieRoute1440pTargetSizeGB = 0.0,
        [double] $MovieRoute4KTargetSizeGB = 0.0,
        [double] $TVRoute1080pTargetSizeGB = 0.0,
        [double] $TVRoute1440pTargetSizeGB = 0.0,
        [double] $TVRoute4KTargetSizeGB = 0.0,
        [double] $DurationSeconds = 0,
        [string] $VideoCodec = '',
        [int] $VideoHeight = 0,
        [bool] $IsHDR = $false,
        $RouteHints = $null,
        $SourceMediaProfile = $null,
        [string] $RoutingProfile = '',
        [string] $RouteThresholdMode = '',
        [string] $SizeGuardMode = '',
        [bool] $AllowH264RemuxIfPlexCompatible = $true,
        [double] $H264RemuxMaxBitrateMbps = 35.0,
        [int] $H264RemuxMaxHeight = 1080,
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1080pMaxVideoBitrateMbps = 20.0,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route1440pMaxVideoBitrateMbps = 35.0,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667,
        [double] $Route4KMaxVideoBitrateMbps = 35.0
    )

    $sizeGB = [double]$FileSizeBytes / 1GB
    $routingProfileName = Resolve-MediaRouteRoutingProfileName -RoutingProfile $RoutingProfile
    $routeThresholdModeName = Resolve-MediaRouteThresholdModeName -RouteThresholdMode $RouteThresholdMode
    $sizeGuardModeName = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode $SizeGuardMode
    $hints = ConvertTo-MediaRouteHintMap $RouteHints
    if (-not [string]::IsNullOrWhiteSpace([string]$hints.routing_profile)) {
        $routingProfileName = Resolve-MediaRouteRoutingProfileName -RoutingProfile ([string]$hints.routing_profile)
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$hints.route_threshold_mode)) {
        $routeThresholdModeName = Resolve-MediaRouteThresholdModeName -RouteThresholdMode ([string]$hints.route_threshold_mode)
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$hints.size_guard_mode)) {
        $sizeGuardModeName = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode ([string]$hints.size_guard_mode)
    }
    $hints['route_threshold_mode'] = $routeThresholdModeName
    if ($null -ne $hints.allow_h264_remux_if_plex_compatible) {
        $AllowH264RemuxIfPlexCompatible = [bool]$hints.allow_h264_remux_if_plex_compatible
    }
    if ($null -ne $hints.h264_remux_max_bitrate_mbps) {
        $H264RemuxMaxBitrateMbps = [double]$hints.h264_remux_max_bitrate_mbps
    }
    if ($null -ne $hints.h264_remux_max_height) {
        $H264RemuxMaxHeight = [int]$hints.h264_remux_max_height
    }
    $duration = [math]::Max(0.0, [double]$DurationSeconds)
    $estimatedBitrate = if ($duration -gt 0) { [math]::Round((([double]$FileSizeBytes * 8.0) / $duration) / 1000000.0, 3) } else { 0.0 }
    $routeHeightBoundaries = Get-MediaRouteHeightToleranceBoundaries `
        -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
        -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
        -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
        -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent
    if (-not $routeHeightBoundaries.IsContiguous) {
        $routeHeightBoundaries = Get-MediaRouteHeightToleranceBoundaries
    }
    $bitrateSelection = if ($null -ne $hints.max_video_bitrate_mbps) {
        [pscustomobject]([ordered]@{
            CapMbps                  = [double]$hints.max_video_bitrate_mbps
            Source                   = 'folder_policy'
            Bucket                   = 'explicit_override'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$routeHeightBoundaries.Route1080pMaxHeight
            Route1440pBucketMinHeight = [int]$routeHeightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$routeHeightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$routeHeightBoundaries.Route4KMinHeight
        })
    } else {
        Resolve-MediaRouteResolutionBitrateSelection `
            -VideoHeight $VideoHeight `
            -IsTV:$IsTV `
            -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
            -Route1080pMaxVideoBitrateMbps $Route1080pMaxVideoBitrateMbps `
            -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
            -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
            -Route1440pMaxVideoBitrateMbps $Route1440pMaxVideoBitrateMbps `
            -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent `
            -Route4KMaxVideoBitrateMbps $Route4KMaxVideoBitrateMbps
    }
    $sizeSelection = Resolve-MediaRouteResolutionSizeSelection `
        -VideoHeight $VideoHeight `
        -IsTV:$IsTV `
        -MovieRoute1080pTargetSizeGB $MovieRoute1080pTargetSizeGB `
        -MovieRoute1440pTargetSizeGB $MovieRoute1440pTargetSizeGB `
        -MovieRoute4KTargetSizeGB $MovieRoute4KTargetSizeGB `
        -TVRoute1080pTargetSizeGB $TVRoute1080pTargetSizeGB `
        -TVRoute1440pTargetSizeGB $TVRoute1440pTargetSizeGB `
        -TVRoute4KTargetSizeGB $TVRoute4KTargetSizeGB `
        -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
        -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
        -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
        -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent
    $threshold = [double]$sizeSelection.TargetGB
    $routeMaxBitrate = [double]$bitrateSelection.CapMbps
    $maxBitrate = [double]$routeMaxBitrate
    $codec = Normalize-MediaRouteCodecName $VideoCodec
    $h264BitrateCapApplied = $false
    if ($AllowH264RemuxIfPlexCompatible -and $H264RemuxMaxBitrateMbps -gt 0 -and $codec -in @('h264','avc')) {
        $beforeH264Cap = [double]$maxBitrate
        $maxBitrate = [math]::Min([double]$maxBitrate, [double]$H264RemuxMaxBitrateMbps)
        $h264BitrateCapApplied = ($maxBitrate -ne $beforeH264Cap)
    }
    $mediaType = if ($IsTV) { 'tv' } else { 'movie' }
    $trace = [System.Collections.Generic.List[object]]::new()
    $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'routing_profile_selected' -Message ("routing profile {0}; route threshold mode {1}; size guard {2}" -f $routingProfileName, $routeThresholdModeName, $sizeGuardModeName) -Data @{ routing_profile = $routingProfileName; route_threshold_mode = $routeThresholdModeName; size_guard_mode = $sizeGuardModeName; route_size_source = [string]$sizeSelection.Source; route_size_bucket = [string]$sizeSelection.Bucket; route_size_movie_target_gb = [double]$sizeSelection.MovieTargetGB; route_size_tv_target_gb = [double]$sizeSelection.TVTargetGB; route_max_bitrate_mbps = [double]$routeMaxBitrate; effective_max_bitrate_mbps = [double]$maxBitrate; route_bitrate_source = [string]$bitrateSelection.Source; route_bitrate_bucket = [string]$bitrateSelection.Bucket; route_bitrate_bucket_height = [int]$bitrateSelection.Height; route_1080p_bucket_max_height = [int]$bitrateSelection.Route1080pBucketMaxHeight; route_1080p_upper_height_tolerance_percent = [double]$Route1080pUpperHeightTolerancePercent; route_1080p_max_video_bitrate_mbps = [double]$Route1080pMaxVideoBitrateMbps; route_1440p_bucket_min_height = [int]$bitrateSelection.Route1440pBucketMinHeight; route_1440p_bucket_max_height = [int]$bitrateSelection.Route1440pBucketMaxHeight; route_1440p_lower_height_tolerance_percent = [double]$Route1440pLowerHeightTolerancePercent; route_1440p_upper_height_tolerance_percent = [double]$Route1440pUpperHeightTolerancePercent; route_1440p_max_video_bitrate_mbps = [double]$Route1440pMaxVideoBitrateMbps; route_4k_lower_height_tolerance_percent = [double]$Route4KLowerHeightTolerancePercent; route_4k_bucket_min_height = [int]$bitrateSelection.Route4KBucketMinHeight; route_4k_max_video_bitrate_mbps = [double]$Route4KMaxVideoBitrateMbps; h264_plex_remux_enabled = [bool]$AllowH264RemuxIfPlexCompatible; h264_max_bitrate_mbps = [double]$H264RemuxMaxBitrateMbps; h264_max_height = [int]$H264RemuxMaxHeight; h264_bitrate_cap_applied = [bool]$h264BitrateCapApplied }))
    $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'size_evaluated' -Message ("source size {0:N2} GB; threshold {1:N2} GB" -f $sizeGB, $threshold) -Data @{ size_gb = $sizeGB; threshold_gb = $threshold; media_type = $mediaType; route_size_source = [string]$sizeSelection.Source; route_size_bucket = [string]$sizeSelection.Bucket; movie_target_gb = [double]$sizeSelection.MovieTargetGB; tv_target_gb = [double]$sizeSelection.TVTargetGB }))
    if ($duration -gt 0) {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'bitrate_estimated' -Message ("estimated source bitrate {0:N2} Mbps from duration {1:N1}s" -f $estimatedBitrate, $duration) -Data @{ bitrate_mbps = $estimatedBitrate; duration_seconds = $duration; max_bitrate_mbps = $maxBitrate }))
    }
    if ($VideoHeight -gt 0) {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'resolution_detected' -Message ("source video height {0}p" -f $VideoHeight) -Data @{ height = $VideoHeight }))
    }
    if (-not [string]::IsNullOrWhiteSpace([string]$VideoCodec)) {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'video_codec_detected' -Message ("source video codec '$((Normalize-MediaRouteCodecName $VideoCodec))'") -Data @{ codec = (Normalize-MediaRouteCodecName $VideoCodec) }))
    }
    $allowed = @($hints.allowed_video_codecs)
    $plexScore = Get-MediaRoutePlexCompatibilityScore -VideoCodec $codec -VideoHeight $VideoHeight -EstimatedBitrateMbps $estimatedBitrate -MaxBitrateMbps $maxBitrate -AllowedVideoCodecs $allowed -IsHDR:$IsHDR
    $effectivePlexStrictMode = [bool]$hints.plex_strict_mode -or ($routingProfileName -eq 'plex_direct_play')
    $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'plex_compatibility_scored' -Message ("Plex compatibility score {0:N0}/100" -f $plexScore) -Data @{ score = $plexScore; strict_mode = [bool]$effectivePlexStrictMode }))
    $sizeOverThreshold = ($sizeGB -gt $threshold)
    $bitrateThresholdEnabled = ($routeThresholdModeName -in @('compatibility_advisory','bitrate','size_or_bitrate'))
    $sizeThresholdEnabled = ($routeThresholdModeName -in @('compatibility_advisory','size','size_or_bitrate'))
    $hardSizeThresholdMode = ($routeThresholdModeName -in @('size','size_or_bitrate'))

    if ($hints.force_route -eq 'encode') {
        $reasonText = if ([string]::IsNullOrWhiteSpace([string]$hints.reason)) { 'folder policy forced encode' } else { "folder policy forced encode: $($hints.reason)" }
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'folder_policy_force_encode' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'folder_policy_force_encode' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }
    if ($hints.force_route -eq 'remux') {
        $reasonText = if ([string]::IsNullOrWhiteSpace([string]$hints.reason)) { 'folder policy forced remux' } else { "folder policy forced remux: $($hints.reason)" }
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'folder_policy_force_remux' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteRemuxName) -ReasonCode 'folder_policy_force_remux' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -RequiresCodecProbe:$true -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }

    if ($allowed.Count -gt 0 -and $codec -ne 'unknown' -and $allowed -notcontains $codec) {
        $reasonText = "codec '$codec' is outside folder-policy allowed codecs: $($allowed -join ', ')"
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'codec_outside_policy' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'codec_outside_policy' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }

    if ($effectivePlexStrictMode -and $plexScore -lt 90) {
        $reasonText = "Plex strict mode score $([math]::Round($plexScore,0))/100 is below 90"
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'plex_strict_score_below_threshold' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'plex_strict_score_below_threshold' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }

    if ($null -ne $hints.max_resolution_height -and $VideoHeight -gt [int]$hints.max_resolution_height) {
        $reasonText = "source height ${VideoHeight}p exceeds folder-policy maximum $($hints.max_resolution_height)p"
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'resolution_over_policy' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'resolution_over_policy' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }

    if ($duration -gt 0 -and $bitrateThresholdEnabled -and $estimatedBitrate -gt $maxBitrate) {
        $reasonText = "estimated source bitrate {0:N2} Mbps exceeds {1:N2} Mbps threshold" -f $estimatedBitrate, $maxBitrate
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'bitrate_over_threshold' -Message $reasonText))
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'bitrate_over_threshold' -Reason $reasonText -SizeGB $sizeGB -ThresholdGB $threshold -IsTV:$IsTV -SourceCodec $codec -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $SourceMediaProfile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $maxBitrate -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    } elseif ($duration -gt 0 -and -not $bitrateThresholdEnabled -and $estimatedBitrate -gt $maxBitrate) {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'bitrate_threshold_ignored' -Message ("estimated source bitrate {0:N2} Mbps exceeds {1:N2} Mbps threshold, but route threshold mode is {2}" -f $estimatedBitrate, $maxBitrate, $routeThresholdModeName) -Data @{ bitrate_mbps = $estimatedBitrate; threshold_mbps = $maxBitrate; route_threshold_mode = $routeThresholdModeName }))
    }

    $h264PlexCompatible = Test-MediaRouteH264PlexCompatible `
        -CodecName $codec `
        -EstimatedBitrateMbps $estimatedBitrate `
        -MaxBitrateMbps $maxBitrate `
        -VideoHeight $VideoHeight `
        -PlexCompatibilityScore $plexScore `
        -AllowH264RemuxIfPlexCompatible:$AllowH264RemuxIfPlexCompatible `
        -H264RemuxMaxBitrateMbps $H264RemuxMaxBitrateMbps `
        -H264RemuxMaxHeight $H264RemuxMaxHeight
    $sizeThresholdBlocksEarlyCopy = $sizeOverThreshold -and (
        $hardSizeThresholdMode -or
        ($routeThresholdModeName -eq 'compatibility_advisory' -and $routingProfileName -eq 'archive_shrink')
    )
    if ($h264PlexCompatible -and -not $sizeThresholdBlocksEarlyCopy) {
        $reasonText = "H.264 source is Plex-compatible ({0:N2} Mbps, {1}p); copying video and applying container/subtitle policy" -f $estimatedBitrate, $VideoHeight
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'plex_compatible_h264_remux' -Message $reasonText -Data @{ codec = $codec; bitrate_mbps = $estimatedBitrate; height = $VideoHeight; max_bitrate_mbps = [double]$H264RemuxMaxBitrateMbps; max_height = [int]$H264RemuxMaxHeight }))
        return New-MediaRoutePlan `
            -Route (Get-MediaRouteRemuxName) `
            -ReasonCode 'plex_compatible_h264_remux' `
            -Reason $reasonText `
            -SizeGB $sizeGB `
            -ThresholdGB $threshold `
            -IsTV:$IsTV `
            -SourceCodec $codec `
            -RequiresCodecProbe:$true `
            -DecisionTrace @($trace) `
            -RouteHints $hints `
            -SourceMediaProfile $SourceMediaProfile `
            -EstimatedBitrateMbps $estimatedBitrate `
            -BitrateThresholdMbps $maxBitrate `
            -PlexCompatibilityScore $plexScore `
            -RoutingProfile $routingProfileName `
            -SizeGuardMode $sizeGuardModeName
    }

    if ($sizeOverThreshold -and $sizeThresholdEnabled) {
        $sizeThresholdForcesEncode = if ($hardSizeThresholdMode) {
            $true
        } else {
            (($routingProfileName -eq 'archive_shrink') -or ($sizeGuardModeName -eq 'strict')) -and ($routingProfileName -ne 'manual')
        }
        $minimumCopyScore = if ($routingProfileName -eq 'plex_direct_play') { 90.0 } else { 85.0 }
        $copyCandidate = Test-MediaRoutePlexCopyCandidate -CodecName $codec -VideoHeight $VideoHeight -EstimatedBitrateMbps $estimatedBitrate -MaxBitrateMbps $maxBitrate -PlexCompatibilityScore $plexScore -MinimumScore $minimumCopyScore
        if ($copyCandidate -and -not $sizeThresholdForcesEncode) {
            $reasonText = "source size {0:N2} GB exceeds {1:N2} GB threshold, but codec/bitrate are Plex-compatible; size threshold is advisory under {2}" -f $sizeGB, $threshold, $routingProfileName
            $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'plex_compatible_size_advisory' -Message $reasonText -Data @{ size_gb = $sizeGB; threshold_gb = $threshold; routing_profile = $routingProfileName; size_guard_mode = $sizeGuardModeName }))
            return New-MediaRoutePlan `
                -Route (Get-MediaRouteRemuxName) `
                -ReasonCode 'plex_compatible_size_advisory' `
                -Reason $reasonText `
                -SizeGB $sizeGB `
                -ThresholdGB $threshold `
                -IsTV:$IsTV `
                -SourceCodec $codec `
                -RequiresCodecProbe:$true `
                -DecisionTrace @($trace) `
                -RouteHints $hints `
                -SourceMediaProfile $SourceMediaProfile `
                -EstimatedBitrateMbps $estimatedBitrate `
                -BitrateThresholdMbps $maxBitrate `
                -PlexCompatibilityScore $plexScore `
                -RoutingProfile $routingProfileName `
                -SizeGuardMode $sizeGuardModeName
        }
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'size_over_threshold' -Message ("source size {0:N2} GB exceeds {1:N2} GB threshold" -f $sizeGB, $threshold)))
        return New-MediaRoutePlan `
            -Route (Get-MediaRouteEncodeName) `
            -ReasonCode 'size_over_threshold' `
            -Reason ("source size {0:N2} GB exceeds {1:N2} GB threshold" -f $sizeGB, $threshold) `
            -SizeGB $sizeGB `
            -ThresholdGB $threshold `
            -IsTV:$IsTV `
            -SourceCodec $codec `
            -DecisionTrace @($trace) `
            -RouteHints $hints `
            -SourceMediaProfile $SourceMediaProfile `
            -EstimatedBitrateMbps $estimatedBitrate `
            -BitrateThresholdMbps $maxBitrate `
            -PlexCompatibilityScore $plexScore `
            -RoutingProfile $routingProfileName `
            -SizeGuardMode $sizeGuardModeName
    }

    $finalRouteReasonCode = 'size_within_threshold'
    $finalRouteReason = "source size {0:N2} GB is within {1:N2} GB threshold; codec probe still required" -f $sizeGB, $threshold
    if ($sizeOverThreshold -and -not $sizeThresholdEnabled) {
        $finalRouteReasonCode = 'size_threshold_ignored'
        $finalRouteReason = "source size {0:N2} GB exceeds {1:N2} GB threshold, but route threshold mode is {2}; codec probe still required" -f $sizeGB, $threshold, $routeThresholdModeName
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code $finalRouteReasonCode -Message $finalRouteReason -Data @{ size_gb = $sizeGB; threshold_gb = $threshold; route_threshold_mode = $routeThresholdModeName }))
    } else {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code $finalRouteReasonCode -Message $finalRouteReason))
    }
    if ($hints.prefer_route -eq 'encode') {
        $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'folder_policy_prefer_encode' -Message 'folder policy prefers encode; size/bitrate did not force remux'))
        return New-MediaRoutePlan `
            -Route (Get-MediaRouteEncodeName) `
            -ReasonCode 'folder_policy_prefer_encode' `
            -Reason 'folder policy prefers encode and no stronger remux rule applies' `
            -SizeGB $sizeGB `
            -ThresholdGB $threshold `
            -IsTV:$IsTV `
            -SourceCodec $codec `
            -DecisionTrace @($trace) `
            -RouteHints $hints `
            -SourceMediaProfile $SourceMediaProfile `
            -EstimatedBitrateMbps $estimatedBitrate `
            -BitrateThresholdMbps $maxBitrate `
            -PlexCompatibilityScore $plexScore `
            -RoutingProfile $routingProfileName `
            -SizeGuardMode $sizeGuardModeName
    }

    return New-MediaRoutePlan `
        -Route (Get-MediaRouteRemuxName) `
        -ReasonCode $finalRouteReasonCode `
        -Reason $finalRouteReason `
        -SizeGB $sizeGB `
        -ThresholdGB $threshold `
        -IsTV:$IsTV `
        -SourceCodec $codec `
        -RequiresCodecProbe:$true `
        -DecisionTrace @($trace) `
        -RouteHints $hints `
        -SourceMediaProfile $SourceMediaProfile `
        -EstimatedBitrateMbps $estimatedBitrate `
        -BitrateThresholdMbps $maxBitrate `
        -PlexCompatibilityScore $plexScore `
        -RoutingProfile $routingProfileName `
        -SizeGuardMode $sizeGuardModeName
}

function Resolve-InitialMediaRoutePlan {
    param(
        [Parameter(Mandatory)] [System.IO.FileInfo] $File,
        [bool] $IsTV = $false,
        $MediaProfile = $null,
        $RouteHints = $null
    )

    $duration = [double](Get-MediaRouteProfileValue -Profile $MediaProfile -Name 'duration_seconds' -Default 0)
    $codec = [string](Get-MediaRouteProfileValue -Profile $MediaProfile -Name 'video_codec' -Default '')
    $height = [int](Get-MediaRouteProfileValue -Profile $MediaProfile -Name 'height' -Default 0)
    $isHdr = [bool](Get-MediaRouteProfileValue -Profile $MediaProfile -Name 'is_hdr' -Default $false)
    $allowH264Remux = if (Get-Variable -Name AllowH264RemuxIfPlexCompatible -Scope Script -ErrorAction SilentlyContinue) { [bool]$script:AllowH264RemuxIfPlexCompatible } else { $true }
    $h264MaxBitrate = if (Get-Variable -Name H264RemuxMaxBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:H264RemuxMaxBitrateMbps } else { 35.0 }
    $h264MaxHeight = if (Get-Variable -Name H264RemuxMaxHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:H264RemuxMaxHeight } else { 1080 }
    $movieRoute1080pTargetSize = if (Get-Variable -Name MovieRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute1080pTargetSizeGB } else { 8.0 }
    $movieRoute1440pTargetSize = if (Get-Variable -Name MovieRoute1440pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute1440pTargetSizeGB } else { 8.0 }
    $movieRoute4kTargetSize = if (Get-Variable -Name MovieRoute4KTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute4KTargetSizeGB } else { 8.0 }
    $tvRoute1080pTargetSize = if (Get-Variable -Name TVRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute1080pTargetSizeGB } else { 3.0 }
    $tvRoute1440pTargetSize = if (Get-Variable -Name TVRoute1440pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute1440pTargetSizeGB } else { 3.0 }
    $tvRoute4kTargetSize = if (Get-Variable -Name TVRoute4KTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute4KTargetSizeGB } else { 3.0 }
    $route1080pUpperTolerance = if (Get-Variable -Name Route1080pUpperHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pUpperHeightTolerancePercent } else { 11.111111 }
    $route1080pMaxBitrate = if (Get-Variable -Name Route1080pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pMaxVideoBitrateMbps } else { 20.0 }
    $route1440pLowerTolerance = if (Get-Variable -Name Route1440pLowerHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pLowerHeightTolerancePercent } else { 16.597222 }
    $route1440pUpperTolerance = if (Get-Variable -Name Route1440pUpperHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pUpperHeightTolerancePercent } else { 24.930556 }
    $route1440pMaxBitrate = if (Get-Variable -Name Route1440pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pMaxVideoBitrateMbps } else { 35.0 }
    $route4kLowerTolerance = if (Get-Variable -Name Route4KLowerHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KLowerHeightTolerancePercent } else { 16.666667 }
    $route4kMaxBitrate = if (Get-Variable -Name Route4KMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KMaxVideoBitrateMbps } else { 35.0 }
    $routeThresholdMode = if (Get-Variable -Name RouteThresholdMode -Scope Script -ErrorAction SilentlyContinue) { [string]$script:RouteThresholdMode } else { 'compatibility_advisory' }

    return Resolve-MediaRouteBySize `
        -FileSizeBytes ([long]$File.Length) `
        -IsTV:$IsTV `
        -MovieRoute1080pTargetSizeGB $movieRoute1080pTargetSize `
        -MovieRoute1440pTargetSizeGB $movieRoute1440pTargetSize `
        -MovieRoute4KTargetSizeGB $movieRoute4kTargetSize `
        -TVRoute1080pTargetSizeGB $tvRoute1080pTargetSize `
        -TVRoute1440pTargetSizeGB $tvRoute1440pTargetSize `
        -TVRoute4KTargetSizeGB $tvRoute4kTargetSize `
        -DurationSeconds $duration `
        -VideoCodec $codec `
        -VideoHeight $height `
        -IsHDR:$isHdr `
        -RouteHints $RouteHints `
        -SourceMediaProfile $MediaProfile `
        -RoutingProfile ([string]$script:RoutingProfile) `
        -RouteThresholdMode $routeThresholdMode `
        -SizeGuardMode ([string]$script:SizeGuardMode) `
        -AllowH264RemuxIfPlexCompatible:$allowH264Remux `
        -H264RemuxMaxBitrateMbps $h264MaxBitrate `
        -H264RemuxMaxHeight $h264MaxHeight `
        -Route1080pUpperHeightTolerancePercent $route1080pUpperTolerance `
        -Route1080pMaxVideoBitrateMbps $route1080pMaxBitrate `
        -Route1440pLowerHeightTolerancePercent $route1440pLowerTolerance `
        -Route1440pUpperHeightTolerancePercent $route1440pUpperTolerance `
        -Route1440pMaxVideoBitrateMbps $route1440pMaxBitrate `
        -Route4KLowerHeightTolerancePercent $route4kLowerTolerance `
        -Route4KMaxVideoBitrateMbps $route4kMaxBitrate
}
