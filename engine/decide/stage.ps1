function Invoke-DecideStage {
    param([Parameter(Mandatory = $true)] $Payload)

    $repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
    $mediaConstantsModule = Join-Path $repoRoot 'engine\shared\media_constants.ps1'
    $routingModule = Join-Path $repoRoot 'engine\decide\routing.ps1'
    if (-not (Test-Path -LiteralPath $mediaConstantsModule -PathType Leaf)) {
        throw "Media constants module not found: $mediaConstantsModule"
    }
    if (-not (Test-Path -LiteralPath $routingModule -PathType Leaf)) {
        throw "Routing module not found: $routingModule"
    }
    . $mediaConstantsModule
    . $routingModule

    $fileSizeBytes = [long](Require-ObjectValue -Object $Payload -Name 'file_size_bytes')
    $durationSeconds = [double](Get-ObjectValue -Object $Payload -Name 'duration_seconds' -Default 0)
    $videoCodec = [string](Get-ObjectValue -Object $Payload -Name 'video_codec' -Default '')
    $videoHeight = [int](Get-ObjectValue -Object $Payload -Name 'video_height' -Default 0)
    $isTv = [bool](Get-ObjectValue -Object $Payload -Name 'is_tv' -Default $false)
    $isHdr = [bool](Get-ObjectValue -Object $Payload -Name 'is_hdr' -Default $false)
    $routeHints = Get-ObjectValue -Object $Payload -Name 'route_hints' -Default $null
    $sourceMediaProfile = Get-ObjectValue -Object $Payload -Name 'source_media_profile' -Default $null
    if ($null -eq $sourceMediaProfile) {
        $sourceMediaProfile = [ordered]@{}
    }

    $plan = Resolve-MediaRouteBySize `
        -FileSizeBytes $fileSizeBytes `
        -IsTV:$isTv `
        -MovieThresholdGB ([double](Get-ObjectValue -Object $Payload -Name 'encode_threshold_gb' -Default 8)) `
        -TVThresholdGB ([double](Get-ObjectValue -Object $Payload -Name 'tv_encode_threshold_gb' -Default 3)) `
        -DurationSeconds $durationSeconds `
        -VideoCodec $videoCodec `
        -VideoHeight $videoHeight `
        -IsHDR:$isHdr `
        -RouteHints $routeHints `
        -SourceMediaProfile $sourceMediaProfile `
        -RoutingProfile ([string](Get-ObjectValue -Object $Payload -Name 'routing_profile' -Default 'plex_direct_stream')) `
        -SizeGuardMode ([string](Get-ObjectValue -Object $Payload -Name 'size_guard_mode' -Default 'advisory')) `
        -AllowH264RemuxIfPlexCompatible:([bool](Get-ObjectValue -Object $Payload -Name 'allow_h264_remux_if_plex_compatible' -Default $true)) `
        -H264RemuxMaxBitrateMbps ([double](Get-ObjectValue -Object $Payload -Name 'h264_remux_max_bitrate_mbps' -Default 35.0)) `
        -H264RemuxMaxHeight ([int](Get-ObjectValue -Object $Payload -Name 'h264_remux_max_height' -Default 1080)) `
        -MovieRouteMaxVideoBitrateMbps ([double](Get-ObjectValue -Object $Payload -Name 'movie_route_max_video_bitrate_mbps' -Default 35.0)) `
        -TVRouteMaxVideoBitrateMbps ([double](Get-ObjectValue -Object $Payload -Name 'tv_route_max_video_bitrate_mbps' -Default 18.0))

    return [ordered]@{
        route                       = [string]$plan.Route
        should_encode               = [bool]$plan.ShouldEncode
        reason_code                 = [string]$plan.ReasonCode
        reason                      = [string]$plan.Reason
        display_route               = [string]$plan.DisplayRoute
        source_codec                = [string]$plan.SourceCodec
        size_gb                     = [double]$plan.SizeGB
        threshold_gb                = [double]$plan.ThresholdGB
        requires_codec_probe        = [bool]$plan.RequiresCodecProbe
        fallback_from_remux         = [bool]$plan.FallbackFromRemux
        estimated_bitrate_mbps      = [double]$plan.EstimatedBitrateMbps
        plex_compatibility_score    = [double]$plan.PlexCompatibilityScore
        routing_profile             = [string]$plan.RoutingProfile
        size_guard_mode             = [string]$plan.SizeGuardMode
        encoder_profile             = ''
        actions                     = (ConvertTo-OrderedMap $plan.Actions)
        decision_trace              = @($plan.DecisionTrace)
        route_hints                 = (ConvertTo-OrderedMap $plan.RouteHints)
        source_media_profile        = (ConvertTo-OrderedMap $plan.SourceMediaProfile)
    }
}
