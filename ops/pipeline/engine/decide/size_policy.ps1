# ==============================================================================
# ops\pipeline\engine\decide\size_policy.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\decide\routing.ps1. Keep public function names stable;
# routing.ps1 dot-sources this file as part of the route policy export surface.
# ==============================================================================

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

function Get-MediaRouteMaxHeightFromUpperTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 + ([double]$TolerancePercent / 100.0)))
}

function Get-MediaRouteMinHeightFromLowerTolerance {
    param(
        [int] $BaseHeight,
        [double] $TolerancePercent
    )

    return [int][Math]::Round([double]$BaseHeight * (1.0 - ([double]$TolerancePercent / 100.0)))
}

function Get-MediaRouteHeightToleranceBoundaries {
    param(
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667
    )

    $route1080pMaxHeight = Get-MediaRouteMaxHeightFromUpperTolerance -BaseHeight 1080 -TolerancePercent $Route1080pUpperHeightTolerancePercent
    $route1440pMinHeight = Get-MediaRouteMinHeightFromLowerTolerance -BaseHeight 1440 -TolerancePercent $Route1440pLowerHeightTolerancePercent
    $route1440pMaxHeight = Get-MediaRouteMaxHeightFromUpperTolerance -BaseHeight 1440 -TolerancePercent $Route1440pUpperHeightTolerancePercent
    $route4kMinHeight = Get-MediaRouteMinHeightFromLowerTolerance -BaseHeight 2160 -TolerancePercent $Route4KLowerHeightTolerancePercent

    return [pscustomobject]([ordered]@{
        Route1080pMaxHeight = [int]$route1080pMaxHeight
        Route1440pMinHeight = [int]$route1440pMinHeight
        Route1440pMaxHeight = [int]$route1440pMaxHeight
        Route4KMinHeight    = [int]$route4kMinHeight
        IsContiguous        = (($route1440pMinHeight -eq ($route1080pMaxHeight + 1)) -and ($route4kMinHeight -eq ($route1440pMaxHeight + 1)))
    })
}

function Resolve-MediaRouteResolutionBitrateSelection {
    param(
        [int] $VideoHeight = 0,
        [bool] $IsTV = $false,
        [double] $MovieRouteMaxVideoBitrateMbps = 35.0,
        [double] $TVRouteMaxVideoBitrateMbps = 18.0,
        [int] $Route1080pBucketMaxHeight = 1200,
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1080pMaxVideoBitrateMbps = 20.0,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route1440pMaxVideoBitrateMbps = 35.0,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667,
        [int] $Route4KBucketMinHeight = 1800,
        [double] $Route4KMaxVideoBitrateMbps = 35.0
    )

    $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries `
        -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
        -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
        -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
        -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent
    if (-not $heightBoundaries.IsContiguous) {
        $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries
    }
    $Route1080pBucketMaxHeight = [int]$heightBoundaries.Route1080pMaxHeight
    $Route4KBucketMinHeight = [int]$heightBoundaries.Route4KMinHeight
    if ($Route1080pMaxVideoBitrateMbps -le 0) { $Route1080pMaxVideoBitrateMbps = 20.0 }
    if ($Route1440pMaxVideoBitrateMbps -le 0) { $Route1440pMaxVideoBitrateMbps = 35.0 }
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
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    }

    if ($VideoHeight -lt $heightBoundaries.Route1440pMinHeight) {
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$Route1080pMaxVideoBitrateMbps
            Source                   = 'source_height_bucket'
            Bucket                   = '1080p'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    }

    if ($VideoHeight -lt $heightBoundaries.Route4KMinHeight) {
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$Route1440pMaxVideoBitrateMbps
            Source                   = 'source_height_bucket'
            Bucket                   = '1440p'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
        })
    }

    return [pscustomobject]([ordered]@{
        CapMbps                  = [double]$Route4KMaxVideoBitrateMbps
        Source                   = 'source_height_bucket'
        Bucket                   = '4k'
        Height                   = [int]$VideoHeight
        Route1080pBucketMaxHeight = [int]$Route1080pBucketMaxHeight
        Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
        Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
        Route4KBucketMinHeight   = [int]$Route4KBucketMinHeight
    })
}

function Resolve-MediaRouteResolutionSizeSelection {
    param(
        [int] $VideoHeight = 0,
        [bool] $IsTV = $false,
        [double] $MovieThresholdGB = 8.0,
        [double] $TVThresholdGB = 3.0,
        [double] $MovieRoute1080pTargetSizeGB = 0.0,
        [double] $MovieRoute1440pTargetSizeGB = 0.0,
        [double] $MovieRoute4KTargetSizeGB = 0.0,
        [double] $TVRoute1080pTargetSizeGB = 0.0,
        [double] $TVRoute1440pTargetSizeGB = 0.0,
        [double] $TVRoute4KTargetSizeGB = 0.0,
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667
    )

    if ($MovieRoute1080pTargetSizeGB -le 0) { $MovieRoute1080pTargetSizeGB = [double]$MovieThresholdGB }
    if ($MovieRoute1440pTargetSizeGB -le 0) { $MovieRoute1440pTargetSizeGB = [double]$MovieThresholdGB }
    if ($MovieRoute4KTargetSizeGB -le 0) { $MovieRoute4KTargetSizeGB = [double]$MovieThresholdGB }
    if ($TVRoute1080pTargetSizeGB -le 0) { $TVRoute1080pTargetSizeGB = [double]$TVThresholdGB }
    if ($TVRoute1440pTargetSizeGB -le 0) { $TVRoute1440pTargetSizeGB = [double]$TVThresholdGB }
    if ($TVRoute4KTargetSizeGB -le 0) { $TVRoute4KTargetSizeGB = [double]$TVThresholdGB }

    $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries `
        -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
        -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
        -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
        -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent
    if (-not $heightBoundaries.IsContiguous) {
        $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries
    }

    $bucket = if ($VideoHeight -le 0) {
        if ($IsTV) { 'unknown_height_tv' } else { 'unknown_height_movie' }
    } elseif ($VideoHeight -lt $heightBoundaries.Route1440pMinHeight) {
        '1080p'
    } elseif ($VideoHeight -lt $heightBoundaries.Route4KMinHeight) {
        '1440p'
    } else {
        '4k'
    }

    $movieTarget = [double]$MovieThresholdGB
    $tvTarget = [double]$TVThresholdGB
    $source = 'movie_tv_fallback'
    switch ($bucket) {
        '1080p' {
            $movieTarget = [double]$MovieRoute1080pTargetSizeGB
            $tvTarget = [double]$TVRoute1080pTargetSizeGB
            $source = 'source_height_bucket'
        }
        '1440p' {
            $movieTarget = [double]$MovieRoute1440pTargetSizeGB
            $tvTarget = [double]$TVRoute1440pTargetSizeGB
            $source = 'source_height_bucket'
        }
        '4k' {
            $movieTarget = [double]$MovieRoute4KTargetSizeGB
            $tvTarget = [double]$TVRoute4KTargetSizeGB
            $source = 'source_height_bucket'
        }
    }

    $designation = if ($IsTV) { 'tv' } else { 'movie' }
    $target = if ($IsTV) { [double]$tvTarget } else { [double]$movieTarget }
    return [pscustomobject]([ordered]@{
        TargetGB                = [double]$target
        Source                  = ("{0}_{1}" -f $source, $designation)
        Bucket                  = [string]$bucket
        MovieTargetGB           = [double]$movieTarget
        TVTargetGB              = [double]$tvTarget
        Route1080pBucketMaxHeight = [int]$heightBoundaries.Route1080pMaxHeight
        Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
        Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
        Route4KBucketMinHeight  = [int]$heightBoundaries.Route4KMinHeight
    })
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
