# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode fallback and remux-fallback evidence helpers.

function Get-MediaPipelineEncodeFallbackBoundaryVersion {
    return 'encode_fallback_boundary.v1'
}

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

function Invoke-MediaPipelineEncodeDynamicHdrPolicy {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $isTV = [bool]$Context.IsTV
    $tvInfo = $Context.TvInfo
    $localIn = $Context.LocalIn
    $videoStreamPolicy = $Context.VideoStreamPolicy
    $isHDR = [bool]$Context.IsHDR

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

    $normalizedEncoderBackend = if ($EncoderBackend) { ([string]$EncoderBackend).Trim().ToLowerInvariant() } else { 'auto' }
    if ([string]::IsNullOrWhiteSpace($normalizedEncoderBackend)) { $normalizedEncoderBackend = 'auto' }
    $forceCpuBackendEncode = $normalizedEncoderBackend -eq 'cpu'
    $encoderReadiness = Resolve-MediaEncoderActivationReadiness -VideoCodec ([string]$VideoCodec) -EncoderBackend $normalizedEncoderBackend -UseCpuFallback:$forceCpuBackendEncode -IsHDR:$isHDR
    if (-not [bool]$encoderReadiness.ok) {
        $readinessErrorCode = if ([string]::IsNullOrWhiteSpace([string]$encoderReadiness.error_code)) { 'ENCODE_ENCODER_UNSUPPORTED' } else { [string]$encoderReadiness.error_code }
        Write-PipelineEvent -EventType 'encoder_activation_policy' -Stage 'encode_prepare' -Route 'encode' -Status 'blocked' -SourcePath $file.FullName -Data $encoderReadiness | Out-Null
        $failureProperties = [ordered]@{
            encoder_activation = $encoderReadiness
            video_codec        = [string]$VideoCodec
            encoder_backend    = $normalizedEncoderBackend
            is_hdr             = [bool]$isHDR
        }
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason ([string]$encoderReadiness.reason) -Stage 'encode-policy' -ErrorCode $readinessErrorCode -SuggestedAction 'Choose an active descriptor-backed encoder such as hevc_nvenc, h264_nvenc for SDR sources, libx264, libaom-av1, or EncoderBackend=cpu; hardware AV1/NVENC, QSV, and AMF remain blocked until runtime and real-media validation are complete.' -AdditionalProperties $failureProperties
        Write-Log "ENCODE POLICY: $($encoderReadiness.reason)" "ERROR"
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-policy'
    }

    $dynamicHdrForceCpuEncode = $false
    $dynamicHdrWorkingDirectory = ''
    $dynamicHdrTempFiles = @()
    $dynamicHdrDolbyVisionRpuPath = ''
    $dynamicHdrDolbyVisionTargetProfile = ''
    $dynamicHdrHdr10PlusJsonPath = ''
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
                        $Context.LocalIn = $null
                        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'dynamic-hdr-extraction'
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
                $Context.LocalIn = $null
                return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'dynamic-hdr-policy'
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
                    $Context.LocalIn = $null
                    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'dynamic-hdr-remux-fallback'
                }
                if (-not $script:LastDynamicHdrRemuxFallbackRejection) {
                    $Context.LocalIn = $null
                    return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'dynamic-hdr-remux-fallback'
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

    $Context.Hdr10MasterDisplay = $hdr10MasterDisplay
    $Context.Hdr10MaxCll = $hdr10MaxCll
    $Context.NormalizedEncoderBackend = $normalizedEncoderBackend
    $Context.ForceCpuBackendEncode = [bool]$forceCpuBackendEncode
    $Context.DynamicHdrPolicy = $dynamicHdrPolicy
    $Context.DynamicHdrDecision = $dynamicHdrEncodeDecision
    $Context.DynamicHdrForceCpuEncode = [bool]$dynamicHdrForceCpuEncode
    $Context.DynamicHdrWorkingDirectory = $dynamicHdrWorkingDirectory
    $Context.DynamicHdrTempFiles = @($dynamicHdrTempFiles)
    $Context.DynamicHdrDolbyVisionRpuPath = $dynamicHdrDolbyVisionRpuPath
    $Context.DynamicHdrDolbyVisionTargetProfile = $dynamicHdrDolbyVisionTargetProfile
    $Context.DynamicHdrHdr10PlusJsonPath = $dynamicHdrHdr10PlusJsonPath
    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'dynamic-hdr-policy'
}

function Invoke-MediaPipelineEncodeAttemptLadder {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $isTV = [bool]$Context.IsTV
    $tvInfo = $Context.TvInfo
    $safeName = [string]$Context.SafeName
    $localIn = [string]$Context.LocalIn
    $subResult = $Context.SubResult
    $isHDR = [bool]$Context.IsHDR
    $hdr10MasterDisplay = [string]$Context.Hdr10MasterDisplay
    $hdr10MaxCll = [string]$Context.Hdr10MaxCll
    $normalizedEncoderBackend = [string]$Context.NormalizedEncoderBackend
    $forceCpuBackendEncode = [bool]$Context.ForceCpuBackendEncode
    $dynamicHdrForceCpuEncode = [bool]$Context.DynamicHdrForceCpuEncode
    $dynamicHdrWorkingDirectory = [string]$Context.DynamicHdrWorkingDirectory
    $dynamicHdrDolbyVisionRpuPath = [string]$Context.DynamicHdrDolbyVisionRpuPath
    $dynamicHdrDolbyVisionTargetProfile = [string]$Context.DynamicHdrDolbyVisionTargetProfile
    $dynamicHdrHdr10PlusJsonPath = [string]$Context.DynamicHdrHdr10PlusJsonPath
    $audioArgs = @($Context.AudioArgs)
    $usingCpu = $false
    $usingSafeRetry = $false
    $globalTitle = "Encoded by MediaPipeline $($script:ProductVersion) (pipeline $($script:PipelineVersion))"
    $Context.GlobalTitle = $globalTitle
    $recordEncodeAttempt = {
        param($Plan, [bool]$Succeeded)
        # D3 fix - record CPU-specific context per attempt so sidecar
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

    # Attempt 1 uses the configured GPU-first encoder. Retry policy and
    # CPU fallback command construction live in ops\pipeline\engine\decide\encode_policy.ps1.
    # Suggestion #2 - when the cached NVENC probe says GPU is
    # unavailable (set by Invalidate-NvencAvailableProbe after an
    # earlier runtime NVENC failure), skip the primary AND safe-retry
    # attempts entirely. Saves ~10-60 s per file on a no-GPU machine.
    $cpuFallbackTarget = Resolve-MediaEncoderCpuFallbackDescriptor -VideoCodec ([string]$VideoCodec) -IsHDR:$isHDR
    $cpuFallbackEncoderName = if ([bool]$cpuFallbackTarget.Resolved) { [string]$cpuFallbackTarget.EncoderName } else { Get-MediaVideoCodecLibx265Name }
    $skipGpuDueToProbe = if ($dynamicHdrForceCpuEncode -or $forceCpuBackendEncode) { $true } else { -not (Test-NvencProbeReportsAvailable) }
    if ($dynamicHdrForceCpuEncode) {
        $cpuFallbackEncoderName = Get-MediaVideoCodecLibx265Name
        Write-Log "ENCODE: Dynamic HDR preservation requires CPU/libx265; skipping GPU-first ladder" "WARN"
        Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
            from_encoder = [string]$VideoCodec
            to_encoder   = $cpuFallbackEncoderName
            reason       = [string]$script:CurrentDynamicHdrEvidence.policy_reason
            trigger      = 'dynamic_hdr_preserve_encode'
            cpu_preset   = [string]$script:CpuEncodePreset
            is_hdr       = [bool]$isHDR
        } | Out-Null
    } elseif ($forceCpuBackendEncode) {
        Write-Log "ENCODE: EncoderBackend=cpu selected; skipping hardware ladder and using $cpuFallbackEncoderName" "WARN"
        Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
            from_encoder    = [string]$VideoCodec
            to_encoder      = $cpuFallbackEncoderName
            reason          = 'EncoderBackend=cpu selected'
            trigger         = 'encoder_backend_cpu_selected'
            encoder_backend = $normalizedEncoderBackend
            cpu_preset      = [string]$script:CpuEncodePreset
            is_hdr          = [bool]$isHDR
        } | Out-Null
    } elseif ($skipGpuDueToProbe) {
        $probeReason = if ($script:NvencAvailableProbe -and $script:NvencAvailableProbe.Reason) { [string]$script:NvencAvailableProbe.Reason } else { 'NVENC probe cache reports unavailable' }
        Write-Log "ENCODE: NVENC unavailable per cached probe ($probeReason); skipping GPU-first ladder and going straight to CPU" "WARN"
        Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
            from_encoder = 'cached_unavailable'
            to_encoder   = $cpuFallbackEncoderName
            reason       = $probeReason
            trigger      = 'nvenc_probe_unavailable'
            cpu_preset   = [string]$script:CpuEncodePreset
            is_hdr       = [bool]$isHDR
        } | Out-Null
    }
    $Context.SkipGpuDueToProbe = [bool]$skipGpuDueToProbe
    $Context.CpuFallbackEncoderName = $cpuFallbackEncoderName

    $primaryAttempt = New-MediaPipelineEncodeCoreAttemptPlan `
        -UseCpuFallback:$false `
        -IsTV:$isTV `
        -IsHDR:$isHDR `
        -InputPath $localIn `
        -ExtraInputs $subResult.ExtraInputs `
        -GlobalTitle $globalTitle `
        -AudioArgs $audioArgs `
        -SubtitleMapArgs $subResult.MapArgs `
        -VideoFilterArgs $subResult.VideoFilterArgs `
        -OutputContainer $OutputContainer `
        -VideoCodec $VideoCodec `
        -VideoPreset $VideoPreset `
        -VideoQuality $VideoQuality `
        -ExtraVideoFlags $ExtraVideoFlags `
        -FallbackCpuQuality $script:FallbackCpuQuality `
        -EncoderBackend $normalizedEncoderBackend `
        -EncodeLadder $script:EncodeLadder `
        -CpuPreset $script:CpuEncodePreset `
        -CpuMaxThreads $script:CpuEncodeMaxThreads `
        -Hdr10MasterDisplay $hdr10MasterDisplay `
        -Hdr10MaxCll $hdr10MaxCll `
        -TempPrefix 'encode_temp'
    $tempOut    = [string]$primaryAttempt.OutputPath
    $encodePlan = $primaryAttempt.Plan
    $ffArgs     = Get-MediaPipelineEncodeCommandArgumentList -Plan $encodePlan

    $nullCount = @($ffArgs | Where-Object { $null -eq $_ }).Count
    if ($nullCount -gt 0) {
        Write-Log "ENCODE: $nullCount null element(s) in FFmpeg args - aborting" "ERROR"
        $Context.TempOut = $tempOut
        $Context.EncodePlan = $encodePlan
        $Context.FfArgs = @($ffArgs)
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-command'
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
                if ([bool]$fallbackResult.KeepScratchInput) { $Context.LocalIn = $null }
                $Context.TempOut = $tempOut
                return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'encode-size-policy'
            }
            $Context.LocalIn = $null
            $Context.TempOut = $tempOut
            return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-size-policy'
        }
    }

    if ($skipGpuDueToProbe) {
        # Don't burn an ffmpeg launch for the primary GPU attempt;
        # synthesize the failure state so the existing fallback
        # branch fires and falls into the CPU path below.
        $success = $false
        $script:LastFFmpegStderr = if ($dynamicHdrForceCpuEncode) { 'Dynamic HDR preservation requires CPU/libx265; primary GPU attempt skipped' } elseif ($forceCpuBackendEncode) { 'EncoderBackend=cpu selected; primary hardware attempt skipped' } else { 'NVENC probe cache reports unavailable; primary GPU attempt skipped' }
        $script:LastFFmpegExit = 1
    } else {
        $success = Invoke-MediaPipelineEncodeAttemptExecution -Plan $encodePlan -ArgumentList $ffArgs -InputPath $localIn -OutputPath $tempOut -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -WasteGuardContext $wasteGuardContext
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
            if ([bool]$fallbackResult.KeepScratchInput) { $Context.LocalIn = $null }
            $Context.TempOut = $tempOut
            return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'encode-size-policy'
        }
        $Context.LocalIn = $null
        $Context.TempOut = $tempOut
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-size-policy'
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
            $safeRetryAttempt = New-MediaPipelineEncodeCoreAttemptPlan `
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
                -OutputContainer $OutputContainer `
                -VideoCodec $VideoCodec `
                -VideoPreset $VideoPreset `
                -VideoQuality $VideoQuality `
                -ExtraVideoFlags $ExtraVideoFlags `
                -FallbackCpuQuality $script:FallbackCpuQuality `
                -EncoderBackend $normalizedEncoderBackend `
                -EncodeLadder $script:EncodeLadder `
                -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll `
                -TempPrefix 'encode_temp_safe' `
                -OutputPath $tempOut
            $tempOut    = [string]$safeRetryAttempt.OutputPath
            $encodePlan = $safeRetryAttempt.Plan
            $ffArgs     = Get-MediaPipelineEncodeCommandArgumentList -Plan $encodePlan
            if ($wasteGuardContext) {
                $wasteGuardContext.OutputPath = $tempOut
            }
            $success    = Invoke-MediaPipelineEncodeAttemptExecution -Plan $encodePlan -ArgumentList $ffArgs -InputPath $localIn -OutputPath $tempOut -TimeoutSeconds $script:FFmpegEncodeTimeoutSeconds -WasteGuardContext $wasteGuardContext
            & $recordEncodeAttempt $encodePlan ([bool]$success)
        } else {
            # Hardware is already skipped; don't even build the safe-retry
            # plan. Force the inner gate to fall straight into the CPU
            # branch.
            $success = $false
            $script:LastFFmpegStderr = if ($dynamicHdrForceCpuEncode) { 'Dynamic HDR preservation requires CPU/libx265; safe-retry skipped' } elseif ($forceCpuBackendEncode) { 'EncoderBackend=cpu selected; hardware safe-retry skipped' } else { 'NVENC probe cache reports unavailable; safe-retry skipped' }
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
                if ([bool]$fallbackResult.KeepScratchInput) { $Context.LocalIn = $null }
                $Context.TempOut = $tempOut
                return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'encode-size-policy'
            }
            $Context.LocalIn = $null
            $Context.TempOut = $tempOut
            return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-size-policy'
        }
        if ($success) {
            $usingSafeRetry = $true
            $script:CurrentRouteReasonCode = 'hardware_encoder_safe_retry_succeeded'
            $script:CurrentRouteReason = 'hardware encoder failed with primary flags; compatibility retry succeeded'
        } elseif (Test-ShouldRetryEncodeWithCpuFallback -Success:$success -StopRequested:$script:StopRequested -VideoCodec $VideoCodec -ErrorText $script:LastFFmpegStderr -ForceCpu:$skipGpuDueToProbe) {
            # Suggestion #2 - second NVENC failure in this file means
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
                Write-Log "ENCODE: compatibility retry also failed - falling back to $cpuFallbackEncoderName (CRF $($script:FallbackCpuQuality), preset $script:CpuEncodePreset, timeout $($script:FFmpegCpuEncodeTimeoutSeconds)s, priority $script:CpuEncodeProcessPriority)" "WARN"
            }
            # Emit a structured event so the desktop diagnostics drawer
            # and the Live tab can light up a CPU-fallback indicator
            # instead of the operator only seeing a log line.
            Write-PipelineEvent -EventType 'encoder_fallback_started' -Stage 'encode_cpu' -Route 'encode' -Status 'warn' -SourcePath $file.FullName -Data @{
                from_encoder         = [string]$VideoCodec
                to_encoder           = $cpuFallbackEncoderName
                cpu_preset           = [string]$script:CpuEncodePreset
                cpu_quality_crf      = [int]$script:FallbackCpuQuality
                cpu_timeout_seconds  = [int]$script:FFmpegCpuEncodeTimeoutSeconds
                cpu_process_priority = [string]$script:CpuEncodeProcessPriority
                is_hdr               = [bool]$isHDR
                dynamic_hdr          = [bool]$dynamicHdrForceCpuEncode
                encoder_backend      = $normalizedEncoderBackend
                trigger              = if ($forceCpuBackendEncode) { 'encoder_backend_cpu_selected' } elseif ($skipGpuDueToProbe) { 'nvenc_probe_unavailable' } else { 'hardware_encoder_failure' }
            } | Out-Null
            if (Test-Path -LiteralPath $tempOut) {
                Remove-Item -LiteralPath $tempOut -Force -ErrorAction SilentlyContinue
            }
            $tempOut    = Join-Path $script:processingDir "encode_temp_cpu_$([guid]::NewGuid().ToString('N')).$OutputContainer"
            # F-new-1 - re-validate scratch space with the CPU-aware
            # multiplier *before* the (potentially multi-hour) CPU
            # run. The original pre-flight at the top of Do-Encode used
            # the default 0.7x NVENC ratio, which can green-light an
            # encode that would actually fill the scratch volume at
            # 95% with CPU encoder output.
            if (-not (Test-EstimatedOutputSpace -SourcePath $localIn -Label "ENCODE-CPU" -IsCpuEncode)) {
                Write-Log "ENCODE-CPU: insufficient scratch space for CPU-fallback encode — aborting before $cpuFallbackEncoderName starts" "ERROR"
                Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'Insufficient scratch space for CPU-fallback encode' -Stage 'encode' -ErrorCode 'ENCODE_CPU_INSUFFICIENT_SPACE' -SuggestedAction 'Free additional space on the scratch volume or lower CpuEncodePreset/FallbackCpuQuality before retrying. CPU encodes need 1:1 source-size headroom because software encoder output can be larger than NVENC.' | Out-Null
                $Context.LocalIn = $null
                $Context.TempOut = $tempOut
                return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode'
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
                -EncoderBackend $normalizedEncoderBackend `
                -EncodeLadder $script:EncodeLadder `
                -CpuPreset $script:CpuEncodePreset `
                -CpuMaxThreads $script:CpuEncodeMaxThreads `
                -Hdr10MasterDisplay $hdr10MasterDisplay `
                -Hdr10MaxCll $hdr10MaxCll `
                -DolbyVisionRpuPath $dynamicHdrDolbyVisionRpuPath `
                -DolbyVisionTargetProfile $dynamicHdrDolbyVisionTargetProfile `
                -Hdr10PlusJsonPath $dynamicHdrHdr10PlusJsonPath
            $ffArgs     = @($encodePlan.ArgumentList)
            $cpuFallbackEncoderName = [string]$encodePlan.SelectedEncoder
            # Differentiate the GUI status string. app/status/service.py renders
            # `encode_cpu` with its own label, but the user-facing status
            # text (currentStatus) is also surfaced verbatim in the live
            # tile and the taskbar tooltip; keep it explicit so the
            # operator immediately knows this is a multi-hour CPU run.
            $cpuStatusText = if ($isTV) { "Encoding TV (CPU fallback)" } else { "Encoding Movie (CPU fallback)" }
            # F-new-4 - serialize CPU encodes machine-wide. If another
            # pipeline process on this box is already running a CPU encoder,
            # show the operator that we're queued behind it instead of
            # silently double-saturating the cores.
            $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
            if (-not $cpuMutexLock.Acquired) {
                Write-Log "ENCODE-CPU: another CPU encode is already in progress on this machine; waiting for it to finish ($($cpuMutexLock.Reason))" "WARN"
                Set-ProgressStage -Stage 'encode_cpu' -Status "Waiting for CPU encode slot" -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
                $script:pipelineStatus = "Waiting for CPU encode slot"
                $cpuMutexWaitSeconds = [int]$script:CpuEncodeMutexWaitSeconds
                $cpuMutexLock = Acquire-CpuEncodeMutex -TimeoutSeconds $cpuMutexWaitSeconds
            }
            if (-not $cpuMutexLock.Acquired) {
                $reason = "ENCODE-CPU: CPU encode mutex was not acquired after waiting $([int]$script:CpuEncodeMutexWaitSeconds) seconds; refusing to start overlapping CPU fallback"
                Write-Log $reason "ERROR"
                $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason $reason -Stage 'encode-cpu-mutex' -ErrorCode 'ENCODE_CPU_MUTEX_UNAVAILABLE' -SuggestedAction 'Wait for the existing CPU encode to finish, inspect stale mutex ownership if no encode is running, then retry.'
                $Context.LocalIn = $null
                $Context.TempOut = $tempOut
                return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-cpu-mutex'
            }
            Set-ProgressStage -Stage 'encode_cpu' -Status $cpuStatusText -Route 'encode-cpu-fallback' -Percent 0 -SaveNow
            $script:pipelineStatus = $cpuStatusText
            try {
                # CPU encodes get their own (typically larger) timeout
                # so a slow software encode is not killed at the 6-hour
                # GPU ceiling.
                $success    = Invoke-FFmpegWithProgress $ffArgs $encodePlan.Label $localIn -TimeoutSeconds $script:FFmpegCpuEncodeTimeoutSeconds -ProgressStage $encodePlan.ProgressStage -ProgressRoute $encodePlan.ProgressRoute -ReproStage $encodePlan.ReproStage -CpuEncode -ProcessPriority $script:CpuEncodeProcessPriority -WorkingDirectory $dynamicHdrWorkingDirectory
            } finally {
                if ($cpuMutexLock -and $cpuMutexLock.Acquired) { & $cpuMutexLock.Release }
            }
            & $recordEncodeAttempt $encodePlan ([bool]$success)
            if ($success) {
                $usingCpu = $true
                # E1 fix - keep the script-scope route state in sync with
                # the actual encoder used. The size-policy guard (and any
                # other consumer that reads CurrentRouteReasonCode during
                # verify) needs to see the correct reason so CPU outputs
                # receive the compatibility growth budget, not the strict 5%.
                # Suggestion #2 - distinguish "GPU known unavailable per
                # cached probe" from "GPU was actually attempted and
                # failed for this file".  Both still use the
                # encode-cpu-fallback route, but the reason code lets
                # diagnostics show why GPU was skipped.
                if ($dynamicHdrForceCpuEncode) {
                    $script:CurrentRouteReasonCode = 'dynamic_hdr_preserve_cpu_encode'
                    $script:CurrentRouteReason     = "Dynamic HDR preservation required CPU/libx265 encode: $($script:CurrentDynamicHdrEvidence.summary)"
                    $script:CurrentDynamicHdrEvidence.outcome = 'preserved_encode'
                } elseif ($forceCpuBackendEncode) {
                    $script:CurrentRouteReasonCode = 'encoder_backend_cpu_selected'
                    $script:CurrentRouteReason     = "EncoderBackend=cpu selected; CPU descriptor '$cpuFallbackEncoderName' used without a hardware attempt"
                } elseif ($skipGpuDueToProbe) {
                    $script:CurrentRouteReasonCode = 'gpu_unavailable_cpu_only'
                    $script:CurrentRouteReason     = 'NVENC unavailable per cached probe; CPU encode without trying GPU'
                } else {
                    $script:CurrentRouteReasonCode = 'hardware_encoder_cpu_fallback'
                    $script:CurrentRouteReason     = 'hardware encoder failed; CPU fallback succeeded'
                }
                # E3 fix - mutate route_actions.video to 'encode_software'
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
                # E5 paired event - operators correlating fallback start
                # with completion get an explicit success record instead
                # of inferring it from a later tool_completed.
                Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'succeeded' -SourcePath $file.FullName -Data @{
                    from_encoder    = [string]$VideoCodec
                    to_encoder      = $cpuFallbackEncoderName
                    cpu_preset      = [string]$encodePlan.CpuPreset
                    cpu_quality_crf = [int]$script:FallbackCpuQuality
                    dynamic_hdr     = [bool]$dynamicHdrForceCpuEncode
                    encoder_backend = $normalizedEncoderBackend
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
        $failedCpuEncoder = if ($encodePlan -and $encodePlan.PSObject.Properties['SelectedEncoder']) { [string]$encodePlan.SelectedEncoder } else { $cpuFallbackEncoderName }
        $suggestedAction = if ($failedEncoderKind -eq 'cpu') {
            "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. The $failedCpuEncoder CPU fallback failed, so re-tuning NVENC will not help; check for source corruption, encoder OOM (lower the preset or quality), or a software encoder build issue."
        } else {
            "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath. If NVENC was unstable, compare against the CPU fallback behavior."
        }
        $failureRetryable = if (Get-Command -Name Get-MediaPipelineCodeRetryable -ErrorAction SilentlyContinue) {
            Get-MediaPipelineCodeRetryable -Code $errorCode -Family ''
        } else {
            $true
        }
        $failureClassification = if ([bool]$failureRetryable) { 'transient' } else { 'permanent' }
        # D2 fix - retryable CPU failures are recorded as 'transient'
        # just like NVENC failures. Permanent source-media failures stay
        # permanent so corrupt/invalid containers do not churn retry slots.
        # Register-SourceFailure still escalates retryable same-(stage,
        # error_code) failures after TransientFailureRetryLimit attempts.
        # Emit the matching encoder_fallback_completed event so the
        # diagnostics drawer can pair start with end (E5).
        if ($failedEncoderKind -eq 'cpu') {
            if ($dynamicHdrForceCpuEncode -and $script:CurrentDynamicHdrEvidence) {
                $script:CurrentDynamicHdrEvidence.outcome = 'preserve_encode_failed'
            }
            Write-PipelineEvent -EventType 'encoder_fallback_completed' -Stage 'encode_cpu' -Route 'encode-cpu-fallback' -Status 'failed' -SourcePath $file.FullName -Data @{
                from_encoder    = [string]$VideoCodec
                to_encoder      = $failedCpuEncoder
                cpu_preset      = if ($encodePlan -and $encodePlan.PSObject.Properties['CpuPreset']) { [string]$encodePlan.CpuPreset } else { '' }
                cpu_quality_crf = [int]$script:FallbackCpuQuality
                error_code      = [string]$errorCode
                dynamic_hdr     = [bool]$dynamicHdrForceCpuEncode
            } | Out-Null
        }
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $failureClassification -Reason $reason -Stage 'encode' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
        $Context.LocalIn = $null
        $Context.TempOut = $tempOut
        $failureDisposition = if ($failureClassification -eq 'transient') {
            'recorded as transient and scheduled for retry'
        } else {
            'recorded as non-retryable source failure'
        }
        Write-Log "ENCODE failed - $failureDisposition`: $safeName" "ERROR"
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode'
    }

    $Context.TempOut = $tempOut
    $Context.EncodePlan = $encodePlan
    $Context.FfArgs = @($ffArgs)
    $Context.WasteGuardContext = $wasteGuardContext
    $Context.UsingCpu = [bool]$usingCpu
    $Context.UsingSafeRetry = [bool]$usingSafeRetry
    $Context.CpuFallbackEncoderName = $cpuFallbackEncoderName
    $Context.VerifyRoute = if ($usingCpu) { 'encode-cpu-fallback' } elseif ($usingSafeRetry) { 'encode-safe-retry' } else { 'encode' }
    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'encode-attempts'
}
