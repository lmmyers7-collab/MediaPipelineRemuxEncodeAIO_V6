# ==============================================================================
# ops\pipeline\engine\decide\profile_selection.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\decide\routing.ps1. Keep public function names stable;
# routing.ps1 dot-sources this file as part of the route policy export surface.
# ==============================================================================

function ConvertTo-MediaRouteHintMap {
    param($Hints)

    $map = [ordered]@{
        routing_profile = ''
        route_threshold_mode = ''
        size_guard_mode = ''
        allow_h264_remux_if_plex_compatible = $null
        h264_remux_max_bitrate_mbps = $null
        h264_remux_max_height = $null
        force_route = 'auto'
        prefer_route = 'auto'
        max_video_bitrate_mbps = $null
        max_resolution_height = $null
        allowed_video_codecs = @()
        plex_strict_mode = $false
        allow_unsafe_forced_remux = $false
        reason = ''
    }
    if (-not $Hints) { return $map }

    foreach ($key in @($map.Keys)) {
        $value = $null
        if ($Hints -is [System.Collections.IDictionary] -and $Hints.Contains($key)) {
            $value = $Hints[$key]
        } else {
            $prop = $Hints.PSObject.Properties[$key]
            if ($prop) { $value = $prop.Value }
        }
        if ($null -eq $value) { continue }
        switch ($key) {
            'force_route' {
                $route = ([string]$value).Trim().ToLowerInvariant()
                if ($route -in @('auto','remux','encode')) { $map[$key] = $route }
            }
            'prefer_route' {
                $route = ([string]$value).Trim().ToLowerInvariant()
                if ($route -in @('auto','remux','encode')) { $map[$key] = $route }
            }
            'routing_profile' {
                $profile = ([string]$value).Trim().ToLowerInvariant()
                if ($profile -in @('plex_direct_stream','plex_direct_play','archive_shrink','archive_quality','manual')) { $map[$key] = $profile }
            }
            'route_threshold_mode' {
                $mode = ([string]$value).Trim().ToLowerInvariant()
                if ($mode -in @('compatibility_advisory','size','bitrate','size_or_bitrate')) { $map[$key] = $mode }
            }
            'size_guard_mode' {
                $mode = ([string]$value).Trim().ToLowerInvariant()
                if ($mode -in @('advisory','strict','fallback_remux','off')) { $map[$key] = $mode }
            }
            'allow_h264_remux_if_plex_compatible' {
                if ($value -is [bool]) { $map[$key] = [bool]$value }
                else { $map[$key] = (([string]$value).Trim() -match '^(?i:true|1|yes|y|on)$') }
            }
            'h264_remux_max_bitrate_mbps' {
                try {
                    $number = [double]$value
                    if ($number -gt 0) { $map[$key] = $number }
                } catch {}
            }
            'h264_remux_max_height' {
                try {
                    $height = [int]$value
                    if ($height -gt 0) { $map[$key] = $height }
                } catch {}
            }
            'max_video_bitrate_mbps' {
                try {
                    $number = [double]$value
                    if ($number -gt 0) { $map[$key] = $number }
                } catch {}
            }
            'max_resolution_height' {
                try {
                    $height = [int]$value
                    if ($height -gt 0) { $map[$key] = $height }
                } catch {}
            }
            'allowed_video_codecs' {
                $map[$key] = @(
                    @($value) |
                        ForEach-Object { Normalize-MediaRouteCodecName ([string]$_) } |
                        Where-Object { $_ -ne 'unknown' } |
                        Select-Object -Unique
                )
            }
            'plex_strict_mode' {
                if ($value -is [bool]) { $map[$key] = [bool]$value }
                else { $map[$key] = (([string]$value).Trim() -match '^(?i:true|1|yes|y|on)$') }
            }
            'allow_unsafe_forced_remux' {
                if ($value -is [bool]) { $map[$key] = [bool]$value }
                else { $map[$key] = (([string]$value).Trim() -match '^(?i:true|1|yes|y|on)$') }
            }
            'reason' {
                $map[$key] = [string]$value
            }
        }
    }
    return $map
}

function Get-ActiveMediaRouteHints {
    if (-not $script:ActiveOverrides) { return (ConvertTo-MediaRouteHintMap $null) }
    $hints = [ordered]@{}
    foreach ($entry in @(
        @{ Key = 'RouteForce'; Name = 'force_route' },
        @{ Key = 'RoutePrefer'; Name = 'prefer_route' },
        @{ Key = 'RoutingProfile'; Name = 'routing_profile' },
        @{ Key = 'RouteThresholdMode'; Name = 'route_threshold_mode' },
        @{ Key = 'SizeGuardMode'; Name = 'size_guard_mode' },
        @{ Key = 'AllowH264RemuxIfPlexCompatible'; Name = 'allow_h264_remux_if_plex_compatible' },
        @{ Key = 'H264RemuxMaxBitrateMbps'; Name = 'h264_remux_max_bitrate_mbps' },
        @{ Key = 'H264RemuxMaxHeight'; Name = 'h264_remux_max_height' },
        @{ Key = 'RouteMaxVideoBitrateMbps'; Name = 'max_video_bitrate_mbps' },
        @{ Key = 'RouteMaxResolutionHeight'; Name = 'max_resolution_height' },
        @{ Key = 'RouteAllowedVideoCodecs'; Name = 'allowed_video_codecs' },
        @{ Key = 'RoutePlexStrictMode'; Name = 'plex_strict_mode' },
        @{ Key = 'RouteAllowUnsafeForcedRemux'; Name = 'allow_unsafe_forced_remux' },
        @{ Key = 'RoutePolicyReason'; Name = 'reason' }
    )) {
        $overrideKey = [string]$entry['Key']
        $hintName = [string]$entry['Name']
        if ($script:ActiveOverrides.ContainsKey($overrideKey)) {
            $hints[$hintName] = $script:ActiveOverrides[$overrideKey]
        }
    }
    return (ConvertTo-MediaRouteHintMap $hints)
}

function Resolve-MediaRouteRoutingProfileName {
    param([string] $RoutingProfile = '')

    $profile = if (-not [string]::IsNullOrWhiteSpace($RoutingProfile)) {
        ([string]$RoutingProfile).Trim().ToLowerInvariant()
    } elseif (Get-Variable -Name RoutingProfile -Scope Script -ErrorAction SilentlyContinue) {
        ([string]$script:RoutingProfile).Trim().ToLowerInvariant()
    } else {
        'plex_direct_stream'
    }
    if ($profile -in @('plex_direct_stream','plex_direct_play','archive_shrink','archive_quality','manual')) {
        return $profile
    }
    return 'plex_direct_stream'
}

function Resolve-MediaRouteThresholdModeName {
    param([string] $RouteThresholdMode = '')

    $mode = if (-not [string]::IsNullOrWhiteSpace($RouteThresholdMode)) {
        ([string]$RouteThresholdMode).Trim().ToLowerInvariant()
    } elseif (Get-Variable -Name RouteThresholdMode -Scope Script -ErrorAction SilentlyContinue) {
        ([string]$script:RouteThresholdMode).Trim().ToLowerInvariant()
    } else {
        'compatibility_advisory'
    }
    if ($mode -in @('compatibility_advisory','size','bitrate','size_or_bitrate')) {
        return $mode
    }
    return 'compatibility_advisory'
}

function Resolve-MediaRouteSizeGuardModeName {
    param([string] $SizeGuardMode = '')

    $mode = if (-not [string]::IsNullOrWhiteSpace($SizeGuardMode)) {
        ([string]$SizeGuardMode).Trim().ToLowerInvariant()
    } elseif (Get-Variable -Name SizeGuardMode -Scope Script -ErrorAction SilentlyContinue) {
        ([string]$script:SizeGuardMode).Trim().ToLowerInvariant()
    } else {
        'advisory'
    }
    if ($mode -in @('advisory','strict','fallback_remux','off')) { return $mode }
    return 'advisory'
}

function Get-MediaRouteProfileValue {
    param(
        $Profile,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if (-not $Profile) { return $Default }
    if ($Profile -is [System.Collections.IDictionary] -and $Profile.Contains($Name)) { return $Profile[$Name] }
    $prop = $Profile.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Get-MediaRouteEvidenceValue {
    param(
        $Evidence,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if ($null -eq $Evidence) { return $Default }
    if ($Evidence -is [System.Collections.IDictionary] -and $Evidence.Contains($Name)) { return $Evidence[$Name] }
    $prop = $Evidence.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function ConvertTo-MediaRouteEvidenceDouble {
    param(
        $Value,
        [double] $Default = 0.0
    )

    if ($null -eq $Value) { return $Default }
    if ([string]::IsNullOrWhiteSpace([string]$Value)) { return $Default }
    try { return [double]$Value } catch { return $Default }
}

function ConvertTo-MediaRouteEvidenceBool {
    param(
        $Value,
        [bool] $Default = $false
    )

    if ($null -eq $Value) { return $Default }
    if ($Value -is [bool]) { return [bool]$Value }
    $text = ([string]$Value).Trim().ToLowerInvariant()
    if ($text -in @('true','1','yes')) { return $true }
    if ($text -in @('false','0','no','')) { return $false }
    try { return [bool]$Value } catch { return $Default }
}

function Get-MediaRouteDecisionTraceEntryByCode {
    param(
        $Metadata,
        [Parameter(Mandatory)] [string[]] $Codes
    )

    $trace = @(Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'decision_trace' -Default @())
    foreach ($entry in $trace) {
        $code = [string](Get-MediaRouteEvidenceValue -Evidence $entry -Name 'code' -Default '')
        if ($Codes -contains $code) { return $entry }
    }
    return $null
}

function New-MediaRouteExplanation {
    param($Metadata)

    if (-not $Metadata) { return $null }

    $route = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'route' -Default '')
    $routeReasonCode = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'route_reason_code' -Default '')
    $routeReason = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'route_reason' -Default '')
    $sourceCodec = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'source_codec' -Default '')
    $routingProfile = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'routing_profile' -Default '')
    $routeThresholdMode = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'route_threshold_mode' -Default '')
    $sizeGuardMode = [string](Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'size_guard_mode' -Default '')
    $sizeGB = ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'size_gb' -Default 0.0)
    $thresholdGB = ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'threshold_gb' -Default 0.0)
    $estimatedBitrateMbps = ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'estimated_bitrate_mbps' -Default 0.0)
    $bitrateThresholdMbps = ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'bitrate_threshold_mbps' -Default 0.0)
    $sizeOverThreshold = ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'size_over_threshold' -Default $false)
    $bitrateOverThreshold = ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'bitrate_over_threshold' -Default $false)
    $plexScore = ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'plex_compatibility_score' -Default 100.0) -Default 100.0
    $sizePolicy = Get-MediaRouteEvidenceValue -Evidence $Metadata -Name 'size_policy' -Default $null

    $sizePolicyMode = if ($sizePolicy) {
        [string](Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'mode' -Default $sizeGuardMode)
    } else {
        $sizeGuardMode
    }
    $sizePolicyExceeded = if ($sizePolicy) {
        ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'exceeded' -Default $false)
    } else {
        $false
    }
    $sizePolicyFallbackEligible = if ($sizePolicy) {
        ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'fallback_remux_eligible' -Default $false)
    } else {
        $false
    }
    $sizePolicyShouldFallback = if ($sizePolicy) {
        ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'should_fallback_remux' -Default $false)
    } else {
        $false
    }
    $sizePolicyForcedOverride = if ($sizePolicy) {
        ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'forced_route_override' -Default $false)
    } else {
        $false
    }
    $sizePolicyMessage = if ($sizePolicy) {
        [string](Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'message' -Default '')
    } else {
        ''
    }

    $fallbackTrace = Get-MediaRouteDecisionTraceEntryByCode -Metadata $Metadata -Codes @('oversized_encode_remux_fallback')
    $codecAcceptedTrace = Get-MediaRouteDecisionTraceEntryByCode -Metadata $Metadata -Codes @('codec_remux_safe','codec_allowed_by_routing_profile','forced_remux_codec_safe')
    $codecBlockedTrace = Get-MediaRouteDecisionTraceEntryByCode -Metadata $Metadata -Codes @('codec_not_remux_safe','forced_remux_rejected_unsafe_codec')
    $fallbackAccepted = ($null -ne $fallbackTrace -or $routeReasonCode -eq 'oversized_encode_remux_fallback')
    $fallbackAttempted = ($fallbackAccepted -or $sizePolicyShouldFallback)

    $fallbackBlockReasonCode = ''
    $fallbackBlockReason = ''
    if ($sizePolicyExceeded -and $sizePolicyMode -ne 'fallback_remux') {
        $fallbackBlockReasonCode = 'size_guard_mode_not_fallback_remux'
        $fallbackBlockReason = "SizeGuardMode '$sizePolicyMode' records the oversize result without attempting remux fallback."
    } elseif ($sizePolicyForcedOverride) {
        $fallbackBlockReasonCode = 'forced_route_override'
        $fallbackBlockReason = 'Fallback remux was not attempted because the encode route was explicitly forced.'
    } elseif ($sizePolicyExceeded -and -not $sizePolicyFallbackEligible) {
        $fallbackBlockReasonCode = 'route_reason_not_fallback_remux_eligible'
        $fallbackBlockReason = 'Fallback remux was not attempted because the encode reason is not an automatic size or bitrate threshold decision.'
    } elseif ($codecBlockedTrace) {
        $fallbackBlockReasonCode = [string](Get-MediaRouteEvidenceValue -Evidence $codecBlockedTrace -Name 'code' -Default '')
        $fallbackBlockReason = [string](Get-MediaRouteEvidenceValue -Evidence $codecBlockedTrace -Name 'message' -Default '')
    }

    $codecGateCode = ''
    $codecGateReason = ''
    if ($codecAcceptedTrace) {
        $codecGateCode = [string](Get-MediaRouteEvidenceValue -Evidence $codecAcceptedTrace -Name 'code' -Default '')
        $codecGateReason = [string](Get-MediaRouteEvidenceValue -Evidence $codecAcceptedTrace -Name 'message' -Default '')
    } elseif ($codecBlockedTrace) {
        $codecGateCode = [string](Get-MediaRouteEvidenceValue -Evidence $codecBlockedTrace -Name 'code' -Default '')
        $codecGateReason = [string](Get-MediaRouteEvidenceValue -Evidence $codecBlockedTrace -Name 'message' -Default '')
    }

    $decisionSummary = @()
    if (-not [string]::IsNullOrWhiteSpace($routeReasonCode) -or -not [string]::IsNullOrWhiteSpace($routeReason)) {
        $decisionSummary += ("route={0}; reason_code={1}; reason={2}" -f $route, $routeReasonCode, $routeReason)
    }
    if ($sizeOverThreshold -or $bitrateOverThreshold) {
        $decisionSummary += ("thresholds: size_over={0}; bitrate_over={1}; size={2:N2}GB/{3:N2}GB; bitrate={4:N2}Mbps/{5:N2}Mbps" -f $sizeOverThreshold, $bitrateOverThreshold, $sizeGB, $thresholdGB, $estimatedBitrateMbps, $bitrateThresholdMbps)
    }
    if ($sizePolicy) {
        $decisionSummary += ("size_guard={0}; exceeded={1}; fallback_eligible={2}; should_fallback_remux={3}" -f $sizePolicyMode, $sizePolicyExceeded, $sizePolicyFallbackEligible, $sizePolicyShouldFallback)
    }
    if ($fallbackAccepted) {
        $decisionSummary += 'remux fallback accepted after oversized encode; direct-copy size and bitrate caps were bypassed for this fallback'
    } elseif (-not [string]::IsNullOrWhiteSpace($fallbackBlockReasonCode)) {
        $decisionSummary += ("remux fallback not used: {0}" -f $fallbackBlockReasonCode)
    }

    $operatorNotes = @()
    if ($sizePolicyExceeded -and $sizePolicyMode -eq 'advisory') {
        $operatorNotes += 'SizeGuardMode advisory warns and publishes; fallback remux is only attempted when SizeGuardMode is fallback_remux.'
    } elseif ($sizePolicyExceeded -and $sizePolicyMode -eq 'strict') {
        $operatorNotes += 'SizeGuardMode strict rejects oversized encodes instead of attempting remux fallback.'
    }
    if ($fallbackAccepted) {
        $operatorNotes += 'The remux fallback is publishable only because the codec/container policy accepted direct stream copy.'
    } elseif ($fallbackBlockReasonCode -eq 'codec_not_remux_safe' -or $fallbackBlockReasonCode -eq 'forced_remux_rejected_unsafe_codec') {
        $operatorNotes += 'Adjust RemuxSafeVideoCodecs only after confirming this codec is acceptable for direct-copy output in this library.'
    }

    return [pscustomobject][ordered]@{
        schema_version = 'route_explanation.v1'
        route = $route
        route_reason_code = $routeReasonCode
        route_reason = $routeReason
        why_initial_route = [ordered]@{
            source_codec = $sourceCodec
            routing_profile = $routingProfile
            route_threshold_mode = $routeThresholdMode
            size_gb = $sizeGB
            threshold_gb = $thresholdGB
            estimated_bitrate_mbps = $estimatedBitrateMbps
            bitrate_threshold_mbps = $bitrateThresholdMbps
            size_over_threshold = $sizeOverThreshold
            bitrate_over_threshold = $bitrateOverThreshold
            plex_compatibility_score = $plexScore
        }
        size_guard = [ordered]@{
            mode = $sizePolicyMode
            policy_checked = [bool]($null -ne $sizePolicy)
            message = $sizePolicyMessage
            ratio = if ($sizePolicy) { ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'ratio' -Default 0.0) } else { 0.0 }
            limit_ratio = if ($sizePolicy) { ConvertTo-MediaRouteEvidenceDouble -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'limit_ratio' -Default 0.0) } else { 0.0 }
            exceeded = $sizePolicyExceeded
            enforced = if ($sizePolicy) { ConvertTo-MediaRouteEvidenceBool -Value (Get-MediaRouteEvidenceValue -Evidence $sizePolicy -Name 'enforced' -Default $false) } else { $false }
            fallback_remux_eligible = $sizePolicyFallbackEligible
            should_fallback_remux = $sizePolicyShouldFallback
            forced_route_override = $sizePolicyForcedOverride
        }
        remux_fallback = [ordered]@{
            eligible = $sizePolicyFallbackEligible
            attempted = $fallbackAttempted
            accepted = $fallbackAccepted
            blocked_reason_code = $fallbackBlockReasonCode
            blocked_reason = $fallbackBlockReason
            codec_gate_code = $codecGateCode
            codec_gate_reason = $codecGateReason
            direct_copy_size_bitrate_caps_bypassed = $fallbackAccepted
        }
        decision_summary = @($decisionSummary)
        operator_notes = @($operatorNotes)
    }
}

function Get-ActiveMediaRoutePlanMetadata {
    if (-not $script:CurrentRoutePlan) { return $null }
    $plan = $script:CurrentRoutePlan
    $metadata = [ordered]@{
        route                  = [string]$plan.Route
        route_reason_code      = [string]$plan.ReasonCode
        route_reason           = [string]$plan.Reason
        size_gb                = [double]$plan.SizeGB
        threshold_gb           = [double]$plan.ThresholdGB
        estimated_bitrate_mbps = if ($plan.PSObject.Properties['EstimatedBitrateMbps']) { [double]$plan.EstimatedBitrateMbps } else { 0.0 }
        bitrate_threshold_mbps = if ($plan.PSObject.Properties['BitrateThresholdMbps']) { [double]$plan.BitrateThresholdMbps } else { 0.0 }
        size_over_threshold    = if ($plan.PSObject.Properties['SizeOverThreshold']) { [bool]$plan.SizeOverThreshold } else { $false }
        bitrate_over_threshold = if ($plan.PSObject.Properties['BitrateOverThreshold']) { [bool]$plan.BitrateOverThreshold } else { $false }
        plex_compatibility_score = if ($plan.PSObject.Properties['PlexCompatibilityScore']) { [double]$plan.PlexCompatibilityScore } else { 100.0 }
        routing_profile       = if ($plan.PSObject.Properties['RoutingProfile']) { [string]$plan.RoutingProfile } else { Resolve-MediaRouteRoutingProfileName }
        route_threshold_mode  = if ($plan.PSObject.Properties['RouteThresholdMode']) { [string]$plan.RouteThresholdMode } else { Resolve-MediaRouteThresholdModeName }
        size_guard_mode       = if ($plan.PSObject.Properties['SizeGuardMode']) { [string]$plan.SizeGuardMode } else { Resolve-MediaRouteSizeGuardModeName }
        h264_plex_remux_policy = [ordered]@{
            enabled          = if (Get-Variable -Name AllowH264RemuxIfPlexCompatible -Scope Script -ErrorAction SilentlyContinue) { [bool]$script:AllowH264RemuxIfPlexCompatible } else { $true }
            max_bitrate_mbps = if (Get-Variable -Name H264RemuxMaxBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:H264RemuxMaxBitrateMbps } else { 35.0 }
            max_height       = if (Get-Variable -Name H264RemuxMaxHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:H264RemuxMaxHeight } else { 1080 }
        }
        resolution_bitrate_policy = [ordered]@{
            route_1080p_bucket_max_height     = if (Get-Variable -Name Route1080pBucketMaxHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:Route1080pBucketMaxHeight } else { 1200 }
            route_1080p_upper_height_tolerance_percent = if (Get-Variable -Name Route1080pUpperHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pUpperHeightTolerancePercent } else { 11.111111 }
            route_1080p_max_bitrate_mbps      = if (Get-Variable -Name Route1080pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pMaxVideoBitrateMbps } else { 20.0 }
            route_1440p_lower_height_tolerance_percent = if (Get-Variable -Name Route1440pLowerHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pLowerHeightTolerancePercent } else { 16.597222 }
            route_1440p_upper_height_tolerance_percent = if (Get-Variable -Name Route1440pUpperHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pUpperHeightTolerancePercent } else { 24.930556 }
            route_1440p_max_bitrate_mbps      = if (Get-Variable -Name Route1440pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1440pMaxVideoBitrateMbps } else { 35.0 }
            route_4k_lower_height_tolerance_percent = if (Get-Variable -Name Route4KLowerHeightTolerancePercent -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KLowerHeightTolerancePercent } else { 16.666667 }
            route_4k_bucket_min_height        = if (Get-Variable -Name Route4KBucketMinHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:Route4KBucketMinHeight } else { 1800 }
            route_4k_max_bitrate_mbps         = if (Get-Variable -Name Route4KMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KMaxVideoBitrateMbps } else { 35.0 }
            unknown_height_bucket             = '1080p'
            unknown_height_max_bitrate_mbps   = if (Get-Variable -Name Route1080pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pMaxVideoBitrateMbps } else { 20.0 }
        }
        resolution_size_policy = [ordered]@{
            movie_1080p_target_gb       = if (Get-Variable -Name MovieRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute1080pTargetSizeGB } else { 8.0 }
            movie_1440p_target_gb       = if (Get-Variable -Name MovieRoute1440pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute1440pTargetSizeGB } else { 8.0 }
            movie_4k_target_gb          = if (Get-Variable -Name MovieRoute4KTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute4KTargetSizeGB } else { 8.0 }
            tv_1080p_target_gb          = if (Get-Variable -Name TVRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute1080pTargetSizeGB } else { 3.0 }
            tv_1440p_target_gb          = if (Get-Variable -Name TVRoute1440pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute1440pTargetSizeGB } else { 3.0 }
            tv_4k_target_gb             = if (Get-Variable -Name TVRoute4KTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute4KTargetSizeGB } else { 3.0 }
            unknown_height_bucket       = '1080p'
            unknown_height_movie_target_gb = if (Get-Variable -Name MovieRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRoute1080pTargetSizeGB } else { 8.0 }
            unknown_height_tv_target_gb = if (Get-Variable -Name TVRoute1080pTargetSizeGB -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRoute1080pTargetSizeGB } else { 3.0 }
        }
        source_codec           = [string]$plan.SourceCodec
        requires_codec_probe   = [bool]$plan.RequiresCodecProbe
        fallback_from_remux    = [bool]$plan.FallbackFromRemux
        actions                = if ($plan.PSObject.Properties['Actions']) { $plan.Actions } else { New-MediaRouteActionSet -Route ([string]$plan.Route) }
        decision_trace         = if ($plan.PSObject.Properties['DecisionTrace']) { @($plan.DecisionTrace) } else { @() }
        route_hints            = if ($plan.PSObject.Properties['RouteHints']) { $plan.RouteHints } else { ConvertTo-MediaRouteHintMap $null }
        source_media_profile   = if ($plan.PSObject.Properties['SourceMediaProfile']) { $plan.SourceMediaProfile } else { $null }
    }
    if ($script:CurrentEncodeAttempts) {
        $metadata['encode_attempts'] = @($script:CurrentEncodeAttempts)
    } else {
        $metadata['encode_attempts'] = @()
    }
    if (Get-Variable -Name CurrentSizePolicyResult -Scope Script -ErrorAction SilentlyContinue) {
        if ($script:CurrentSizePolicyResult) {
            $metadata['size_policy'] = $script:CurrentSizePolicyResult
        }
    }
    $metadata['route_rule_outcomes'] = Get-MediaRouteRuleOutcomeEvidence -RoutePlan $plan
    if (Get-Variable -Name CurrentRuntimeEffectiveSettings -Scope Script -ErrorAction SilentlyContinue) {
        if ($script:CurrentRuntimeEffectiveSettings) {
            $metadata['runtime_effective_settings'] = $script:CurrentRuntimeEffectiveSettings
            $metadata['runtime_effective_settings_ref'] = 'runtime_effective_settings.v1'
            $metadata['library_effective_settings_ref'] = 'library-only'
            if (Get-Command -Name Get-MediaPipelineRuntimeLayerNames -ErrorAction SilentlyContinue) {
                $metadata['runtime_override_layers'] = Get-MediaPipelineRuntimeLayerNames -RuntimeEffectiveSettings $script:CurrentRuntimeEffectiveSettings
            }
        }
    }
    return $metadata
}

function Add-MediaRoutePlanMetadataToMap {
    param(
        [Parameter(Mandatory)] [System.Collections.IDictionary] $Map,
        $Metadata
    )

    if (-not $Metadata) { return $Map }
    $Map['route_plan'] = $Metadata
    $Map['route_actions'] = $Metadata.actions
    $Map['route_decision_trace'] = @($Metadata.decision_trace)
    $Map['route_hints'] = $Metadata.route_hints
    $Map['source_media_profile'] = $Metadata.source_media_profile
    $Map['encode_attempts'] = @($Metadata.encode_attempts)
    if ($Metadata.PSObject.Properties['size_policy']) {
        $Map['size_policy'] = $Metadata.size_policy
    }
    $routeExplanation = New-MediaRouteExplanation -Metadata $Metadata
    if ($routeExplanation) {
        $Map['route_explanation'] = $routeExplanation
    }
    return $Map
}
