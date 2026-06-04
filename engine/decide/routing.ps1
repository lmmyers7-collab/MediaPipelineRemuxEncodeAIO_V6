# ==============================================================================
# engine\decide\routing.ps1
# ==============================================================================
# Pure route policy helpers for initial size-based routing and remux codec
# safety. Dot-sourced by engine/decide/stage.ps1 and the legacy
# legacy routing shim.
#
# Reads at call time only from compatibility wrappers:
#   $EncodeThresholdGB, $TVEncodeThresholdGB
#   $RouteThresholdMode
#   $MovieRouteMaxVideoBitrateMbps, $TVRouteMaxVideoBitrateMbps
#   $Route1080pBucketMaxHeight, $Route1080pMaxVideoBitrateMbps
#   $Route4KBucketMinHeight, $Route4KMaxVideoBitrateMbps
# ==============================================================================

function Normalize-MediaRouteCodecName {
    param([string]$CodecName)

    $text = ([string]$CodecName).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($text)) { return 'unknown' }
    return $text
}

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
                if ($mode -in @('advisory','strict','off')) { $map[$key] = $mode }
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

function Get-MediaRouteDefaultMaxBitrateMbps {
    param(
        [bool] $IsTV = $false,
        [double] $MovieRouteMaxVideoBitrateMbps = 35.0,
        [double] $TVRouteMaxVideoBitrateMbps = 18.0
    )

    if ($IsTV) {
        if ($TVRouteMaxVideoBitrateMbps -gt 0) { return [double]$TVRouteMaxVideoBitrateMbps }
        return 18.0
    }
    if ($MovieRouteMaxVideoBitrateMbps -gt 0) { return [double]$MovieRouteMaxVideoBitrateMbps }
    return 35.0
}

function Resolve-MediaRouteResolutionBitrateSelection {
    param(
        [int] $VideoHeight = 0,
        [bool] $IsTV = $false,
        [double] $MovieRouteMaxVideoBitrateMbps = 35.0,
        [double] $TVRouteMaxVideoBitrateMbps = 18.0,
        [int] $Route1080pBucketMaxHeight = 1200,
        [double] $Route1080pMaxVideoBitrateMbps = 20.0,
        [int] $Route4KBucketMinHeight = 1800,
        [double] $Route4KMaxVideoBitrateMbps = 35.0
    )

    if ($Route1080pBucketMaxHeight -le 0) { $Route1080pBucketMaxHeight = 1200 }
    if ($Route4KBucketMinHeight -le 0) { $Route4KBucketMinHeight = 1800 }
    if ($Route1080pBucketMaxHeight -ge $Route4KBucketMinHeight) {
        $Route1080pBucketMaxHeight = 1200
        $Route4KBucketMinHeight = 1800
    }
    if ($Route1080pMaxVideoBitrateMbps -le 0) { $Route1080pMaxVideoBitrateMbps = 20.0 }
    if ($Route4KMaxVideoBitrateMbps -le 0) { $Route4KMaxVideoBitrateMbps = 35.0 }

    if ($VideoHeight -le 0) {
        $cap = Get-MediaRouteDefaultMaxBitrateMbps `
            -IsTV:$IsTV `
            -MovieRouteMaxVideoBitrateMbps $MovieRouteMaxVideoBitrateMbps `
            -TVRouteMaxVideoBitrateMbps $TVRouteMaxVideoBitrateMbps
        $fallback = if ($IsTV) { 'unknown_height_tv' } else { 'unknown_height_movie' }
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$cap
            Source                   = 'movie_tv_fallback'
            Bucket                   = $fallback
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    }

    if ($VideoHeight -le $Route1080pBucketMaxHeight) {
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$Route1080pMaxVideoBitrateMbps
            Source                   = 'source_height_bucket'
            Bucket                   = '1080ish'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    }

    $bucket = if ($VideoHeight -ge $Route4KBucketMinHeight) { '4k' } else { 'between_1080ish_and_4k' }
    return [pscustomobject]([ordered]@{
        CapMbps                  = [double]$Route4KMaxVideoBitrateMbps
        Source                   = 'source_height_bucket'
        Bucket                   = $bucket
        Height                   = [int]$VideoHeight
        Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
        Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
    })
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
    if ($mode -in @('advisory','strict','off')) { return $mode }
    return 'advisory'
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

function Test-MediaEncodeOutputSizePolicy {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $RoutingProfile = '',
        [string] $SizeGuardMode = '',
        [double] $MaxGrowthPercent = 5,
        [double] $CompatibilityGrowthPercent = 15,
        [string] $RouteReasonCode = ''
    )

    $mode = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode $SizeGuardMode
    $profile = Resolve-MediaRouteRoutingProfileName -RoutingProfile $RoutingProfile
    $compatibilityReasons = @(
        'plex_strict_score_below_threshold',
        'codec_outside_policy',
        'resolution_over_policy',
        'bitrate_over_threshold',
        'forced_remux_rejected_unsafe_codec',
        'hardware_encoder_safe_retry_succeeded',
        'hardware_encoder_cpu_fallback',
        # Suggestion #2 — GPU skipped per cached probe; the libx265
        # output is the same shape whether we tried NVENC first or not.
        'gpu_unavailable_cpu_only'
    )
    $reasonCode = ([string]$RouteReasonCode).Trim().ToLowerInvariant()
    $growthPercent = if ($profile -eq 'plex_direct_play' -or $reasonCode -in $compatibilityReasons) {
        [double]$CompatibilityGrowthPercent
    } else {
        [double]$MaxGrowthPercent
    }
    if ($growthPercent -lt 0) { $growthPercent = 0 }
    $limitRatio = 1.0 + ($growthPercent / 100.0)

    $metadata = [ordered]@{
        mode                       = $mode
        routing_profile            = $profile
        route_reason_code          = $reasonCode
        max_growth_percent         = [double]$growthPercent
        limit_ratio                = [double]$limitRatio
        source_size_bytes          = 0L
        output_size_bytes          = 0L
        ratio                      = 0.0
        exceeded                   = $false
        enforced                   = ($mode -eq 'strict')
        message                    = ''
    }

    if ($mode -eq 'off') {
        $metadata.message = 'encode output size guard disabled'
        return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; Severity = 'info'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
    }

    try {
        if (-not (Test-Path -LiteralPath $SourcePath) -or -not (Test-Path -LiteralPath $OutputPath)) {
            $metadata.message = 'encode output size guard skipped because source or output was unavailable'
            return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; Severity = 'warn'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }
        $sourceSize = [long](Get-Item -LiteralPath $SourcePath).Length
        $outputSize = [long](Get-Item -LiteralPath $OutputPath).Length
        $metadata.source_size_bytes = $sourceSize
        $metadata.output_size_bytes = $outputSize
        if ($sourceSize -le 0 -or $outputSize -le 0) {
            $metadata.message = 'encode output size guard skipped because source or output size was zero'
            return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; Severity = 'warn'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }
        $ratio = [math]::Round(([double]$outputSize / [double]$sourceSize), 4)
        $metadata.ratio = $ratio
        if ($ratio -le $limitRatio) {
            $metadata.message = ("encoded output is {0:N2}x source; within {1:N2}x limit" -f $ratio, $limitRatio)
            return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; Severity = 'info'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }

        $metadata.exceeded = $true
        $metadata.message = ("encoded output is {0:N2}x source; exceeds {1:N2}x limit ({2:N0}% growth policy)" -f $ratio, $limitRatio, $growthPercent)
        $shouldBlock = ($mode -eq 'strict')
        return [pscustomobject]@{
            Ok          = (-not $shouldBlock)
            Exceeded    = $true
            ShouldBlock = $shouldBlock
            Severity    = if ($shouldBlock) { 'error' } else { 'warn' }
            Message     = $metadata.message
            Metadata    = [pscustomobject]$metadata
        }
    } catch {
        $metadata.message = "encode output size guard failed to inspect file sizes: $($_.Exception.Message)"
        return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; Severity = 'warn'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
    }
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
        'unsafe_forced_remux_allowed'
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

function Resolve-MediaRouteBySize {
    param(
        [Parameter(Mandatory)] [long] $FileSizeBytes,
        [bool] $IsTV = $false,
        [Parameter(Mandatory)] [double] $MovieThresholdGB,
        [Parameter(Mandatory)] [double] $TVThresholdGB,
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
        [double] $MovieRouteMaxVideoBitrateMbps = 35.0,
        [double] $TVRouteMaxVideoBitrateMbps = 18.0,
        [int] $Route1080pBucketMaxHeight = 1200,
        [double] $Route1080pMaxVideoBitrateMbps = 20.0,
        [int] $Route4KBucketMinHeight = 1800,
        [double] $Route4KMaxVideoBitrateMbps = 35.0
    )

    $sizeGB = [double]$FileSizeBytes / 1GB
    $threshold = if ($IsTV) { [double]$TVThresholdGB } else { [double]$MovieThresholdGB }
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
    $bitrateSelection = if ($null -ne $hints.max_video_bitrate_mbps) {
        [pscustomobject]([ordered]@{
            CapMbps                  = [double]$hints.max_video_bitrate_mbps
            Source                   = 'folder_policy'
            Bucket                   = 'explicit_override'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    } else {
        Resolve-MediaRouteResolutionBitrateSelection `
            -VideoHeight $VideoHeight `
            -IsTV:$IsTV `
            -MovieRouteMaxVideoBitrateMbps $MovieRouteMaxVideoBitrateMbps `
            -TVRouteMaxVideoBitrateMbps $TVRouteMaxVideoBitrateMbps `
            -Route1080pBucketMaxHeight $Route1080pBucketMaxHeight `
            -Route1080pMaxVideoBitrateMbps $Route1080pMaxVideoBitrateMbps `
            -Route4KBucketMinHeight $Route4KBucketMinHeight `
            -Route4KMaxVideoBitrateMbps $Route4KMaxVideoBitrateMbps
    }
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
    $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'routing_profile_selected' -Message ("routing profile {0}; route threshold mode {1}; size guard {2}" -f $routingProfileName, $routeThresholdModeName, $sizeGuardModeName) -Data @{ routing_profile = $routingProfileName; route_threshold_mode = $routeThresholdModeName; size_guard_mode = $sizeGuardModeName; route_max_bitrate_mbps = [double]$routeMaxBitrate; effective_max_bitrate_mbps = [double]$maxBitrate; route_bitrate_source = [string]$bitrateSelection.Source; route_bitrate_bucket = [string]$bitrateSelection.Bucket; route_bitrate_bucket_height = [int]$bitrateSelection.Height; route_1080p_bucket_max_height = [int]$Route1080pBucketMaxHeight; route_1080p_max_video_bitrate_mbps = [double]$Route1080pMaxVideoBitrateMbps; route_4k_bucket_min_height = [int]$Route4KBucketMinHeight; route_4k_max_video_bitrate_mbps = [double]$Route4KMaxVideoBitrateMbps; h264_plex_remux_enabled = [bool]$AllowH264RemuxIfPlexCompatible; h264_max_bitrate_mbps = [double]$H264RemuxMaxBitrateMbps; h264_max_height = [int]$H264RemuxMaxHeight; h264_bitrate_cap_applied = [bool]$h264BitrateCapApplied }))
    $trace.Add((New-MediaRouteDecisionTraceEntry -Code 'size_evaluated' -Message ("source size {0:N2} GB; threshold {1:N2} GB" -f $sizeGB, $threshold) -Data @{ size_gb = $sizeGB; threshold_gb = $threshold; media_type = $mediaType }))
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
    $movieRouteMaxBitrate = if (Get-Variable -Name MovieRouteMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRouteMaxVideoBitrateMbps } else { 35.0 }
    $tvRouteMaxBitrate = if (Get-Variable -Name TVRouteMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRouteMaxVideoBitrateMbps } else { 18.0 }
    $route1080pBucketMaxHeight = if (Get-Variable -Name Route1080pBucketMaxHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:Route1080pBucketMaxHeight } else { 1200 }
    $route1080pMaxBitrate = if (Get-Variable -Name Route1080pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pMaxVideoBitrateMbps } else { 20.0 }
    $route4kBucketMinHeight = if (Get-Variable -Name Route4KBucketMinHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:Route4KBucketMinHeight } else { 1800 }
    $route4kMaxBitrate = if (Get-Variable -Name Route4KMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KMaxVideoBitrateMbps } else { 35.0 }
    $routeThresholdMode = if (Get-Variable -Name RouteThresholdMode -Scope Script -ErrorAction SilentlyContinue) { [string]$script:RouteThresholdMode } else { 'compatibility_advisory' }

    return Resolve-MediaRouteBySize `
        -FileSizeBytes ([long]$File.Length) `
        -IsTV:$IsTV `
        -MovieThresholdGB ([double]$EncodeThresholdGB) `
        -TVThresholdGB ([double]$TVEncodeThresholdGB) `
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
        -MovieRouteMaxVideoBitrateMbps $movieRouteMaxBitrate `
        -TVRouteMaxVideoBitrateMbps $tvRouteMaxBitrate `
        -Route1080pBucketMaxHeight $route1080pBucketMaxHeight `
        -Route1080pMaxVideoBitrateMbps $route1080pMaxBitrate `
        -Route4KBucketMinHeight $route4kBucketMinHeight `
        -Route4KMaxVideoBitrateMbps $route4kMaxBitrate
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
            route_1080p_max_bitrate_mbps      = if (Get-Variable -Name Route1080pMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route1080pMaxVideoBitrateMbps } else { 20.0 }
            route_4k_bucket_min_height        = if (Get-Variable -Name Route4KBucketMinHeight -Scope Script -ErrorAction SilentlyContinue) { [int]$script:Route4KBucketMinHeight } else { 1800 }
            route_4k_max_bitrate_mbps         = if (Get-Variable -Name Route4KMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:Route4KMaxVideoBitrateMbps } else { 35.0 }
            unknown_height_fallback_movie_mbps = if (Get-Variable -Name MovieRouteMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:MovieRouteMaxVideoBitrateMbps } else { 35.0 }
            unknown_height_fallback_tv_mbps   = if (Get-Variable -Name TVRouteMaxVideoBitrateMbps -Scope Script -ErrorAction SilentlyContinue) { [double]$script:TVRouteMaxVideoBitrateMbps } else { 18.0 }
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
    return $Map
}
