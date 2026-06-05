# ==============================================================================
# ops\pipeline\engine\decide\codec_policy.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\decide\routing.ps1. Keep public function names stable;
# routing.ps1 dot-sources this file as part of the route policy export surface.
# ==============================================================================

function Normalize-MediaRouteCodecName {
    param([string]$CodecName)

    $text = ([string]$CodecName).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($text)) { return 'unknown' }
    return $text
}

function Test-MediaRouteCodecIsPlexCopyCandidate {
    param([string] $CodecName)

    $codec = Normalize-MediaRouteCodecName $CodecName
    return ($codec -in @('h264','avc','hevc','h265','h.265'))
}

function Test-MediaRouteH264PlexCompatible {
    param(
        [string] $CodecName,
        [double] $EstimatedBitrateMbps = 0,
        [double] $MaxBitrateMbps = 0,
        [int] $VideoHeight = 0,
        [double] $PlexCompatibilityScore = 100,
        [bool] $AllowH264RemuxIfPlexCompatible = $true,
        [double] $H264RemuxMaxBitrateMbps = 35.0,
        [int] $H264RemuxMaxHeight = 1080
    )

    if (-not $AllowH264RemuxIfPlexCompatible) { return $false }
    $codec = Normalize-MediaRouteCodecName $CodecName
    if ($codec -notin @('h264','avc')) { return $false }
    if ($PlexCompatibilityScore -lt 90) { return $false }
    if ($H264RemuxMaxHeight -gt 0 -and $VideoHeight -gt 0 -and $VideoHeight -gt $H264RemuxMaxHeight) { return $false }

    $effectiveMaxBitrate = 0.0
    foreach ($candidate in @([double]$MaxBitrateMbps, [double]$H264RemuxMaxBitrateMbps)) {
        if ($candidate -gt 0 -and ($effectiveMaxBitrate -le 0 -or $candidate -lt $effectiveMaxBitrate)) {
            $effectiveMaxBitrate = $candidate
        }
    }
    if ($effectiveMaxBitrate -gt 0 -and $EstimatedBitrateMbps -gt 0 -and $EstimatedBitrateMbps -gt $effectiveMaxBitrate) {
        return $false
    }
    return $true
}

function Test-MediaRoutePlexCopyCandidate {
    param(
        [string] $CodecName,
        [int] $VideoHeight = 0,
        [double] $EstimatedBitrateMbps = 0,
        [double] $MaxBitrateMbps = 0,
        [double] $PlexCompatibilityScore = 100,
        [double] $MinimumScore = 85
    )

    if (-not (Test-MediaRouteCodecIsPlexCopyCandidate -CodecName $CodecName)) { return $false }
    if ($PlexCompatibilityScore -lt $MinimumScore) { return $false }
    if ($VideoHeight -gt 2160) { return $false }
    if ($MaxBitrateMbps -gt 0 -and $EstimatedBitrateMbps -gt 0 -and $EstimatedBitrateMbps -gt $MaxBitrateMbps) { return $false }
    return $true
}

function Get-MediaRoutePlexCompatibilityScore {
    param(
        [string] $VideoCodec = '',
        [int] $VideoHeight = 0,
        [double] $EstimatedBitrateMbps = 0,
        [double] $MaxBitrateMbps = 0,
        [array] $AllowedVideoCodecs = @(),
        [bool] $IsHDR = $false
    )

    $score = 100
    $codec = Normalize-MediaRouteCodecName $VideoCodec
    $allowed = @(
        $AllowedVideoCodecs |
            ForEach-Object { Normalize-MediaRouteCodecName ([string]$_) } |
            Where-Object { $_ -ne 'unknown' } |
            Select-Object -Unique
    )
    if ($codec -eq 'unknown') {
        $score -= 15
    } elseif ($allowed.Count -gt 0 -and $allowed -notcontains $codec) {
        $score -= 40
    } elseif ($codec -notin @('h264','avc','hevc','h265','h.265')) {
        $score -= 20
    }
    if ($VideoHeight -gt 2160) { $score -= 25 }
    elseif ($VideoHeight -gt 1080) { $score -= 10 }
    if ($MaxBitrateMbps -gt 0 -and $EstimatedBitrateMbps -gt $MaxBitrateMbps) {
        $score -= [int]([math]::Min(35, [math]::Ceiling(($EstimatedBitrateMbps - $MaxBitrateMbps) / [math]::Max(1.0, $MaxBitrateMbps) * 35.0)))
    }
    if ($IsHDR) { $score -= 5 }
    return [double]([math]::Min(100, [math]::Max(0, $score)))
}

function Test-IsRemuxSafeVideoCodec {
    param(
        [string] $CodecName,
        [array] $SafeCodecs = @()
    )

    $codec = Normalize-MediaRouteCodecName $CodecName
    $safe = @(
        $SafeCodecs |
            ForEach-Object { Normalize-MediaRouteCodecName ([string]$_) } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
    )
    return ($safe -contains $codec)
}

function Resolve-RemuxCodecRoutePlan {
    param(
        [string] $SourceCodec,
        [array] $RemuxSafeVideoCodecs = @(),
        $BasePlan = $null
    )

    $codec = Normalize-MediaRouteCodecName $SourceCodec
    $baseTrace = if ($BasePlan -and $BasePlan.PSObject.Properties['DecisionTrace']) { @($BasePlan.DecisionTrace) } else { @() }
    $hints = if ($BasePlan -and $BasePlan.PSObject.Properties['RouteHints']) { $BasePlan.RouteHints } else { $null }
    $profile = if ($BasePlan -and $BasePlan.PSObject.Properties['SourceMediaProfile']) { $BasePlan.SourceMediaProfile } else { $null }
    $sizeGB = if ($BasePlan) { [double]$BasePlan.SizeGB } else { 0.0 }
    $thresholdGB = if ($BasePlan) { [double]$BasePlan.ThresholdGB } else { 0.0 }
    $estimatedBitrate = if ($BasePlan -and $BasePlan.PSObject.Properties['EstimatedBitrateMbps']) { [double]$BasePlan.EstimatedBitrateMbps } else { 0.0 }
    $bitrateThreshold = if ($BasePlan -and $BasePlan.PSObject.Properties['BitrateThresholdMbps']) { [double]$BasePlan.BitrateThresholdMbps } else { 0.0 }
    $sizeOverThreshold = if ($BasePlan -and $BasePlan.PSObject.Properties['SizeOverThreshold']) { [bool]$BasePlan.SizeOverThreshold } else { $false }
    $bitrateOverThreshold = if ($BasePlan -and $BasePlan.PSObject.Properties['BitrateOverThreshold']) { [bool]$BasePlan.BitrateOverThreshold } else { $false }
    $plexScore = if ($BasePlan -and $BasePlan.PSObject.Properties['PlexCompatibilityScore']) { [double]$BasePlan.PlexCompatibilityScore } else { 100.0 }
    $isTV = if ($BasePlan) { [bool]$BasePlan.IsTV } else { $false }
    $routingProfileName = if ($BasePlan -and $BasePlan.PSObject.Properties['RoutingProfile']) { Resolve-MediaRouteRoutingProfileName -RoutingProfile ([string]$BasePlan.RoutingProfile) } else { Resolve-MediaRouteRoutingProfileName }
    $sizeGuardModeName = if ($BasePlan -and $BasePlan.PSObject.Properties['SizeGuardMode']) { Resolve-MediaRouteSizeGuardModeName -SizeGuardMode ([string]$BasePlan.SizeGuardMode) } else { Resolve-MediaRouteSizeGuardModeName }
    $videoHeight = [int](Get-MediaRouteProfileValue -Profile $profile -Name 'height' -Default 0)

    if ($BasePlan -and [string]$BasePlan.ReasonCode -eq 'folder_policy_force_remux') {
        if (Test-IsRemuxSafeVideoCodec -CodecName $codec -SafeCodecs $RemuxSafeVideoCodecs) {
            $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'forced_remux_codec_safe' -Message "folder policy forced remux and codec '$codec' is remux-safe")
            return New-MediaRoutePlan -Route (Get-MediaRouteRemuxName) -ReasonCode 'folder_policy_force_remux' -Reason ([string]$BasePlan.Reason) -SourceCodec $codec -SizeGB $sizeGB -ThresholdGB $thresholdGB -IsTV:$isTV -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $profile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $bitrateThreshold -SizeOverThreshold:$sizeOverThreshold -BitrateOverThreshold:$bitrateOverThreshold -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
        }
        if ($hints -and [bool]$hints.allow_unsafe_forced_remux) {
            $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'unsafe_forced_remux_allowed' -Message "folder policy explicitly allowed unsafe forced remux; codec '$codec' will be attempted as stream copy")
            return New-MediaRoutePlan -Route (Get-MediaRouteRemuxName) -ReasonCode 'folder_policy_force_remux_unsafe' -Reason ([string]$BasePlan.Reason) -SourceCodec $codec -SizeGB $sizeGB -ThresholdGB $thresholdGB -IsTV:$isTV -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $profile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $bitrateThreshold -SizeOverThreshold:$sizeOverThreshold -BitrateOverThreshold:$bitrateOverThreshold -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
        }
        $reasonText = "folder policy forced remux, but codec '$codec' is not remux-safe; encoding instead"
        $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'forced_remux_rejected_unsafe_codec' -Message $reasonText)
        return New-MediaRoutePlan -Route (Get-MediaRouteEncodeName) -ReasonCode 'forced_remux_rejected_unsafe_codec' -Reason $reasonText -SourceCodec $codec -FallbackFromRemux:$true -SizeGB $sizeGB -ThresholdGB $thresholdGB -IsTV:$isTV -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $profile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $bitrateThreshold -SizeOverThreshold:$sizeOverThreshold -BitrateOverThreshold:$bitrateOverThreshold -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
    }

    if ($BasePlan -and (([string]$BasePlan.ReasonCode) -in @('plex_compatible_h264_remux','plex_compatible_size_advisory'))) {
        $minimumCopyScore = if ($routingProfileName -eq 'plex_direct_play') { 90.0 } else { 85.0 }
        if (Test-MediaRoutePlexCopyCandidate -CodecName $codec -VideoHeight $videoHeight -EstimatedBitrateMbps $estimatedBitrate -MaxBitrateMbps 0 -PlexCompatibilityScore $plexScore -MinimumScore $minimumCopyScore) {
            $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'codec_allowed_by_routing_profile' -Message "codec '$codec' allowed by routing profile '$routingProfileName' for stream copy")
            return New-MediaRoutePlan -Route (Get-MediaRouteRemuxName) -ReasonCode ([string]$BasePlan.ReasonCode) -Reason ([string]$BasePlan.Reason) -SourceCodec $codec -SizeGB $sizeGB -ThresholdGB $thresholdGB -IsTV:$isTV -DecisionTrace @($trace) -RouteHints $hints -SourceMediaProfile $profile -EstimatedBitrateMbps $estimatedBitrate -BitrateThresholdMbps $bitrateThreshold -SizeOverThreshold:$sizeOverThreshold -BitrateOverThreshold:$bitrateOverThreshold -PlexCompatibilityScore $plexScore -RoutingProfile $routingProfileName -SizeGuardMode $sizeGuardModeName
        }
    }

    if (Test-IsRemuxSafeVideoCodec -CodecName $codec -SafeCodecs $RemuxSafeVideoCodecs) {
        $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'codec_remux_safe' -Message "codec '$codec' is remux-safe")
        return New-MediaRoutePlan `
            -Route (Get-MediaRouteRemuxName) `
            -ReasonCode 'codec_remux_safe' `
            -Reason "codec '$codec' is remux-safe" `
            -SourceCodec $codec `
            -SizeGB $sizeGB `
            -ThresholdGB $thresholdGB `
            -IsTV:$isTV `
            -DecisionTrace @($trace) `
            -RouteHints $hints `
            -SourceMediaProfile $profile `
            -EstimatedBitrateMbps $estimatedBitrate `
            -BitrateThresholdMbps $bitrateThreshold `
            -SizeOverThreshold:$sizeOverThreshold `
            -BitrateOverThreshold:$bitrateOverThreshold `
            -PlexCompatibilityScore $plexScore `
            -RoutingProfile $routingProfileName `
            -SizeGuardMode $sizeGuardModeName
    }

    $trace = @($baseTrace) + (New-MediaRouteDecisionTraceEntry -Code 'codec_not_remux_safe' -Message "codec '$codec' not remux-safe; encoding instead")
    return New-MediaRoutePlan `
        -Route (Get-MediaRouteEncodeName) `
        -ReasonCode 'codec_not_remux_safe' `
        -Reason "codec '$codec' not remux-safe — encoding instead" `
        -SourceCodec $codec `
        -FallbackFromRemux:$true `
        -SizeGB $sizeGB `
        -ThresholdGB $thresholdGB `
        -IsTV:$isTV `
        -DecisionTrace @($trace) `
        -RouteHints $hints `
        -SourceMediaProfile $profile `
        -EstimatedBitrateMbps $estimatedBitrate `
        -BitrateThresholdMbps $bitrateThreshold `
        -SizeOverThreshold:$sizeOverThreshold `
        -BitrateOverThreshold:$bitrateOverThreshold `
        -PlexCompatibilityScore $plexScore `
        -RoutingProfile $routingProfileName `
        -SizeGuardMode $sizeGuardModeName
}
