# Dot-sourced by ops/pipeline/entrypoints/MediaPipeline/module_loader.ps1.
# Remux FFmpeg AV temp stage.

function Invoke-MediaPipelineRemuxFfmpegAvStage {
    param([Parameter(Mandatory)] $Context)

    $Context.TempAvFile = Join-Path $script:processingDir "temp_av_$([guid]::NewGuid().ToString('N')).mkv"
    $videoArgs = [System.Collections.Generic.List[string]]::new()
    $videoArgs.AddRange([string[]]@(
        "-fflags", "+genpts",
        "-i", $Context.LocalIn,
        "-map", "0:V", "-c:v", "copy"
    ))
    if ($Context.SourceCodec -in (Get-MediaVideoCodecHevcNames)) {
        $videoArgs.AddRange([string[]]@("-bsf:v", "hevc_mp4toannexb"))
        Write-Log "REMUX: applying HEVC bitstream filter for Matroska stream-copy compatibility" "DEBUG"
    }

    $threadCapArgs = @()
    if ([bool]$script:LastAudioTranscodeActive -and [int]$script:CpuEncodeMaxThreads -gt 0) {
        $threadCapArgs = @('-threads', [string]$script:CpuEncodeMaxThreads)
    }
    $ffAvArgs = @($videoArgs.ToArray()) + @(
        "-map", "0:t?",
        "-map_chapters", "0",
        "-map_metadata", "0"
    ) + $threadCapArgs + @($Context.AudioArgs) + @("-y", $Context.TempAvFile)

    $remuxAvCpuLock = $null
    $remuxAvCpuEncode = [bool]$script:LastAudioTranscodeActive
    if ($remuxAvCpuEncode) {
        Write-Log "REMUX-AV: audio transcode active (priority $script:CpuEncodeProcessPriority, threads $(if ($script:CpuEncodeMaxThreads -gt 0) { $script:CpuEncodeMaxThreads } else { 'auto' }))" "DEBUG"
        $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds 0
        if (-not $remuxAvCpuLock.Acquired) {
            Write-Log "REMUX-AV: another CPU-bound job is already in progress on this machine; waiting for it ($($remuxAvCpuLock.Reason))" "WARN"
            Set-ProgressStage -Stage 'remux_av' -Status "Waiting for CPU slot (audio transcode)" -Route 'remux' -Percent 0 -SaveNow
            $remuxAvCpuLock = Acquire-CpuEncodeMutex -TimeoutSeconds $script:FFmpegRemuxTimeoutSeconds
        }
    }
    try {
        $remuxAvCallArgs = @{
            FFArgs          = $ffAvArgs
            Label           = 'REMUX-AV'
            InputFile       = $Context.LocalIn
            TimeoutSeconds  = $script:FFmpegRemuxTimeoutSeconds
            ProgressStage   = 'remux_av'
            ProgressRoute   = 'remux'
            ReproStage      = 'remux-av'
        }
        if ($remuxAvCpuEncode) {
            $remuxAvCallArgs['CpuEncode']       = $true
            $remuxAvCallArgs['ProcessPriority'] = $script:CpuEncodeProcessPriority
        }
        $remuxAvSuccess = Invoke-FFmpegWithProgress @remuxAvCallArgs
    } finally {
        if ($remuxAvCpuLock -and $remuxAvCpuLock.Acquired) { & $remuxAvCpuLock.Release }
    }
    if (-not $remuxAvSuccess) {
        $reproPath = $script:LastFFmpegReproPath
        $ffmpegErrorSummary = Get-ErrorTextSummary -ErrorText $script:LastFFmpegStderr
        $errorCode = Get-FFmpegFailureCode -Stage 'remux-av' -ErrorText $script:LastFFmpegStderr -ExitCode ([int]$script:LastFFmpegExit)
        $reason = if ($ffmpegErrorSummary) { "FFmpeg remux AV stage failed: $ffmpegErrorSummary" } else { 'FFmpeg remux AV stage failed' }
        $suggestedAction = if ($errorCode -eq 'REMUX_HEVC_MKV_BITSTREAM_FAILED') {
            "This looks like an HEVC stream-copy to Matroska header failure. Retry with the updated pipeline so the primary video stream is mapped explicitly and hevc_mp4toannexb is applied."
        } elseif ($errorCode -eq 'REMUX_ATTACHED_PICTURE_MAPPED') {
            "This looks like attached cover art was mapped as video. Retry with the updated pipeline so only the primary video stream is selected."
        } else {
            "Inspect FFmpeg stderr log $($script:LastFFmpegErrorLog) and repro command $reproPath, then retry once the source/share issue is fixed."
        }
        $null = Register-SourceFailure -SourceFile $Context.File -ScratchPath $Context.LocalIn -Classification 'transient' -Reason $reason -Stage 'remux-av' -ErrorCode $errorCode -ReproPath $reproPath -SuggestedAction $suggestedAction
        $Context.LocalIn = $null
        return New-MediaPipelineRemuxStageResult -Ok $false -Terminal $true -Value $false -Stage 'remux-av'
    }

    return New-MediaPipelineRemuxStageResult -Ok $true -Terminal $false -Stage 'remux-av'
}
