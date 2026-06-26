# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Encode scratch/source readiness and pre-tool gates.

function Invoke-MediaPipelineEncodePreflight {
    param([Parameter(Mandatory)] $Context)

    Set-ProgressStage -Stage 'copy_to_scratch' -Status $script:pipelineStatus -Route 'encode' -CopyState 'starting' -Percent $null -SaveNow
    $Context.LocalIn = Ensure-ScratchCopy $Context.File $Context.SafeName
    if (-not $Context.LocalIn) {
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'copy_to_scratch'
    }

    $Context.Paths = Get-OutputPaths $Context.File $Context.IsTV $Context.TvInfo $Context.SafeName
    if (Test-Path -LiteralPath $Context.Paths.ServerOut) {
        if (-not (Test-OutputNeedsReprocess -OutputPath $Context.Paths.ServerOut -SourceFile $Context.File)) {
            if (-not (Invoke-Tx3gSidecarExportForExistingOutput -SourceFile $Context.File -ScratchPath $Context.LocalIn -MediaOutputPath $Context.Paths.ServerOut -Context "ENCODE: ")) {
                $Context.LocalIn = $null
                return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'existing-output-sidecar'
            }
            $script:LastPublishResult = New-ExistingOutputPublishResult -SourceFile $Context.File -OutputPath $Context.Paths.ServerOut
            Write-Log "SKIP ENCODE (exists on server): $(Split-Path $Context.Paths.ServerOut -Leaf)"
            Clear-SourceFailureState $Context.File
            return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $true -Value $true -Stage 'existing-output'
        }
        Write-Log "ENCODE: reprocess mode - existing output will remain in place until the replacement is verified" "WARN"
    }
    if (-not (Test-DiskSpace $LocalBase -MinGB $MinFreeSpaceGB -Label "LOCAL")) {
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'disk-space'
    }

    if (-not (Test-EstimatedOutputSpace -SourcePath $Context.LocalIn -Label "ENCODE")) {
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'encode-space'
    }

    $videoStreamPolicy = Test-SourceVideoStreamPublishPolicy -FilePath $Context.LocalIn -Route 'encode'
    $Context.VideoStreamPolicy = $videoStreamPolicy
    if (-not [bool]$videoStreamPolicy.Allowed) {
        $reason = [string]$videoStreamPolicy.Reason
        $errorCode = [string]$videoStreamPolicy.ErrorCode
        $failureProperties = [ordered]@{
            source_video_stream_count       = [int]$videoStreamPolicy.Inventory.RealVideoStreamCount
            attached_picture_stream_count   = [int]$videoStreamPolicy.Inventory.AttachedPicCount
            video_stream_inventory          = $videoStreamPolicy.Inventory
            video_stream_evidence           = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoStreamPolicy.Inventory -Route 'encode' -Reason $reason -ErrorCode $errorCode
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'operator_required' -Reason $reason -Stage 'video-stream-policy' -ErrorCode $errorCode -SuggestedAction 'Inspect ffprobe video stream inventory and attached-picture detection; publish remains blocked until source video stream inventory is probeable.' -AdditionalProperties $failureProperties
        Write-Log "ENCODE: $reason" "ERROR"
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'video-stream-policy'
    }

    try {
        $hdrState = Get-HDRState $Context.LocalIn
        if (-not [bool]$hdrState.Known) {
            throw "HDR_DETECTION_UNKNOWN: $($hdrState.Reason)"
        }
        $Context.IsHDR = [bool]$hdrState.IsHDR
    } catch {
        $reason = [string]$_.Exception.Message
        Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason $reason -Stage 'hdr-detection' -ErrorCode 'HDR_DETECTION_UNKNOWN' -SuggestedAction 'Inspect ffprobe video stream metadata and confirm the source file is complete; retry after replacing or repairing the source.' | Out-Null
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'hdr-detection'
    }

    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'encode-preflight'
}

function Invoke-MediaPipelineEncodeStreamPreparation {
    param([Parameter(Mandatory)] $Context)

    $file = $Context.File
    $localIn = $Context.LocalIn
    $videoStreamPolicy = $Context.VideoStreamPolicy

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
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'audio-probe'
    }
    $defaultAudioLang = Get-DefaultAudioLang $localIn
    $subFilter        = Filter-SubtitleStreams $localIn "ENCODE: " -OriginalSourcePath $file.FullName
    if ($subFilter.ProbeFailed) {
        Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'transient' -Reason ([string]$subFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$subFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently encode with unknown subtitle state.' | Out-Null
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'subtitle-probe'
    }
    $subResult        = Build-SubtitleArgsForFFmpeg $subFilter $defaultAudioLang $localIn "ENCODE: "
    if ($subResult.Failures -and @($subResult.Failures).Count -gt 0) {
        Register-SubtitleExtractionFailure -SourceFile $file -ScratchPath $localIn -Failures @($subResult.Failures) -Stage 'subtitle-extract'
        $Context.SubResult = $subResult
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'subtitle-extract'
    }
    if ($subResult.BurnTrack -and [int]$videoStreamPolicy.Inventory.RealVideoStreamCount -gt 1) {
        $reason = "Subtitle burn-in currently produces one filtered video output, but source has $([int]$videoStreamPolicy.Inventory.RealVideoStreamCount) real video streams; refusing encode because preserve-all video policy cannot be satisfied."
        $failureProperties = [ordered]@{
            source_video_stream_count = [int]$videoStreamPolicy.Inventory.RealVideoStreamCount
            subtitle_burn_stream      = $subResult.BurnTrack
            video_stream_inventory    = $videoStreamPolicy.Inventory
            video_stream_evidence     = ConvertTo-VideoStreamFailureEvidence -SourceInventory $videoStreamPolicy.Inventory -Route 'encode' -Reason $reason -ErrorCode 'SUBTITLE_BURN_MULTI_VIDEO_UNSUPPORTED'
        }
        $null = Register-SourceFailure -SourceFile $file -ScratchPath $localIn -Classification 'operator_required' -Reason $reason -Stage 'subtitle-burn-video-stream-policy' -ErrorCode 'SUBTITLE_BURN_MULTI_VIDEO_UNSUPPORTED' -SuggestedAction 'Disable subtitle burn-in or use a single-video source until burn-in topology can preserve secondary video streams without silent loss.' -AdditionalProperties $failureProperties
        Write-Log "ENCODE: $reason" "ERROR"
        $Context.SubResult = $subResult
        $Context.LocalIn = $null
        return New-MediaPipelineEncodeStageResult -Ok $false -Terminal $true -Value $false -Stage 'subtitle-burn-video-stream-policy'
    }

    $Context.AudioArgs = @($audioArgs)
    $Context.DefaultAudioLang = $defaultAudioLang
    $Context.SubResult = $subResult
    return New-MediaPipelineEncodeStageResult -Ok $true -Terminal $false -Stage 'encode-stream-preparation'
}
