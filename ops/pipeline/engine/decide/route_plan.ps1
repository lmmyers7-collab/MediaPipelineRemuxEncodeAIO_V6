# ==============================================================================
# ops\pipeline\engine\decide\route_plan.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\decide\routing.ps1. Keep public function names stable;
# routing.ps1 dot-sources this file as part of the route policy export surface.
# ==============================================================================

function New-MediaRouteDecisionTraceEntry {
    param(
        [Parameter(Mandatory)] [string] $Code,
        [Parameter(Mandatory)] [string] $Message,
        $Data = $null
    )

    $entry = [ordered]@{
        code    = ([string]$Code).Trim().ToLowerInvariant()
        message = [string]$Message
    }
    if ($null -ne $Data) { $entry['data'] = $Data }
    return [pscustomobject]$entry
}

function New-MediaRouteActionSet {
    param(
        [Parameter(Mandatory)] [string] $Route,
        [string] $VideoAction = '',
        [string] $AudioAction = 'copy_or_policy',
        [string] $SubtitleAction = 'normalize_or_copy',
        [string] $ContainerAction = ''
    )

    $routeText = ([string]$Route).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($VideoAction)) {
        $VideoAction = if ($routeText -eq (Get-MediaRouteEncodeName)) { 'encode_hardware' } else { 'copy' }
    }
    if ([string]::IsNullOrWhiteSpace($ContainerAction)) {
        $ContainerAction = if ($routeText -eq (Get-MediaRouteEncodeName)) { 'encode_mkv' } else { 'remux_mkv' }
    }
    return [ordered]@{
        video     = $VideoAction
        audio     = $AudioAction
        subtitles = $SubtitleAction
        container = $ContainerAction
    }
}

function New-MediaRoutePlan {
    param(
        [Parameter(Mandatory)] [string] $Route,
        [Parameter(Mandatory)] [string] $ReasonCode,
        [Parameter(Mandatory)] [string] $Reason,
        [double] $SizeGB = 0,
        [double] $ThresholdGB = 0,
        [bool] $IsTV = $false,
        [string] $SourceCodec = '',
        [bool] $RequiresCodecProbe = $false,
        [bool] $FallbackFromRemux = $false,
        [array] $DecisionTrace = @(),
        $Actions = $null,
        $RouteHints = $null,
        $SourceMediaProfile = $null,
        [double] $EstimatedBitrateMbps = 0,
        [double] $BitrateThresholdMbps = 0,
        [bool] $SizeOverThreshold = $false,
        [bool] $BitrateOverThreshold = $false,
        [double] $PlexCompatibilityScore = 100,
        [string] $RoutingProfile = '',
        [string] $RouteThresholdMode = '',
        [string] $SizeGuardMode = ''
    )

    $routeText = ([string]$Route).Trim().ToLowerInvariant()
    $encodeRoute = Get-MediaRouteEncodeName
    $effectiveRoutingProfile = Resolve-MediaRouteRoutingProfileName -RoutingProfile $RoutingProfile
    $trace = @($DecisionTrace | Where-Object { $null -ne $_ })
    if ($trace.Count -eq 0) {
        $trace = @((New-MediaRouteDecisionTraceEntry -Code $ReasonCode -Message $Reason))
    }
    $effectiveActions = if ($Actions) { $Actions } else { New-MediaRouteActionSet -Route $routeText }
    $effectiveHints = ConvertTo-MediaRouteHintMap $RouteHints
    $effectiveRouteThresholdMode = if (-not [string]::IsNullOrWhiteSpace($RouteThresholdMode)) {
        Resolve-MediaRouteThresholdModeName -RouteThresholdMode $RouteThresholdMode
    } elseif (-not [string]::IsNullOrWhiteSpace([string]$effectiveHints.route_threshold_mode)) {
        Resolve-MediaRouteThresholdModeName -RouteThresholdMode ([string]$effectiveHints.route_threshold_mode)
    } else {
        Resolve-MediaRouteThresholdModeName
    }
    $effectiveSizeGuardMode = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode $SizeGuardMode
    $effectiveBitrateThreshold = [double]$BitrateThresholdMbps
    $effectiveSizeOverThreshold = [bool]$SizeOverThreshold
    if (-not $effectiveSizeOverThreshold -and $ThresholdGB -gt 0 -and $SizeGB -gt $ThresholdGB) {
        $effectiveSizeOverThreshold = $true
    }
    $effectiveBitrateOverThreshold = [bool]$BitrateOverThreshold
    if (-not $effectiveBitrateOverThreshold -and $effectiveBitrateThreshold -gt 0 -and $EstimatedBitrateMbps -gt $effectiveBitrateThreshold) {
        $effectiveBitrateOverThreshold = $true
    }
    return [pscustomobject]@{
        Route              = $routeText
        ShouldEncode       = ($routeText -eq $encodeRoute)
        ReasonCode         = $ReasonCode
        Reason             = $Reason
        DisplayRoute       = if ($routeText -eq $encodeRoute) { 'ENCODE' } elseif ($RequiresCodecProbe) { 'REMUX (codec check pending)' } else { 'REMUX' }
        SizeGB             = $SizeGB
        ThresholdGB        = $ThresholdGB
        IsTV               = [bool]$IsTV
        SourceCodec        = $SourceCodec
        RequiresCodecProbe = [bool]$RequiresCodecProbe
        FallbackFromRemux  = [bool]$FallbackFromRemux
        Actions            = $effectiveActions
        DecisionTrace      = @($trace)
        RouteHints         = $effectiveHints
        SourceMediaProfile = $SourceMediaProfile
        EstimatedBitrateMbps = [double]$EstimatedBitrateMbps
        BitrateThresholdMbps = $effectiveBitrateThreshold
        SizeOverThreshold = $effectiveSizeOverThreshold
        BitrateOverThreshold = $effectiveBitrateOverThreshold
        PlexCompatibilityScore = [double]$PlexCompatibilityScore
        RoutingProfile     = $effectiveRoutingProfile
        RouteThresholdMode = $effectiveRouteThresholdMode
        SizeGuardMode      = $effectiveSizeGuardMode
    }
}

function Get-MediaRouteRuleOutcomeEvidence {
    param($RoutePlan)

    $trace = if ($RoutePlan -and $RoutePlan.PSObject.Properties['DecisionTrace']) { @($RoutePlan.DecisionTrace) } else { @() }
    $hardCodes = @(
        'folder_policy_force_encode',
        'folder_policy_force_remux',
        'folder_policy_force_remux_unsafe',
        'file_override_force_encode',
        'file_override_force_remux',
        'file_override_force_remux_unsafe',
        'codec_outside_policy',
        'plex_strict_score_below_threshold',
        'resolution_over_policy',
        'bitrate_over_threshold',
        'size_over_threshold',
        'forced_remux_rejected_unsafe_codec',
        'codec_not_remux_safe'
    )
    $softCodes = @(
        'routing_profile_selected',
        'size_evaluated',
        'bitrate_estimated',
        'resolution_detected',
        'video_codec_detected',
        'plex_compatibility_scored',
        'codec_remux_safe',
        'plex_compatible_h264_remux'
    )
    $advisoryCodes = @(
        'bitrate_threshold_ignored',
        'plex_compatible_size_advisory',
        'size_threshold_ignored',
        'folder_policy_prefer_encode',
        'codec_allowed_by_routing_profile',
        'unsafe_forced_remux_allowed',
        'oversized_encode_remux_fallback'
    )

    $classify = {
        param([string[]] $Codes)
        return @($trace | Where-Object {
            $code = ''
            try { $code = [string]$_.code } catch {}
            $Codes -contains $code
        })
    }

    return [ordered]@{
        hard     = & $classify $hardCodes
        soft     = & $classify $softCodes
        advisory = & $classify $advisoryCodes
    }
}
