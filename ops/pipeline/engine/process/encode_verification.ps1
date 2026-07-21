# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode verification boundary module.

function Get-MediaPipelineEncodeVerificationBoundaryVersion {
    return 'encode_verification_boundary.v1'
}

function Set-MediaPipelineEncodeVerificationMonitorOutcome {
    param(
        [Parameter(Mandatory)] [ValidateSet('completed','failed','review')] [string] $State,
        [string] $Detail = '',
        [string] $ReasonCode = ''
    )
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorStage -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorStage `
            -StageId 'verification' `
            -State $State `
            -Detail $Detail `
            -ReasonCode $ReasonCode `
            -EvidenceSource 'verification_result' | Out-Null
    }
}

function Invoke-MediaPipelineEncodeVerification {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $safeName = [string]$Context.SafeName
    $localIn = $Context.LocalIn
    $tempOut = $Context.TempOut
    $globalTitle = [string]$Context.GlobalTitle
    $usingCpu = [bool]$Context.UsingCpu
    $usingSafeRetry = [bool]$Context.UsingSafeRetry
    $dynamicHdrForceCpuEncode = [bool]$Context.DynamicHdrForceCpuEncode
    $dynamicHdrPolicy = [string]$Context.DynamicHdrPolicy
    $videoStreamPolicy = $Context.VideoStreamPolicy

    if (-not (Test-Path -LiteralPath $tempOut) -or (Get-Item -LiteralPath $tempOut).Length -eq 0) {
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE output missing or empty after ffmpeg' -Stage 'encode'
        $Context.LocalIn = $null
        Write-Log "ENCODE: output missing or empty after ffmpeg" "ERROR"
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode'
    }

    $verifyRoute = if ($usingCpu) { 'encode-cpu-fallback' } elseif ($usingSafeRetry) { 'encode-safe-retry' } else { 'encode' }
    $Context.VerifyRoute = $verifyRoute
    $muxResult = Invoke-EncodeMkvAttachmentMuxIfNeeded `
        -SourcePath $localIn `
        -EncodedPath $tempOut `
        -ProcessingDirectory $script:processingDir `
        -GlobalTitle $globalTitle `
        -ProgressRoute $verifyRoute
    if (-not [bool]$muxResult.ok) {
        $muxErrorCode = if ([string]::IsNullOrWhiteSpace([string]$muxResult.error_code)) { 'ENCODE_MKVMERGE_FAILED' } else { [string]$muxResult.error_code }
        $muxStage = if ([string]::IsNullOrWhiteSpace([string]$muxResult.stage)) { 'encode-mkvmerge' } else { [string]$muxResult.stage }
        $muxClassification = if ($muxErrorCode -eq 'ENCODE_ATTACHMENT_VERIFY_FAILED') { 'operator_required' } else { 'transient' }
        $failureProperties = [ordered]@{
            encode_attachment_mux = $muxResult
        }
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification $muxClassification -Reason ([string]$muxResult.reason) -Stage $muxStage -ErrorCode $muxErrorCode -ReproPath ([string]$muxResult.repro_path) -SuggestedAction 'Inspect the mkvmerge stderr log and repro command. The video/audio/subtitle encode succeeded, but final MKV attachment mux or verification failed before publish.' -AdditionalProperties $failureProperties
        $Context.LocalIn = $null
        Write-Log "ENCODE MUX: $($muxResult.reason)" "ERROR"
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage $muxStage
    }
    if ([bool]$muxResult.muxed) {
        $encodedTempOut = $tempOut
        $tempOut = [string]$muxResult.output_path
        if ($encodedTempOut -and $encodedTempOut -ne $tempOut -and (Test-Path -LiteralPath $encodedTempOut -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $encodedTempOut -Force -ErrorAction SilentlyContinue
        }
        Write-Log "ENCODE MUX: $($muxResult.reason)" "DEBUG"
    }
    $Context.TempOut = $tempOut

    # Duration sanity check — catches silent truncations.
    # AllowAVFallback tolerates the common case where an ASS subtitle cue
    # extends past the actual A/V end, inflating the source container duration.
    # D5 fix — preserve the encode-cpu-fallback route badge through the
    # verify stage so the GUI doesn't briefly drop the CPU label between
    # encode_cpu (100%) and the publish step.
    Set-ProgressStage -Stage 'encode_verify' -Status $script:pipelineStatus -Route $verifyRoute -Percent $null -SaveNow
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorOutput -State active -ScratchPath ([string]$localIn) -WorkingOutputPath ([string]$tempOut) -IntendedFinalPath ([string]$Context.Paths.ServerOut) -VerificationState active | Out-Null
    }
    $verificationPollHandler = if (Get-Command -Name New-MediaPipelineCurrentStageNativePollHandler -ErrorAction SilentlyContinue) {
        New-MediaPipelineCurrentStageNativePollHandler `
            -Stage 'encode_verify' `
            -Status 'Verifying encoded output' `
            -Route $verifyRoute `
            -MinimumIntervalSeconds 15 `
            -EvidenceSource 'verification_process_heartbeat'
    } else {
        $null
    }
    if (-not (Test-DurationMatch -SourcePath $localIn -OutputPath $tempOut -Label "ENCODE" -AllowAVFallback -PollHandler $verificationPollHandler -PollMilliseconds 1000)) {
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason 'ENCODE duration mismatch' -Stage 'encode-verify' -SuggestedAction 'Compare source and encoded output A/V end times. Container-duration differences caused by subtitle tails are tolerated, so a remaining encode-verify failure usually means the output A/V is genuinely shorter than the source.'
        $Context.LocalIn = $null
        Write-Log "ENCODE: duration mismatch - recorded as transient and scheduled for retry: $safeName" "ERROR"
        Set-MediaPipelineEncodeVerificationMonitorOutcome -State failed -Detail 'Encoded output duration does not match source A/V duration.' -ReasonCode 'ENCODE_DURATION_MISMATCH'
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-verify'
    }

    $expectedVideoCodec = ''
    if ($Context.EncodePlan -and $Context.EncodePlan.PSObject.Properties['SelectedEncoder']) { $expectedVideoCodec = [string]$Context.EncodePlan.SelectedEncoder }
    $videoPreservation = Test-OutputVideoStreamPreservation -SourcePath $localIn -OutputPath $tempOut -Route $verifyRoute -SourceInventory $videoStreamPolicy.Inventory -ExpectedVideoCodec $expectedVideoCodec -PollHandler $verificationPollHandler -PollMilliseconds 1000
    $script:LastMediaVerification = $videoPreservation
    $Context.MediaVerification = $videoPreservation
    if (-not [bool]$videoPreservation.Allowed) {
        $reason = [string]$videoPreservation.Reason
        $errorCode = [string]$videoPreservation.ErrorCode
        $failureProperties = [ordered]@{
            video_stream_preservation = $videoPreservation
            source_video_stream_count = [int]$videoPreservation.SourceCount
            output_video_stream_count = [int]$videoPreservation.OutputCount
            video_stream_evidence     = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoPreservation.SourceInventory -OutputInventory $videoPreservation.OutputInventory -Route $verifyRoute -Reason $reason -ErrorCode $errorCode
        }
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $tempOut -Classification 'operator_required' -Reason $reason -Stage 'encode-video-stream-verify' -ErrorCode $errorCode -SuggestedAction 'Inspect source/output ffprobe stream inventories and saved FFmpeg repro commands; publish remains blocked until every real source video stream is present in output.' -AdditionalProperties $failureProperties
        Write-Log "ENCODE: $reason" "ERROR"
        $Context.TempOut = $null
        Set-MediaPipelineEncodeVerificationMonitorOutcome -State review -Detail $reason -ReasonCode $errorCode
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-video-stream-verify'
    }

    $hdr10Verification = Test-Hdr10OutputMetadataPreservation `
        -SourcePath $localIn `
        -OutputPath $tempOut `
        -SourceInventory $videoPreservation.SourceInventory `
        -OutputInventory $videoPreservation.OutputInventory `
        -PollHandler $verificationPollHandler `
        -PollMilliseconds 1000
    $Context.Hdr10Verification = $hdr10Verification
    if (-not [bool]$hdr10Verification.Allowed) {
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $tempOut -Classification 'operator_required' -Reason ([string]$hdr10Verification.Reason) -Stage 'encode-hdr10-verify' -ErrorCode ([string]$hdr10Verification.ErrorCode) -SuggestedAction 'Inspect source/output ffprobe HDR10 facts and saved repro evidence. Publish remains blocked until every HDR10 output stream has 10-bit BT.2020/PQ signalling and preserves source mastering-display/MaxCLL when present.' -AdditionalProperties @{ hdr10_verification = $hdr10Verification; video_stream_preservation = $videoPreservation }
        Write-Log "ENCODE HDR10 VERIFY: $($hdr10Verification.Reason)" "ERROR"
        $Context.TempOut = $null
        Set-MediaPipelineEncodeVerificationMonitorOutcome -State review -Detail ([string]$hdr10Verification.Reason) -ReasonCode ([string]$hdr10Verification.ErrorCode)
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-hdr10-verify'
    }

    $trackVerificationPlan = $Context.MediaTrackVerificationPlan
    if (-not $trackVerificationPlan) {
        $trackVerificationPlan = New-MediaTrackOutputVerificationPlanFromFfmpegSubtitleArgs -AudioDecisions @(Get-LastAudioDecisionRecords) -SubtitleMapArgs @($Context.SubResult.MapArgs)
    }
    $trackVerification = Test-MediaTrackOutputVerification -OutputPath $tempOut -Plan $trackVerificationPlan -PollHandler $verificationPollHandler -PollMilliseconds 1000
    $script:LastMediaTrackVerification = $trackVerification
    $Context.MediaTrackVerification = $trackVerification
    $script:LastAudioVerification = Get-MediaTrackVerificationFacet -Verification $trackVerification -Kind 'audio'
    $script:LastSubtitleVerification = Get-MediaTrackVerificationFacet -Verification $trackVerification -Kind 'subtitle'
    $Context.AudioVerification = $script:LastAudioVerification
    $Context.SubtitleVerification = $script:LastSubtitleVerification
    if (-not [bool]$trackVerification.allowed) {
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $tempOut -Classification 'operator_required' -Reason ([string]$trackVerification.reason) -Stage 'encode-media-track-verify' -ErrorCode ([string]$trackVerification.error_code) -SuggestedAction 'Inspect source/output ffprobe stream inventories and backend policy evidence; publish remains blocked until every resolved audio and subtitle output track matches the plan.' -AdditionalProperties @{ media_track_verification = $trackVerification; media_track_verification_plan = $trackVerificationPlan; audio_verification = $script:LastAudioVerification; subtitle_verification = $script:LastSubtitleVerification }
        $Context.TempOut = $null
        Set-MediaPipelineEncodeVerificationMonitorOutcome -State review -Detail ([string]$trackVerification.reason) -ReasonCode ([string]$trackVerification.error_code)
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-media-track-verify'
    }

    if ($dynamicHdrForceCpuEncode -and $script:CurrentDynamicHdrEvidence) {
        Set-ProgressStage -Stage 'encode_verify' -Status "Verifying Dynamic HDR preservation" -Route $verifyRoute -Percent $null -SaveNow
        $expectedRpuFrameCount = 0
        if ($script:CurrentDynamicHdrEvidence.PSObject.Properties['x265_artifacts']) {
            $expectedRpuFrameCount = [int](Get-DynamicHdrResultValue -Result $script:CurrentDynamicHdrEvidence.x265_artifacts -Name 'rpu_frame_count')
        }
        $dynamicHdrVerification = Test-DynamicHdrOutputPreservation -SourceEvidence $script:CurrentDynamicHdrEvidence -OutputPath $tempOut -ExpectedRpuFrameCount $expectedRpuFrameCount -PollHandler $verificationPollHandler -PollMilliseconds 1000
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
            $Context.LocalIn = $null
            Write-Log "DYNAMIC HDR VERIFY: $($dynamicHdrVerification.reason)" "ERROR"
            Set-MediaPipelineEncodeVerificationMonitorOutcome -State review -Detail ([string]$dynamicHdrVerification.reason) -ReasonCode $verifyErrorCode
            return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'dynamic-hdr-output-verify'
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
            -TimeoutSeconds $script:QualityVerifyTimeoutSeconds `
            -PollHandler $verificationPollHandler `
            -PollMilliseconds 1000
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
            $Context.LocalIn = $null
            Write-Log "ENCODE QUALITY: $qualityReason`: $safeName" "ERROR"
            Set-MediaPipelineEncodeVerificationMonitorOutcome -State review -Detail $qualityReason -ReasonCode $qualityErrorCode
            return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-quality-verify'
        }
        if ($qualityOutcome -in @('warn', 'fail')) {
            Write-Log "ENCODE QUALITY: $qualityOutcome score $($qualityRecord['score']) $($qualityRecord['metric']) for $safeName (warn=$($qualityRecord['warn_threshold']), fail=$($qualityRecord['fail_threshold']), action=$($qualityRecord['fail_action']))" "WARN"
        } elseif ($qualityOutcome -in @('error', 'stopped')) {
            Write-Log "ENCODE QUALITY: verification $qualityOutcome for $safeName; publishing remains fail-open. $($qualityRecord['tool_error'])" "WARN"
        } else {
            Write-Log "ENCODE QUALITY: pass score $($qualityRecord['score']) $($qualityRecord['metric']) for $safeName" "DEBUG"
        }
    }

    $Context.TempOut = $tempOut
    $Context.VerifyRoute = $verifyRoute
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        $verifiedOutputItem = Get-Item -LiteralPath $tempOut -ErrorAction SilentlyContinue
        Set-MediaPipelineCurrentRunMonitorOutput -State verified -ScratchPath ([string]$localIn) -WorkingOutputPath ([string]$tempOut) -IntendedFinalPath ([string]$Context.Paths.ServerOut) -SizeBytes $(if ($verifiedOutputItem) { [int64]$verifiedOutputItem.Length } else { $null }) -VerificationState completed | Out-Null
    }
    Set-MediaPipelineEncodeVerificationMonitorOutcome -State completed -Detail 'Encoded output passed duration, stream, track, metadata, and configured quality verification.'
    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'encode-verify'
}
