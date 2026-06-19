# ==============================================================================
# ops\pipeline\engine\decide\size_policy.ps1
# ==============================================================================
# Extracted from ops\pipeline\engine\decide\routing.ps1. Keep public function names stable;
# routing.ps1 dot-sources this file as part of the route policy export surface.
# ==============================================================================

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
        [double] $Route1080pUpperHeightTolerancePercent = 11.111111,
        [double] $Route1080pMaxVideoBitrateMbps = 20.0,
        [double] $Route1440pLowerHeightTolerancePercent = 16.597222,
        [double] $Route1440pUpperHeightTolerancePercent = 24.930556,
        [double] $Route1440pMaxVideoBitrateMbps = 35.0,
        [double] $Route4KLowerHeightTolerancePercent = 16.666667,
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
    $route1080pBucketMaxHeight = [int]$heightBoundaries.Route1080pMaxHeight
    $route4KBucketMinHeight = [int]$heightBoundaries.Route4KMinHeight
    if ($Route1080pMaxVideoBitrateMbps -le 0) { $Route1080pMaxVideoBitrateMbps = 20.0 }
    if ($Route1440pMaxVideoBitrateMbps -le 0) { $Route1440pMaxVideoBitrateMbps = 35.0 }
    if ($Route4KMaxVideoBitrateMbps -le 0) { $Route4KMaxVideoBitrateMbps = 35.0 }
    if ($MovieRouteMaxVideoBitrateMbps -le 0) { $MovieRouteMaxVideoBitrateMbps = 35.0 }
    if ($TVRouteMaxVideoBitrateMbps -le 0) { $TVRouteMaxVideoBitrateMbps = 18.0 }

    if ($VideoHeight -le 0) {
        $unknownHeightCapMbps = if ($IsTV) { [double]$TVRouteMaxVideoBitrateMbps } else { [double]$MovieRouteMaxVideoBitrateMbps }
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$unknownHeightCapMbps
            Source                   = 'unknown_height_1080p_bucket'
            Bucket                   = '1080p'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$route1080pBucketMaxHeight
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$route4KBucketMinHeight
        })
    }

    if ($VideoHeight -lt $heightBoundaries.Route1440pMinHeight) {
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$Route1080pMaxVideoBitrateMbps
            Source                   = 'source_height_bucket'
            Bucket                   = '1080p'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$route1080pBucketMaxHeight
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$route4KBucketMinHeight
        })
    }

    if ($VideoHeight -lt $heightBoundaries.Route4KMinHeight) {
        return [pscustomobject]([ordered]@{
            CapMbps                  = [double]$Route1440pMaxVideoBitrateMbps
            Source                   = 'source_height_bucket'
            Bucket                   = '1440p'
            Height                   = [int]$VideoHeight
            Route1080pBucketMaxHeight = [int]$route1080pBucketMaxHeight
            Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
            Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
            Route4KBucketMinHeight   = [int]$route4KBucketMinHeight
        })
    }

    return [pscustomobject]([ordered]@{
        CapMbps                  = [double]$Route4KMaxVideoBitrateMbps
        Source                   = 'source_height_bucket'
        Bucket                   = '4k'
        Height                   = [int]$VideoHeight
        Route1080pBucketMaxHeight = [int]$route1080pBucketMaxHeight
        Route1440pBucketMinHeight = [int]$heightBoundaries.Route1440pMinHeight
        Route1440pBucketMaxHeight = [int]$heightBoundaries.Route1440pMaxHeight
        Route4KBucketMinHeight   = [int]$route4KBucketMinHeight
    })
}

function Resolve-MediaRouteResolutionSizeSelection {
    param(
        [int] $VideoHeight = 0,
        [bool] $IsTV = $false,
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

    if ($MovieRoute1080pTargetSizeGB -le 0) { $MovieRoute1080pTargetSizeGB = 8.0 }
    if ($MovieRoute1440pTargetSizeGB -le 0) { $MovieRoute1440pTargetSizeGB = 8.0 }
    if ($MovieRoute4KTargetSizeGB -le 0) { $MovieRoute4KTargetSizeGB = 8.0 }
    if ($TVRoute1080pTargetSizeGB -le 0) { $TVRoute1080pTargetSizeGB = 3.0 }
    if ($TVRoute1440pTargetSizeGB -le 0) { $TVRoute1440pTargetSizeGB = 3.0 }
    if ($TVRoute4KTargetSizeGB -le 0) { $TVRoute4KTargetSizeGB = 3.0 }

    $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries `
        -Route1080pUpperHeightTolerancePercent $Route1080pUpperHeightTolerancePercent `
        -Route1440pLowerHeightTolerancePercent $Route1440pLowerHeightTolerancePercent `
        -Route1440pUpperHeightTolerancePercent $Route1440pUpperHeightTolerancePercent `
        -Route4KLowerHeightTolerancePercent $Route4KLowerHeightTolerancePercent
    if (-not $heightBoundaries.IsContiguous) {
        $heightBoundaries = Get-MediaRouteHeightToleranceBoundaries
    }

    $bucket = if ($VideoHeight -le 0) {
        '1080p'
    } elseif ($VideoHeight -lt $heightBoundaries.Route1440pMinHeight) {
        '1080p'
    } elseif ($VideoHeight -lt $heightBoundaries.Route4KMinHeight) {
        '1440p'
    } else {
        '4k'
    }

    $movieTarget = [double]$MovieRoute1080pTargetSizeGB
    $tvTarget = [double]$TVRoute1080pTargetSizeGB
    $source = if ($VideoHeight -le 0) { 'unknown_height_1080p_bucket' } else { 'source_height_bucket' }
    switch ($bucket) {
        '1080p' {
            $movieTarget = [double]$MovieRoute1080pTargetSizeGB
            $tvTarget = [double]$TVRoute1080pTargetSizeGB
            if ($VideoHeight -gt 0) { $source = 'source_height_bucket' }
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

function Get-MediaEncodeForcedRouteOverrideReasonCodes {
    return @(
        'folder_policy_force_encode',
        'file_override_force_encode',
        'forced_remux_rejected_unsafe_codec'
    )
}

function Get-MediaEncodeFallbackRemuxReasonCodes {
    return @(
        'bitrate_over_threshold',
        'size_over_threshold'
    )
}

function Get-MediaEncodeCompatibilitySizeReasonCodes {
    return @(
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
}

function Resolve-MediaEncodeWasteGuardModeName {
    param([string]$WasteGuardMode = '')

    $mode = ([string]$WasteGuardMode).Trim().ToLowerInvariant()
    if ($mode -in @('dry_run', 'enforce')) { return $mode }
    return 'off'
}

function Test-MediaEncodeWasteGuardEligibility {
    param(
        [string] $WasteGuardMode = 'off',
        [string] $SizeGuardMode = '',
        [string] $RouteReasonCode = '',
        [string] $RouteIntentReasonCode = '',
        [bool] $UseCpuFallback = $false
    )

    $wasteMode = Resolve-MediaEncodeWasteGuardModeName -WasteGuardMode $WasteGuardMode
    $sizeMode = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode $SizeGuardMode
    $reasonCode = ([string]$RouteReasonCode).Trim().ToLowerInvariant()
    $intentReasonCode = ([string]$RouteIntentReasonCode).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($intentReasonCode)) { $intentReasonCode = $reasonCode }

    $forcedRouteOverride = ($intentReasonCode -in (Get-MediaEncodeForcedRouteOverrideReasonCodes))
    $fallbackRemuxEligible = ($intentReasonCode -in (Get-MediaEncodeFallbackRemuxReasonCodes))
    $reason = 'eligible'
    $eligible = $true
    if ($wasteMode -eq 'off') {
        $eligible = $false
        $reason = 'waste_guard_off'
    } elseif ($sizeMode -ne 'fallback_remux') {
        $eligible = $false
        $reason = 'size_guard_mode_not_fallback_remux'
    } elseif ($UseCpuFallback) {
        $eligible = $false
        $reason = 'cpu_encode_not_guarded'
    } elseif ($forcedRouteOverride) {
        $eligible = $false
        $reason = 'forced_route_override'
    } elseif (-not $fallbackRemuxEligible) {
        $eligible = $false
        $reason = 'route_reason_not_fallback_remux_eligible'
    }

    return [pscustomobject][ordered]@{
        Eligible                = [bool]$eligible
        Mode                    = $wasteMode
        Enforce                 = ($wasteMode -eq 'enforce')
        DryRun                  = ($wasteMode -eq 'dry_run')
        Reason                  = $reason
        SizeGuardMode           = $sizeMode
        RouteReasonCode         = $reasonCode
        RouteIntentReasonCode   = $intentReasonCode
        ForcedRouteOverride     = [bool]$forcedRouteOverride
        FallbackRemuxEligible   = [bool]$fallbackRemuxEligible
        UseCpuFallback          = [bool]$UseCpuFallback
    }
}

function Measure-MediaEncodeWasteGuardProjection {
    param(
        [long] $SourceSizeBytes = 0,
        [long] $OutputSizeBytes = 0,
        [double] $ProgressPercent = 0,
        [double] $LimitRatio = 1.05,
        [double] $OversizeMarginPercent = 20,
        [double] $MinProgressPercent = 15,
        [double] $ElapsedSeconds = 0,
        [double] $MinElapsedSeconds = 120,
        [int] $PreviousConsecutiveHits = 0,
        [int] $ConsecutiveSamples = 2
    )

    if ($LimitRatio -le 0) { $LimitRatio = 1.0 }
    if ($OversizeMarginPercent -lt 0) { $OversizeMarginPercent = 0 }
    if ($MinProgressPercent -lt 0) { $MinProgressPercent = 0 }
    if ($MinElapsedSeconds -lt 0) { $MinElapsedSeconds = 0 }
    if ($ConsecutiveSamples -lt 1) { $ConsecutiveSamples = 1 }

    $progress = [math]::Max(0.0, [math]::Min(100.0, [double]$ProgressPercent))
    $allowedBytes = [math]::Max(0.0, [double]$SourceSizeBytes * [double]$LimitRatio)
    $abortThresholdBytes = $allowedBytes * (1.0 + ([double]$OversizeMarginPercent / 100.0))
    $projectedBytes = 0.0
    $exceeded = $false
    $reason = 'ok'
    if ($SourceSizeBytes -le 0) {
        $reason = 'missing_source_size'
    } elseif ($OutputSizeBytes -le 0) {
        $reason = 'missing_output_size'
    } elseif ($progress -lt [double]$MinProgressPercent) {
        $reason = 'below_min_progress'
    } elseif ([double]$ElapsedSeconds -lt [double]$MinElapsedSeconds) {
        $reason = 'below_min_elapsed'
    } else {
        $projectedBytes = [double]$OutputSizeBytes / ([double]$progress / 100.0)
        $exceeded = ($projectedBytes -gt $abortThresholdBytes)
        if ($exceeded) { $reason = 'projected_oversize' }
    }

    $hits = if ($exceeded) { [int]$PreviousConsecutiveHits + 1 } else { 0 }
    $shouldAbort = ($exceeded -and $hits -ge [int]$ConsecutiveSamples)
    return [pscustomobject][ordered]@{
        ShouldAbort            = [bool]$shouldAbort
        Exceeded               = [bool]$exceeded
        Reason                 = $reason
        SourceSizeBytes        = [long]$SourceSizeBytes
        OutputSizeBytes        = [long]$OutputSizeBytes
        ProgressPercent        = [double]$progress
        ElapsedSeconds         = [double]$ElapsedSeconds
        LimitRatio             = [double]$LimitRatio
        OversizeMarginPercent  = [double]$OversizeMarginPercent
        AllowedOutputBytes     = [double]$allowedBytes
        AbortThresholdBytes    = [double]$abortThresholdBytes
        ProjectedOutputBytes   = [double]$projectedBytes
        ProjectedRatio         = if ($SourceSizeBytes -gt 0 -and $projectedBytes -gt 0) { [math]::Round($projectedBytes / [double]$SourceSizeBytes, 4) } else { 0.0 }
        ConsecutiveHits        = [int]$hits
        ConsecutiveSamples     = [int]$ConsecutiveSamples
    }
}

function Test-MediaEncodeOutputSizePolicy {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $RoutingProfile = '',
        [string] $SizeGuardMode = '',
        [double] $MaxGrowthPercent = 5,
        [double] $CompatibilityGrowthPercent = 15,
        [string] $RouteReasonCode = '',
        [string] $RouteIntentReasonCode = ''
    )

    $mode = Resolve-MediaRouteSizeGuardModeName -SizeGuardMode $SizeGuardMode
    $profile = Resolve-MediaRouteRoutingProfileName -RoutingProfile $RoutingProfile
    $forcedRouteOverrideReasons = Get-MediaEncodeForcedRouteOverrideReasonCodes
    $fallbackRemuxReasons = Get-MediaEncodeFallbackRemuxReasonCodes
    $compatibilityReasons = Get-MediaEncodeCompatibilitySizeReasonCodes
    $reasonCode = ([string]$RouteReasonCode).Trim().ToLowerInvariant()
    $intentReasonCode = ([string]$RouteIntentReasonCode).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($intentReasonCode)) { $intentReasonCode = $reasonCode }
    $forcedRouteOverride = ($intentReasonCode -in $forcedRouteOverrideReasons)
    $fallbackRemuxEligible = ($intentReasonCode -in $fallbackRemuxReasons)
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
        route_intent_reason_code   = $intentReasonCode
        max_growth_percent         = [double]$growthPercent
        limit_ratio                = [double]$limitRatio
        source_size_bytes          = 0L
        output_size_bytes          = 0L
        ratio                      = 0.0
        exceeded                   = $false
        enforced                   = ($mode -eq 'strict')
        forced_route_override      = [bool]$forcedRouteOverride
        fallback_remux_eligible    = [bool]$fallbackRemuxEligible
        should_fallback_remux      = $false
        message                    = ''
    }

    if ($mode -eq 'off') {
        $metadata.message = 'encode output size guard disabled'
        return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; ShouldFallbackRemux = $false; Severity = 'info'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
    }

    try {
        if (-not (Test-Path -LiteralPath $SourcePath) -or -not (Test-Path -LiteralPath $OutputPath)) {
            $metadata.message = 'encode output size guard could not verify because source or output was unavailable'
            $inspectionFailureBlocks = ($mode -in @('strict','fallback_remux'))
            $metadata.enforced = [bool]$inspectionFailureBlocks
            return [pscustomobject]@{ Ok = (-not $inspectionFailureBlocks); Exceeded = $false; ShouldBlock = [bool]$inspectionFailureBlocks; ShouldFallbackRemux = $false; Severity = if ($inspectionFailureBlocks) { 'error' } else { 'warn' }; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }
        $sourceSize = [long](Get-Item -LiteralPath $SourcePath).Length
        $outputSize = [long](Get-Item -LiteralPath $OutputPath).Length
        $metadata.source_size_bytes = $sourceSize
        $metadata.output_size_bytes = $outputSize
        if ($sourceSize -le 0 -or $outputSize -le 0) {
            $metadata.message = 'encode output size guard could not verify because source or output size was zero'
            $inspectionFailureBlocks = ($mode -in @('strict','fallback_remux'))
            $metadata.enforced = [bool]$inspectionFailureBlocks
            return [pscustomobject]@{ Ok = (-not $inspectionFailureBlocks); Exceeded = $false; ShouldBlock = [bool]$inspectionFailureBlocks; ShouldFallbackRemux = $false; Severity = if ($inspectionFailureBlocks) { 'error' } else { 'warn' }; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }
        $ratio = [math]::Round(([double]$outputSize / [double]$sourceSize), 4)
        $metadata.ratio = $ratio
        if ($ratio -le $limitRatio) {
            $metadata.message = ("encoded output is {0:N2}x source; within {1:N2}x limit" -f $ratio, $limitRatio)
            return [pscustomobject]@{ Ok = $true; Exceeded = $false; ShouldBlock = $false; ShouldFallbackRemux = $false; Severity = 'info'; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
        }

        $metadata.exceeded = $true
        $metadata.message = ("encoded output is {0:N2}x source; exceeds {1:N2}x limit ({2:N0}% growth policy)" -f $ratio, $limitRatio, $growthPercent)
        $shouldBlock = ($mode -eq 'strict')
        $shouldFallbackRemux = ($mode -eq 'fallback_remux' -and $fallbackRemuxEligible)
        if ($mode -eq 'fallback_remux') {
            if ($shouldFallbackRemux) {
                $metadata.message = "$($metadata.message); fallback remux will be attempted because encode was an automatic size/bitrate threshold decision"
            } elseif ($forcedRouteOverride) {
                $metadata.message = "$($metadata.message); fallback remux not applied because route was explicitly forced by override"
            } else {
                $metadata.message = "$($metadata.message); fallback remux not applied because encode reason is not eligible for automatic fallback"
            }
        }
        $metadata.enforced = ($shouldBlock -or $shouldFallbackRemux)
        $metadata.should_fallback_remux = [bool]$shouldFallbackRemux
        return [pscustomobject]@{
            Ok                  = (-not $shouldBlock)
            Exceeded            = $true
            ShouldBlock         = $shouldBlock
            ShouldFallbackRemux = $shouldFallbackRemux
            Severity            = if ($shouldBlock) { 'error' } else { 'warn' }
            Message             = $metadata.message
            Metadata            = [pscustomobject]$metadata
        }
    } catch {
        $metadata.message = "encode output size guard failed to inspect file sizes: $($_.Exception.Message)"
        $inspectionFailureBlocks = ($mode -in @('strict','fallback_remux'))
        $metadata.enforced = [bool]$inspectionFailureBlocks
        return [pscustomobject]@{ Ok = (-not $inspectionFailureBlocks); Exceeded = $false; ShouldBlock = [bool]$inspectionFailureBlocks; ShouldFallbackRemux = $false; Severity = if ($inspectionFailureBlocks) { 'error' } else { 'warn' }; Message = $metadata.message; Metadata = [pscustomobject]$metadata }
    }
}
