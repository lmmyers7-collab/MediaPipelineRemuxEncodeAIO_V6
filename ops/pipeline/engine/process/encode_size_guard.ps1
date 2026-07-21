# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode waste and size guard helpers.

function Get-MediaPipelineEncodeSizeGuardBoundaryVersion {
    return 'encode_size_guard_boundary.v1'
}

function Get-EncodeWasteGuardConfigValue {
    param(
        [Parameter(Mandatory)] [string] $Name,
        $DefaultValue = $null
    )

    $var = Get-Variable -Name $Name -Scope Script -ErrorAction SilentlyContinue
    if ($var) { return $var.Value }
    return $DefaultValue
}

function Get-EncodeWasteGuardLimitPolicy {
    param(
        [string] $RoutingProfile = '',
        [string] $RouteReasonCode = '',
        [string] $RouteIntentReasonCode = ''
    )

    $profile = Resolve-MediaRouteRoutingProfileName -RoutingProfile $RoutingProfile
    $reasonCode = ([string]$RouteReasonCode).Trim().ToLowerInvariant()
    $intentReasonCode = ([string]$RouteIntentReasonCode).Trim().ToLowerInvariant()
    if ([string]::IsNullOrWhiteSpace($intentReasonCode)) { $intentReasonCode = $reasonCode }
    $compatibilityReasons = Get-MediaEncodeCompatibilitySizeReasonCodes
    $growthPercent = if ($profile -eq 'plex_direct_play' -or $reasonCode -in $compatibilityReasons) {
        [double](Get-EncodeWasteGuardConfigValue -Name 'CompatibilityEncodeGrowthPercent' -DefaultValue 15)
    } else {
        [double](Get-EncodeWasteGuardConfigValue -Name 'MaxEncodeGrowthPercent' -DefaultValue 5)
    }
    if ($growthPercent -lt 0) { $growthPercent = 0 }
    return [pscustomobject][ordered]@{
        RoutingProfile = $profile
        GrowthPercent  = [double]$growthPercent
        LimitRatio     = [double](1.0 + ($growthPercent / 100.0))
        RouteReasonCode = $reasonCode
        RouteIntentReasonCode = $intentReasonCode
    }
}

function New-EncodeWasteGuardContext {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputPath,
        [string] $RouteReasonCode = '',
        [string] $RouteIntentReasonCode = '',
        [bool] $UseCpuFallback = $false
    )

    $wasteMode = [string](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardMode' -DefaultValue 'off')
    $eligibility = Test-MediaEncodeWasteGuardEligibility `
        -WasteGuardMode $wasteMode `
        -SizeGuardMode ([string](Get-EncodeWasteGuardConfigValue -Name 'SizeGuardMode' -DefaultValue 'advisory')) `
        -RouteReasonCode $RouteReasonCode `
        -RouteIntentReasonCode $RouteIntentReasonCode `
        -UseCpuFallback:$UseCpuFallback
    $limitPolicy = Get-EncodeWasteGuardLimitPolicy `
        -RoutingProfile ([string](Get-EncodeWasteGuardConfigValue -Name 'RoutingProfile' -DefaultValue 'standard')) `
        -RouteReasonCode $RouteReasonCode `
        -RouteIntentReasonCode $RouteIntentReasonCode
    $sourceSize = 0L
    try {
        if (Test-Path -LiteralPath $SourcePath -ErrorAction SilentlyContinue) {
            $sourceSize = [long](Get-Item -LiteralPath $SourcePath).Length
        }
    } catch {
        $sourceSize = 0L
    }

    return [pscustomobject][ordered]@{
        Enabled                 = [bool]$eligibility.Eligible
        Mode                    = [string]$eligibility.Mode
        Enforce                 = [bool]$eligibility.Enforce
        DryRun                  = [bool]$eligibility.DryRun
        Reason                  = [string]$eligibility.Reason
        SizeGuardMode           = [string]$eligibility.SizeGuardMode
        RoutingProfile          = [string]$limitPolicy.RoutingProfile
        RouteReasonCode         = [string]$limitPolicy.RouteReasonCode
        RouteIntentReasonCode   = [string]$limitPolicy.RouteIntentReasonCode
        ForcedRouteOverride     = [bool]$eligibility.ForcedRouteOverride
        FallbackRemuxEligible   = [bool]$eligibility.FallbackRemuxEligible
        SourceSizeBytes         = [long]$sourceSize
        OutputPath              = $OutputPath
        MaxGrowthPercent        = [double]$limitPolicy.GrowthPercent
        LimitRatio              = [double]$limitPolicy.LimitRatio
        OversizeMarginPercent   = [double](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardOversizeMarginPercent' -DefaultValue 20)
        MinProgressPercent      = [double](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardMinProgressPercent' -DefaultValue 15)
        MinElapsedSeconds       = [double](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardMinElapsedSeconds' -DefaultValue 120)
        ConsecutiveSamples      = [int](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardConsecutiveSamples' -DefaultValue 2)
        PollSeconds             = [double](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardPollSeconds' -DefaultValue 10)
    }
}

function New-EncodeWasteGuardSizePolicyMetadata {
    param(
        [Parameter(Mandatory)] $WasteGuardContext,
        [Parameter(Mandatory)] $Projection,
        [Parameter(Mandatory)] [string] $Trigger,
        [Parameter(Mandatory)] [string] $Message
    )

    $ratio = if ([long]$Projection.SourceSizeBytes -gt 0 -and [long]$Projection.OutputSizeBytes -gt 0) {
        [math]::Round(([double]$Projection.OutputSizeBytes / [double]$Projection.SourceSizeBytes), 4)
    } else {
        0.0
    }
    return [pscustomobject][ordered]@{
        mode                       = [string]$WasteGuardContext.SizeGuardMode
        routing_profile            = [string]$WasteGuardContext.RoutingProfile
        route_reason_code          = [string]$WasteGuardContext.RouteReasonCode
        route_intent_reason_code   = [string]$WasteGuardContext.RouteIntentReasonCode
        max_growth_percent         = [double]$WasteGuardContext.MaxGrowthPercent
        limit_ratio                = [double]$WasteGuardContext.LimitRatio
        source_size_bytes          = [long]$Projection.SourceSizeBytes
        output_size_bytes          = [long]$Projection.OutputSizeBytes
        ratio                      = [double]$ratio
        exceeded                   = $true
        enforced                   = [bool]$WasteGuardContext.Enforce
        forced_route_override      = [bool]$WasteGuardContext.ForcedRouteOverride
        fallback_remux_eligible    = [bool]$WasteGuardContext.FallbackRemuxEligible
        should_fallback_remux      = [bool]$WasteGuardContext.Enforce
        message                    = $Message
        waste_guard_mode           = [string]$WasteGuardContext.Mode
        waste_guard_trigger        = $Trigger
        waste_guard_projection     = $Projection
    }
}

function Invoke-EncodeWasteGuardPreflight {
    param(
        [Parameter(Mandatory)] [string] $SourcePath,
        [Parameter(Mandatory)] [string] $OutputContainer,
        [Parameter(Mandatory)] $EncodePlan,
        [array] $VideoFilterArgs = @(),
        [Parameter(Mandatory)] $WasteGuardContext,
        [Parameter(Mandatory)] $SourceFile
    )

    $emptyResult = [pscustomobject][ordered]@{
        ShouldFallbackRemux = $false
        Projection = $null
        Message = ''
        Reason = 'not_run'
    }
    if (-not [bool]$WasteGuardContext.Enabled) { return $emptyResult }
    if (-not [bool](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardPreflightEnabled' -DefaultValue $false)) { return $emptyResult }

    $duration = 0.0
    try {
        $durationResult = Invoke-FFprobeCommand -ArgumentList @(
            "-v","error","-show_entries","format=duration",
            "-of","default=noprint_wrappers=1:nokey=1","--",$SourcePath
        ) -TimeoutSeconds 30 -Stage 'encode-waste-guard-preflight-duration'
        if ([int]$durationResult.ExitCode -eq 0) {
            [double]::TryParse(([string]$durationResult.Output).Trim(), [ref]$duration) | Out-Null
        }
    } catch {
        $duration = 0.0
    }
    if ($duration -le 0) {
        Write-Log "ENCODE SIZE: waste guard preflight skipped because duration could not be probed" "WARN"
        $emptyResult.Reason = 'duration_unavailable'
        return $emptyResult
    }

    $sampleCount = [math]::Max(1, [int](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardPreflightSampleCount' -DefaultValue 3))
    $sampleSeconds = [math]::Max(1.0, [double](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardPreflightSampleSeconds' -DefaultValue 30))
    $timeoutSeconds = [math]::Max(30, [int](Get-EncodeWasteGuardConfigValue -Name 'EncodeWasteGuardPreflightTimeoutSeconds' -DefaultValue 900))
    $effectiveSampleSeconds = [math]::Min($sampleSeconds, [math]::Max(1.0, $duration))
    $totalSampleSeconds = 0.0
    $totalSampleBytes = 0L
    $samplePaths = @()
    try {
        for ($idx = 0; $idx -lt $sampleCount; $idx++) {
            $start = if ($duration -le $effectiveSampleSeconds) {
                0.0
            } elseif ($sampleCount -le 1) {
                [math]::Max(0.0, (($duration - $effectiveSampleSeconds) / 2.0))
            } else {
                [math]::Max(0.0, (($duration - $effectiveSampleSeconds) * ([double]$idx / [double]($sampleCount - 1))))
            }
            $samplePath = Join-Path $script:processingDir ("encode_waste_guard_sample_{0}.{1}" -f ([guid]::NewGuid().ToString('N')), $OutputContainer)
            $samplePaths += $samplePath
            $sampleArgs = New-EncodeWasteGuardSampleArgumentList `
                -InputPath $SourcePath `
                -VideoFlags @($EncodePlan.VideoFlags) `
                -VideoFilterArgs $VideoFilterArgs `
                -OutputPath $samplePath `
                -StartSeconds $start `
                -SampleSeconds $effectiveSampleSeconds
            $sampleResult = Invoke-FFmpegCommand -ArgumentList $sampleArgs -TimeoutSeconds $timeoutSeconds -Stage 'encode-waste-guard-preflight' -SaveReproOnFailure
            if ([int]$sampleResult.ExitCode -ne 0 -or -not (Test-Path -LiteralPath $samplePath -ErrorAction SilentlyContinue)) {
                Write-Log "ENCODE SIZE: waste guard preflight sample failed; full encode will continue" "WARN"
                $emptyResult.Reason = 'sample_failed'
                return $emptyResult
            }
            $sampleBytes = [long](Get-Item -LiteralPath $samplePath).Length
            if ($sampleBytes -le 0) {
                Write-Log "ENCODE SIZE: waste guard preflight sample was empty; full encode will continue" "WARN"
                $emptyResult.Reason = 'sample_empty'
                return $emptyResult
            }
            $totalSampleBytes += $sampleBytes
            $totalSampleSeconds += $effectiveSampleSeconds
        }

        $sampleProgressPercent = [math]::Min(100.0, [math]::Max(0.1, ($totalSampleSeconds / $duration) * 100.0))
        $projection = Measure-MediaEncodeWasteGuardProjection `
            -SourceSizeBytes ([long]$WasteGuardContext.SourceSizeBytes) `
            -OutputSizeBytes $totalSampleBytes `
            -ProgressPercent $sampleProgressPercent `
            -LimitRatio ([double]$WasteGuardContext.LimitRatio) `
            -OversizeMarginPercent ([double]$WasteGuardContext.OversizeMarginPercent) `
            -MinProgressPercent 0 `
            -ElapsedSeconds ([double]$totalSampleSeconds) `
            -MinElapsedSeconds 0 `
            -PreviousConsecutiveHits 0 `
            -ConsecutiveSamples 1
        $script:LastEncodeWasteGuardProjection = $projection
        if (-not [bool]$projection.ShouldAbort) {
            return [pscustomobject][ordered]@{ ShouldFallbackRemux = $false; Projection = $projection; Message = ''; Reason = 'within_projection' }
        }

        $message = ("preflight samples project encode output {0:N0} bytes above waste guard threshold {1:N0} bytes; remux fallback will be attempted before full GPU encode" -f [double]$projection.ProjectedOutputBytes, [double]$projection.AbortThresholdBytes)
        $eventData = @{
            mode                   = [string]$WasteGuardContext.Mode
            projected_output_bytes = [double]$projection.ProjectedOutputBytes
            abort_threshold_bytes  = [double]$projection.AbortThresholdBytes
            sample_count           = [int]$sampleCount
            sample_seconds         = [double]$effectiveSampleSeconds
            sampled_bytes          = [long]$totalSampleBytes
            sampled_progress_pct   = [double]$sampleProgressPercent
        }
        if ([bool]$WasteGuardContext.DryRun) {
            Write-Log "ENCODE SIZE: waste guard preflight dry-run would fallback-remux: $message" "WARN"
            Write-PipelineEvent -EventType 'encode_waste_guard_preflight' -Stage 'encode_preflight' -Route 'encode' -Status 'dry_run' -SourcePath $SourceFile.FullName -Data $eventData | Out-Null
            return [pscustomobject][ordered]@{ ShouldFallbackRemux = $false; Projection = $projection; Message = $message; Reason = 'dry_run' }
        }

        Write-PipelineEvent -EventType 'encode_waste_guard_preflight' -Stage 'encode_preflight' -Route 'encode' -Status 'fallback_remux' -SourcePath $SourceFile.FullName -Data $eventData | Out-Null
        return [pscustomobject][ordered]@{ ShouldFallbackRemux = $true; Projection = $projection; Message = $message; Reason = 'projected_oversize' }
    } finally {
        foreach ($samplePath in $samplePaths) {
            Remove-Item -LiteralPath ([string]$samplePath) -Force -ErrorAction SilentlyContinue
        }
    }
}

function Invoke-EncodeWasteGuardRemuxFallback {
    param(
        [Parameter(Mandatory)] $SourceFile,
        [Parameter(Mandatory)] [string] $ScratchPath,
        [bool] $IsTV,
        $TvInfo,
        [Parameter(Mandatory)] $WasteGuardContext,
        [Parameter(Mandatory)] $Projection,
        [Parameter(Mandatory)] [string] $Trigger,
        [Parameter(Mandatory)] [string] $Message
    )

    $originalRoutePlan = $script:CurrentRoutePlan
    $originalRouteReasonCode = [string]$script:CurrentRouteReasonCode
    $originalRouteReason = [string]$script:CurrentRouteReason
    $originalSizePolicyResult = $script:CurrentSizePolicyResult
    $script:CurrentSizePolicyResult = New-EncodeWasteGuardSizePolicyMetadata `
        -WasteGuardContext $WasteGuardContext `
        -Projection $Projection `
        -Trigger $Trigger `
        -Message $Message
    Write-Log "ENCODE SIZE: attempting remux fallback after waste guard ${Trigger}; direct-copy size/bitrate caps are bypassed for this fallback" "WARN"
    Set-MediaPipelineEncodeRemuxFallbackRouteEvidence `
        -Trigger $Trigger `
        -Reason $Message | Out-Null
    $fallbackRemuxOk = Do-Remux $SourceFile $IsTV $TvInfo -FallbackFromOversizedEncode
    if ($fallbackRemuxOk) {
        Write-Log "ENCODE SIZE: remux fallback published; rejected projected-oversize encode temp output will be deleted" "WARN"
        return [pscustomobject][ordered]@{ Ok = $true; KeepScratchInput = [bool]($script:LastPublishResult -and $script:LastPublishResult.KeepScratchInput) }
    }

    $script:CurrentRoutePlan = $originalRoutePlan
    $script:CurrentRouteReasonCode = $originalRouteReasonCode
    $script:CurrentRouteReason = $originalRouteReason
    $script:CurrentSizePolicyResult = $originalSizePolicyResult
    $fallbackFailureReason = Add-RemuxFallbackRejectionToFailureReason -Reason "$Message; remux fallback unavailable or blocked; projected-oversize encode rejected before publish"
    $fallbackFailureProperties = New-RemuxFallbackFailureProperties
    $null = Register-SourceFailure -SourceFile $SourceFile -ScratchPath $ScratchPath -Classification 'operator_required' -Reason $fallbackFailureReason -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source, remux_fallback_rejection details, and remux-safe codec/container policy. Adjust the route, size guard, or encode waste guard settings before retrying; the projected oversized encode was not published.' -AdditionalProperties $fallbackFailureProperties
    $fallbackBlockDetail = Get-LastRemuxFallbackRejectionReasonText
    if ([string]::IsNullOrWhiteSpace($fallbackBlockDetail)) {
        Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting projected-oversize encode before publish: $(Get-SafeLocalName $SourceFile.Name)" "ERROR"
    } else {
        Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting projected-oversize encode before publish: $(Get-SafeLocalName $SourceFile.Name); block reason: $fallbackBlockDetail" "ERROR"
    }
    return [pscustomobject][ordered]@{ Ok = $false; KeepScratchInput = $false }
}

function Invoke-MediaPipelineEncodeSizeGuard {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $isTV = [bool]$Context.IsTV
    $tvInfo = $Context.TvInfo
    $safeName = [string]$Context.SafeName
    $localIn = $Context.LocalIn
    $tempOut = $Context.TempOut

    $routeIntentReasonCode = Get-CurrentEncodeRouteIntentReasonCode
    $sizePolicy = Test-MediaEncodeOutputSizePolicy `
        -SourcePath $localIn `
        -OutputPath $tempOut `
        -RoutingProfile $script:RoutingProfile `
        -SizeGuardMode $script:SizeGuardMode `
        -MaxGrowthPercent $script:MaxEncodeGrowthPercent `
        -CompatibilityGrowthPercent $script:CompatibilityEncodeGrowthPercent `
        -RouteReasonCode ([string]$script:CurrentRouteReasonCode) `
        -RouteIntentReasonCode $routeIntentReasonCode
    $script:CurrentSizePolicyResult = $sizePolicy.Metadata
    $Context.SizePolicyResult = $sizePolicy.Metadata
    if ($sizePolicy.Exceeded) {
        $sizePolicySeverity = ([string]$sizePolicy.Severity).ToUpperInvariant()
        Write-Log "ENCODE SIZE: $($sizePolicy.Message)" $sizePolicySeverity
    } else {
        Write-Log "ENCODE SIZE: $($sizePolicy.Message)" "DEBUG"
    }
    if (-not $sizePolicy.Ok) {
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$sizePolicy.Message) -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source and routing policy. Use advisory/off size guard, force remux for a compatible source, or adjust encode quality/ladder before retrying.'
        $Context.LocalIn = $null
        Write-Log "ENCODE: output rejected by strict size policy: $safeName" "ERROR"
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-size-policy'
    }
    if ([bool]$sizePolicy.ShouldFallbackRemux) {
        $originalRoutePlan = $script:CurrentRoutePlan
        $originalRouteReasonCode = [string]$script:CurrentRouteReasonCode
        $originalRouteReason = [string]$script:CurrentRouteReason
        $originalSizePolicyResult = $script:CurrentSizePolicyResult
        Write-Log "ENCODE SIZE: attempting remux fallback for oversized automatic size/bitrate-threshold encode; direct-copy size/bitrate caps are bypassed for this fallback" "WARN"
        Set-MediaPipelineEncodeRemuxFallbackRouteEvidence `
            -Trigger 'post_encode_size_guard' `
            -Reason ([string]$sizePolicy.Message) | Out-Null
        $fallbackRemuxOk = Do-Remux $file $isTV $tvInfo -FallbackFromOversizedEncode
        if ($fallbackRemuxOk) {
            Write-Log "ENCODE SIZE: remux fallback published; rejected oversized encode temp output will be deleted" "WARN"
            if ($script:LastPublishResult -and $script:LastPublishResult.KeepScratchInput) { $Context.LocalIn = $null }
            return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'encode-size-policy'
        }
        $script:CurrentRoutePlan = $originalRoutePlan
        $script:CurrentRouteReasonCode = $originalRouteReasonCode
        $script:CurrentRouteReason = $originalRouteReason
        $script:CurrentSizePolicyResult = $originalSizePolicyResult
        $Context.SizePolicyResult = $originalSizePolicyResult
        $fallbackFailureReason = Add-RemuxFallbackRejectionToFailureReason -Reason "$($sizePolicy.Message); remux fallback unavailable or blocked; oversized encode rejected before publish"
        $fallbackFailureProperties = New-RemuxFallbackFailureProperties
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $fallbackFailureReason -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source, remux_fallback_rejection details, and remux-safe codec/container policy. Adjust the route, size guard, or encode settings before retrying; the oversized encode was not published.' -AdditionalProperties $fallbackFailureProperties
        $Context.LocalIn = $null
        $fallbackBlockDetail = Get-LastRemuxFallbackRejectionReasonText
        if ([string]::IsNullOrWhiteSpace($fallbackBlockDetail)) {
            Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting oversized encode before publish: $safeName" "ERROR"
        } else {
            Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting oversized encode before publish: $safeName; block reason: $fallbackBlockDetail" "ERROR"
        }
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-size-policy'
    }

    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'encode-size-policy'
}
