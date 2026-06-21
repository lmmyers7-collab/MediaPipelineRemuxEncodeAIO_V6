# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline.ps1.
# Encode route implementation and command construction.

# ==============================================================================
# ENCODE
# ==============================================================================
function Get-CurrentEncodeRouteIntentReasonCode {
    $routeIntentReasonCode = ''
    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['ReasonCode']) {
        $routeIntentReasonCode = [string]$script:CurrentRoutePlan.ReasonCode
    }
    if ([string]::IsNullOrWhiteSpace($routeIntentReasonCode)) {
        $routeIntentReasonCode = [string]$script:CurrentRouteReasonCode
    }
    return $routeIntentReasonCode
}

function Get-RemuxFallbackRejectionValue {
    param(
        $Rejection,
        [Parameter(Mandatory)] [string] $Name,
        $Default = $null
    )

    if (-not $Rejection) { return $Default }
    if ($Rejection -is [System.Collections.IDictionary] -and $Rejection.Contains($Name)) { return $Rejection[$Name] }
    $prop = $Rejection.PSObject.Properties[$Name]
    if ($prop) { return $prop.Value }
    return $Default
}

function Get-LastRemuxFallbackRejection {
    $var = Get-Variable -Name LastRemuxFallbackRejection -Scope Script -ErrorAction SilentlyContinue
    if (-not $var) { return $null }
    return $script:LastRemuxFallbackRejection
}

function Get-LastRemuxFallbackRejectionReasonText {
    $rejection = Get-LastRemuxFallbackRejection
    if (-not $rejection) { return '' }

    $reason = [string](Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'reason' -Default '')
    $reasonCode = [string](Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'reason_code' -Default '')
    $sourceCodec = [string](Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'source_codec' -Default '')
    $safeCodecs = @(Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'remux_safe_video_codecs' -Default @())

    $parts = @()
    if (-not [string]::IsNullOrWhiteSpace($reason)) { $parts += $reason }
    if (-not [string]::IsNullOrWhiteSpace($reasonCode)) { $parts += "code=$reasonCode" }
    if (-not [string]::IsNullOrWhiteSpace($sourceCodec)) { $parts += "source_codec=$sourceCodec" }
    if ($safeCodecs.Count -gt 0) { $parts += "RemuxSafeVideoCodecs=$($safeCodecs -join ', ')" }
    return ($parts -join '; ')
}

function Add-RemuxFallbackRejectionToFailureReason {
    param([Parameter(Mandatory)] [string] $Reason)

    $detail = Get-LastRemuxFallbackRejectionReasonText
    if ([string]::IsNullOrWhiteSpace($detail)) { return $Reason }
    return "$Reason; remux fallback block reason: $detail"
}

function New-RemuxFallbackFailureProperties {
    $properties = @{}
    $rejection = Get-LastRemuxFallbackRejection
    if ($rejection) {
        $properties['remux_fallback_rejection'] = $rejection
    }
    if (Get-Command -Name Get-ActiveMediaRoutePlanMetadata -ErrorAction SilentlyContinue) {
        $routePlanMetadata = Get-ActiveMediaRoutePlanMetadata
        if ($routePlanMetadata -and (Get-Command -Name New-MediaRouteExplanation -ErrorAction SilentlyContinue)) {
            $routeExplanation = New-MediaRouteExplanation -Metadata $routePlanMetadata
            if ($routeExplanation) {
                if ($rejection -and $routeExplanation.PSObject.Properties['remux_fallback']) {
                    $rejectionReasonCode = [string](Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'reason_code' -Default '')
                    $rejectionReason = [string](Get-RemuxFallbackRejectionValue -Rejection $rejection -Name 'reason' -Default '')
                    $routeExplanation.remux_fallback['attempted'] = $true
                    $routeExplanation.remux_fallback['accepted'] = $false
                    $routeExplanation.remux_fallback['blocked_reason_code'] = $rejectionReasonCode
                    $routeExplanation.remux_fallback['blocked_reason'] = $rejectionReason
                    $routeExplanation.remux_fallback['codec_gate_code'] = $rejectionReasonCode
                    $routeExplanation.remux_fallback['codec_gate_reason'] = $rejectionReason
                    $routeExplanation.decision_summary = @($routeExplanation.decision_summary) + ("remux fallback blocked: {0}" -f $rejectionReasonCode)
                }
                $properties['route_explanation'] = $routeExplanation
            }
        }
    }
    return $properties
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

function Do-Encode {
    param($file, [bool]$isTV, $tvInfo)
    $safeName  = Get-SafeLocalName $file.Name
    $localIn   = $null
    $paths     = $null
    $tempOut   = $null
    $subResult = $null
    # FIX#10: same push-tracking flag pattern as Do-Remux.
    $pushOk    = $false
    $script:CurrentEncodeAttempts = @()
    $script:LastPublishResult = $null
    $script:CurrentSizePolicyResult = $null
    $script:LastRemuxFallbackRejection = $null
    $script:LastQualityVerification = $null
    $script:CurrentDynamicHdrEvidence = $null
    $dynamicHdrForceCpuEncode = $false
    $dynamicHdrWorkingDirectory = ''
    $dynamicHdrTempFiles = @()
    $dynamicHdrDolbyVisionRpuPath = ''
    $dynamicHdrDolbyVisionTargetProfile = ''
    $dynamicHdrHdr10PlusJsonPath = ''

    try {
        Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'encode' -CopyState 'starting' -Percent $null -SaveNow
        $localIn = Ensure-ScratchCopy $file $safeName
        if (-not $localIn) { return $false }

        $paths = Get-OutputPaths $file $isTV $tvInfo $safeName
        if (Test-Path -LiteralPath $paths.ServerOut) {
            if (-not (Test-OutputNeedsReprocess -OutputPath $paths.ServerOut -SourceFile $file)) {
                if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $file -ScratchPath $localIn -MediaOutputPath $paths.ServerOut -Context "ENCODE: ")) {
                    $localIn = $null
                    return $false
                }
                $script:LastPublishResult = New-ExistingOutputPublishResult -SourceFile $file -OutputPath $paths.ServerOut
                Write-Log "SKIP ENCODE (exists on server): $(Split-Path $paths.ServerOut -Leaf)"
                Clear-SourceFailureState $file
                return $true
            }
            Write-Log "ENCODE: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
        }
        if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) { return $false }

        # Pre-encode estimated output-size check. Fails fast if the scratch
        # drive can't hold the estimated output plus configured headroom,
        # instead of crashing mid-encode at 80%.
        if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE")) {
            return $false
        }

        $videoStreamPolicy = Test-SourceVideoStreamPublishPolicy -FilePath $localIn -Route 'encode'
        if (-not [bool]$videoStreamPolicy.Allowed) {
            $reason = [string]$videoStreamPolicy.Reason
            $errorCode = [string]$videoStreamPolicy.ErrorCode
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $reason -Stage 'video-stream-policy' -ErrorCode $errorCode -SuggestedAction 'Use a source with one real video stream or add per-stream routing and output-manifest validation before processing multi-video sources.'
            Write-Log "ENCODE: $reason" "ERROR"
            $localIn = $null
            return $false
        }

        try {
            $hdrState = Get-HDRState $localIn
            if (-not [bool]$hdrState.Known) {
                throw "HDR_DETECTION_UNKNOWN: $($hdrState.Reason)"
            }
            $isHDR = [bool]$hdrState.IsHDR
        } catch {
            $reason = [string]$_.Exception.Message
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'hdr-detection' -ErrorCode 'HDR_DETECTION_UNKNOWN' -SuggestedAction 'Inspect ffprobe video stream metadata and confirm the source file is complete; retry after replacing or repairing the source.' | Out-Null
            $localIn = $null
            return $false
        }
        # Suggestion #1 — extract HDR10 mastering display + MaxCLL once per
        # file so any CPU-fallback x265 invocation can emit a complete
        # HDR10 SEI. Probe is best-effort: SDR sources / probes that fail
        # return Known=$false and we leave the metadata strings empty.
        $hdr10MasterDisplay = ''
        $hdr10MaxCll = ''
        if ($isHDR) {
            $hdr10Meta = Get-SourceHdr10MasteringMetadata -FilePath $localIn
            if ($hdr10Meta.Known) {
                if ($hdr10Meta.HasMasterDisplay) { $hdr10MasterDisplay = [string]$hdr10Meta.MasterDisplay }
                if ($hdr10Meta.HasMaxCll)        { $hdr10MaxCll        = [string]$hdr10Meta.MaxCll }
                Write-Log "ENCODE: HDR10 metadata found — master-display='$hdr10MasterDisplay' max-cll='$hdr10MaxCll'" "DEBUG"
            } else {
                Write-Log "ENCODE: HDR source but no HDR10 mastering metadata in side_data ($($hdr10Meta.Reason)); CPU-encoded HDR output will lack master-display/MaxCLL SEI" "WARN"
            }
        }

        $encoderReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec ([string]$VideoCodec) -IsHDR:$isHDR
        if (-not [bool]$encoderReadiness.ok) {
            $readinessErrorCode = if ([string]::IsNullOrWhiteSpace([string]$encoderReadiness.error_code)) { 'ENCODE_ENCODER_UNSUPPORTED' } else { [string]$encoderReadiness.error_code }
            Write-PipelineEvent -EventType 'encoder_activation_policy' -Stage 'encode_prepare' -Route 'encode' -Status 'blocked' -SourcePath $file.FullName -Data $encoderReadiness | Out-Null
            $failureProperties = [ordered]@{
                encoder_activation = $encoderReadiness
                video_codec        = [string]$VideoCodec
                is_hdr             = [bool]$isHDR
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$encoderReadiness.reason) -Stage 'encode-policy' -ErrorCode $readinessErrorCode -SuggestedAction 'Choose an active descriptor-backed encoder such as hevc_nvenc or h264_nvenc for SDR sources, or wait until this encoder family has descriptor-owned flags, fallback policy, command topology tests, and real-media validation.' -AdditionalProperties $failureProperties
            Write-Log "ENCODE POLICY: $($encoderReadiness.reason)" "ERROR"
            $localIn = $null
            return $false
        }

        $dynamicHdrPolicy = Resolve-DynamicHdrPolicy -Policy ([string]$script:DynamicHdrPolicy)
        $dynamicHdrEncodeDecision = $null
        if ($isHDR -and $dynamicHdrPolicy -ne 'off') {
            $doviState = Get-DolbyVisionState -FilePath $localIn
            $hdr10PlusState = Test-Hdr10PlusPresence -FilePath $localIn
            $script:CurrentDynamicHdrEvidence = New-DynamicHdrEvidence -Route 'encode' -Policy $dynamicHdrPolicy -DoviState $doviState -Hdr10PlusState $hdr10PlusState
            if ([bool]$script:CurrentDynamicHdrEvidence.dynamic_metadata_present) {
                $dynamicHdrTools = [pscustomobject][ordered]@{ DoviToolAvailable = $false; Hdr10PlusToolAvailable = $false }
                $dynamicHdrCapability = [pscustomobject][ordered]@{ DolbyVision = $false; Hdr10Plus = $false }
                if ($dynamicHdrPolicy -in @('preserve_or_remux','preserve_or_review')) {
                    $dynamicHdrTools = Test-DynamicHdrToolsAvailable -DoviToolPath ([string]$script:DoviToolPath) -Hdr10PlusToolPath ([string]$script:Hdr10PlusToolPath)
                    $dynamicHdrCapability = Test-X265DynamicHdrCapability -FfmpegPath $ffmpegPath
                }
                $dynamicHdrEncodeDecision = Resolve-DynamicHdrEncodePreservationDecision `
                    -Evidence $script:CurrentDynamicHdrEvidence `
                    -Policy $dynamicHdrPolicy `
                    -OutputContainer ([string]$OutputContainer) `
                    -VideoCodec ([string]$VideoCodec) `
                    -DoviToolAvailable:([bool]$dynamicHdrTools.DoviToolAvailable) `
                    -Hdr10PlusToolAvailable:([bool]$dynamicHdrTools.Hdr10PlusToolAvailable) `
                    -X265DolbyVisionCapable:([bool]$dynamicHdrCapability.DolbyVision) `
                    -X265Hdr10PlusCapable:([bool]$dynamicHdrCapability.Hdr10Plus)
                $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'policy_action' -NotePropertyValue ([string]$dynamicHdrEncodeDecision.action) -Force
                $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'policy_reason_code' -NotePropertyValue ([string]$dynamicHdrEncodeDecision.reason_code) -Force
                $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'policy_reason' -NotePropertyValue ([string]$dynamicHdrEncodeDecision.reason) -Force
                $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'recommended_route' -NotePropertyValue ([string]$dynamicHdrEncodeDecision.recommended_route) -Force

                if ([string]$dynamicHdrEncodeDecision.action -eq 'preserve_encode') {
                    $preserveEncodeReady = $true
                    $preserveFailureReason = ''
                    $preserveFailureCode = ''
                    $videoTrackId = -1
                    $extension = [System.IO.Path]::GetExtension($localIn).TrimStart('.').ToLowerInvariant()
                    if ($extension -eq 'mkv') {
                        $primaryVideoStream = @($videoStreamPolicy.Inventory.RealVideoStreams)[0]
                        $ffprobeVideoStreamIndex = if ($primaryVideoStream) { [int]$primaryVideoStream.Index } else { -1 }
                        $trackResolution = Resolve-DynamicHdrMkvVideoTrackId -SourceFile $localIn -FfprobeVideoStreamIndex $ffprobeVideoStreamIndex
                        $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'mkv_video_track_resolution' -NotePropertyValue $trackResolution -Force
                        if ([bool]$trackResolution.ok) {
                            $videoTrackId = [int]$trackResolution.track_id
                        } else {
                            $preserveEncodeReady = $false
                            $preserveFailureReason = [string]$trackResolution.reason
                            $preserveFailureCode = if ([string]::IsNullOrWhiteSpace([string]$trackResolution.error_code)) { 'DYNAMIC_HDR_VIDEO_TRACK_UNRESOLVED' } else { [string]$trackResolution.error_code }
                        }
                    }

                    if ($preserveEncodeReady) {
                        $extractionPlan = New-DynamicHdrMetadataExtractionPlan `
                            -ScratchPath $localIn `
                            -WorkDir $script:processingDir `
                            -DoviPresent:([bool]$script:CurrentDynamicHdrEvidence.dovi_present) `
                            -DoviProfile ([int]$script:CurrentDynamicHdrEvidence.dovi_profile) `
                            -DoviBlCompatId ([int]$script:CurrentDynamicHdrEvidence.dovi_bl_compat_id) `
                            -DoviElPresent:([bool]$script:CurrentDynamicHdrEvidence.dovi_el_present) `
                            -Hdr10PlusPresent:([bool]$script:CurrentDynamicHdrEvidence.hdr10plus_present) `
                            -DoviToolPath ([string]$script:DoviToolPath) `
                            -Hdr10PlusToolPath ([string]$script:Hdr10PlusToolPath) `
                            -MkvExtractPath ([string]$mkvextractPath) `
                            -FfmpegPath ([string]$ffmpegPath) `
                            -VideoTrackId $videoTrackId `
                            -PlanId ([guid]::NewGuid().ToString('N'))
                        $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'extraction_plan' -NotePropertyValue $extractionPlan -Force
                        if (-not [bool]$extractionPlan.ok) {
                            $preserveEncodeReady = $false
                            $preserveFailureReason = [string]$extractionPlan.reason
                            $preserveFailureCode = if ([string]::IsNullOrWhiteSpace([string]$extractionPlan.error_code)) { 'DYNAMIC_HDR_PLAN_MISSING' } else { [string]$extractionPlan.error_code }
                        }
                    }

                    if ($preserveEncodeReady) {
                        Write-PipelineEvent -EventType 'dynamic_hdr_preservation_prepare' -Stage 'encode_prepare' -Route 'encode-cpu-fallback' -Status 'started' -SourcePath $file.FullName -Data @{
                            policy  = $dynamicHdrPolicy
                            summary = [string]$script:CurrentDynamicHdrEvidence.summary
                        } | Out-Null
                        $extractionResult = Export-DynamicHdrMetadata -Plan $extractionPlan -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProcessPriority $script:CpuEncodeProcessPriority
                        $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'extraction_result' -NotePropertyValue $extractionResult -Force
                        if (-not [bool]$extractionResult.ok) {
                            $preserveEncodeReady = $false
                            $preserveFailureReason = [string]$extractionResult.reason
                            $preserveFailureCode = if ([string]::IsNullOrWhiteSpace([string]$extractionResult.error_code)) { 'DYNAMIC_HDR_EXTRACTION_RESULT_MISSING' } else { [string]$extractionResult.error_code }
                        }
                    }

                    if ($preserveEncodeReady) {
                        $x265Artifacts = Resolve-DynamicHdrX265ArtifactPaths -ExtractionResult $extractionResult -BaseDirectory $script:processingDir
                        $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'x265_artifacts' -NotePropertyValue $x265Artifacts -Force
                        if (-not [bool]$x265Artifacts.ok) {
                            $preserveEncodeReady = $false
                            $preserveFailureReason = [string]$x265Artifacts.reason
                            $preserveFailureCode = if ([string]::IsNullOrWhiteSpace([string]$x265Artifacts.error_code)) { 'DYNAMIC_HDR_X265_PATH_UNREPRESENTABLE' } else { [string]$x265Artifacts.error_code }
                        }
                    }

                    if ($preserveEncodeReady) {
                        $dynamicHdrForceCpuEncode = $true
                        $dynamicHdrWorkingDirectory = $script:processingDir
                        $dynamicHdrTempFiles = @((Get-DynamicHdrResultValue -Result $extractionResult -Name 'temp_files'))
                        $dynamicHdrDolbyVisionRpuPath = [string](Get-DynamicHdrResultValue -Result $x265Artifacts -Name 'dolby_vision_rpu_path')
                        $dynamicHdrDolbyVisionTargetProfile = [string](Get-DynamicHdrResultValue -Result $x265Artifacts -Name 'target_dovi_profile')
                        $dynamicHdrHdr10PlusJsonPath = [string](Get-DynamicHdrResultValue -Result $x265Artifacts -Name 'hdr10plus_json_path')
                        $script:CurrentDynamicHdrEvidence.outcome = 'will_preserve_encode'
                        $script:CurrentDynamicHdrEvidence.policy_reason = 'dynamic HDR metadata extracted and ready for CPU/libx265 encode preservation'
                        Write-Log "DYNAMIC HDR: preservation artifacts extracted; forcing CPU/libx265 encode for $($script:CurrentDynamicHdrEvidence.summary)"
                        Write-PipelineEvent -EventType 'dynamic_hdr_preservation_prepare' -Stage 'encode_prepare' -Route 'encode-cpu-fallback' -Status 'succeeded' -SourcePath $file.FullName -Data @{
                            policy                    = $dynamicHdrPolicy
                            summary                   = [string]$script:CurrentDynamicHdrEvidence.summary
                            dolby_vision_rpu_path     = $dynamicHdrDolbyVisionRpuPath
                            dolby_vision_profile      = $dynamicHdrDolbyVisionTargetProfile
                            hdr10plus_json_path       = $dynamicHdrHdr10PlusJsonPath
                            working_directory         = $dynamicHdrWorkingDirectory
                            rpu_frame_count           = [int](Get-DynamicHdrResultValue -Result $x265Artifacts -Name 'rpu_frame_count')
                        } | Out-Null
                    } else {
                        $script:CurrentDynamicHdrEvidence.policy_reason = $preserveFailureReason
                        $script:CurrentDynamicHdrEvidence.policy_reason_code = $preserveFailureCode
                        Write-PipelineEvent -EventType 'dynamic_hdr_preservation_prepare' -Stage 'encode_prepare' -Route 'encode' -Status 'failed' -SourcePath $file.FullName -Data @{
                            policy      = $dynamicHdrPolicy
                            action      = 'preserve_encode'
                            reason_code = $preserveFailureCode
                            reason      = $preserveFailureReason
                            summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                        } | Out-Null
                        if ($dynamicHdrPolicy -eq 'preserve_or_review') {
                            $script:CurrentDynamicHdrEvidence.outcome = 'blocked_review'
                            Write-Log "DYNAMIC HDR: encode preservation failed under preserve_or_review; routing source to review: $preserveFailureReason" "ERROR"
                            $failureProperties = [ordered]@{
                                dynamic_hdr_policy      = $dynamicHdrPolicy
                                dynamic_hdr_action      = 'preserve_encode'
                                dynamic_hdr_reason_code = $preserveFailureCode
                                dynamic_hdr_summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                                dynamic_hdr_reasons     = @($preserveFailureReason)
                            }
                            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $preserveFailureReason -Stage 'dynamic-hdr-extraction' -ErrorCode $preserveFailureCode -SuggestedAction 'Inspect Dynamic HDR extraction tool output, mkvmerge track mapping, and source metadata. preserve_or_review blocks publish until Dolby Vision/HDR10+ extraction and x265 injection can be validated.' -AdditionalProperties $failureProperties
                            $localIn = $null
                            return $false
                        }
                        $script:CurrentDynamicHdrEvidence.outcome = 'preserve_encode_failed_try_remux'
                        $script:CurrentDynamicHdrEvidence.policy_action = 'prefer_remux'
                        $script:CurrentDynamicHdrEvidence.recommended_route = 'remux'
                        Write-Log "DYNAMIC HDR: encode preservation failed under preserve_or_remux; attempting remux fallback before any lossy encode: $preserveFailureReason" "WARN"
                    }
                }

                if ([bool]$dynamicHdrEncodeDecision.should_hold_review) {
                    $script:CurrentDynamicHdrEvidence.outcome = 'blocked_review'
                    Write-Log ("DYNAMIC HDR: preserve policy requires review before encode publishes '{0}': {1}" -f $script:CurrentDynamicHdrEvidence.summary, $dynamicHdrEncodeDecision.reason) "ERROR"
                    Write-PipelineEvent -EventType 'dynamic_hdr_policy_review' -Stage 'encode_prepare' -Route 'encode' -Status 'blocked' -SourcePath $file.FullName -Data @{
                        policy      = $dynamicHdrPolicy
                        action      = [string]$dynamicHdrEncodeDecision.action
                        reason_code = [string]$dynamicHdrEncodeDecision.reason_code
                        summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                    } | Out-Null
                    $failureProperties = [ordered]@{
                        dynamic_hdr_policy      = $dynamicHdrPolicy
                        dynamic_hdr_action      = [string]$dynamicHdrEncodeDecision.action
                        dynamic_hdr_reason_code = [string]$dynamicHdrEncodeDecision.reason_code
                        dynamic_hdr_summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                        dynamic_hdr_reasons     = @($dynamicHdrEncodeDecision.reasons)
                    }
                    $failureErrorCode = if ([string]::IsNullOrWhiteSpace([string]$dynamicHdrEncodeDecision.error_code)) { 'DYNAMIC_HDR_UNPRESERVABLE' } else { [string]$dynamicHdrEncodeDecision.error_code }
                    $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$dynamicHdrEncodeDecision.reason) -Stage 'dynamic-hdr-policy' -ErrorCode $failureErrorCode -SuggestedAction 'Use preserve_or_remux for remux-safe sources, switch DynamicHdrPolicy to warn to allow static-HDR10 encode loss intentionally, or provide validated Dynamic HDR tools/capability before retrying preserve_or_review.' -AdditionalProperties $failureProperties
                    $localIn = $null
                    return $false
                }

                $shouldTryDynamicHdrRemux = ([bool]$dynamicHdrEncodeDecision.should_prefer_remux -or ([string]$script:CurrentDynamicHdrEvidence.policy_action -eq 'prefer_remux'))
                if ($shouldTryDynamicHdrRemux) {
                    $savedDynamicHdrEvidence = $script:CurrentDynamicHdrEvidence
                    $originalRoutePlan = $script:CurrentRoutePlan
                    $originalRouteReasonCode = [string]$script:CurrentRouteReasonCode
                    $originalRouteReason = [string]$script:CurrentRouteReason
                    $script:CurrentRouteReasonCode = 'dynamic_hdr_prefer_remux'
                    $script:CurrentRouteReason = "Dynamic HDR preserve policy prefers remux before lossy encode: $($script:CurrentDynamicHdrEvidence.summary)"
                    Write-Log "DYNAMIC HDR: attempting remux fallback before encode because policy '$dynamicHdrPolicy' should preserve $($script:CurrentDynamicHdrEvidence.summary)" "WARN"
                    Write-PipelineEvent -EventType 'dynamic_hdr_policy_remux_fallback' -Stage 'encode_prepare' -Route 'remux' -Status 'started' -SourcePath $file.FullName -Data @{
                        policy      = $dynamicHdrPolicy
                        action      = [string]$script:CurrentDynamicHdrEvidence.policy_action
                        reason_code = [string]$script:CurrentDynamicHdrEvidence.policy_reason_code
                        summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                    } | Out-Null
                    $script:LastDynamicHdrRemuxFallbackRejection = $null
                    $dynamicHdrRemuxOk = Do-Remux $file $isTV $tvInfo -FallbackFromDynamicHdrEncode
                    if ($dynamicHdrRemuxOk) {
                        $localIn = $null
                        return $true
                    }
                    if (-not $script:LastDynamicHdrRemuxFallbackRejection) {
                        $localIn = $null
                        return $false
                    }
                    $script:CurrentDynamicHdrEvidence = $savedDynamicHdrEvidence
                    $script:CurrentRoutePlan = $originalRoutePlan
                    $script:CurrentRouteReasonCode = $originalRouteReasonCode
                    $script:CurrentRouteReason = $originalRouteReason
                    $script:CurrentDynamicHdrEvidence.outcome = 'will_drop_encode_remux_blocked'
                    $script:CurrentDynamicHdrEvidence.policy_reason = "remux fallback was blocked: $($script:LastDynamicHdrRemuxFallbackRejection.reason)"
                    Write-Log "DYNAMIC HDR: remux fallback blocked; preserve_or_remux allows encode to continue with dynamic metadata drop warning: $($script:LastDynamicHdrRemuxFallbackRejection.reason)" "WARN"
                    Write-PipelineEvent -EventType 'dynamic_hdr_policy_remux_fallback' -Stage 'encode_prepare' -Route 'remux' -Status 'blocked' -SourcePath $file.FullName -Data @{
                        policy      = $dynamicHdrPolicy
                        action      = [string]$script:CurrentDynamicHdrEvidence.policy_action
                        reason_code = [string]$script:CurrentDynamicHdrEvidence.policy_reason_code
                        summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                        block_code  = [string]$script:LastDynamicHdrRemuxFallbackRejection.reason_code
                    } | Out-Null
                }

                if (-not $dynamicHdrForceCpuEncode) {
                    Write-Log ("ENCODE: source carries dynamic HDR metadata ({0}) - it will be DROPPED by this encode (static HDR10 only)" -f $script:CurrentDynamicHdrEvidence.summary) "WARN"
                    Write-PipelineEvent -EventType 'dynamic_hdr_metadata_dropped' -Stage 'encode_prepare' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                        dovi_present      = [bool]$script:CurrentDynamicHdrEvidence.dovi_present
                        dovi_profile      = [int]$script:CurrentDynamicHdrEvidence.dovi_profile
                        hdr10plus_present = [bool]$script:CurrentDynamicHdrEvidence.hdr10plus_present
                        summary           = [string]$script:CurrentDynamicHdrEvidence.summary
                        outcome           = [string]$script:CurrentDynamicHdrEvidence.outcome
                        probe_error       = [string]$script:CurrentDynamicHdrEvidence.probe_error
                        policy            = $dynamicHdrPolicy
                        policy_action     = [string]$script:CurrentDynamicHdrEvidence.policy_action
                        policy_reason     = [string]$script:CurrentDynamicHdrEvidence.policy_reason
                    } | Out-Null
                }
            }
        } elseif ($isHDR) {
            Write-Log "ENCODE: DynamicHdrPolicy=off; skipping Dynamic HDR probes and preservation routing" "DEBUG"
        }
        $usingCpu    = $false
        $usingSafeRetry = $false
        $globalTitle = "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
        $recordEncodeAttempt = {
            param($Plan, [bool]$Succeeded)
            # D3 fix — record CPU-specific context per attempt so sidecar
            # consumers (analytics, diagnostics drawer) can correlate preset
            # / timeout / priority with success rate and elapsed time.
            # cpu_* fields are only meaningful for CPU attempts; GPU / safe
            # rows get empty/zero defaults so the schema stays uniform.
            $cpuPresetField = if ($Plan.PSObject.Properties['CpuPreset']) { [string]$Plan.CpuPreset } else { '' }
            $cpuTimeoutField = if ([bool]$Plan.UseCpuFallback) { [int]$script:FFmpegCpuEncodeTimeoutSeconds } else { 0 }
            $cpuPriorityField = if ([bool]$Plan.UseCpuFallback) { [string]$script:CpuEncodeProcessPriority } else { '' }
            $script:CurrentEncodeAttempts = @(@($script:CurrentEncodeAttempts) + ([ordered]@{
                attempt              = [string]$Plan.Attempt
                route                = [string]$Plan.Route
                label                = [string]$Plan.Label
                success              = [bool]$Succeeded
                used_cpu             = [bool]$Plan.UseCpuFallback
                safe_retry           = [bool]$Plan.UseSafeHardwareRetry
                repro_stage          = [string]$Plan.ReproStage
                encode_ladder        = [string]$Plan.EncodeLadder
                selected_encoder     = [string]$Plan.SelectedEncoder
                encoder_kind         = [string]$Plan.EncoderKind
                selected_gpu_device  = [string]$Plan.SelectedGpuDevice
                cpu_preset           = $cpuPresetField
                cpu_timeout_seconds  = $cpuTimeoutField
                cpu_process_priority = $cpuPriorityField
            }))
        }

        if ($isHDR) { Write-Log "ENCODE: HDR detected - Main10 / BT.2020" }
        else        { Write-Log "ENCODE: SDR - Main profile" }

        Set-ProgressStage -Stage 'encode_prepare' -Status $script:pipelineStatus -Route 'encode' -CopyState 'complete' -Percent 0 -SaveNow
        try {
            $audioArgs = Build-AudioArgs $localIn
        } catch {
            $reason = [string]$_.Exception.Message
            $errorCode = if ($reason -match 'SOURCE_MEDIA_AUDIO_MISSING') { 'SOURCE_MEDIA_AUDIO_MISSING' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_INVALID') { 'SOURCE_MEDIA_AUDIO_INVALID' } elseif ($reason -match 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') { 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED' } else { 'AUDIO_ARGUMENT_BUILD_FAILED' }
            $classification = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') { 'permanent' } else { 'transient' }
            $suggestedAction = if ($errorCode -eq 'SOURCE_MEDIA_AUDIO_MISSING') {
                'Replace the source with a media file that contains at least one audio stream, or add an explicit no-audio workflow before retrying.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_INVALID') {
                'Inspect ffprobe audio stream metadata and confirm the source file is complete; retry after replacing or repairing the source.'
            } elseif ($errorCode -eq 'SOURCE_MEDIA_AUDIO_METADATA_PROBE_FAILED') {
                'Inspect ffprobe audio stream JSON and confirm the source is fully copied/unlocked; retry after repairing or replacing the source.'
            } else {
                'Inspect ffprobe audio output and the pipeline log; retry after correcting the source or tool failure.'
            }
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $classification -Reason $reason -Stage 'audio-probe' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
            $localIn = $null
            return $false
        }
        $defaultAudioLang = Get-DefaultAudioLang $localIn
        $subFilter        = Filter-SubtitleStreams $localIn "ENCODE: " -OriginalSourcePath $file.FullName
        if ($subFilter.ProbeFailed) {
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently encode with unknown subtitle state.' | Out-Null
            $localIn = $null
            return $false
        }
        $subResult        = Build-SubtitleArgsForFFmpeg $subFilter $defaultAudioLang $localIn "ENCODE: "
        if ($subResult.Failures -and @($subResult.Failures).Count -gt 0) {
            Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subResult.Failures) -Stage 'subtitle-extract'
            $localIn = $null
            return $false
        }

        # Attempt 1 uses the configured GPU-first encoder. Retry policy and
        # CPU fallback command construction live in ops\pipeline\engine\decide\encode_policy.ps1.
        # Suggestion #2 — when the cached NVENC probe says GPU is
        # unavailable (set by Invalidate-NvencAvailableProbe after an
        # earlier runtime NVENC failure), skip the primary AND safe-retry
        # attempts entirely. Saves ~10–60 s per file on a no-GPU machine.
        $skipGpuDueToProbe = if ($dynamicHdrForceCpuEncode) { $true } else { -not (Test-NvencProbeReportsAvailable) }
        if ($dynamicHdrForceCpuEncode) {
            Write-Log "ENCODE: Dynamic HDR preservation requires CPU/libx265; skipping GPU-first ladder" "WARN"
            Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                from_encoder = [string]$VideoCodec
                to_encoder   = (Get-MediaVideoCodecLibx265Name)
                reason       = [string]$script:CurrentDynamicHdrEvidence.policy_reason
                trigger      = 'dynamic_hdr_preserve_encode'
                cpu_preset   = [string]$script:CpuEncodePreset
                is_hdr       = [bool]$isHDR
            } | Out-Null
        } elseif ($skipGpuDueToProbe) {
            $probeReason = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.Reason) { [string]$script:NvencAvailableProbe.Reason } else { 'NVENC probe cache reports unavailable' }
            Write-Log "ENCODE: NVENC unavailable per cached probe ($probeReason); skipping GPU-first ladder and going straight to CPU" "WARN"
            Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                from_encoder = 'cached_unavailable'
                to_encoder   = (Get-MediaVideoCodecLibx265Name)
                reason       = $probeReason
                trigger      = 'nvenc_probe_unavailable'
                cpu_preset   = [string]$script:CpuEncodePreset
                is_hdr       = [bool]$isHDR
            } | Out-Null
        }

        $tempOut    = Join-Path $script:processingDir "encode_temp_$([guid]::NewGuid().ToString('N')).$OutputContainer"
        $encodePlan = New-EncodeAttemptPlan `
            -UseCpuFallback:$false `
            -IsTV:$isTV `
            -IsHDR:$isHDR `
            -InputPath $localIn `
            -ExtraInputs $subResult.ExtraInputs `
            -GlobalTitle $globalTitle `
            -AudioArgs $audioArgs `
            -SubtitleMapArgs $subResult.MapArgs `
            -VideoFilterArgs $subResult.VideoFilterArgs `
            -OutputPath $tempOut `
            -VideoCodec $VideoCodec `
            -VideoPreset $VideoPreset `
            -VideoQuality $VideoQuality `
            -ExtraVideoFlags $ExtraVideoFlags `
            -FallbackCpuQuality $script:FallbackCpuQuality `
            -EncodeLadder $script:EncodeLadder `
            -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll
        $ffArgs     = @($encodePlan.ArgumentList)

        $nullCount = @($ffArgs | Where-Object { $null -eq $_ }).Count
        if ($nullCount -gt 0) {
            Write-Log "ENCODE: $nullCount null element(s) in FFmpeg args - aborting" "ERROR"
            return $false
        }

        $routeIntentReasonCode = Get-CurrentEncodeRouteIntentReasonCode
        $wasteGuardContext = New-EncodeWasteGuardContext `
            -SourcePath $localIn `
            -OutputPath $tempOut `
            -RouteReasonCode ([string]$script:CurrentRouteReasonCode) `
            -RouteIntentReasonCode $routeIntentReasonCode `
            -UseCpuFallback:$false
        if ([bool]$wasteGuardContext.Enabled -and -not $skipGpuDueToProbe) {
            $preflight = Invoke-EncodeWasteGuardPreflight `
                -SourcePath $localIn `
                -OutputContainer $OutputContainer `
                -EncodePlan $encodePlan `
                -VideoFilterArgs $subResult.VideoFilterArgs `
                -WasteGuardContext $wasteGuardContext `
                -SourceFile $file
            if ([bool]$preflight.ShouldFallbackRemux) {
                $fallbackResult = Invoke-EncodeWasteGuardRemuxFallback `
                    -SourceFile $file `
                    -ScratchPath $localIn `
                    -IsTV:$isTV `
                    -TvInfo $tvInfo `
                    -WasteGuardContext $wasteGuardContext `
                    -Projection $preflight.Projection `
                    -Trigger 'preflight_projection' `
                    -Message ([string]$preflight.Message)
                if ([bool]$fallbackResult.Ok) {
                    if ([bool]$fallbackResult.KeepScratchInput) { $localIn = $null }
                    return $true
                }
                $localIn = $null
                return $false
            }
        }

        if ($skipGpuDueToProbe) {
            # Don't burn an ffmpeg launch for the primary GPU attempt;
            # synthesize the failure state so the existing fallback
            # branch fires and falls into the CPU path below.
            $success = $false
            $script:LastFFmpegStderr = if ($dynamicHdrForceCpuEncode) { 'Dynamic HDR preservation requires CPU/libx265; primary GPU attempt skipped' } else { 'NVENC probe cache reports unavailable; primary GPU attempt skipped' }
            $script:LastFFmpegExit = 1
        } else {
            $success = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -OutputPath $tempOut -WasteGuardContext $wasteGuardContext
            & $recordEncodeAttempt $encodePlan ([bool]$success)
        }

        if (-not $success -and [string]$script:LastFFmpegAbortCode -eq 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE') {
            $fallbackMessage = [string]$script:LastFFmpegAbortReason
            if ([string]::IsNullOrWhiteSpace($fallbackMessage)) {
                $fallbackMessage = 'live encode projection exceeded waste guard threshold'
            }
            $fallbackResult = Invoke-EncodeWasteGuardRemuxFallback `
                -SourceFile $file `
                -ScratchPath $localIn `
                -IsTV:$isTV `
                -TvInfo $tvInfo `
                -WasteGuardContext $wasteGuardContext `
                -Projection $script:LastEncodeWasteGuardProjection `
                -Trigger 'live_projection' `
                -Message $fallbackMessage
            if ([bool]$fallbackResult.Ok) {
                if ([bool]$fallbackResult.KeepScratchInput) { $localIn = $null }
                return $true
            }
            $localIn = $null
            return $false
        }

        if (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
            if (-not $skipGpuDueToProbe) {
                Write-Log "ENCODE: hardware encoder failure detected - retrying once with compatibility flags before CPU fallback" "WARN"
            }
            if (Test-Path -LiteralPath $tempOut) {
                Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
            }
            $tempOut    = Join-Path $script:processingDir "encode_temp_safe_$([guid]::NewGuid().ToString('N')).$OutputContainer"
            if (-not $skipGpuDueToProbe) {
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$false `
                    -UseSafeHardwareRetry:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -VideoFilterArgs $subResult.VideoFilterArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                    -CpuMaxThreads $script:CpuEncodeMaxThreads `
                    -Hdr10MasterDisplay $hdr10MasterDisplay `
                    -Hdr10MaxCll $hdr10MaxCll
                $ffArgs     = @($encodePlan.ArgumentList)
                if ($wasteGuardContext) {
                    $wasteGuardContext.OutputPath = $tempOut
                }
                $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -OutputPath $tempOut -WasteGuardContext $wasteGuardContext
                & $recordEncodeAttempt $encodePlan ([bool]$success)
            } else {
                # GPU is already known unavailable; don't even build the
                # safe-retry plan. Force the inner gate to fall straight
                # into the CPU branch.
                $success = $false
                $script:LastFFmpegStderr = if ($dynamicHdrForceCpuEncode) { 'Dynamic HDR preservation requires CPU/libx265; safe-retry skipped' } else { 'NVENC probe cache reports unavailable; safe-retry skipped' }
                $script:LastFFmpegExit = 1
            }
            if (-not $success -and [string]$script:LastFFmpegAbortCode -eq 'ENCODE_WASTE_GUARD_PROJECTED_OVERSIZE') {
                $fallbackMessage = [string]$script:LastFFmpegAbortReason
                if ([string]::IsNullOrWhiteSpace($fallbackMessage)) {
                    $fallbackMessage = 'live encode projection exceeded waste guard threshold'
                }
                $fallbackResult = Invoke-EncodeWasteGuardRemuxFallback `
                    -SourceFile $file `
                    -ScratchPath $localIn `
                    -IsTV:$isTV `
                    -TvInfo $tvInfo `
                    -WasteGuardContext $wasteGuardContext `
                    -Projection $script:LastEncodeWasteGuardProjection `
                    -Trigger 'live_projection_safe_retry' `
                    -Message $fallbackMessage
                if ([bool]$fallbackResult.Ok) {
                    if ([bool]$fallbackResult.KeepScratchInput) { $localIn = $null }
                    return $true
                }
                $localIn = $null
                return $false
            }
            if ($success) {
                $usingSafeRetry = $true
                $script:CurrentRouteReasonCode = 'hardware_encoder_safe_retry_succeeded'
                $script:CurrentRouteReason = 'hardware encoder failed with primary flags; compatibility retry succeeded'
            } elseif (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
                # Suggestion #2 — second NVENC failure in this file means
                # the GPU is genuinely sick (driver hang, eGPU disconnect,
                # VRAM exhausted, etc.). Invalidate the probe cache so
                # the NEXT file goes straight to CPU instead of repeating
                # primary + safe-retry just to fail twice more. Skip when
                # we already came in via $skipGpuDueToProbe.
                if (-not $skipGpuDueToProbe) {
                    $invalidateReason = if ($script:LastFFmpegStderr) {
                        $tail = ($script:LastFFmpegStderr -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -Last 1)
                        "GPU primary + safe-retry both failed: $tail"
                    } else {
                        'GPU primary + safe-retry both failed'
                    }
                    Invalidate-NvencAvailableProbe -Reason $invalidateReason -SourcePath $file.FullName
                }
                if ($dynamicHdrForceCpuEncode) {
                    Write-Log "ENCODE: Dynamic HDR preservation continuing with $(Get-MediaVideoCodecLibx265Name) (CRF $($script:FallbackCpuQuality), preset $script:CpuEncodePreset, timeout $($script:FFmpegCpuEncodeTimeoutSeconds)s, priority $script:CpuEncodeProcessPriority)" "WARN"
                } else {
                    Write-Log "ENCODE: compatibility retry also failed - falling back to $(Get-MediaVideoCodecLibx265Name) (CRF $($script:FallbackCpuQuality), preset $script:CpuEncodePreset, timeout $($script:FFmpegCpuEncodeTimeoutSeconds)s, priority $script:CpuEncodeProcessPriority)" "WARN"
                }
                # Emit a structured event so the desktop diagnostics drawer
                # and the Live tab can light up a CPU-fallback indicator
                # instead of the operator only seeing a log line.
                Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                    from_encoder         = [string]$VideoCodec
                    to_encoder           = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset           = [string]$script:CpuEncodePreset
                    cpu_quality_crf      = [int]$script:FallbackCpuQuality
                    cpu_timeout_seconds  = [int]$script:FFmpegCpuEncodeTimeoutSeconds
                    cpu_process_priority = [string]$script:CpuEncodeProcessPriority
                    is_hdr               = [bool]$isHDR
                    dynamic_hdr          = [bool]$dynamicHdrForceCpuEncode
                } | Out-Null
                if (Test-Path -LiteralPath $tempOut) {
                    Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
                }
                $tempOut    = Join-Path $script:processingDir "encode_temp_cpu_$([guid]::NewGuid().ToString('N')).$OutputContainer"
                # F-new-1 — re-validate scratch space with the CPU-aware
                # multiplier *before* the (potentially multi-hour) libx265
                # run. The original pre-flight at the top of Do-Encode used
                # the default 0.7x NVENC ratio, which can green-light an
                # encode that would actually fill the scratch volume at
                # 95% with libx265 output.
                if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE-CPU" -IsCpuEncode)) {
                    Write-Log "ENCODE-CPU: insufficient scratch space for CPU-fallback encode — aborting before libx265 starts" "ERROR"
                    Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for CPU-fallback encode' -Stage 'encode' -ErrorCode 'ENCODE_CPU_INSUFFICIENT_SPACE' -SuggestedAction 'Free additional space on the scratch volume or lower CpuEncodePreset/FallbackCpuQuality before retrying. CPU encodes need 1:1 source-size headroom because libx265 output is typically larger than NVENC.' | Out-Null
                    $localIn = $null
                    return $false
                }
                $encodePlan = New-EncodeAttemptPlan `
                    -UseCpuFallback:$true `
                    -IsTV:$isTV `
                    -IsHDR:$isHDR `
                    -InputPath $localIn `
                    -ExtraInputs $subResult.ExtraInputs `
                    -GlobalTitle $globalTitle `
                    -AudioArgs $audioArgs `
                    -SubtitleMapArgs $subResult.MapArgs `
                    -VideoFilterArgs $subResult.VideoFilterArgs `
                    -OutputPath $tempOut `
                    -VideoCodec $VideoCodec `
                    -VideoPreset $VideoPreset `
                    -VideoQuality $VideoQuality `
                    -ExtraVideoFlags $ExtraVideoFlags `
                    -FallbackCpuQuality $script:FallbackCpuQuality `
                    -EncodeLadder $script:EncodeLadder `
                    -CpuPreset $script:CpuEncodePreset `
                    -CpuMaxThreads $script:CpuEncodeMaxThreads `
                    -Hdr10MasterDisplay $hdr10MasterDisplay `
                    -Hdr10MaxCll $hdr10MaxCll `
                    -DolbyVisionRpuPath $dynamicHdrDolbyVisionRpuPath `
                    -DolbyVisionTargetProfile $dynamicHdrDolbyVisionTargetProfile `
                    -Hdr10PlusJsonPath $dynamicHdrHdr10PlusJsonPath
                $ffArgs     = @($encodePlan.ArgumentList)
                # Differentiate the GUI status string. app/status/service.py renders
                # `encode_cpu` with its own label, but the user-facing status
                # text (currentStatus) is also surfaced verbatim in the live
                # tile and the taskbar tooltip; keep it explicit so the
                # operator immediately knows this is a multi-hour CPU run.
                $cpuStatusText = if ($isTV) { "Encoding TV (CPU fallback)" } else { "Encoding Movie (CPU fallback)" }
                # F-new-4 — serialize CPU encodes machine-wide. If another
                # pipeline process on this box is already running libx265,
                # show the operator that we're queued behind it instead of
                # silently double-saturating the cores.
                $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
                if (-not $cpuMutexLock.Acquired) {
                    Write-Log "ENCODE-CPU: another CPU encode is already in progress on this machine; waiting for it to finish ($($cpuMutexLock.Reason))" "WARN"
                    Set-ProgressStage -Stage 'encode_cpu' -Status "Waiting for CPU encode slot" -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                    $script:pipelineStatus = "Waiting for CPU encode slot"
                    # Wait up to the CPU encode timeout for the slot. Worst
                    # case the prior holder times out and releases.
                    $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds
                }
                if (-not $cpuMutexLock.Acquired) {
                    $reason = "ENCODE-CPU: CPU encode mutex was not acquired after waiting $($script:FFmpegCpuEncodeTimeoutSeconds) seconds; refusing to start overlapping CPU fallback"
                    Write-Log $reason "ERROR"
                    $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode-cpu-mutex' -ErrorCode 'ENCODE_CPU_MUTEX_UNAVAILABLE' -SuggestedAction 'Wait for the existing CPU encode to finish, inspect stale mutex ownership if no encode is running, then retry.'
                    $localIn = $null
                    return $false
                }
                Set-ProgressStage -Stage 'encode_cpu' -Status $cpuStatusText -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                $script:pipelineStatus = $cpuStatusText
                try {
                    # CPU encodes get their own (typically larger) timeout
                    # so a slow libx265 run is not killed at the 6-hour
                    # GPU ceiling.
                    $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -CpuEncode -ProcessPriority $script:CpuEncodeProcessPriority -WorkingDirectory $dynamicHdrWorkingDirectory
                } finally {
                    if ($cpuMutexLock -and $cpuMutexLock.Acquired) { & $cpuMutexLock.Release }
                }
                & $recordEncodeAttempt $encodePlan ([bool]$success)
                if ($success) {
                    $usingCpu = $true
                    # E1 fix — keep the script-scope route state in sync with
                    # the actual encoder used. The size-policy guard (and any
                    # other consumer that reads CurrentRouteReasonCode during
                    # verify) needs to see the correct reason so CPU outputs
                    # receive the compatibility growth budget, not the strict 5%.
                    # Suggestion #2 — distinguish "GPU known unavailable per
                    # cached probe" from "GPU was actually attempted and
                    # failed for this file".  Both still use the
                    # encode-cpu-fallback route, but the reason code lets
                    # diagnostics show why GPU was skipped.
                    if ($dynamicHdrForceCpuEncode) {
                        $script:CurrentRouteReasonCode = 'dynamic_hdr_preserve_cpu_encode'
                        $script:CurrentRouteReason     = "Dynamic HDR preservation required CPU/libx265 encode: $($script:CurrentDynamicHdrEvidence.summary)"
                        $script:CurrentDynamicHdrEvidence.outcome = 'preserved_encode'
                    } elseif ($skipGpuDueToProbe) {
                        $script:CurrentRouteReasonCode = 'gpu_unavailable_cpu_only'
                        $script:CurrentRouteReason     = 'NVENC unavailable per cached probe; CPU encode without trying GPU'
                    } else {
                        $script:CurrentRouteReasonCode = 'hardware_encoder_cpu_fallback'
                        $script:CurrentRouteReason     = 'hardware encoder failed; CPU fallback succeeded'
                    }
                    # E3 fix — mutate route_actions.video to 'encode_software'
                    # immediately on CPU success.  If a later verify/size-guard
                    # step rejects this output, the failure sidecar still has
                    # the correct encoder kind instead of the stale planned
                    # 'encode_hardware' label.
                    if ($script:CurrentRoutePlan -and $script:CurrentRoutePlan.PSObject.Properties['Actions']) {
                        $actions = $script:CurrentRoutePlan.Actions
                        if ($actions -is [System.Collections.IDictionary]) {
                            $actions['video'] = 'encode_software'
                        } else {
                            $videoProp = $actions.PSObject.Properties['video']
                            if ($videoProp) { $videoProp.Value = 'encode_software' }
                        }
                    }
                    # E5 paired event — operators correlating fallback start
                    # with completion get an explicit success record instead
                    # of inferring it from a later tool_completed.
                    Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'succeeded' -SourcePath $file.FullName -Data @{
                        from_encoder    = [string]$VideoCodec
                        to_encoder      = (Get-MediaVideoCodecLibx265Name)
                        cpu_preset      = [string]$encodePlan.CpuPreset
                        cpu_quality_crf = [int]$script:FallbackCpuQuality
                        dynamic_hdr     = [bool]$dynamicHdrForceCpuEncode
                    } | Out-Null
                }
            }
        }

        if (-not $success) {
            $reproStage = if ($encodePlan -and $encodePlan.ReproStage) { [string]$encodePlan.ReproStage } elseif ($usingCpu) { 'encode-cpu' } else { 'encode' }
            $reproPath = $script:LastFFmpegReproPath
            $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
            $errorCode = Get-FFmpegFailureCode -Stage $reproStage -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
            # Encoder-aware reason / suggestion text. The previous text always
            # blamed NVENC even when the failed attempt was the CPU fallback,
            # which sent operators chasing the wrong root cause.
            $failedEncoderKind = if ($encodePlan -and $encodePlan.EncoderKind) { [string]$encodePlan.EncoderKind } elseif ($usingCpu) { 'cpu' } else { 'unknown' }
            $reasonPrefix = switch ($failedEncoderKind) {
                'cpu'   { 'FFmpeg CPU encode failed' }
                'nvenc' { 'FFmpeg NVENC encode failed' }
                default { 'FFmpeg encode failed' }
            }
            $reason = if ($ffmpegErrorSummary) { "${reasonPrefix}: $ffmpegErrorSummary" } else { $reasonPrefix }
            $suggestedAction = if ($failedEncoderKind -eq 'cpu') {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. The libx265 CPU fallback failed, so re-tuning NVENC will not help; check for source corruption, libx265 OOM (lower the preset or quality), or an x265 build issue."
            } else {
                "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. If NVENC was unstable, compare against the CPU fallback behavior."
            }
            # D2 fix — CPU failures are recorded as 'transient' just like
            # NVENC failures. Register-SourceFailure already escalates to
            # 'operator_required' after $TransientFailureRetryLimit repeated
            # same-(stage,error_code) failures (see ops\pipeline\engine\failures\failure_state.ps1
            # ~line 670). That gives a CPU job N retry chances for
            # genuinely transient errors (antivirus locks, transient OOM,
            # disk full near end), then escalates exactly once instead of
            # the previous "first failure is permanent" behavior.
            # Emit the matching encoder_fallback_completed event so the
            # diagnostics drawer can pair start with end (E5).
            if ($failedEncoderKind -eq 'cpu') {
                if ($dynamicHdrForceCpuEncode -and $script:CurrentDynamicHdrEvidence) {
                    $script:CurrentDynamicHdrEvidence.outcome = 'preserve_encode_failed'
                }
                Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'failed' -SourcePath $file.FullName -Data @{
                    from_encoder    = [string]$VideoCodec
                    to_encoder      = (Get-MediaVideoCodecLibx265Name)
                    cpu_preset      = if ($encodePlan -and $encodePlan.PSObject.Properties['CpuPreset']) { [string]$encodePlan.CpuPreset } else { '' }
                    cpu_quality_crf = [int]$script:FallbackCpuQuality
                    error_code      = [string]$errorCode
                    dynamic_hdr     = [bool]$dynamicHdrForceCpuEncode
                } | Out-Null
            }
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
            $localIn = $null
            Write-Log "ENCODE failed - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        if (-not (Test-Path -LiteralPath $tempOut) -or (Get-Item -LiteralPath $tempOut).Length -eq 0) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE output missing or empty after ffmpeg' -Stage 'encode'
            $localIn = $null
            Write-Log "ENCODE: output missing or empty after ffmpeg" "ERROR"; return $false
        }

        # Duration sanity check — catches silent truncations.
        # AllowAVFallback tolerates the common case where an ASS subtitle cue
        # extends past the actual A/V end, inflating the source container duration.
        # D5 fix — preserve the encode-cpu-fallback route badge through the
        # verify stage so the GUI doesn't briefly drop the CPU label between
        # encode_cpu (100%) and the publish step.
        $verifyRoute = if ($usingCpu) { 'encode-cpu-fallback' } elseif ($usingSafeRetry) { 'encode-safe-retry' } else { 'encode' }
        Set-ProgressStage -Stage 'encode_verify' -Status $script:pipelineStatus -Route $verifyRoute -Percent $null -SaveNow
        if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $tempOut -Label "ENCODE" -AllowAVFallback)) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE duration mismatch' -Stage 'encode-verify' -SuggestedAction 'Compare source and encoded output A/V end times. Container-duration differences caused by subtitle tails are tolerated, so a remaining encode-verify failure usually means the output A/V is genuinely shorter than the source.'
            $localIn = $null
            Write-Log "ENCODE: duration mismatch - recorded as transient and scheduled for retry: $safeName" "ERROR"
            return $false
        }

        if ($dynamicHdrForceCpuEncode -and $script:CurrentDynamicHdrEvidence) {
            Set-ProgressStage -Stage 'encode_verify' -Status "Verifying Dynamic HDR preservation" -Route $verifyRoute -Percent $null -SaveNow
            $expectedRpuFrameCount = 0
            if ($script:CurrentDynamicHdrEvidence.PSObject.Properties['x265_artifacts']) {
                $expectedRpuFrameCount = [int](Get-DynamicHdrResultValue -Result $script:CurrentDynamicHdrEvidence.x265_artifacts -Name 'rpu_frame_count')
            }
            $dynamicHdrVerification = Test-DynamicHdrOutputPreservation -SourceEvidence $script:CurrentDynamicHdrEvidence -OutputPath $tempOut -ExpectedRpuFrameCount $expectedRpuFrameCount
            $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'verification' -NotePropertyValue $dynamicHdrVerification -Force
            Write-PipelineEvent -EventType 'dynamic_hdr_output_verification' -Stage 'encode_verify' -Route $verifyRoute -Status $(if ([bool]$dynamicHdrVerification.ok) { 'succeeded' } else { 'failed' }) -SourcePath $file.FullName -Data $dynamicHdrVerification | Out-Null
            if (-not [bool]$dynamicHdrVerification.ok) {
                $script:CurrentDynamicHdrEvidence.outcome = 'output_verify_failed'
                $verifyErrorCode = if ([string]::IsNullOrWhiteSpace([string]$dynamicHdrVerification.error_code)) { 'DYNAMIC_HDR_OUTPUT_VERIFY_FAILED' } else { [string]$dynamicHdrVerification.error_code }
                $failureProperties = [ordered]@{
                    dynamic_hdr_policy      = [string]$dynamicHdrPolicy
                    dynamic_hdr_action      = 'preserve_encode'
                    dynamic_hdr_reason_code = $verifyErrorCode
                    dynamic_hdr_summary     = [string]$script:CurrentDynamicHdrEvidence.summary
                    dynamic_hdr_verification = $dynamicHdrVerification
                }
                $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$dynamicHdrVerification.reason) -Stage 'dynamic-hdr-output-verify' -ErrorCode $verifyErrorCode -SuggestedAction 'Inspect the encoded temp output with ffprobe, dovi_tool, and hdr10plus_tool. Dynamic HDR preserve mode blocks publish until expected Dolby Vision or HDR10+ metadata is detected in output.' -AdditionalProperties $failureProperties
                $localIn = $null
                Write-Log "DYNAMIC HDR VERIFY: $($dynamicHdrVerification.reason)" "ERROR"
                return $false
            }
            $script:CurrentDynamicHdrEvidence.outcome = 'preserved_encode_verified'
            Write-Log "DYNAMIC HDR VERIFY: expected dynamic metadata detected in encoded output"
        }

        $script:LastQualityVerification = $null
        if ([bool]$script:EnableQualityVerification) {
            Set-ProgressStage -Stage 'encode_verify' -Status "Verifying encode quality ($($script:QualityMetric))" -Route $verifyRoute -Percent $null -SaveNow
            $qualityRecord = Invoke-MediaQualityVerification `
                -ReferencePath $localIn `
                -DistortedPath $tempOut `
                -Metric $script:QualityMetric `
                -SampleMode $script:QualitySampleMode `
                -SampleSeconds $script:QualitySampleSeconds `
                -SampleCount $script:QualitySampleCount `
                -TimeoutSeconds $script:QualityVerifyTimeoutSeconds
            $qualityRecord = Resolve-MediaQualityOutcome `
                -Record $qualityRecord `
                -WarnThreshold $script:QualityWarnThreshold `
                -FailThreshold $script:QualityFailThreshold `
                -FailAction $script:QualityFailAction
            $script:LastQualityVerification = $qualityRecord
            $qualityOutcome = [string]$qualityRecord['outcome']
            Write-PipelineEvent -EventType 'quality_verification' -Stage 'encode-quality-verify' -Route $verifyRoute -Status $qualityOutcome -SourcePath $file.FullName -Data $qualityRecord | Out-Null
            if ([bool]$qualityRecord['block_publish']) {
                $qualityErrorCode = 'ENCODE_QUALITY_BELOW_FLOOR'
                $qualitySuggestedAction = 'Compare the recorded quality score and metric against the configured thresholds; review the encode settings or thresholds before re-encoding or accepting the output.'
                $qualityReason = "ENCODE quality score $($qualityRecord['score']) $($qualityRecord['metric']) is below fail threshold $($qualityRecord['fail_threshold']); output rejected before publish"
                if ($qualityOutcome -in @('error', 'stopped')) {
                    $qualityErrorCode = 'ENCODE_QUALITY_VERIFICATION_FAILED'
                    $toolError = [string]$qualityRecord['tool_error']
                    $qualityReason = if ([string]::IsNullOrWhiteSpace($toolError)) {
                        "ENCODE quality verification $qualityOutcome with no score; output rejected before publish"
                    } else {
                        "ENCODE quality verification $qualityOutcome with no score; output rejected before publish: $toolError"
                    }
                    $qualitySuggestedAction = 'Inspect the quality verifier ffprobe/ffmpeg logs and metric configuration. In block_review mode, verifier errors must be resolved or the mode changed intentionally before publish.'
                }
                $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $qualityReason -Stage 'encode-quality-verify' -ErrorCode $qualityErrorCode -SuggestedAction $qualitySuggestedAction
                $localIn = $null
                Write-Log "ENCODE QUALITY: $qualityReason`: $safeName" "ERROR"
                return $false
            }
            if ($qualityOutcome -in @('warn', 'fail')) {
                Write-Log "ENCODE QUALITY: $qualityOutcome score $($qualityRecord['score']) $($qualityRecord['metric']) for $safeName (warn=$($qualityRecord['warn_threshold']), fail=$($qualityRecord['fail_threshold']), action=$($qualityRecord['fail_action']))" "WARN"
            } elseif ($qualityOutcome -in @('error', 'stopped')) {
                Write-Log "ENCODE QUALITY: verification $qualityOutcome for $safeName; publishing remains fail-open. $($qualityRecord['tool_error'])" "WARN"
            } else {
                Write-Log "ENCODE QUALITY: pass score $($qualityRecord['score']) $($qualityRecord['metric']) for $safeName" "DEBUG"
            }
        }

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
        if ($sizePolicy.Exceeded) {
            $sizePolicySeverity = ([string]$sizePolicy.Severity).ToUpperInvariant()
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" $sizePolicySeverity
        } else {
            Write-Log "ENCODE SIZE: $($sizePolicy.Message)" "DEBUG"
        }
        if (-not $sizePolicy.Ok) {
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$sizePolicy.Message) -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source and routing policy. Use advisory/off size guard, force remux for a compatible source, or adjust encode quality/ladder before retrying.'
            $localIn = $null
            Write-Log "ENCODE: output rejected by strict size policy: $safeName" "ERROR"
            return $false
        }
        if ([bool]$sizePolicy.ShouldFallbackRemux) {
            $originalRoutePlan = $script:CurrentRoutePlan
            $originalRouteReasonCode = [string]$script:CurrentRouteReasonCode
            $originalRouteReason = [string]$script:CurrentRouteReason
            $originalSizePolicyResult = $script:CurrentSizePolicyResult
            Write-Log "ENCODE SIZE: attempting remux fallback for oversized automatic size/bitrate-threshold encode; direct-copy size/bitrate caps are bypassed for this fallback" "WARN"
            $fallbackRemuxOk = Do-Remux $file $isTV $tvInfo -FallbackFromOversizedEncode
            if ($fallbackRemuxOk) {
                Write-Log "ENCODE SIZE: remux fallback published; rejected oversized encode temp output will be deleted" "WARN"
                if ($script:LastPublishResult -and $script:LastPublishResult.KeepScratchInput) { $localIn = $null }
                return $true
            }
            $script:CurrentRoutePlan = $originalRoutePlan
            $script:CurrentRouteReasonCode = $originalRouteReasonCode
            $script:CurrentRouteReason = $originalRouteReason
            $script:CurrentSizePolicyResult = $originalSizePolicyResult
            $fallbackFailureReason = Add-RemuxFallbackRejectionToFailureReason -Reason "$($sizePolicy.Message); remux fallback unavailable or blocked; oversized encode rejected before publish"
            $fallbackFailureProperties = New-RemuxFallbackFailureProperties
            $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $fallbackFailureReason -Stage 'encode-size-policy' -ErrorCode 'ENCODE_SIZE_GUARD_EXCEEDED' -SuggestedAction 'Review the source, remux_fallback_rejection details, and remux-safe codec/container policy. Adjust the route, size guard, or encode settings before retrying; the oversized encode was not published.' -AdditionalProperties $fallbackFailureProperties
            $localIn = $null
            $fallbackBlockDetail = Get-LastRemuxFallbackRejectionReasonText
            if ([string]::IsNullOrWhiteSpace($fallbackBlockDetail)) {
                Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting oversized encode before publish: $safeName" "ERROR"
            } else {
                Write-Log "ENCODE SIZE: remux fallback unavailable; rejecting oversized encode before publish: $safeName; block reason: $fallbackBlockDetail" "ERROR"
            }
            return $false
        }

        [System.IO.Directory]::CreateDirectory($paths.LocalDir) | Out-Null
        [System.IO.Directory]::CreateDirectory($paths.ServerDir) | Out-Null

        [System.IO.File]::Move($tempOut, $paths.LocalOut, $true)
        $tempOut = $null

        Write-PlexCompatibilityReport -FilePath $paths.LocalOut -Context "ENCODE: "

        # CurrentRouteReasonCode/Reason and route_actions.video are already
        # synchronized at the point $usingCpu / $usingSafeRetry was set. The
        # locals below are derived for the publish call only; do not re-mutate
        # script-scope state here (see E1 / E3 fixes).
        $route = if ($usingCpu) { "encode-cpu-fallback" } elseif ($usingSafeRetry) { "encode-safe-retry" } else { "encode" }
        $routeReasonCode = [string]$script:CurrentRouteReasonCode
        $routeReason     = [string]$script:CurrentRouteReason
        $publishResult = Complete-PipelineOutputPublish -SourceFile $file -ScratchPath $localIn -Paths $paths -Route $route -ProgressRoute 'encode' -StagePrefix 'encode' -Context "ENCODE: " -RouteReasonCode $routeReasonCode -RouteReason $routeReason -Tx3gTracks @($subResult.Tx3gTracks) -BdpgsTracks @($subResult.BdpgsTracks) -VobSubTracks @($subResult.VobSubTracks) -ConvertedSrtSidecarCandidates @($subResult.ConvertedSrtSidecarCandidates) -SubtitleOutputReduction @($subResult.SubtitleOutputReduction)
        $script:LastPublishResult = $publishResult
        if ($publishResult.DeleteLocalOutput) { $pushOk = $true }
        if ($publishResult.KeepScratchInput) { $localIn = $null }
        return [bool]$publishResult.Ok

    } catch {
        Write-Log "Do-Encode unexpected error: $_" "ERROR"
        Write-Log "Stack: $($_.ScriptStackTrace)" "DEBUG"
        if ($file) {
            $reason = "Do-Encode unexpected error: $($_.Exception.Message)"
            Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode-exception' -ErrorCode 'ENCODE_UNEXPECTED_EXCEPTION' -SuggestedAction 'Inspect the pipeline log stack trace and failure artifact, then clear the marker after fixing the root cause.' | Out-Null
            $localIn = $null
        }
        return $false
    } finally {
        if ($subResult -and $subResult.TempFiles) {
            $subResult.TempFiles | ForEach-Object { Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue }
        }
        if ($dynamicHdrTempFiles) {
            $dynamicHdrTempFiles | ForEach-Object {
                if (-not [string]::IsNullOrWhiteSpace([string]$_)) {
                    Remove-Item -LiteralPath ([string]$_) -Force -ErrorAction SilentlyContinue
                }
            }
        }
        if ($tempOut -and (Test-Path -LiteralPath $tempOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
        }
        if ($localIn -and (Test-Path -LiteralPath $localIn -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $localIn -Force -ErrorAction SilentlyContinue
            Remove-ScratchFingerprint $localIn
            Remove-EmptyScratchContainer $localIn
        }
        # FIX#10: ONLY delete local encoded output when server push
        # succeeded. On failure Invoke-ParkPendingPush has already moved
        # the file to PendingServerPush; deleting here would destroy
        # hours of encode work.
        if ($pushOk -and $paths -and $paths.LocalOut -and
            (Test-Path -LiteralPath $paths.LocalOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $paths.LocalOut -Force -ErrorAction SilentlyContinue
        }
    }
}
