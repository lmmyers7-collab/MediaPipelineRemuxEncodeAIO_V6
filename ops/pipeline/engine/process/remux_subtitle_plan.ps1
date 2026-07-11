# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux audio and subtitle planning stages.

function New-MediaPipelineRemuxSubtitlePlan {
    param([Parameter(Mandatory)] $Context)

    try {
        $Context.AudioArgs = @(Build-AudioArgs $Context.LocalIn)
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
        Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification $classification -Reason $reason -Stage 'audio-probe' -ErrorCode $errorCode -SuggestedAction $suggestedAction | Out-Null
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'audio-probe'
    }

    $Context.DefaultAudioLang = Get-DefaultAudioLang $Context.LocalIn
    $Context.SubFilter = Filter-SubtitleStreams $Context.LocalIn "REMUX: " -OriginalSourcePath $Context.File.FullName
    if ($Context.SubFilter.ProbeFailed) {
        Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason ([string]$Context.SubFilter.Reason) -Stage 'subtitle-probe' -ErrorCode ([string]$Context.SubFilter.ErrorCode) -SuggestedAction 'Inspect ffprobe subtitle output and the source file; the pipeline will not silently remux with unknown subtitle state.' | Out-Null
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'subtitle-probe'
    }

    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-subtitle-plan'
}

function Complete-MediaPipelineRemuxSubtitlePlan {
    param([Parameter(Mandatory)] $Context)

    $Context.SubTracks = Build-SubtitleTracksForMkvmerge $Context.SubFilter $Context.DefaultAudioLang $Context.LocalIn "REMUX: "
    if ($Context.SubTracks.Failures -and @($Context.SubTracks.Failures).Count -gt 0) {
        Register-SubtitleExtractionFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Failures @($Context.SubTracks.Failures) -Stage 'subtitle-extract'
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'subtitle-extract'
    }

    $Context.MediaTrackVerificationPlan = New-MediaTrackOutputVerificationPlan -AudioDecisions @(Get-LastAudioDecisionRecords) -SubtitleTracks @($Context.SubTracks.VerificationTracks)

    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-subtitle-complete'
}
