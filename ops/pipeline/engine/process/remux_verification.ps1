# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux output verification before publish handoff.

function Set-MediaPipelineRemuxVerificationMonitorOutcome {
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

function Invoke-MediaPipelineRemuxVerification {
    param([Parameter(Mandatory)] $Context)

    if (-not (Test-Path -LiteralPath $Context.Paths.LocalOut) -or
        (Get-Item -LiteralPath $Context.Paths.LocalOut).Length -eq 0) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason 'REMUX output missing or empty after mkvmerge' -Stage 'remux-mkvmerge'
        $Context.LocalIn = $null
        Write-Log "REMUX: output missing or empty after mkvmerge" "ERROR"
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-mkvmerge'
    }

    Set-ProgressStage -Stage 'remux_verify' -Status $script:pipelineStatus -Route 'remux' -Percent $null -SaveNow
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        Set-MediaPipelineCurrentRunMonitorOutput -State active -ScratchPath ([string]$Context.LocalIn) -WorkingOutputPath ([string]$Context.Paths.LocalOut) -IntendedFinalPath ([string]$Context.Paths.ServerOut) -VerificationState active | Out-Null
    }
    $verificationPollHandler = if (Get-Command -Name New-MediaPipelineCurrentStageNativePollHandler -ErrorAction SilentlyContinue) {
        New-MediaPipelineCurrentStageNativePollHandler `
            -Stage 'remux_verify' `
            -Status 'Verifying remuxed output' `
            -Route 'remux' `
            -MinimumIntervalSeconds 15 `
            -EvidenceSource 'verification_process_heartbeat'
    } else {
        $null
    }
    if (-not (Test-DurationMatch -SourcePath $Context.LocalIn -OutputPath $Context.Paths.LocalOut -Label "REMUX" -AllowAVFallback -PollHandler $verificationPollHandler -PollMilliseconds 1000)) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.Paths.LocalOut -Classification 'transient' -Reason 'REMUX duration mismatch' -Stage 'remux-verify' -SuggestedAction 'Compare source and remuxed output A/V end times. Subtitle-tail container differences are tolerated now, so a remaining remux-verify failure usually indicates the output A/V is actually short.'
        Write-Log "REMUX: output duration mismatch - treating as failure" "ERROR"
        Set-MediaPipelineRemuxVerificationMonitorOutcome -State failed -Detail 'Remuxed output duration does not match source A/V duration.' -ReasonCode 'REMUX_DURATION_MISMATCH'
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-verify'
    }

    $videoPreservation = Test-OutputVideoStreamPreservation -SourcePath $Context.LocalIn -OutputPath $Context.Paths.LocalOut -Route 'remux' -SourceInventory $Context.VideoStreamPolicy.Inventory -PollHandler $verificationPollHandler -PollMilliseconds 1000
    $script:LastMediaVerification = $videoPreservation
    $Context.MediaVerification = $videoPreservation
    if (-not [bool]$videoPreservation.Allowed) {
        $reason = [string]$videoPreservation.Reason
        $errorCode = [string]$videoPreservation.ErrorCode
        $failureProperties = [ordered]@{
            video_stream_preservation = $videoPreservation
            source_video_stream_count = [int]$videoPreservation.SourceCount
            output_video_stream_count = [int]$videoPreservation.OutputCount
            video_stream_evidence     = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoPreservation.SourceInventory -OutputInventory $videoPreservation.OutputInventory -Route 'remux' -Reason $reason -ErrorCode $errorCode
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.Paths.LocalOut -Classification 'operator_required' -Reason $reason -Stage 'remux-video-stream-verify' -ErrorCode $errorCode -SuggestedAction 'Inspect source/output ffprobe stream inventories and saved FFmpeg/mkvmerge repro commands; publish remains blocked until every real source video stream is present in output.' -AdditionalProperties $failureProperties
        Write-Log "REMUX: $reason" "ERROR"
        Set-MediaPipelineRemuxVerificationMonitorOutcome -State review -Detail $reason -ReasonCode $errorCode
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-video-stream-verify'
    }

    $trackVerificationPlan = $Context.MediaTrackVerificationPlan
    if (-not $trackVerificationPlan) {
        $trackVerificationPlan = New-MediaTrackOutputVerificationPlan -AudioDecisions @(Get-LastAudioDecisionRecords) -SubtitleTracks @($Context.SubTracks.VerificationTracks)
    }
    $trackVerification = Test-MediaTrackOutputVerification -OutputPath $Context.Paths.LocalOut -Plan $trackVerificationPlan -PollHandler $verificationPollHandler -PollMilliseconds 1000
    $script:LastMediaTrackVerification = $trackVerification
    $Context.MediaTrackVerification = $trackVerification
    $script:LastAudioVerification = Get-MediaTrackVerificationFacet -Verification $trackVerification -Kind 'audio'
    $script:LastSubtitleVerification = Get-MediaTrackVerificationFacet -Verification $trackVerification -Kind 'subtitle'
    $Context.AudioVerification = $script:LastAudioVerification
    $Context.SubtitleVerification = $script:LastSubtitleVerification
    if (-not [bool]$trackVerification.allowed) {
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.Paths.LocalOut -Classification 'operator_required' -Reason ([string]$trackVerification.reason) -Stage 'remux-media-track-verify' -ErrorCode ([string]$trackVerification.error_code) -SuggestedAction 'Inspect source/output ffprobe stream inventories and backend policy evidence; publish remains blocked until every resolved audio and subtitle output track matches the plan.' -AdditionalProperties @{ media_track_verification = $trackVerification; media_track_verification_plan = $trackVerificationPlan; audio_verification = $script:LastAudioVerification; subtitle_verification = $script:LastSubtitleVerification }
        Set-MediaPipelineRemuxVerificationMonitorOutcome -State review -Detail ([string]$trackVerification.reason) -ReasonCode ([string]$trackVerification.error_code)
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-media-track-verify'
    }

    $dynamicHdrPolicy = Resolve-DynamicHdrPolicy -Policy ([string]$script:DynamicHdrPolicy)
    if ($script:CurrentDynamicHdrEvidence -and [bool]$script:CurrentDynamicHdrEvidence.dynamic_metadata_present) {
        if ($dynamicHdrPolicy -in @('preserve_or_remux','preserve_or_review')) {
            if (-not [bool]$script:CurrentDynamicHdrEvidence.probed) {
                $reason = 'Dynamic HDR source detection was inconclusive; preservation policy cannot verify remux output.'
                $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'operator_required' -Reason $reason -Stage 'remux-dynamic-hdr-verify' -ErrorCode 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN' -SuggestedAction 'Inspect source ffprobe Dynamic HDR evidence and retry only after both Dolby Vision and HDR10+ probes are conclusive.' -AdditionalProperties @{ dynamic_hdr = $script:CurrentDynamicHdrEvidence }
                Set-MediaPipelineRemuxVerificationMonitorOutcome -State review -Detail $reason -ReasonCode 'DYNAMIC_HDR_OUTPUT_VERIFY_UNKNOWN'
                return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-dynamic-hdr-verify'
            }
            $dynamicHdrVerification = Test-DynamicHdrOutputPreservation -SourceEvidence $script:CurrentDynamicHdrEvidence -OutputPath $Context.Paths.LocalOut -PollHandler $verificationPollHandler -PollMilliseconds 1000
            $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'verification' -NotePropertyValue $dynamicHdrVerification -Force
            if (-not [bool]$dynamicHdrVerification.ok) {
                $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'operator_required' -Reason ([string]$dynamicHdrVerification.reason) -Stage 'remux-dynamic-hdr-verify' -ErrorCode ([string]$dynamicHdrVerification.error_code) -SuggestedAction 'Inspect output ffprobe Dolby Vision/HDR10+ side data. Preservation policy blocks remux publish until expected metadata is detected.' -AdditionalProperties @{ dynamic_hdr = $script:CurrentDynamicHdrEvidence }
                Set-MediaPipelineRemuxVerificationMonitorOutcome -State review -Detail ([string]$dynamicHdrVerification.reason) -ReasonCode ([string]$dynamicHdrVerification.error_code)
                return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-dynamic-hdr-verify'
            }
            $script:CurrentDynamicHdrEvidence.outcome = 'preserved_remux_verified'
        } elseif ($dynamicHdrPolicy -eq 'warn') {
            $script:CurrentDynamicHdrEvidence.outcome = 'preservation_unverified_warn'
            $script:CurrentDynamicHdrEvidence | Add-Member -NotePropertyName 'policy_reason' -NotePropertyValue 'warn policy permits remux publish without Dynamic HDR output verification' -Force
        }
        if (Get-Command -Name Write-PipelineEvent -ErrorAction SilentlyContinue) {
            Write-PipelineEvent -EventType 'dynamic_hdr_remux_verification' -Stage 'remux-dynamic-hdr-verify' -SourcePath $Context.File -Route 'remux' -Status ([string]$script:CurrentDynamicHdrEvidence.outcome) -Data @{
                policy       = $dynamicHdrPolicy
                outcome      = [string]$script:CurrentDynamicHdrEvidence.outcome
                verification = $script:CurrentDynamicHdrEvidence.verification
            } | Out-Null
        }
    }

    Write-PlexCompatibilityReport -FilePath $Context.Paths.LocalOut -Context "REMUX: " -PollHandler $verificationPollHandler -PollMilliseconds 1000
    if (Get-Command -Name Set-MediaPipelineCurrentRunMonitorOutput -ErrorAction SilentlyContinue) {
        $verifiedOutputItem = Get-Item -LiteralPath $Context.Paths.LocalOut -ErrorAction SilentlyContinue
        Set-MediaPipelineCurrentRunMonitorOutput -State verified -ScratchPath ([string]$Context.LocalIn) -WorkingOutputPath ([string]$Context.Paths.LocalOut) -IntendedFinalPath ([string]$Context.Paths.ServerOut) -SizeBytes $(if ($verifiedOutputItem) { [int64]$verifiedOutputItem.Length } else { $null }) -VerificationState completed | Out-Null
    }
    Set-MediaPipelineRemuxVerificationMonitorOutcome -State completed -Detail 'Remuxed output passed duration, stream, track, and metadata verification.'
    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-verify'
}
